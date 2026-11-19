# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Installed Foundations 2 discovery, adapter chaining, and validation."""

import subprocess
import sys
from importlib.metadata import entry_points
from textwrap import dedent

import pytest
from conftest import _body, _fixed_joint, _mesh, _new_stage
from pxr import Sdf, UsdPhysics, UsdShade


@pytest.mark.parametrize("consumer", ["direct", "derive"])
@pytest.mark.parametrize("version", ["1.0.0", "1.1.0"])
def test_installed_capability_adapters_chain_and_validate(tmp_path, copy_for_output, consumer, version):
    """Real profile resolution must select the wheel's callbacks and repair all gates."""
    if not any(
        provider.dist is not None and provider.dist.name == "simready-foundation-tier-isaac"
        for provider in entry_points(group="simready.feature_adapters")
    ):
        pytest.skip("installed Isaac tier wheel not present")

    pytest.importorskip("simready.validate")
    if consumer == "derive":
        pytest.importorskip("simready.derive")
    from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization import (
        visual_mesh_merge,
    )

    try:
        visual_mesh_merge._optimizer()
    except ModuleNotFoundError as error:
        if error.name != "usd_optimize":
            raise
        pytest.skip("real profile transformation requires usd-optimize >=1.4.0")

    source_path = tmp_path / "source.usda"
    stage = _new_stage(source_path)
    _body(stage, "/Asset/base")
    _body(stage, "/Asset/tip", translate=(0.0, 0.0, 0.2))
    _mesh(stage, "/Asset/base/one")
    _mesh(stage, "/Asset/base/two")
    render = _mesh(stage, "/Asset/tip/render")
    UsdPhysics.CollisionAPI.Apply(render).CreateCollisionEnabledAttr().Set(False)
    _fixed_joint(stage, "/Asset/weld", "/Asset/base", "/Asset/tip")
    material = UsdShade.Material.Define(stage, "/Asset/Material")
    surface = UsdShade.Shader.Define(stage, "/Asset/Material/OpenPBR")
    surface.CreateIdAttr("ND_open_pbr_surface_surfaceshader")
    material.CreateSurfaceOutput("MTLX" if consumer == "direct" else "mtlx").ConnectToSource(
        surface.CreateOutput("out", Sdf.ValueTypeNames.Token))
    stage.GetRootLayer().Save()
    original = source_path.read_bytes()
    _, output_stage = copy_for_output(source_path)

    # Validate discovery resets process-wide registries. Keep that lifecycle out
    # of the process holding the direct-checker fixtures used by other tests.
    script = dedent(
        """\
        import sys
        from importlib.metadata import entry_points
        from pxr import Usd
        from simready import validate

        input_stage = Usd.Stage.Open(sys.argv[1])
        output_stage = Usd.Stage.Open(sys.argv[2])
        validate.initialize([], [], [])
        version = sys.argv[4]
        if sys.argv[3] == "derive":
            from simready.derive.impl.adapt import apply_feature_adapters, select_adapters_for_profiles
            from simready.derive.impl.discover import load_feature_adapters
            from simready.derive.impl.profiles import empty_profile, resolve_profile

            profile = resolve_profile("Asset-Optimization", version)
            load_feature_adapters()
            adapters = select_adapters_for_profiles(empty_profile(), profile)
        else:
            provider, = entry_points(group="simready.feature_adapters", name="isaac_optimization")
            adapters = sorted(provider.load()(), key=lambda item: (-item.priority, item.name))
            if version == "1.0.0":
                adapters = [adapter for adapter in adapters if adapter.name != "remove_materialx_shaders"]
        expected = [
            "fixed_joint_rigid_body_merge",
            "remove_inactive_render_collision_schemas",
            "rigid_body_visual_mesh_merge",
        ]
        if version == "1.1.0":
            expected.append("remove_materialx_shaders")
        assert [adapter.name for adapter in adapters] == expected

        before = validate.validate_stage(
            input_stage,
            profile_id="Asset-Optimization",
            profile_version=version,
            write_metadata=False,
        )
        assert len(before.features_summary) == len(expected)
        assert all(not result["passed"] for result in before.features_summary.values())

        if sys.argv[3] == "derive":
            apply_feature_adapters(adapters, input_stage=input_stage, output_stage=output_stage)
        else:
            for adapter in adapters:
                previous = Usd.Stage.Open(output_stage.Flatten())
                adapter.callback(previous, output_stage)
        output_stage.Save()
        after = validate.validate_stage(
            Usd.Stage.Open(output_stage.GetRootLayer().realPath),
            profile_id="Asset-Optimization",
            profile_version=version,
            write_metadata=False,
        )
        expected_capabilities = {
            "CAP102_RigidBodyCollapse.Isaac.0-1-0",
            "CAP103_VisualMeshMerge.Isaac.0-1-0",
            "CAP104_RenderCollisionSeparation.Isaac.0-1-0",
        }
        if version == "1.1.0":
            expected_capabilities.add("CAP105_MaterialXRemoval.Isaac.0-1-0")
        assert set(after.features_summary) == expected_capabilities
        assert validate.features_summary_passed(after.features_summary)
    """
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(source_path), output_stage.GetRootLayer().realPath, consumer, version],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert source_path.read_bytes() == original
