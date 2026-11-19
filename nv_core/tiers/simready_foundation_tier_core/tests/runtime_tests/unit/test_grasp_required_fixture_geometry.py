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
import copy
import math
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest
from pxr import Gf, Usd, UsdGeom, UsdPhysics
from simready.evaluate_engine_kit import fabric_utils
from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_geometry import bounded_lift_height
from simready.foundation.tier_core.runtime_tests.fet005_grasp.phase_dropping import DroppingPhase
from simready.foundation.tier_core.runtime_tests.fet005_grasp.phase_grasping import GraspingPhase
from simready.foundation.tier_core.runtime_tests.fet005_grasp.phase_lifting import LiftingPhase


@pytest.fixture
def bound_scene(monkeypatch):
    stage = Usd.Stage.CreateInMemory()
    body = UsdGeom.Cube.Define(stage, "/Asset/Body")
    body.CreateSizeAttr(1.0)
    UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
    engine = ModuleType("simready.evaluate_engine_kit.physics_utils")
    engine.active_physics_engine = lambda: "physx"
    monkeypatch.setitem(sys.modules, engine.__name__, engine)
    scene = SimpleNamespace(
        stage=stage,
        scene_properties={"tracked_body_path": "/Asset/Body", "target_asset_path": "/Asset"},
        robot=SimpleNamespace(lift=lambda *_args: pytest.fail("unexpected lift command")),
    )
    return scene, body, engine


@pytest.mark.parametrize("dimension", [0.05, 0.2, 2.0])
@pytest.mark.parametrize("runtime", ["physx", "newton"])
def test_lift_height_preserves_existing_valid_formula(bound_scene, monkeypatch, dimension, runtime):
    scene, body, engine = bound_scene
    engine.active_physics_engine = lambda: runtime
    if runtime == "physx":
        body.AddScaleOp().Set(Gf.Vec3f(dimension, dimension, dimension))
    else:
        # Authored rest geometry deliberately differs from observed geometry.
        body.AddScaleOp().Set(Gf.Vec3f(0.01, 0.01, 0.01))
        calls = []

        def live(stage, path, select, require_complete=False):
            calls.append((stage, path, select, require_complete))
            return (0.0, 0.0, 0.0), (dimension, dimension, dimension)

        monkeypatch.setattr(fabric_utils, "live_world_aabb", live)
    phase = LiftingPhase({"physics_fps": 240})

    assert phase._compute_lift_height(scene) == pytest.approx(bounded_lift_height(dimension, 2.0, 0.3, 0.5))
    if runtime == "newton":
        assert calls == [(scene.stage, "/Asset/Body", fabric_utils.is_rigid_body, True)]


def test_lift_height_uses_selected_body_without_requiring_unused_asset_fallback(bound_scene):
    scene, _body, _engine = bound_scene
    scene.scene_properties.pop("target_asset_path")
    assert LiftingPhase({"physics_fps": 240})._compute_lift_height(scene) == 0.5


@pytest.mark.parametrize("purpose", [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy])
def test_lift_height_includes_each_supported_geometry_purpose(bound_scene, purpose):
    scene, body, _engine = bound_scene
    body.CreatePurposeAttr(purpose)
    body.AddScaleOp().Set(Gf.Vec3f(0.2, 0.2, 0.2))

    assert LiftingPhase({"physics_fps": 240})._compute_lift_height(scene) == pytest.approx(0.4)


@pytest.mark.parametrize(
    "bounds",
    [
        None,
        ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ((0.0, 0.0, 0.0), (-1.0, 1.0, 1.0)),
        ((0.0, 0.0, 0.0), (math.nan, 1.0, 1.0)),
        ((0.0, 0.0, 0.0), (math.inf, 1.0, 1.0)),
        ((0.0, 0.0), (1.0, 1.0)),
        ((0.0, 0.0, 0.0), ("1", 1.0, 1.0)),
        ((0.0, 0.0, 0.0), (True, 1.0, 1.0)),
        (np.zeros(3), np.array([1.0, 1.0, 1.0], dtype=object)),
        (np.zeros(3), np.array([1.0, 1.0, 1.0], dtype=complex)),
    ],
)
def test_unusable_live_lift_bound_never_falls_back_to_minimum_or_commands(bound_scene, monkeypatch, bounds):
    scene, _body, engine = bound_scene
    engine.active_physics_engine = lambda: "newton"
    monkeypatch.setattr(fabric_utils, "live_world_aabb", lambda *_args, **_kwargs: bounds)
    phase = LiftingPhase({"physics_fps": 240})
    with pytest.raises(RuntimeError, match="Required grasp-body bounds"):
        phase.check_frame(0, 0.0, scene, SimpleNamespace(center_history=[(0.0, 0.0, 1.0)]))


def test_native_lift_bound_error_preserves_original_cause(bound_scene, monkeypatch):
    scene, _body, engine = bound_scene
    engine.active_physics_engine = lambda: "newton"
    error = fabric_utils.LiveBoundsReadError("native body pose unavailable")

    def unavailable(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(fabric_utils, "live_world_aabb", unavailable)
    with pytest.raises(RuntimeError) as captured:
        LiftingPhase({"physics_fps": 240})._compute_lift_height(scene)
    assert captured.value.__cause__ is error


@pytest.mark.parametrize("missing", ["path", "prim", "geometry"])
def test_missing_lift_geometry_is_setup_error_not_minimum_height(bound_scene, missing):
    scene, _body, _engine = bound_scene
    if missing == "path":
        scene.scene_properties = {}
    elif missing == "prim":
        scene.scene_properties["tracked_body_path"] = "/Missing"
    else:
        scene.scene_properties["tracked_body_path"] = str(UsdGeom.Xform.Define(scene.stage, "/Empty").GetPath())
    with pytest.raises(RuntimeError, match="Required grasp-body bounds"):
        LiftingPhase({"physics_fps": 240})._compute_lift_height(scene)


def test_overflowed_drop_height_is_setup_error_not_infinite_behavioral_threshold(bound_scene, monkeypatch):
    scene, _body, engine = bound_scene
    engine.active_physics_engine = lambda: "newton"
    bounds = ((0.0, 0.0, -1e308), (1.0, 1.0, 1e308))
    monkeypatch.setattr(fabric_utils, "live_world_aabb", lambda *_args, **_kwargs: bounds)
    with pytest.raises(RuntimeError, match="Required grasp-body bounds") as captured:
        DroppingPhase({"physics_fps": 240})._compute_required_fall(scene)
    assert "non-finite" in str(captured.value.__cause__)


@pytest.mark.parametrize("field", ["lift_height_multiplier", "lift_min_height", "lift_max_height"])
@pytest.mark.parametrize("value", [True, "0.5", math.nan, math.inf, -1.0])
def test_lift_geometry_configuration_is_not_coerced_or_fallback(field, value):
    with pytest.raises(ValueError, match=field):
        LiftingPhase({"physics_fps": 240, field: value})


def test_lift_geometry_configuration_retains_valid_zero_multiplier_and_equal_limits():
    phase = LiftingPhase(
        {"physics_fps": 240, "lift_height_multiplier": 0.0, "lift_min_height": 0.3, "lift_max_height": 0.3}
    )
    assert bounded_lift_height(1.0, phase._height_mult, phase._minimum_lift_height, phase._maximum_lift_height) == 0.3


def fixture_properties():
    return {
        "gripper_position_info": {"grasp_distance": 0.2},
        "gripper_pad_properties": {"scale": 0.02},
        "pad_to_surface_distance": 0.05,
        "expected_contact_travel": 0.05,
    }


def closing_scene(properties):
    commands = []
    robot = SimpleNamespace(
        close=commands.append,
        get_finger_joint_positions=lambda: (-0.005, -0.005),
        get_gripper_joint_target=lambda: commands[-1],
    )
    tracker = SimpleNamespace(
        center_history=[(0.0, 0.0, 1.0)],
        finger_positions=[(-0.005, -0.005)],
        finger_times=[0.0],
    )
    return SimpleNamespace(robot=robot, scene_properties=properties), tracker, commands


@pytest.mark.parametrize("pad_to_surface", [0.0, 0.05, 0.1, 0.15, None])
def test_valid_close_geometry_retains_targets_ramp_and_ticks(pad_to_surface):
    props = fixture_properties()
    if pad_to_surface is None:
        props.pop("pad_to_surface_distance")
        pad_to_surface = 0.1
    else:
        props["pad_to_surface_distance"] = pad_to_surface
    scene, tracker, commands = closing_scene(props)
    phase = GraspingPhase({"physics_fps": 240, "close_duration": 0.5})
    surface_travel = pad_to_surface if pad_to_surface < 0.1 else 0.09
    expected_close = min(0.09, surface_travel + 0.005)
    expected_frames = max(120, math.ceil(expected_close / 0.04 * 240))

    for frame in range(10):
        assert phase.check_frame(frame, frame / 240.0, scene, tracker) is None

    assert phase._close_frames == expected_frames
    assert commands == pytest.approx([-expected_close * frame / expected_frames for frame in range(10)])


@pytest.mark.parametrize(
    "missing",
    ["gripper_position_info", "gripper_pad_properties", "grasp_distance", "scale", "expected_contact_travel"],
)
@pytest.mark.parametrize("already_stable", [False, True])
def test_missing_required_close_geometry_does_not_manufacture_command(missing, already_stable):
    props = fixture_properties()
    if missing == "grasp_distance":
        props["gripper_position_info"].pop(missing)
    elif missing == "scale":
        props["gripper_pad_properties"].pop(missing)
    else:
        props.pop(missing)
    scene, tracker, commands = closing_scene(props)
    phase = GraspingPhase({"physics_fps": 240})
    if already_stable:
        phase._stable_target = -0.02
    with pytest.raises(RuntimeError, match="Required generated gripper geometry"):
        phase.check_frame(0, 0.0, scene, tracker)
    assert commands == []
    assert phase._settle_samples == []


@pytest.mark.parametrize("field", ["grasp_distance", "scale", "pad_to_surface_distance", "expected_contact_travel"])
@pytest.mark.parametrize("value", [True, "0.02", None, math.nan, math.inf, -0.1, complex(0.02)])
def test_malformed_close_geometry_is_setup_error_before_commands(field, value):
    props = copy.deepcopy(fixture_properties())
    target = props["gripper_position_info"] if field == "grasp_distance" else props
    if field == "scale":
        target = props["gripper_pad_properties"]
    target[field] = value
    scene, tracker, commands = closing_scene(props)
    with pytest.raises(RuntimeError, match="Required generated gripper geometry"):
        GraspingPhase({"physics_fps": 240}).check_frame(0, 0.0, scene, tracker)
    assert commands == []


@pytest.mark.parametrize("value", [True, "0.005", math.nan, math.inf, -0.001])
def test_contact_preload_configuration_is_validated_without_coercion(value):
    with pytest.raises(ValueError, match="grasp_contact_compression"):
        GraspingPhase({"physics_fps": 240, "grasp_contact_compression": value})


def test_zero_contact_preload_remains_valid_policy():
    assert GraspingPhase({"physics_fps": 240, "grasp_contact_compression": 0.0})._contact_compression == 0.0
