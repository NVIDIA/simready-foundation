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
"""USD-level tests for articulation_phases.gripper_carrier.

Covers the pure-USD helpers (gantry layout, drive-target read/write,
idempotent teardown) that don't require a running Kit / Isaac Sim.
The async ``attach_carrier`` / ``detach_carrier`` flow needs a PhysX
runtime (``physics.stop()`` / ``play()``, ``robot.articulation``,
``world.reset_async()``) and is exercised by integration tests inside
Kit, not here.

``_build_gantry`` itself depends on ``pxr.PhysxSchema`` (Kit-only;
not in the ``usd-core`` PyPI distribution that this package's hard
dependencies pull in). Tests that need it use ``pytest.importorskip``
so they skip cleanly on host-Python machines without Kit.
"""
from types import SimpleNamespace

import pytest

pytest.importorskip("pxr")
from pxr import Usd, UsdGeom, UsdPhysics  # noqa: E402  -- must follow importorskip
from simready_benchmark_kit_suite.articulation_phases.gripper_carrier import (  # noqa: E402
    _GANTRY_BASE,
    _GANTRY_ROOT,
    _GANTRY_Z,
    _JOINT_Z,
    CarrierHandle,
    _build_gantry,
    _capture_root_orientation,
    _carrier_world_axis_sign,
    _gantry_dof_index,
    _gantry_paths,
    _remove_existing_gantry,
    _restore_root_orientation,
    _restore_world_pin,
    _rollback_partial_carrier,
    carrier_target_z,
    detach_carrier,
    set_carrier_target_z,
)


def _stage_with_gripper_base():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    base = UsdGeom.Xform.Define(stage, "/World/Asset/base").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(base)
    return stage, base


# ---- no-Kit tests (run anywhere usd-core is installed) ------------------------


def test_remove_existing_gantry_is_idempotent_on_empty_stage():
    """attach_carrier calls this before authoring, so it must be a safe no-op."""
    stage = Usd.Stage.CreateInMemory()
    _remove_existing_gantry(stage)  # must not raise


def test_remove_existing_gantry_only_removes_requested_namespace():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    UsdGeom.Xform.Define(stage, "/World/_FET028_Gantry_foreign")
    UsdGeom.Xform.Define(stage, "/World/_FET028_Gantry_this_run")

    _remove_existing_gantry(stage, "/World/_FET028_Gantry_this_run")

    assert not stage.GetPrimAtPath("/World/_FET028_Gantry_this_run").IsValid()
    assert stage.GetPrimAtPath("/World/_FET028_Gantry_foreign").IsValid()


def test_restore_world_pin_reactivates_exact_authored_prim():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    UsdGeom.Xform.Define(stage, "/World/Asset")
    pin = UsdPhysics.FixedJoint.Define(stage, "/World/authored_pin")
    pin.CreateBody1Rel().SetTargets(["/World/Asset"])
    prim = pin.GetPrim()
    prim.SetActive(False)

    assert _restore_world_pin(stage, "/World/authored_pin")

    restored = UsdPhysics.FixedJoint(stage.GetPrimAtPath("/World/authored_pin"))
    assert restored.GetPrim().IsActive()
    assert restored.GetBody1Rel().GetTargets() == ["/World/Asset"]


@pytest.mark.asyncio
async def test_partial_attach_rollback_restores_stage_and_physics_state():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    root = UsdGeom.Xform.Define(stage, "/World/Asset").GetPrim()
    root_state = _capture_root_orientation(stage, "/World/Asset")
    UsdGeom.Xformable(root).AddOrientOp()
    gantry_path = "/World/_FET028_Gantry_failed"
    UsdGeom.Xform.Define(stage, gantry_path)
    pin = UsdPhysics.FixedJoint.Define(stage, "/World/authored_pin").GetPrim()
    pin.SetActive(False)

    class Articulation:
        def __init__(self):
            self.default_state = None
            self.joint_state = None

        def set_default_state(self, **kwargs):
            self.default_state = kwargs

        def set_joints_default_state(self, **kwargs):
            self.joint_state = kwargs

    class Physics:
        def __init__(self):
            self.stops = 0
            self.plays = 0

        def stop(self):
            self.stops += 1

        def play(self):
            self.plays += 1

    class World:
        reset = False

        async def reset_async(self):
            self.reset = True

    world = World()
    robot = SimpleNamespace(prim_path="/World/Asset", articulation=Articulation(), _world=None)

    async def initialize(ctx):
        robot.articulation = Articulation()
        robot._world = world

    robot.initialize = initialize
    physics = Physics()
    setup_state = {
        "root_path": gantry_path,
        "physics_was_playing": True,
        "physics_stopped": True,
        "root_orientation_state": root_state,
        "articulation_default_state": ("position", "orientation"),
        "joint_default_state": ("positions", "velocities", "efforts"),
        "world_pin_paths": ("/World/authored_pin",),
    }

    errors = await _rollback_partial_carrier(stage, robot, physics, setup_state)

    assert errors == []
    assert not stage.GetPrimAtPath(gantry_path).IsValid()
    assert not root.GetAttribute("xformOp:orient").IsDefined()
    assert stage.GetPrimAtPath("/World/authored_pin").IsActive()
    assert physics.stops == 1
    assert physics.plays == 1
    assert robot.articulation.default_state == {"position": "position", "orientation": "orientation"}
    assert robot.articulation.joint_state == {
        "positions": "positions",
        "velocities": "velocities",
        "efforts": "efforts",
    }
    assert world.reset


def test_root_orientation_snapshot_removes_test_authored_orient_op():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    root = UsdGeom.Xform.Define(stage, "/World/Asset").GetPrim()
    state = _capture_root_orientation(stage, "/World/Asset")
    UsdGeom.Xformable(root).AddOrientOp()

    _restore_root_orientation(stage, "/World/Asset", state)

    assert not root.GetAttribute("xformOp:orient").IsDefined()


def test_carrier_target_z_returns_zero_when_gantry_absent():
    """Read on a stage with no gantry returns 0.0 instead of raising. Defends
    callers that may query before attach (e.g. logging at scene init)."""
    stage = Usd.Stage.CreateInMemory()
    assert carrier_target_z(stage) == 0.0


def test_set_carrier_target_z_is_noop_when_gantry_absent():
    """Symmetric to the read: a write before attach should not raise."""
    stage = Usd.Stage.CreateInMemory()
    set_carrier_target_z(stage, handle=None, target_z=0.5)  # handle unused by impl
    assert carrier_target_z(stage) == 0.0


def test_carrier_world_axis_sign_matches_runtime_joint_conventions():
    common = {
        "robot": None,
        "gripper_base_path": "/World/Asset/base",
        "physics": None,
        "initial_target_z": 0.0,
        "world_pin_was_present": False,
    }

    assert _carrier_world_axis_sign(CarrierHandle(**common, active_physics_engine="physx")) == 1.0
    assert _carrier_world_axis_sign(CarrierHandle(**common, active_physics_engine="newton")) == -1.0


def test_generated_carrier_joint_name_is_unique_and_does_not_select_asset_joint_z():
    first_path = _gantry_paths("/World/Robot/_FET028_Carrier_first")["joint_z"]
    second_path = _gantry_paths("/World/Robot/_FET028_Carrier_second")["joint_z"]
    first_name = first_path.rsplit("/", 1)[-1]

    assert first_path != second_path
    assert first_name != "joint_z"
    robot = SimpleNamespace(dof_names=["joint_z", first_name, "jaw_driver"])
    assert _gantry_dof_index(robot, first_path) == 1


@pytest.mark.asyncio
async def test_detach_reinitializes_robot_before_resetting_world():
    stage, base = _stage_with_gripper_base()
    UsdGeom.Xform.Define(stage, _GANTRY_ROOT)

    class Physics:
        def stop(self):
            pass

        def play(self):
            pass

    class World:
        reset = False

        async def reset_async(self):
            self.reset = True

    old_world = World()
    new_world = World()
    robot = SimpleNamespace(
        _world=old_world,
        articulation=SimpleNamespace(),
        prim_path="/World/Asset/base",
    )

    async def initialize(ctx):
        robot._world = new_world

    robot.initialize = initialize
    handle = CarrierHandle(
        robot=robot,
        gripper_base_path=str(base.GetPath()),
        physics=Physics(),
        initial_target_z=0.0,
        world_pin_was_present=False,
    )

    await detach_carrier(stage, handle)

    assert old_world.reset is False
    assert new_world.reset is True
    assert not stage.GetPrimAtPath(_GANTRY_ROOT).IsValid()


# ---- tests that require PhysxSchema (Kit-only) -------------------------------


def test_build_gantry_authors_expected_prim_layout():
    """Verifies the gantry's USD shape: base + Z xforms with rigid bodies and
    mass, prismatic Z joint between them with DriveAPI(linear), and an attach
    FixedJoint bound to the gripper base. attach_carrier relies on this layout
    -- if any prim path or joint relationship shifts, the runtime breaks."""
    pytest.importorskip("pxr.PhysxSchema")
    stage, base = _stage_with_gripper_base()

    _build_gantry(stage, str(base.GetPath()), (1.0, 2.0, 3.0))

    assert stage.GetPrimAtPath(_GANTRY_ROOT).IsValid()
    assert stage.GetPrimAtPath(_GANTRY_BASE).IsA(UsdGeom.Xform)
    assert stage.GetPrimAtPath(_GANTRY_Z).IsA(UsdGeom.Xform)

    for path in (_GANTRY_BASE, _GANTRY_Z):
        prim = stage.GetPrimAtPath(path)
        assert prim.HasAPI(UsdPhysics.RigidBodyAPI)
        assert prim.HasAPI(UsdPhysics.MassAPI)

    joint_z_prim = stage.GetPrimAtPath(_JOINT_Z)
    assert joint_z_prim.IsA(UsdPhysics.PrismaticJoint)
    pj = UsdPhysics.PrismaticJoint(joint_z_prim)
    assert pj.GetAxisAttr().Get() == UsdPhysics.Tokens.z
    assert str(pj.GetBody0Rel().GetTargets()[0]) == _GANTRY_BASE
    assert str(pj.GetBody1Rel().GetTargets()[0]) == _GANTRY_Z
    # DriveAPI(linear) is what set_carrier_target_z writes through.
    assert joint_z_prim.HasAPI(UsdPhysics.DriveAPI, "linear")


def test_build_gantry_attach_joint_binds_gantry_z_to_gripper_base():
    """The FixedJoint between gantry_z and the gripper base is what makes the
    gripper follow the prismatic drive; excludeFromArticulation=True keeps the
    gantry out of the gripper's articulation graph (otherwise PhysX merges
    them and ParallelGripper crashes on shape mismatch)."""
    pytest.importorskip("pxr.PhysxSchema")
    stage, base = _stage_with_gripper_base()
    _build_gantry(stage, str(base.GetPath()), (0.0, 0.0, 0.0))

    attach_path = _GANTRY_ROOT + "/attach_joint"
    attach_prim = stage.GetPrimAtPath(attach_path)
    assert attach_prim.IsA(UsdPhysics.FixedJoint)
    fj = UsdPhysics.FixedJoint(attach_prim)
    assert str(fj.GetBody0Rel().GetTargets()[0]) == _GANTRY_Z
    assert str(fj.GetBody1Rel().GetTargets()[0]) == str(base.GetPath())
    assert fj.GetExcludeFromArticulationAttr().Get() is True


def test_set_carrier_target_z_roundtrip_via_carrier_target_z():
    """The drive-target write/read pair is what the test phases use to
    command and observe gantry motion. Round-trip must be exact."""
    pytest.importorskip("pxr.PhysxSchema")
    stage, base = _stage_with_gripper_base()
    _build_gantry(stage, str(base.GetPath()), (0.0, 0.0, 0.0))

    set_carrier_target_z(stage, handle=None, target_z=0.42)
    assert carrier_target_z(stage) == pytest.approx(0.42)

    set_carrier_target_z(stage, handle=None, target_z=-0.17)
    assert carrier_target_z(stage) == pytest.approx(-0.17)


def test_remove_existing_gantry_clears_built_layout():
    """attach_carrier calls _remove_existing_gantry on each entry to guarantee
    a clean slate. After removal, none of the gantry prims should remain."""
    pytest.importorskip("pxr.PhysxSchema")
    stage, base = _stage_with_gripper_base()
    _build_gantry(stage, str(base.GetPath()), (0.0, 0.0, 0.0))
    assert stage.GetPrimAtPath(_GANTRY_ROOT).IsValid()

    _remove_existing_gantry(stage)
    for path in (_GANTRY_ROOT, _GANTRY_BASE, _GANTRY_Z, _JOINT_Z):
        assert not stage.GetPrimAtPath(path).IsValid()
