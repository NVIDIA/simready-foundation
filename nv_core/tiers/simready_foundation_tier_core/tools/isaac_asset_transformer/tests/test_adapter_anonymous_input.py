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
"""The Isaac composition adapters must accept simready.derive's anonymous snapshots.

``simready.derive`` runs adapters with an anonymous, stitched snapshot of the
output stage as ``input_stage``. Transformer rules save edits back into the
layers they compose, so the adapter must hand the transformer real files.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from pxr import Sdf, Usd, UsdGeom, UsdPhysics

_TOOLS_ROOT = Path(__file__).resolve().parents[2]


def _adapter_package():
    sys.path.insert(0, str(_TOOLS_ROOT))
    try:
        return importlib.import_module("asset_handler_modules.physx_to_isaacsim")
    finally:
        sys.path.remove(str(_TOOLS_ROOT))


def _write_robot_package(root: Path) -> Path:
    """Write a robot whose bodies and joint live in a referenced payloads layer."""
    (root / "payloads").mkdir(parents=True)
    body_stage = Usd.Stage.CreateNew(str(root / "payloads/base.usda"))
    robot = UsdGeom.Xform.Define(body_stage, "/robot")
    body_stage.SetDefaultPrim(robot.GetPrim())
    UsdPhysics.ArticulationRootAPI.Apply(robot.GetPrim())
    base = UsdGeom.Xform.Define(body_stage, "/robot/base")
    UsdPhysics.RigidBodyAPI.Apply(base.GetPrim())
    link = UsdGeom.Xform.Define(body_stage, "/robot/link")
    UsdPhysics.RigidBodyAPI.Apply(link.GetPrim())
    joint = UsdPhysics.RevoluteJoint.Define(body_stage, "/robot/joint")
    joint.CreateBody0Rel().SetTargets([base.GetPath()])
    joint.CreateBody1Rel().SetTargets([link.GetPath()])
    body_stage.GetRootLayer().Save()

    root_layer = Sdf.Layer.CreateNew(str(root / "robot.usda"))
    prim = Sdf.CreatePrimInLayer(root_layer, "/robot")
    prim.specifier = Sdf.SpecifierDef
    prim.referenceList.Prepend(Sdf.Reference("./payloads/base.usda"))
    root_layer.defaultPrim = "robot"
    root_layer.Save()
    return root / "robot.usda"


def _anonymous_snapshot(path: Path) -> Usd.Stage:
    """Mimic derive's snapshot_stage: anonymous copies linked by anonymous identifiers."""
    source = Sdf.Layer.FindOrOpen(str(path))
    dependency = source.GetCompositionAssetDependencies()[0]
    referenced = Sdf.Layer.FindOrOpen(source.ComputeAbsolutePath(dependency))
    base_copy = Sdf.Layer.CreateAnonymous("base.usda")
    base_copy.TransferContent(referenced)
    root_copy = Sdf.Layer.CreateAnonymous("robot.usda")
    root_copy.TransferContent(source)
    root_copy.UpdateCompositionAssetDependency(dependency, base_copy.identifier)
    stage = Usd.Stage.Open(root_copy)
    stage._keep_alive = (root_copy, base_copy)
    return stage


def test_materialize_relinks_anonymous_layers(tmp_path: Path) -> None:
    package = _adapter_package()
    snapshot = _anonymous_snapshot(_write_robot_package(tmp_path / "source"))
    assert package.stage_source_path(snapshot) is None

    root = package.materialize_stage(snapshot, tmp_path / "materialized", "robot.usda")

    assert root == tmp_path / "materialized/robot.usda"
    (dependency,) = Sdf.Layer.FindOrOpen(str(root)).GetCompositionAssetDependencies()
    assert dependency.startswith("./layers/") and dependency.endswith("base.usda")
    stage = Usd.Stage.Open(str(root))
    assert stage.GetPrimAtPath("/robot/joint").IsA(UsdPhysics.RevoluteJoint)
    assert package.stage_source_path(stage) == str(root.resolve()).replace("\\", "/") or package.stage_source_path(
        stage
    )


def test_robot_adapter_accepts_anonymous_snapshot_input(tmp_path: Path) -> None:
    package = _adapter_package()
    snapshot = _anonymous_snapshot(_write_robot_package(tmp_path / "source"))
    output_dir = tmp_path / "derived/simready_usd"
    output_dir.mkdir(parents=True)
    output_stage = Usd.Stage.CreateNew(str(output_dir / "robot.usd"))

    package.convert_to_isaacsim_robot(snapshot, output_stage)

    composed = Usd.Stage.Open(str(output_dir / "robot.usd"))
    assert composed.GetPrimAtPath("/robot/joint").IsA(UsdPhysics.RevoluteJoint)
    assert composed.GetPrimAtPath("/robot/base").HasAPI(UsdPhysics.RigidBodyAPI)
    assert not (tmp_path / "derived/temp_source_asset").exists()
