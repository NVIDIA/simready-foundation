# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""CIP feature-adapter registrations for multiphysics upgrade edges.

The upgrade implementation ships in the standalone
``simready-multiphysics-upgrade`` distribution. This package keeps the CIP
registrations and republishes the implementation modules under their historical
``asset_handler_modules.multiphysics_upgrade.<module>`` import paths, so
existing CIP configurations, scripts, and tests keep working unchanged.

When ``omni.cip`` is unavailable, a no-op decorator preserves local import and
attaches registration metadata on each wrapper for discovery.
"""

from __future__ import annotations

import sys

from pxr import Usd

from ._bootstrap import ensure_importable

ensure_importable()

from simready.multiphysics_upgrade import (  # noqa: E402
    core,
    edges,
    neutral_to_runtimes,
    runner,
    types,
)

# Republish the implementation modules under the legacy submodule paths so
# `from asset_handler_modules.multiphysics_upgrade.runner import main` resolves
# to the same module object as the packaged import.
for _legacy_name, _module in (
    ("core", core),
    ("edges", edges),
    ("neutral_to_runtimes", neutral_to_runtimes),
    ("runner", runner),
    ("types", types),
):
    sys.modules[f"{__name__}.{_legacy_name}"] = _module

try:
    from omni.cip.configurable.feature_adapter import feature_adapter
except ImportError:  # pragma: no cover - local standalone / unit-test path

    def feature_adapter(**kwargs):
        def deco(fn):
            fn._feature_adapter = kwargs
            return fn

        return deco


def _run(apply_fn, input_stage: Usd.Stage, output_stage: Usd.Stage) -> None:
    # CIP supplies a copied output stage; mutate that and save.
    _ = input_stage
    apply_fn(output_stage)
    output_stage.GetRootLayer().Save()


@feature_adapter(
    name="minimal_standard_0_1_0_to_1_0_1",
    input_feature_id="FET001_MinimalPlaceableVisual.0-1-0",
    output_feature_id="FET001_MinimalPlaceableVisual.1-0-1",
)
def minimal_standard_0_1_0_to_1_0_1(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _run(core.apply_minimal_upgrade, input_stage, output_stage)


@feature_adapter(
    name="rigid_body_physx_0_1_0_to_standard_0_2_0",
    input_feature_id="FET003_RigidBody.PhysX.0-1-0",
    output_feature_id="FET003_RigidBody.0-2-0",
)
def rigid_body_physx_0_1_0_to_standard_0_2_0(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _run(core.apply_physx_to_standard_rigid_body, input_stage, output_stage)


@feature_adapter(
    name="multibody_physx_0_1_0_to_standard_0_2_0",
    input_feature_id="FET004_Multibody.PhysX.0-1-0",
    output_feature_id="FET004_Multibody.0-2-0",
)
def multibody_physx_0_1_0_to_standard_0_2_0(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _run(core.apply_physx_to_standard_multibody, input_stage, output_stage)


@feature_adapter(
    name="core_standard_to_physx_0_1_0",
    input_feature_id="CAP000_Core.0-1-0",
    output_feature_id="CAP000_Core.PhysX.0-1-0",
)
def core_standard_to_physx_0_1_0(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _run(lambda s: core.apply_runtime_scaffold(s, "PhysX"), input_stage, output_stage)


@feature_adapter(
    name="core_standard_to_newton_0_1_0",
    input_feature_id="CAP000_Core.0-1-0",
    output_feature_id="CAP000_Core.Newton.0-1-0",
)
def core_standard_to_newton_0_1_0(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _run(lambda s: core.apply_runtime_scaffold(s, "Newton"), input_stage, output_stage)


@feature_adapter(
    name="core_standard_to_mujoco_0_1_0",
    input_feature_id="CAP000_Core.0-1-0",
    output_feature_id="CAP000_Core.MuJoCo.0-1-0",
)
def core_standard_to_mujoco_0_1_0(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _run(lambda s: core.apply_runtime_scaffold(s, "MuJoCo"), input_stage, output_stage)


@feature_adapter(
    name="rigid_body_standard_0_2_0_to_physx_0_4_0",
    input_feature_id="FET003_RigidBody.0-2-0",
    output_feature_id="FET003_RigidBody.PhysX.0-4-0",
)
def rigid_body_standard_0_2_0_to_physx_0_4_0(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _run(core.apply_standard_to_physx_rigid_body, input_stage, output_stage)


@feature_adapter(
    name="rigid_body_standard_0_2_0_to_newton_0_1_0",
    input_feature_id="FET003_RigidBody.0-2-0",
    output_feature_id="FET003_RigidBody.Newton.0-1-0",
)
def rigid_body_standard_0_2_0_to_newton_0_1_0(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _run(core.apply_standard_to_newton_rigid_body, input_stage, output_stage)


@feature_adapter(
    name="rigid_body_standard_0_2_0_to_mujoco_0_1_0",
    input_feature_id="FET003_RigidBody.0-2-0",
    output_feature_id="CAP003_RigidBody.MuJoCo.0-1-0",
)
def rigid_body_standard_0_2_0_to_mujoco_0_1_0(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _run(core.apply_standard_to_mujoco_rigid_body, input_stage, output_stage)


@feature_adapter(
    name="multibody_standard_0_2_0_to_physx_0_4_0",
    input_feature_id="FET004_Multibody.0-2-0",
    output_feature_id="FET004_Multibody.PhysX.0-4-0",
)
def multibody_standard_0_2_0_to_physx_0_4_0(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _run(core.apply_standard_to_physx_multibody, input_stage, output_stage)


@feature_adapter(
    name="multibody_standard_0_2_0_to_newton_0_1_0",
    input_feature_id="FET004_Multibody.0-2-0",
    output_feature_id="FET004_Multibody.Newton.0-1-0",
)
def multibody_standard_0_2_0_to_newton_0_1_0(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _run(core.apply_standard_to_newton_multibody, input_stage, output_stage)


@feature_adapter(
    name="multibody_standard_0_2_0_to_mujoco_0_1_0",
    input_feature_id="FET004_Multibody.0-2-0",
    output_feature_id="CAP004_Multibody.MuJoCo.0-1-0",
)
def multibody_standard_0_2_0_to_mujoco_0_1_0(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _run(core.apply_standard_to_mujoco_multibody, input_stage, output_stage)
