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
"""Hand poses/schedules stay bounded, angular and actuator-owned."""

import ast
import asyncio
import copy
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases import gripper_close_lift as phase
from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_state import (
    FLOAT32_SAFE_COORDINATE_ABS,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.hand_controls import (
    delayed_close_targets,
    effective_trial_controls,
    normalize_hand_trial_controls,
    resolve_hand_trial_specs,
    validate_close_delays,
)


def _specs():
    return [
        {"name": "finger", "idx": 1, "open": 0.0, "closed": 1.0},
        {"name": "opposition", "idx": 2, "open": 0.0, "closed": -1.0},
        {"name": "flexor", "idx": 3, "open": 1.0, "closed": 0.0},
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, 0, 1, -1, 0.0, "false", "true", "", [], {}, [False], np.bool_(False)])
async def test_native_contact_opt_in_rejects_nonboolean_config_before_scene_access(monkeypatch, value):
    from simready.foundation.tier_core.runtime_tests import engine_guard

    monkeypatch.setattr(engine_guard, "require_physx_test_engine", lambda: None)

    class UnvisitedScene:
        @property
        def stage(self):
            pytest.fail("invalid native-contact opt-in reached scene/trial mutation")

    with pytest.raises(ValueError, match="diagnostic_native_contact_pairs.*explicit boolean"):
        await phase.run_gripper_close_lift(
            SimpleNamespace(scene=UnvisitedScene()), None, {}, {"diagnostic_native_contact_pairs": value}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config", [{}, {"diagnostic_native_contact_pairs": False}, {"diagnostic_native_contact_pairs": True}]
)
async def test_native_contact_boolean_config_and_default_reach_unchanged_scene_setup(monkeypatch, config):
    from simready.foundation.tier_core.runtime_tests import engine_guard

    monkeypatch.setattr(engine_guard, "require_physx_test_engine", lambda: None)

    class SceneReached(RuntimeError):
        pass

    class Scene:
        @property
        def stage(self):
            raise SceneReached("valid opt-in reached normal setup")

    with pytest.raises(SceneReached):
        await phase.run_gripper_close_lift(SimpleNamespace(scene=Scene()), None, {}, config)


def _eligible():
    return {
        name: {"idx": index, "unit": "rad", "identity_resolved": True}
        for index, name in enumerate(["carrier", "finger", "opposition", "flexor"])
        if name != "carrier"
    }


@pytest.mark.parametrize(
    "raw", [{}, {"joints": {}}, {"close_delay_steps": {}}, {"joints": {}, "close_delay_steps": {}}]
)
def test_empty_controls_preserve_specs_and_do_not_require_angular_metadata(raw):
    controls = normalize_hand_trial_controls(raw)
    specs = _specs()
    assert controls == {}
    assert resolve_hand_trial_specs(specs, controls, {}, ([], [])) == specs
    assert validate_close_delays(controls, specs, 600, 300) == {}


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        {"typo": 0},
        {"joints": {"finger": {"closed_rad": 0.5}}},
        {"joints": {"finger": {"hold_rad": 0.5, "closed_rad": 0.5}}},
        {"joints": {"finger": {"open_rad": True, "closed_rad": 0.5}}},
        {"joints": {"finger": {"hold_rad": float("nan")}}},
        {"joints": {"": {"hold_rad": 0.0}}},
        {"close_delay_steps": {"finger": True}},
        {"close_delay_steps": {"finger": 1.5}},
        {"close_delay_steps": {"finger": -1}},
        {"close_delay_steps": {"finger": 10001}},
        {"approach_pitch_deg": -1},
        {"approach_pitch_deg": 91},
        {"approach_pitch_deg": float("inf")},
        {"grasp_center_base_m": [0, 0]},
        {"grasp_center_base_m": [0, 0, float("nan")]},
        {"object_offset_world_xy_m": [0, 0, 0]},
        {"descent_reference": "unknown"},
        {"descent_reference": "grasp_center"},
        {"joints": {f"joint_{index}": {"hold_rad": 0.0} for index in range(65)}},
    ],
)
def test_invalid_serialized_controls_rejected_before_motion(raw):
    with pytest.raises(ValueError):
        normalize_hand_trial_controls(raw)


def test_signed_closure_and_held_opposition_remain_independent_and_do_not_mutate_inputs():
    specs = _specs()
    original = copy.deepcopy(specs)
    controls = normalize_hand_trial_controls(
        {
            "joints": {
                "opposition": {"hold_rad": -0.8},
                "flexor": {"open_rad": 0.9, "closed_rad": 0.2},
            }
        }
    )
    result = resolve_hand_trial_specs(specs, controls, _eligible(), ([0, 0, -1, 0], [1, 1, 0, 1]))
    assert specs == original
    assert result[0] == original[0]
    assert result[1]["open"] == result[1]["closed"] == -0.8
    assert result[1]["contact_active"] is False
    assert result[2]["open"] == 0.9 and result[2]["closed"] == 0.2
    assert {spec["idx"] for spec in phase._contact_active_specs(result)} == {1, 3}
    assert {spec["idx"] for spec in result} == {1, 2, 3}  # Never carrier index zero.


@pytest.mark.parametrize("joint", ["carrier", "mimic_follower", "missing"])
def test_overrides_cannot_promote_non_owned_dofs(joint):
    controls = normalize_hand_trial_controls({"joints": {joint: {"hold_rad": 0.0}}})
    with pytest.raises(ValueError, match="independently driven angular"):
        resolve_hand_trial_specs(_specs(), controls, _eligible(), ([0, 0, -1, 0], [1, 1, 0, 1]))


@pytest.mark.parametrize(
    "identity", [{"unit": "unknown_native", "identity_resolved": True}, {"unit": "rad", "identity_resolved": False}]
)
def test_explicit_rad_targets_require_confirmed_angular_identity(identity):
    controls = normalize_hand_trial_controls({"joints": {"finger": {"open_rad": 0.0, "closed_rad": 0.5}}})
    eligible = _eligible()
    eligible["finger"].update(identity)
    with pytest.raises(ValueError, match="angular"):
        resolve_hand_trial_specs(_specs(), controls, eligible, ([0, 0, -1, 0], [1, 1, 0, 1]))


@pytest.mark.parametrize(
    "limits,targets",
    [
        (([0, 0, -1, 0], [1, 1, 0, 1]), {"open_rad": -0.1, "closed_rad": 0.5}),
        (([0, 1, -1, 0], [1, 0, 0, 1]), {"open_rad": 0.0, "closed_rad": 0.5}),
        (([0, float("nan"), -1, 0], [1, 1, 0, 1]), {"hold_rad": 0.0}),
    ],
)
def test_invalid_limits_or_out_of_range_targets_rejected(limits, targets):
    controls = normalize_hand_trial_controls({"joints": {"finger": targets}})
    with pytest.raises(ValueError):
        resolve_hand_trial_specs(_specs(), controls, _eligible(), limits)


def test_explicit_target_overflow_envelope_is_rejected_even_inside_large_authored_limits():
    controls = normalize_hand_trial_controls({"joints": {"finger": {"open_rad": 0.0, "closed_rad": 1e35}}})
    with pytest.raises(ValueError, match="representational safety envelope"):
        resolve_hand_trial_specs(_specs(), controls, _eligible(), ([0, 0, -1, 0], [1, 1e35, 0, 1]))


def test_complete_explicit_targets_can_resolve_a_geometrically_unclassified_eligible_joint():
    controls = normalize_hand_trial_controls({"joints": {"flexor": {"open_rad": 0.0, "closed_rad": 0.4}}})
    resolved = resolve_hand_trial_specs(_specs()[:2], controls, _eligible(), ([0, 0, -1, 0], [1, 1, 0, 1]))
    assert resolved[-1]["name"] == "flexor" and resolved[-1]["idx"] == 3
    assert resolved[-1]["contact_active"] is True


@pytest.mark.parametrize("scenario", ["closing", "held", "stale", "prismatic"])
def test_actual_hand_branch_validates_final_targets_after_overrides_without_hiding_probe_errors(scenario):
    from pxr import Usd, UsdPhysics
    from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_mapping import (
        GripperMappingError,
    )

    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Asset", "Xform")
    for name in ("finger", "opposition", "flexor"):
        joint_type = (
            UsdPhysics.PrismaticJoint if name == "flexor" and scenario == "prismatic" else UsdPhysics.RevoluteJoint
        )
        joint_type.Define(stage, "/Asset/" + name)
    specs = [
        {"idx": 0, "name": "finger", "open": 0.0, "closed": 1.0},
        {"idx": 1, "name": "opposition", "open": -1.0, "closed": -1.0},
        {"idx": 2, "name": "flexor", "open": 0.0, "closed": 0.0},
    ]
    original = copy.deepcopy(specs)
    failure = GripperMappingError("stale live probe")

    async def infer(*args):
        if scenario == "stale":
            raise failure
        return specs, []

    def unexpected(*args):
        raise AssertionError("probe/setup problems cannot become asset FAIL")

    tree = ast.parse(Path(phase.__file__).read_text(encoding="utf-8"))
    branch = next(
        node.orelse
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and node.orelse
        and any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "_infer_hand_grasp_specs"
            for statement in node.orelse
            for child in ast.walk(statement)
        )
    )
    body = ast.AsyncFunctionDef(
        name="run_branch",
        args=ast.arguments(
            posonlyargs=[], args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
        ),
        body=branch + [ast.Return(ast.Name("grasp_specs", ast.Load()))],
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[body], type_ignores=[]))
    namespace = dict(
        vars(phase),
        ctx=SimpleNamespace(log=lambda *args: None, fail=unexpected, precheck_failure=unexpected),
        stage=stage,
        asset_prim=root,
        robot=SimpleNamespace(
            dof_names=["finger", "opposition", "flexor"], get_joint_position_limits=lambda: ([0, -1, 0], [1, 0, 1])
        ),
        fingertip_set=SimpleNamespace(finger_chains=[[0], [1, 2]]),
        probe_config={},
        grasp_center_for_test=np.zeros(3),
        gripper_base_path="/Asset/base",
        _infer_hand_grasp_specs=infer,
        config=dict(
            phase.get_defaults(),
            hand_trial_controls={
                "joints": {
                    "opposition": {"hold_rad": -0.8},
                    "flexor": {"open_rad": 0.0, "closed_rad": 0.0 if scenario == "held" else 0.5},
                }
            },
        ),
    )
    exec(compile(module, str(phase.__file__), "exec"), namespace)
    if scenario == "closing":
        result = asyncio.run(namespace["run_branch"]())
        assert result[-1]["closed"] == 0.5 and result[1]["contact_active"] is False
    else:
        with pytest.raises(ValueError if scenario == "prismatic" else GripperMappingError) as caught:
            asyncio.run(namespace["run_branch"]())
        if scenario == "stale":
            assert caught.value is failure
    assert specs == original


def test_delayed_signed_ramps_hold_start_and_complete_inside_close_budget():
    specs = _specs()
    controls = normalize_hand_trial_controls({"close_delay_steps": {"flexor": 300}})
    delays = validate_close_delays(controls, specs, 600, 300)
    assert delayed_close_targets([0, 0, 1], specs, 300, 300, delays) == [1, -1, 1]
    assert delayed_close_targets([0, 0, 1], specs, 450, 300, delays) == [1, -1, 0.5]
    assert delayed_close_targets([0, 0, 1], specs, 600, 300, delays) == [1, -1, 0]


@pytest.mark.parametrize(
    "controls,total,ramp",
    [
        ({"close_delay_steps": {"flexor": 301}}, 600, 300),
        ({"close_delay_steps": {"missing": 1}}, 600, 300),
        ({"close_delay_steps": {"opposition": 1}}, 600, 300),
        ({"joints": {"finger": {"hold_rad": 0.0}}}, 10001, 300),
    ],
)
def test_invalid_delay_or_step_budget_rejected(controls, total, ramp):
    specs = _specs()
    specs[1]["closed"] = specs[1]["open"]
    with pytest.raises(ValueError):
        validate_close_delays(normalize_hand_trial_controls(controls), specs, total, ramp)


@pytest.mark.parametrize("total,ramp", [(True, 1), (600, True), (600.5, 300), (600, 300.5), ("600", 300)])
def test_configured_close_counts_are_integers_before_coercion(total, ramp):
    with pytest.raises(ValueError, match="step budget"):
        validate_close_delays({"approach_pitch_deg": 15.0}, _specs(), total, ramp)


def test_effective_controls_preserve_unknown_native_units_and_configured_dimensions():
    config = dict(phase.get_defaults(), object_size_fraction=1.1, tested_mass_kg_override=1.0)
    result = effective_trial_controls("cube", {}, _specs(), {}, config, 0.06, 1.0, 0.05764)
    assert result["configured_trial"] is True
    assert result["object_size_m"] == 0.06 and result["object_mass_kg"] == 1.0
    assert result["joints"][0]["unit"] == "unknown_native"
    assert "open_rad" not in result["joints"][0]
    sphere_config = dict(phase.get_defaults(), payload_mass_fraction=0.5)
    assert effective_trial_controls("sphere", {}, [], {}, sphere_config, 0.04, 0.5, 0.06)["configured_trial"] is False


@pytest.mark.parametrize(
    "key,value",
    [("enable_shake", False), ("enable_drop", False), ("lift_duration_s", 3.0), ("horizontal_drift_max", 1.0)],
)
def test_effective_controls_record_procedure_overrides_without_claiming_default_trial(key, value):
    defaults = phase.get_defaults()
    config = dict(defaults, **{key: value})
    result = effective_trial_controls("cube", {}, [], {}, config, 0.04, 0.5, 0.06, defaults)
    assert result["configured_trial"] is True
    assert result["procedure_settings"][key] == value
    assert (
        effective_trial_controls("cube", {}, [], {}, defaults, 0.04, 0.5, 0.06, defaults)["configured_trial"] is False
    )


@pytest.mark.parametrize("operation", ["open", "close"])
@pytest.mark.parametrize("bad_value", [np.nan, 1e35, True, "0.5", 0.5 + 0j])
def test_required_invalid_selected_state_stops_before_capture(monkeypatch, operation, bad_value):
    state = {"value": 0.0, "steps": 0, "captures": 0}
    specs = [{"idx": 0, "name": "finger", "open": 0.0, "closed": 1.0}]
    robot = SimpleNamespace(dof_count=2, get_joint_positions=lambda: [state["value"], np.nan])

    async def step():
        state["steps"] += 1
        state["value"] = bad_value

    async def capture(index):
        state["captures"] += 1

    monkeypatch.setattr(phase, "_command_grasp_targets", lambda *args, **kwargs: None)
    drive = phase._drive_to_open if operation == "open" else phase._drive_to_close
    with pytest.raises(RuntimeError, match=f"required {operation} before capture"):
        asyncio.run(
            drive(
                SimpleNamespace(step_one=step),
                robot,
                specs,
                SimpleNamespace(tip_link_paths=[]),
                phase.get_defaults(),
                on_step=capture,
            )
        )
    assert state["steps"] == 1 and state["captures"] == 0


@pytest.mark.parametrize("value", [1.1, -0.1, FLOAT32_SAFE_COORDINATE_ABS])
def test_required_native_numeric_guard_preserves_ordinary_overshoot_and_unselected_missing_state(value):
    robot = SimpleNamespace(dof_count=3, get_joint_positions=lambda: [None, value, "unavailable"])
    assert phase._required_grasp_positions(robot, [{"idx": 1}], "controlled") == [value]


@pytest.mark.parametrize(
    "buffer", [np.array([True]), np.array(["0.5"]), np.array([0.5 + 0j]), np.array([0.5], dtype=object)]
)
def test_required_original_invalid_numpy_dtype_is_not_coerced_to_real_position(buffer):
    robot = SimpleNamespace(dof_count=1, get_joint_positions=lambda: buffer)
    with pytest.raises(RuntimeError, match="real numeric"):
        phase._required_grasp_positions(robot, [{"idx": 0}], "controlled")


@pytest.mark.parametrize("operation", ["open", "close"])
@pytest.mark.parametrize(
    "buffer", [np.array([0.5, 0.3], dtype=object), np.array([0.5 + 0j, 0.3 + 0j]), np.array([True, False])]
)
def test_invalid_original_tensor_dtype_after_step_stops_before_capture(monkeypatch, operation, buffer):
    state = {"steps": 0, "captures": 0}
    robot = SimpleNamespace(dof_count=2, get_joint_positions=lambda: buffer if state["steps"] else [0.0, np.nan])

    async def step():
        state["steps"] += 1

    async def capture(index):
        state["captures"] += 1

    monkeypatch.setattr(phase, "_command_grasp_targets", lambda *args, **kwargs: None)
    drive = phase._drive_to_open if operation == "open" else phase._drive_to_close
    with pytest.raises(RuntimeError, match="real numeric i/u/f dtype"):
        asyncio.run(
            drive(
                SimpleNamespace(step_one=step),
                robot,
                [{"idx": 0, "name": "finger", "open": 0.0, "closed": 1.0}],
                SimpleNamespace(tip_link_paths=[]),
                phase.get_defaults(),
                on_step=capture,
            )
        )
    assert state["steps"] == 1 and state["captures"] == 0


@pytest.mark.parametrize("with_capture", [False, True])
def test_held_controlled_joint_remains_required_after_capture_or_without_callback(monkeypatch, with_capture):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import force_utils

    state = {"positions": [0.0, -0.5, np.nan], "steps": 0, "captures": 0}
    robot = SimpleNamespace(dof_count=3, get_joint_positions=lambda: list(state["positions"]))

    async def step():
        state["steps"] += 1
        state["positions"][0] = 0.1
        if not with_capture:
            state["positions"][1] = np.nan

    async def capture(index):
        state["captures"] += 1
        state["positions"][1] = np.nan

    monkeypatch.setattr(phase, "_command_grasp_targets", lambda *args, **kwargs: None)
    monkeypatch.setattr(force_utils, "read_contact_force_magnitude", lambda *args: None)
    specs = [
        {"idx": 0, "name": "finger", "open": 0.0, "closed": 1.0},
        {"idx": 1, "name": "positioning", "open": -0.5, "closed": -0.5},
    ]
    with pytest.raises(RuntimeError, match="required close joint readback"):
        asyncio.run(
            phase._drive_to_close(
                SimpleNamespace(step_one=step),
                robot,
                specs,
                SimpleNamespace(tip_link_paths=[]),
                dict(phase.get_defaults(), close_steps=2, close_ramp_steps=2),
                on_step=capture if with_capture else None,
            )
        )
    assert state["steps"] == 1 and state["captures"] == int(with_capture)


def test_optional_trial_record_transport_failure_does_not_abort_or_mutate_controls():
    controls = normalize_hand_trial_controls({"joints": {"finger": {"open_rad": 0.0, "closed_rad": 0.5}}})
    original = copy.deepcopy(controls)
    values = effective_trial_controls("cube", controls, _specs(), {}, phase.get_defaults(), 0.04, 0.5, 0.06)

    def broken(*args):
        raise RuntimeError("optional transport failure")

    phase._record_gripper_trial_controls(SimpleNamespace(add_metric=broken, warn=broken), values, 0)
    assert controls == original


def test_optional_trial_record_is_bounded_with_explicit_omissions_and_separate_motion_controls():
    names = [f"joint_{index}_" + "x" * 240 for index in range(64)]
    controls = normalize_hand_trial_controls(
        {
            "joints": {name: {"open_rad": 0.0, "closed_rad": 1.0} for name in names},
            "close_delay_steps": dict.fromkeys(names, 1),
        }
    )
    original = copy.deepcopy(controls)
    specs = [{"name": name, "idx": index, "open": 0.0, "closed": 1.0} for index, name in enumerate(names)]
    values = effective_trial_controls("cube", controls, specs, {}, phase.get_defaults(), 0.04, 0.5, 0.06)
    record = phase._bounded_gripper_trial_controls(values)
    assert len(json.dumps(record).encode("utf-8")) <= 32768
    assert sum(record["transport_omissions"].values()) > 0
    assert (
        controls == original
        and values["joints"]
        == effective_trial_controls("cube", controls, specs, {}, phase.get_defaults(), 0.04, 0.5, 0.06)["joints"]
    )


def test_optional_trial_record_cancellation_is_not_suppressed():
    values = effective_trial_controls("cube", {}, [], {}, phase.get_defaults(), 0.04, 0.5, 0.06)

    def cancelled(*args):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        phase._record_gripper_trial_controls(SimpleNamespace(add_metric=cancelled), values, 0)


def test_default_and_explicit_empty_close_preserve_commands_steps_and_optional_unselected_nulls(monkeypatch):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import force_utils

    monkeypatch.setattr(force_utils, "read_contact_force_magnitude", lambda *args: None)
    runs = []
    for controls in [None, {}, {"joints": {}, "close_delay_steps": {}}]:
        state = {"actual": 0.0, "steps": 0, "commands": []}
        robot = SimpleNamespace(dof_count=2, get_joint_positions=lambda state=state: [state["actual"], np.nan])

        async def step(state=state):
            state["steps"] += 1
            state["actual"] = min(0.3, state["commands"][-1][0])

        def command(*args, state=state, **kwargs):
            state["commands"].append(kwargs["target_values"])

        monkeypatch.setattr(phase, "_command_grasp_targets", command)
        config = dict(phase.get_defaults(), close_steps=4, close_ramp_steps=4)
        if controls is not None:
            config["hand_trial_controls"] = controls
        result = asyncio.run(
            phase._drive_to_close(
                SimpleNamespace(step_one=step, log=lambda *args: None),
                robot,
                [{"idx": 0, "name": "finger", "open": 0.0, "closed": 1.0}],
                SimpleNamespace(tip_link_paths=[]),
                config,
            )
        )
        runs.append((result, state["commands"], state["steps"]))
    assert runs[0] == runs[1] == runs[2] == (True, [[0.15625], [0.5], [0.84375], [1.0]], 4)


def test_actual_delayed_close_cannot_stall_before_last_ramp_finishes(monkeypatch):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import force_utils

    state = {"steps": 0, "commands": []}
    specs = [
        {"idx": 0, "name": "finger", "open": 0.0, "closed": 1.0},
        {"idx": 1, "name": "flexor", "open": 1.0, "closed": 0.0},
    ]
    robot = SimpleNamespace(dof_count=2, get_joint_positions=lambda: [0.1 if state["steps"] else 0, 1])

    async def step():
        state["steps"] += 1

    monkeypatch.setattr(force_utils, "read_contact_force_magnitude", lambda *args: None)
    monkeypatch.setattr(
        phase, "_command_grasp_targets", lambda *args, **kwargs: state["commands"].append(kwargs["target_values"])
    )
    config = dict(
        phase.get_defaults(),
        close_steps=6,
        close_ramp_steps=3,
        close_stall_window=1,
        hand_trial_controls={"close_delay_steps": {"flexor": 3}},
    )
    result = asyncio.run(
        phase._drive_to_close(
            SimpleNamespace(step_one=step, log=lambda *args: None),
            robot,
            specs,
            SimpleNamespace(tip_link_paths=[]),
            config,
        )
    )
    assert result is True and state["steps"] == 6
    assert state["commands"][2] == [1, 1] and state["commands"][-1] == [1, 0]


def test_measured_center_metres_and_pitch_preserve_offset_physical_root_pivot():
    from pxr import Gf, Usd, UsdGeom

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)
    root = UsdGeom.Xform.Define(stage, "/Asset/root")
    root.AddTranslateOp().Set((10, 0, 0))
    base = UsdGeom.Xform.Define(stage, "/Asset/base")
    base.AddTranslateOp().Set((20, 0, 0))
    site = SimpleNamespace(
        forward_axis_world=np.array([1, 0, 0]),
        grip_line_world=[np.zeros(3), np.array([0, -1, 0])],
        grasp_center_world_initial=lambda: np.array([20, 0, 10]),
    )
    quaternion, center, _ = phase._authored_hand_orientation(
        stage, "/Asset/base", site, pivot_path="/Asset/root", pitch_deg=90, center_base_m=[0.1, 0, 0]
    )
    rotation = Gf.Rotation(Gf.Quatd(float(quaternion[0]), Gf.Vec3d(*quaternion[1:])))
    expected = Gf.Vec3d(10, 0, 0) + rotation.TransformDir(Gf.Vec3d(20, 0, 0))
    assert np.allclose(center, expected)
    assert np.allclose(rotation.TransformDir(Gf.Vec3d(1, 0, 0)), [0, 0, -1])


def test_optional_contact_integration_uses_object_body_and_explicit_pad_scope(monkeypatch):
    calls = []
    provider = ModuleType("simready.evaluate_engine_kit.contact_diagnostics")
    collector = object()

    def begin(ctx, **kwargs):
        calls.append(kwargs)
        return collector

    provider.begin_physx_contact_diagnostics = begin
    monkeypatch.setitem(sys.modules, provider.__name__, provider)

    def getter():
        return "close"

    assert phase._begin_gripper_contact_diagnostics(None, "/Object/body", ["/Hand/pad"], getter) is collector
    assert calls == [{"object_paths": ["/Object/body"], "hand_body_paths": ["/Hand/pad"], "phase_getter": getter}]


@pytest.mark.parametrize(
    "outcome",
    ["available", "unavailable", "cleanup_failure", "incomplete", "snapshot_failure", "oversized", "recording_failure"],
)
def test_contact_finalization_is_bounded_best_effort_and_never_invents_clean_restoration(outcome):
    calls, metrics, warnings = [], {}, []

    def close(reason):
        calls.append(reason)
        if outcome == "cleanup_failure":
            raise RuntimeError("injected unsubscribe failure")

    def snapshot():
        if outcome == "snapshot_failure":
            raise RuntimeError("injected snapshot failure")
        return {
            "status": "available",
            "cleanup_complete": outcome != "incomplete",
            "summaries": [],
            "extra": "a" * 40000 if outcome == "oversized" else None,
        }

    def record(name, value):
        if outcome == "recording_failure":
            raise RuntimeError("injected recorder failure")
        metrics[name] = value

    ctx = SimpleNamespace(add_metric=record, warn=warnings.append)
    collector = None if outcome == "unavailable" else SimpleNamespace(close=close, snapshot=snapshot)
    phase._finish_gripper_contact_diagnostics(ctx, collector, "native_contact_diagnostics_trial_002", "failed")
    assert calls == ([] if collector is None else ["failed"])
    if outcome == "recording_failure":
        assert warnings and not metrics
    else:
        metric = metrics["native_contact_diagnostics_trial_002"]
        assert len(str(metric)) < 32768
        assert metric["cleanup_complete"] is (
            False
            if outcome in ("cleanup_failure", "incomplete")
            else None if outcome in ("snapshot_failure", "oversized") else True
        )
        if outcome in ("snapshot_failure", "oversized", "unavailable"):
            assert metric["status"] == "unavailable"


def test_contact_start_cancellation_is_preserved(monkeypatch):
    provider = ModuleType("simready.evaluate_engine_kit.contact_diagnostics")

    def begin(*args, **kwargs):
        raise asyncio.CancelledError()

    provider.begin_physx_contact_diagnostics = begin
    monkeypatch.setitem(sys.modules, provider.__name__, provider)
    with pytest.raises(asyncio.CancelledError):
        phase._begin_gripper_contact_diagnostics(None, "/Object/body", ["/Hand/pad"], lambda: "close")


@pytest.mark.parametrize("failure", ["getter", "mapping", "missing_mapping"])
def test_optional_separation_getter_or_mapping_failure_cannot_abort_readable_controlled_state(failure):
    class BrokenMapping:
        def get(self, key):
            raise RuntimeError("diagnostic mapping unavailable")

    def positions(paths):
        if failure == "getter":
            raise RuntimeError("diagnostic pose getter unavailable")
        return BrokenMapping() if failure == "mapping" else None

    robot = SimpleNamespace(dof_count=1, get_joint_positions=lambda: [0.2], get_link_world_positions=positions)
    assert phase._required_grasp_positions(robot, [{"idx": 0}], "open") == [0.2]
    assert phase._measure_finger_separation(robot, SimpleNamespace(tip_link_paths=["/Hand/a", "/Hand/b"])) is None


def test_optional_separation_preserves_cancellation():
    def positions(paths):
        raise asyncio.CancelledError()

    robot = SimpleNamespace(get_link_world_positions=positions)
    with pytest.raises(asyncio.CancelledError):
        phase._measure_finger_separation(robot, SimpleNamespace(tip_link_paths=["/Hand/a", "/Hand/b"]))


@pytest.mark.parametrize("scenario", ["center_overflow", "offset_overflow", "offset_envelope", "spawn_overflow"])
def test_configured_resolved_geometry_rejected_before_native_or_usd_authoring(scenario):
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)
    UsdGeom.Xform.Define(stage, "/Asset/root")
    UsdGeom.Xform.Define(stage, "/Asset/base")
    site = SimpleNamespace(
        forward_axis_world=np.array([1, 0, 0]),
        grip_line_world=[np.zeros(3), np.array([0, -1, 0])],
        grasp_center_world_initial=lambda: np.zeros(3),
    )
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(RuntimeError, match="configured hand geometry setup"):
        if scenario == "center_overflow":
            phase._authored_hand_orientation(
                stage, "/Asset/base", site, pivot_path="/Asset/root", center_base_m=[1e308, 0.0, 0.0]
            )
        else:
            controls = {"object_offset_world_xy_m": [1e308 if scenario == "offset_overflow" else 1e20, 0.0]}
            config = phase.get_defaults()
            if scenario == "spawn_overflow":
                controls = {"object_offset_world_xy_m": [0.0, 0.0]}
                config["object_size_fraction"] = 1e308
            phase._validate_hand_trial_placement(stage, controls, np.zeros(3), config, 0.05)
    assert stage.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("scale", [None, True, "0.01", 0, -0.01, float("nan"), float("inf")])
def test_configured_geometry_requires_original_finite_positive_numeric_stage_scale(monkeypatch, scale):
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.CreateInMemory()
    monkeypatch.setattr(UsdGeom, "GetStageMetersPerUnit", lambda stage: scale)
    with pytest.raises(RuntimeError, match="numeric stage length scale"):
        phase._validate_hand_trial_placement(
            stage, {"object_offset_world_xy_m": [0, 0]}, np.zeros(3), phase.get_defaults(), 0.05
        )


def test_repeated_shapes_retain_actual_grasp_joint_and_force_histories(tmp_path):
    from simready.evaluate.runner.test_context import RunContext
    from simready.foundation.tier_core.runtime_tests.motion_observer import MotionObserver

    ctx = RunContext("asset.usd", "asset.usd", str(tmp_path), "motion", "1", "FET", "kit", "1", "session", None)
    expected = []
    for trial_index in range(2):
        for kind, joint_index in (("grasp", None), ("joint", 0), ("contacts", None)):
            name, metadata = phase._gripper_motion_identity("cube", trial_index, kind, joint_index)
            observer = MotionObserver(
                ctx, name, {"value": {"unit": "unknown_native", "source": "host regression"}}, metadata
            )
            assert observer.history is not None
            assert observer.history.metadata["trial_index"] == trial_index
            assert observer.history.metadata["trial_number"] == trial_index + 1
            assert observer.history.metadata["shape"] == "cube"
            observer.sample({"value": 0.0}, time_s=0.0, phase="close")
            observer.finish("shape_trial_completed")
            expected.append(name)
    assert expected == [
        "gripper_cube",
        "gripper_cube_joint_000",
        "gripper_cube_contacts",
        "gripper_cube_trial_002",
        "gripper_cube_joint_000_trial_002",
        "gripper_cube_contacts_trial_002",
    ]
    ctx.finalize_motion_evidence()
    assert all("motion_history_" + name in ctx.metrics for name in expected)
    assert not ctx.failed and not ctx.skipped


def test_pitched_hand_logged_target_uses_resolved_intended_direction():
    from pxr import Gf

    local, world = phase._authored_hand_frames([1, 0, 0], [0, -1, 0], pitch_deg=15.0)
    matrix = world.T @ local
    quaternion = Gf.Matrix3d(*matrix.T.flatten().tolist()).ExtractRotation().GetQuat()
    xyz = quaternion.GetImaginary()
    resolved = phase._intended_approach_direction([quaternion.GetReal(), xyz[0], xyz[1], xyz[2]], [1, 0, 0])
    assert np.allclose(resolved, [np.cos(np.deg2rad(15)), 0, -np.sin(np.deg2rad(15))])


def _discovered_fingertips(kind):
    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
        FingertipSet,
    )

    hand = kind == "independent_fingers"
    return FingertipSet(
        kind=kind,
        tip_link_paths=["/Asset/a", "/Asset/b"],
        mimic_master_dof=None if hand else 0,
        mimic_master_dofs=None if hand else [0, 1],
        mimic_follower_dof=None if hand else 2,
        finger_chains=[[0], [1]] if hand else None,
    )


@pytest.mark.parametrize("kind", ["independent_fingers", "mimic_parallel_jaw"])
@pytest.mark.parametrize("reorder_between_trials", [False, True])
def test_each_trial_resolves_original_names_without_remapping_already_shifted_indices(kind, reorder_between_trials):
    source = _discovered_fingertips(kind)
    original = copy.deepcopy(source)
    identity = phase._capture_gripper_dof_names(source, ["a", "b", "follower"])
    first_trial = None
    for trial in range(2):
        unmerged = ["b", "follower", "a"] if trial and reorder_between_trials else ["a", "b", "follower"]
        before_attachment = phase._resolve_gripper_dof_names(source, identity, unmerged)
        merged = ["rail"] + unmerged
        after_attachment = phase._resolve_gripper_dof_names(source, identity, merged)
        for resolved, names in ((before_attachment, unmerged), (after_attachment, merged)):
            assert resolved is not source
            if kind == "independent_fingers":
                assert [[names[index] for index in chain] for chain in resolved.finger_chains] == [["a"], ["b"]]
                assert len({index for chain in resolved.finger_chains for index in chain}) == 2
            else:
                assert names[resolved.mimic_master_dof] == "a"
                assert [names[index] for index in resolved.mimic_master_dofs] == ["a", "b"]
                assert names[resolved.mimic_follower_dof] == "follower"
        if trial == 0:
            first_trial = after_attachment
            first_trial.tip_link_paths.append("/Asset/selected_runtime_tip")
            first_trial.master_open_closed_positions = {1: (0.0, 1.0)}
        else:
            assert after_attachment is not first_trial
            assert after_attachment.tip_link_paths == original.tip_link_paths
            assert after_attachment.master_open_closed_positions is None
    assert source == original
    assert identity.chains == (("a",), ("b",)) if kind == "independent_fingers" else identity.masters == ("a", "b")


@pytest.mark.parametrize("kind", ["independent_fingers", "mimic_parallel_jaw"])
@pytest.mark.parametrize("current", [["rail", "a", "follower"], ["rail", "a", "b", "a", "follower"]])
def test_missing_or_ambiguous_required_native_name_never_falls_back_to_stale_index(kind, current):
    source = _discovered_fingertips(kind)
    original = copy.deepcopy(source)
    identity = phase._capture_gripper_dof_names(source, ["a", "b", "follower"])
    with pytest.raises(RuntimeError, match="required gripper DOF name.*missing/ambiguous"):
        phase._resolve_gripper_dof_names(source, identity, current)
    assert source == original


@pytest.mark.parametrize("kind", ["independent_fingers", "mimic_parallel_jaw"])
def test_ambiguous_discovered_selected_name_is_rejected_before_attachment(kind):
    with pytest.raises(RuntimeError, match="discovered gripper DOF name is missing/ambiguous"):
        phase._capture_gripper_dof_names(_discovered_fingertips(kind), ["a", "a", "follower"])


def test_hidden_follower_diagnostic_identity_does_not_become_stale_native_index():
    source = _discovered_fingertips("mimic_parallel_jaw")
    identity = phase._capture_gripper_dof_names(source, ["a", "b", "follower"])
    resolved = phase._resolve_gripper_dof_names(source, identity, ["rail", "b", "a"])
    assert resolved.mimic_master_dof == 2 and resolved.mimic_master_dofs == [2, 1]
    assert resolved.mimic_follower_dof is None


def test_production_resolves_stable_names_after_actual_attachment_before_mapping_commands():
    tree = ast.parse(Path(phase.__file__).read_text(encoding="utf-8"))
    run = next(
        node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "run_gripper_close_lift"
    )
    calls = [node for node in ast.walk(run) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    capture = next(node for node in calls if node.func.id == "_capture_gripper_dof_names")
    attach = next(node for node in calls if node.func.id == "attach_carrier")
    resolutions = sorted(node.lineno for node in calls if node.func.id == "_resolve_gripper_dof_names")
    mappings = [
        node.lineno for node in calls if node.func.id in ("_detect_open_closed_positions", "_infer_hand_grasp_specs")
    ]
    assert capture.lineno < resolutions[0] < attach.lineno < resolutions[1] < min(mappings)
