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

"""Focused tests for FET004 joint-movement excitation and measurement."""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import numpy as np
import pytest
from pxr import Gf, Usd, UsdPhysics


def test_joint_tracker_records_existing_relative_pose_reads(joint_movement, monkeypatch):
    stage = Usd.Stage.CreateInMemory()
    reads, samples, captures, finished, metadata = [], [], [], [], []
    translation = [0.0]

    def world_matrix(_stage, path):
        reads.append(path)
        matrix = Gf.Matrix4d(1.0)
        if path == "/Asset/child":
            matrix.SetTranslate(Gf.Vec3d(translation[0], 0, 0))
        return matrix

    history = types.SimpleNamespace(
        sample=lambda time, values, **kwargs: samples.append((time, values, kwargs)),
        record_capture=captures.append,
        finish=finished.append,
        mark_partial=lambda reason: pytest.fail(reason),
    )
    ctx = types.SimpleNamespace(
        config={"physics_fps": 240},
        begin_motion_history=lambda name, channels, metadata: metadata_capture(name, channels, metadata),
        warn=lambda message: pytest.fail(message),
    )

    def metadata_capture(name, channels, context):
        metadata.append((name, channels, context))
        return history

    monkeypatch.setattr(joint_movement, "_get_world_matrix", world_matrix)
    monkeypatch.setattr(joint_movement, "_get_bbox_diagonal", lambda *_: 1.0)
    tracker = joint_movement.JointTracker(
        stage,
        {
            "name": "hinge",
            "prim_path": "/Asset/hinge",
            "parent_body_path": "/Asset/parent",
            "child_body_path": "/Asset/child",
        },
        ctx,
        "drive_probe",
    )
    translation[0] = 0.025
    tracker.update()
    tracker.record_capture("frame.png")
    tracker.finish()
    assert reads == ["/Asset/parent", "/Asset/child"] * 2
    assert samples[0][0] == pytest.approx(1 / 240)
    assert samples[0][1]["translation_x"] == pytest.approx(0.025)
    assert samples[0][1]["translation_delta"] == pytest.approx(0.025)
    assert samples[0][2] == {"phase": "drive_probe", "clock_source": "estimated"}
    assert metadata[0][1]["translation_x"]["unit"] == "stage_length"
    assert captures == [pytest.approx(1 / 240)]
    assert finished == ["observation_budget_exhausted"]


@pytest.mark.parametrize("missing", ["reference_parent", "update_parent", "update_child", "watchdog"])
def test_joint_tracker_marks_incomplete_trials_partial(joint_movement, monkeypatch, missing):
    stage = Usd.Stage.CreateInMemory()
    samples, partial, warnings, finished = [], [], [], []
    updating = False

    def world_matrix(_stage, path):
        if path == "/Asset/parent" and (missing == "reference_parent" or (updating and missing == "update_parent")):
            return None
        if updating and missing == "update_child" and path == "/Asset/child":
            return None
        return Gf.Matrix4d(1.0)

    history = types.SimpleNamespace(
        sample=lambda *args, **kwargs: samples.append((args, kwargs)),
        mark_partial=partial.append,
        finish=finished.append,
    )
    ctx = types.SimpleNamespace(
        config={"physics_fps": 240},
        begin_motion_history=lambda *args, **kwargs: history,
        warn=warnings.append,
    )
    monkeypatch.setattr(joint_movement, "_get_world_matrix", world_matrix)
    monkeypatch.setattr(joint_movement, "_get_bbox_diagonal", lambda *_: 1.0)
    if missing == "reference_parent":
        with pytest.raises(RuntimeError, match="required transform unavailable"):
            joint_movement.JointTracker(
                stage,
                {
                    "name": "hinge",
                    "prim_path": "/Asset/hinge",
                    "parent_body_path": "/Asset/parent",
                    "child_body_path": "/Asset/child",
                },
                ctx,
            )
        assert samples == []
        return
    tracker = joint_movement.JointTracker(
        stage,
        {
            "name": "hinge",
            "prim_path": "/Asset/hinge",
            "parent_body_path": "/Asset/parent",
            "child_body_path": "/Asset/child",
        },
        ctx,
    )
    updating = True
    if missing in ("update_parent", "update_child"):
        with pytest.raises(RuntimeError, match="required transform unavailable"):
            tracker.update()
        assert samples == []
        return
    tracker.update()
    stop = "watchdog_budget_exhausted" if missing == "watchdog" else "observation_budget_exhausted"
    tracker.finish(stop)
    assert partial
    assert len(warnings) == 1
    assert finished == [stop]
    assert len(samples) == (1 if missing == "watchdog" else 0)


def test_joint_tracker_marks_missing_stage_scale_partial(joint_movement, monkeypatch):
    from pxr import UsdGeom

    partial, warnings, captured_metadata = [], [], []
    history = types.SimpleNamespace(mark_partial=partial.append)

    def begin(_name, _channels, metadata):
        captured_metadata.append(metadata)
        return history

    ctx = types.SimpleNamespace(config={"physics_fps": 240}, begin_motion_history=begin, warn=warnings.append)
    monkeypatch.setattr(joint_movement, "_get_world_matrix", lambda *_: Gf.Matrix4d(1.0))
    monkeypatch.setattr(joint_movement, "_get_bbox_diagonal", lambda *_: 1.0)

    def unavailable_scale(_stage):
        raise RuntimeError("stage metadata unavailable")

    monkeypatch.setattr(UsdGeom, "GetStageMetersPerUnit", unavailable_scale)
    joint_movement.JointTracker(
        Usd.Stage.CreateInMemory(),
        {"name": "hinge", "prim_path": "/Asset/hinge", "child_body_path": "/Asset/child"},
        ctx,
    )
    assert captured_metadata[0]["context_partial"] is True
    assert "meters_per_unit" not in captured_metadata[0]
    assert partial
    assert len(warnings) == 1


# The focused helpers below are pure USD logic, but their production module also
# imports Kit-only visualization/runtime helpers. Keep this unit test runnable in
# the normal Python test environment without requiring a Kit process.
@pytest.fixture()
def joint_movement(monkeypatch):
    """Load the production module without leaking Kit stubs into pytest."""
    fabric_utils = types.ModuleType("simready.evaluate_engine_kit.fabric_utils")
    fabric_utils.live_world_matrix = lambda *_args, **_kwargs: None
    monkeypatch.setitem(sys.modules, "simready.evaluate_engine_kit.fabric_utils", fabric_utils)

    force_display = types.ModuleType("simready.evaluate_engine_kit.force_display")
    force_display.clear_visuals = lambda *_args, **_kwargs: None
    force_display.compute_arrow_length = lambda *_args, **_kwargs: 0.0
    force_display.draw_force_arrow = lambda *_args, **_kwargs: None
    force_display.get_prim_world_position = lambda *_args, **_kwargs: None
    monkeypatch.setitem(sys.modules, "simready.evaluate_engine_kit.force_display", force_display)

    physics_utils = types.ModuleType("simready.evaluate_engine_kit.physics_utils")
    physics_utils.active_physics_engine = lambda *_args, **_kwargs: "physx"
    physics_utils.find_root_body = lambda *_args, **_kwargs: None
    monkeypatch.setitem(sys.modules, "simready.evaluate_engine_kit.physics_utils", physics_utils)

    decorator_module = types.ModuleType("simready.evaluate.core.decorator")
    decorator_module.test = lambda *_args, **_kwargs: lambda fn: fn
    monkeypatch.setitem(sys.modules, "simready.evaluate.core.decorator", decorator_module)

    source = (
        Path(__file__).resolve().parents[1]
        / "simready/foundation/tier_newton/runtime_tests"
        / "fet004_multibody"
        / "joint_movement.py"
    )
    module_name = "_test_newton_fet004_joint_movement_impl"
    spec = importlib.util.spec_from_file_location(module_name, source)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def _assessment_movement_scene(monkeypatch, module, kind="empty"):
    from simready.foundation.tier_newton.runtime_tests import engine_guard

    stage = Usd.Stage.CreateInMemory()
    stage.DefinePrim("/Asset", "Xform")
    if kind != "empty":
        _rigid_body(stage, "/Asset/parent")
        _rigid_body(stage, "/Asset/child")
        joint_class = {
            "fixed": UsdPhysics.FixedJoint,
            "scalar": UsdPhysics.PrismaticJoint,
            "spherical": UsdPhysics.SphericalJoint,
            "unsupported": UsdPhysics.DistanceJoint,
        }[kind]
        joint = joint_class.Define(stage, "/Asset/joint")
        joint.CreateBody0Rel().SetTargets(["/Asset/parent"])
        joint.CreateBody1Rel().SetTargets(["/Asset/child"])
        if kind == "scalar":
            joint.CreateLowerLimitAttr(-1)
            joint.CreateUpperLimitAttr(1)
    usd = types.SimpleNamespace(get_context=lambda: types.SimpleNamespace(get_stage=lambda: stage))
    monkeypatch.setitem(sys.modules, "omni", types.SimpleNamespace(usd=usd))
    monkeypatch.setitem(sys.modules, "omni.usd", usd)
    monkeypatch.setattr(engine_guard, "require_physx_test_engine", lambda: None, raising=False)
    monkeypatch.setattr(module, "articulationize_loose_joints", lambda *args: None)
    physics_utils = sys.modules["simready.evaluate_engine_kit.physics_utils"]
    physics_utils.check_physics_cookable = lambda *args: None
    physics_utils.cook_skip_message = lambda result: None
    room = types.SimpleNamespace(
        auto_size=lambda *args: None,
        set_color=lambda *args: None,
        show_ground=lambda **kwargs: None,
        place_asset_at_ground=lambda: None,
    )
    physics = types.SimpleNamespace(play=lambda: None, stop=lambda: None)

    async def prepared(*args, **kwargs):
        return None

    class Context:
        asset_path = "asset.usda"

        def __init__(self):
            self.config = dict(module.JOINT_MOVEMENT_KWARGS["config_defaults"], show_force_arrows=False)
            self.recorded, self.skipped, self.events = {}, [], []
            self.scene = types.SimpleNamespace(
                asset=types.SimpleNamespace(prim_path="/Asset"),
                load_asset=lambda *args, **kwargs: None,
                add_room=lambda: room,
                lighting=types.SimpleNamespace(add_dome=lambda **kwargs: None),
                add_physics=lambda **kwargs: physics,
                setup_camera_follow=lambda: None,
                prepare_physics=prepared,
            )

        @property
        def metrics(self):
            return dict(self.recorded)

        def add_metric(self, name, value):
            self.recorded[name] = value
            self.events.append("metric")

        def skip(self, message):
            self.skipped.append(message)
            self.events.append("skip")

        def fail(self, message):
            pytest.fail("No joint response was evaluated: " + message)

        precheck_failure = fail

        def step(self, *args, **kwargs):
            pass

        log = warn = set_settle_frames = step
        settle = prepared

    return Context(), stage


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["empty", "fixed"])
async def test_no_movable_joint_publishes_applicability_before_skip(joint_movement, monkeypatch, kind):
    ctx, _ = _assessment_movement_scene(monkeypatch, joint_movement, kind)
    await joint_movement.run_joint_movement(ctx)
    assert len(ctx.skipped) == 1
    assert ctx.recorded["assessment_applicability"] == {
        "status": "not_applicable",
        "reason_code": "no_movable_joints",
        "reason": ctx.skipped[0],
    }
    assert ctx.events.index("metric") < ctx.events.index("skip")


@pytest.mark.asyncio
async def test_unwrappable_movable_joint_is_setup_error(joint_movement, monkeypatch):
    ctx, _ = _assessment_movement_scene(monkeypatch, joint_movement, "scalar")
    with pytest.raises(RuntimeError, match="articulation"):
        await joint_movement.run_joint_movement(ctx)
    assert not ctx.skipped
    assert "assessment_applicability" not in ctx.recorded


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["scalar", "spherical", "unsupported"])
async def test_unavailable_newton_probe_is_execution_gap(joint_movement, monkeypatch, kind):
    ctx, stage = _assessment_movement_scene(monkeypatch, joint_movement, kind)
    UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath("/Asset"))
    monkeypatch.setattr(joint_movement, "active_physics_engine", lambda: "newton")
    monkeypatch.setattr(joint_movement, "newton_scene_initialized", lambda: True)
    monkeypatch.setattr(joint_movement, "_lever_application_point", lambda *args: None)

    async def unavailable_drive(*args, **kwargs):
        return {}, [], False, "native drive mapping unavailable"

    monkeypatch.setattr(joint_movement, "_run_newton_drive_sim", unavailable_drive)
    with pytest.raises(RuntimeError):
        await joint_movement.run_joint_movement(ctx)
    assert not ctx.skipped
    assert "assessment_applicability" not in ctx.recorded


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "record_error",
    [
        "native force view unavailable",
        "Newton returned no finite positive mass for the child link",
        "Newton returned no finite transform for the child link",
        "Newton child-link transform became unavailable",
    ],
)
@pytest.mark.parametrize("cleanup_error", [False, True])
async def test_spherical_recording_state_loss_is_execution_error(
    joint_movement, monkeypatch, record_error, cleanup_error
):
    ctx, stage = _assessment_movement_scene(monkeypatch, joint_movement, "spherical")
    UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath("/Asset"))
    monkeypatch.setattr(joint_movement, "active_physics_engine", lambda: "newton")
    monkeypatch.setattr(joint_movement, "newton_scene_initialized", lambda: True)
    monkeypatch.setattr(joint_movement, "_lever_application_point", lambda *_: ((1, 0, 0), (1, 0, 0)))
    tracker = types.SimpleNamespace(
        result=lambda: {"moved": True, "rotation_deg": 2.0, "translation_pct": 0.0, "bbox_diag_m": 1.0}
    )
    captures, cleanup, failures = [], [], []

    async def probe(*args, **kwargs):
        captures.append(kwargs["capture"])
        return (None, [], record_error) if kwargs["capture"] else (tracker, [], None)

    def stop():
        cleanup.append("stop")
        if cleanup_error and len(captures) == 2:
            raise RuntimeError("native stop unavailable")

    physics = ctx.scene.add_physics()
    physics.stop = stop
    monkeypatch.setattr(joint_movement, "_run_newton_spherical_force_sim", probe)
    monkeypatch.setattr(joint_movement, "_reset_transforms", lambda *_: cleanup.append("transforms"))
    monkeypatch.setattr(joint_movement, "_clear_arrows", lambda *_: cleanup.append("arrows"))
    monkeypatch.setattr(ctx, "fail", failures.append)
    monkeypatch.setattr(sys, "_simready_evaluate_kit_engine_retired", False, raising=False)

    with pytest.raises(RuntimeError, match="spherical force recording unavailable") as caught:
        await joint_movement.run_joint_movement(ctx)

    assert record_error in str(caught.value)
    assert captures == [False, True]
    assert not failures and not ctx.skipped
    assert "jm_joints_passed" not in ctx.recorded and "assessment_applicability" not in ctx.recorded
    assert cleanup == (["stop", "stop"] if cleanup_error else ["stop", "stop", "transforms", "arrows"])
    assert sys._simready_evaluate_kit_engine_retired is cleanup_error
    if cleanup_error:
        assert any("native stop unavailable" in note for note in caught.value.__notes__)


def _rigid_body(stage, path):
    prim = stage.DefinePrim(path, "Xform")
    UsdPhysics.RigidBodyAPI.Apply(prim)
    return prim


def test_joint_tracker_detects_child_rotation_relative_to_parent(monkeypatch, joint_movement):
    stage = Usd.Stage.CreateInMemory()
    _rigid_body(stage, "/Asset/parent")
    _rigid_body(stage, "/Asset/child")
    matrices = {
        "/Asset/parent": Gf.Matrix4d(1.0),
        "/Asset/child": Gf.Matrix4d(1.0),
    }
    monkeypatch.setattr(joint_movement, "_get_world_matrix", lambda _stage, path: matrices[path])
    monkeypatch.setattr(joint_movement, "_get_bbox_diagonal", lambda _stage, _path: 1.0)
    tracker = joint_movement.JointTracker(
        stage,
        {
            "child_body_path": "/Asset/child",
            "parent_body_path": "/Asset/parent",
            "_rot_thresh_deg": 1.0,
            "_trans_thresh_pct": 2.0,
        },
    )

    common_rotation = Gf.Matrix4d(1.0)
    common_rotation.SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), 25.0))
    relative_rotation = Gf.Matrix4d(1.0)
    relative_rotation.SetRotate(Gf.Rotation(Gf.Vec3d(1, 0, 0), 8.0))
    matrices["/Asset/parent"] = common_rotation
    matrices["/Asset/child"] = relative_rotation * common_rotation

    tracker.update()

    result = tracker.result()
    assert result["rotation_deg"] == pytest.approx(8.0, abs=0.001)
    assert result["translation_m"] == 0.0
    assert result["moved"] is True


@pytest.mark.parametrize("name", ["rotation_threshold_deg", "translation_threshold_pct"])
@pytest.mark.parametrize("invalid", [-1.0, float("nan"), float("inf"), float("-inf"), True, False, "1.0", None, 1j, []])
def test_malformed_movement_threshold_fails_before_scene_work(joint_movement, monkeypatch, name, invalid):
    config = dict(joint_movement.JOINT_MOVEMENT_KWARGS["config_defaults"])
    config[name] = invalid

    def forbidden(*_args, **_kwargs):
        pytest.fail("Malformed measurement policy must not mutate the scene or produce an asset verdict")

    ctx = types.SimpleNamespace(
        config=config,
        asset_path="unused.usda",
        set_settle_frames=forbidden,
        scene=types.SimpleNamespace(load_asset=forbidden),
        fail=forbidden,
        pass_test=forbidden,
    )
    with pytest.raises(RuntimeError, match="FET004 invalid measurement configuration: " + name):
        asyncio.run(joint_movement.run_joint_movement(ctx))


@pytest.mark.parametrize(
    ("name", "override"),
    [("rotation_threshold_deg", "_rot_thresh_deg"), ("translation_threshold_pct", "_trans_thresh_pct")],
)
@pytest.mark.parametrize("invalid", [-1.0, float("nan"), float("inf"), float("-inf"), True, False, "1.0", None, 1j, []])
def test_tracker_rejects_malformed_threshold_before_readback(joint_movement, monkeypatch, name, override, invalid):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Malformed measurement policy must not read runtime state")

    monkeypatch.setattr(joint_movement, "_get_world_matrix", forbidden)
    monkeypatch.setattr(joint_movement, "_get_bbox_diagonal", forbidden)
    with pytest.raises(RuntimeError, match="FET004 invalid measurement configuration: " + name):
        joint_movement.JointTracker(None, {"child_body_path": "/Asset/child", override: invalid})


@pytest.mark.parametrize("threshold", [0.0, 1e-12, 1.0, 1000.0])
def test_tracker_preserves_finite_nonnegative_threshold_policy(joint_movement, monkeypatch, threshold):
    monkeypatch.setattr(joint_movement, "_get_world_matrix", lambda *_args: Gf.Matrix4d(1.0))
    monkeypatch.setattr(joint_movement, "_get_bbox_diagonal", lambda *_args: 1.0)
    tracker = joint_movement.JointTracker(
        None,
        {"child_body_path": "/Asset/child", "_rot_thresh_deg": threshold, "_trans_thresh_pct": threshold},
    )
    tracker.update()
    assert tracker.rot_thresh == threshold
    assert tracker.trans_thresh_pct == threshold
    assert tracker.result()["moved"] is (threshold == 0.0)


def test_stationary_tracker_does_not_pass_default_thresholds(joint_movement, monkeypatch):
    monkeypatch.setattr(joint_movement, "_get_world_matrix", lambda *_args: Gf.Matrix4d(1.0))
    monkeypatch.setattr(joint_movement, "_get_bbox_diagonal", lambda *_args: 1.0)
    tracker = joint_movement.JointTracker(None, {"child_body_path": "/Asset/child"})
    tracker.update()
    assert tracker.result()["moved"] is False


def test_perpendicular_force_directions_prioritize_largest_lever_torque(joint_movement):
    directions = joint_movement._perpendicular_force_directions((2.0, 0.0, 0.0))

    assert directions == [(0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]


def test_newton_link_mass_reads_selected_runtime_body(joint_movement):
    class PhysicsView:
        def get_masses(self):
            return np.asarray([[4.0, 0.125, 8.0]], dtype=np.float32)

    force_view = {"physics_view": PhysicsView(), "body_index": 1}

    assert joint_movement._newton_link_mass(force_view) == pytest.approx(0.125)


def test_newton_force_probe_balances_child_and_parent_wrench(joint_movement):
    class PhysicsView:
        def apply_forces_and_torques_at_position(self, forces, torques, positions, indices, is_global):
            self.call = (forces, torques, positions, indices, is_global)

    physics_view = PhysicsView()
    force_view = {
        "art": object(),
        "physics_view": physics_view,
        "body_count": 3,
        "body_index": 2,
        "parent_index": 0,
    }

    joint_movement._apply_newton_force_at_position(
        force_view,
        direction=(0.0, 1.0, 0.0),
        magnitude=0.25,
        position=(1.0, 2.0, 3.0),
    )

    forces, torques, positions, indices, is_global = physics_view.call
    assert torques is None
    assert is_global is True
    assert indices.tolist() == [0]
    assert forces[0, 2].tolist() == pytest.approx([0.0, 0.25, 0.0])
    assert forces[0, 0].tolist() == pytest.approx([0.0, -0.25, 0.0])
    assert np.allclose(np.sum(forces, axis=1), 0.0)
    assert positions[0, 2].tolist() == pytest.approx([1.0, 2.0, 3.0])
    assert positions[0, 0].tolist() == pytest.approx([1.0, 2.0, 3.0])
