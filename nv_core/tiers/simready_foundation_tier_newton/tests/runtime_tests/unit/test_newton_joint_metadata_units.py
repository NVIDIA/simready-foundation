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
from types import SimpleNamespace

import pytest
from simready.foundation.tier_newton.runtime_tests import motion_observer


@pytest.mark.parametrize("meters_per_unit", [1.0, 0.01])
@pytest.mark.parametrize(
    "version,expected_unit", [("1.2.1", "stage_length"), ("1.3.0", "unknown_native"), (None, "unknown_native")]
)
def test_prismatic_units_require_qualified_newton_version(monkeypatch, meters_per_unit, version, expected_unit):
    from pxr import Usd, UsdGeom, UsdPhysics

    monkeypatch.setattr(motion_observer, "_newton_version_for_units", lambda: (version, "fixture"))
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageMetersPerUnit(stage, meters_per_unit)
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    joint = UsdPhysics.PrismaticJoint.Define(stage, "/Robot/joint")
    joint.CreateLowerLimitAttr(0.0)
    joint.CreateUpperLimitAttr(100.0)
    drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear")
    drive.CreateTargetPositionAttr(50.0)
    before = stage.GetRootLayer().ExportToString()

    info = motion_observer.joint_metadata(stage, root, "joint")

    assert info["identity_resolved"]
    assert info["unit"] == expected_unit
    assert info["meters_per_unit"] == meters_per_unit
    assert info["native_tensor_package_version"] == version
    assert "Newton 1.2.1" in info["unit_basis"]
    assert stage.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("version", ["1.2.1", "1.3.0", None])
def test_revolute_units_do_not_depend_on_linear_qualification(monkeypatch, version):
    from pxr import Usd, UsdGeom, UsdPhysics

    monkeypatch.setattr(motion_observer, "_newton_version_for_units", lambda: (version, "fixture"))
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    UsdPhysics.RevoluteJoint.Define(stage, "/Robot/joint")
    info = motion_observer.joint_metadata(stage, root, "joint")
    assert info["unit"] == "rad"
    assert "radians" in info["unit_basis"]


def test_loaded_sdk_version_takes_precedence_without_import(monkeypatch):
    monkeypatch.setitem(motion_observer.sys.modules, "newton", SimpleNamespace(__version__="1.3.0"))
    monkeypatch.setattr(motion_observer.metadata, "version", lambda name: "1.2.1")
    assert motion_observer._newton_version_for_units() == ("1.3.0", "loaded newton.__version__")


def test_unknown_sdk_version_remains_unknown_without_import(monkeypatch):
    monkeypatch.delitem(motion_observer.sys.modules, "newton", raising=False)

    def unavailable(name):
        raise motion_observer.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(motion_observer.metadata, "version", unavailable)
    assert motion_observer._newton_version_for_units() == (None, "unavailable")
