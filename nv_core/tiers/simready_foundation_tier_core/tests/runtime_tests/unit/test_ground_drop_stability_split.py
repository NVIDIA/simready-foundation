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


"""Official PhysX entry points keep independent, qualified drop/rest verdicts."""

import asyncio
from types import SimpleNamespace

import pytest
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade
from simready.foundation.tier_core.runtime_tests import engine_guard
from simready.foundation.tier_core.runtime_tests.fet003_physics import (
    _ground_trial,
    ground_drop,
    ground_stability,
    physics_checks,
)

_REAL_APPLY_GROUND_MATERIAL = _ground_trial.apply_ground_physics_material


def _bounds(z=0.05, x=0.0):
    return SimpleNamespace(min=(x, 0.0, z), max=(x + 0.1, 0.1, z + 0.1))


class _Context:
    def __init__(self, observations, *, config=None, stop_error=None, stop_result=None):
        self.config = dict(ground_drop.GROUND_DROP_KWARGS["config_defaults"])
        self.config.update({"physics_fps": 10, "capture_fps": 2})
        if config:
            self.config.update(config)
        self.asset_path = "asset.usda"
        self.observations = iter([_bounds(0.3), *observations])
        self.metrics = {}
        self.messages = []
        self.failures = []
        self.warnings = []
        self.events = []
        self.stop_error = stop_error
        self.stop_result = stop_result
        room = SimpleNamespace(
            auto_size=lambda asset: None,
            set_color=lambda *args: None,
            show_ground=lambda **kwargs: None,
            place_asset_above_ground=lambda **kwargs: self.events.append(("placement", kwargs)),
        )
        physics = SimpleNamespace(play=lambda: self.events.append("play"), stop=self.stop)
        self.scene = SimpleNamespace(
            asset=object(),
            load_asset=lambda *args, **kwargs: self.events.append("load"),
            add_room=lambda: room,
            lighting=SimpleNamespace(add_dome=lambda **kwargs: None),
            add_physics=lambda **kwargs: physics,
            enable_ground_plane=lambda **kwargs: "/World/GroundPlane",
            setup_camera_follow=lambda: None,
            update_camera_follow=lambda: None,
            prepare_physics=self.prepare_physics,
        )

    def stop(self):
        self.events.append("stop")
        if self.stop_error:
            raise self.stop_error
        return self.stop_result

    async def prepare_physics(self):
        return {}

    def set_settle_frames(self, value):
        self.events.append("set_settle")

    async def settle(self, count):
        pass

    async def physics_step(self):
        self.events.append("step")

    async def physics_advance(self):
        self.events.append("advance")

    async def capture_frame(self, label):
        self.events.append(("capture", label))
        return "captured.png"

    def encode_video(self, frames, **kwargs):
        self.events.append(("video", kwargs["label"]))

    def get_asset_bounds(self, authored=False):
        return next(self.observations)

    def step(self, text):
        self.messages.append(text)

    def log(self, text):
        self.messages.append(text)

    def warn(self, text):
        self.warnings.append(text)

    def fail(self, text):
        self.failures.append(text)

    def skip(self, text):
        self.events.append(("skip", text))

    def precheck_failure(self, text):
        self.events.append(("precheck", text))

    def add_metric(self, name, value, unit=None):
        self.metrics[name] = value


@pytest.fixture(autouse=True)
def _qualified_fixture(monkeypatch):
    from simready.evaluate_engine_kit import physics_utils

    monkeypatch.setattr(engine_guard, "require_physx_test_engine", lambda: None)
    monkeypatch.setattr(physics_checks, "run_pre_checks", lambda ctx: None)
    monkeypatch.setattr(physics_utils, "cook_skip_message", lambda status: None)
    monkeypatch.setattr(_ground_trial, "apply_ground_physics_material", lambda path: None)


def _observations(*, moving=False):
    return [_bounds(0.2)] + [_bounds(x=index * 0.03 if moving else 0.0) for index in range(110)]


@pytest.mark.asyncio
@pytest.mark.parametrize("moving", [False, True])
async def test_independent_official_drop_and_rest_verdicts(moving):
    drop_ctx, rest_ctx = _Context(_observations(moving=moving)), _Context(_observations(moving=moving))
    await ground_drop.run_ground_drop(drop_ctx)
    await ground_stability.run_ground_stability(rest_ctx)
    assert drop_ctx.metrics["ground_drop_passed"] == 1
    assert not drop_ctx.failures
    assert rest_ctx.metrics["ground_stability_passed"] == (0 if moving else 1)
    assert bool(rest_ctx.failures) == moving
    # Stability covers the full requested elapsed hold, one extra interval
    # beyond the preserved legacy drop diagnostic sample count.
    assert rest_ctx.events.count("step") - drop_ctx.events.count("step") == (0 if moving else 1)
    assert drop_ctx.events[-1] == rest_ctx.events[-1] == "stop"


@pytest.mark.asyncio
@pytest.mark.parametrize("procedure", [ground_drop.run_ground_drop, ground_stability.run_ground_stability])
@pytest.mark.parametrize("reason", ["no_proximity", "overlap"])
async def test_measured_prerequisite_breaches_remain_failures(procedure, reason):
    observations = [_bounds(0.2)] * 110 if reason == "no_proximity" else [_bounds(0.2), _bounds(-0.2)] * 60
    ctx = _Context(observations)
    await procedure(ctx)
    assert len(ctx.failures) == 1
    assert ("proximity" if reason == "no_proximity" else "overlap") in ctx.failures[0]
    assert ctx.events[-1] == "stop"


@pytest.mark.asyncio
@pytest.mark.parametrize("procedure", [ground_drop.run_ground_drop, ground_stability.run_ground_stability])
@pytest.mark.parametrize(
    "bad",
    [
        None,
        SimpleNamespace(min=(0, 0), max=(1, 1, 1)),
        SimpleNamespace(min=(0, 0, float("nan")), max=(1, 1, 1)),
        SimpleNamespace(min=(0, 0, 0), max=(1, 1, float("inf"))),
        SimpleNamespace(min=(False, 0, 0), max=(1, 1, 1)),
        SimpleNamespace(min=(2, 0, 0), max=(1, 1, 1)),
        SimpleNamespace(min=(0, 0, 0), max=(0, 0, 0)),
    ],
)
async def test_missing_or_invalid_required_observations_are_errors(procedure, bad):
    ctx = _Context([bad])
    with pytest.raises(RuntimeError, match="required live bounding-box"):
        await procedure(ctx)
    assert not ctx.failures
    assert ctx.events[-1] == "stop"
    assert not any(name.endswith("_passed") for name in ctx.metrics)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config",
    [
        {"rest_detection_hold_seconds": 0},
        {"rest_detection_hold_seconds": -0.1},
        {"rest_detection_max_seconds": 0.1},
        {"simulation_seconds": 0.1},
        {"floor_margin": float("nan")},
        {"physics_fps": True},
    ],
)
async def test_stability_rejects_bad_or_impossible_configuration_before_scene_mutation(config):
    ctx = _Context(_observations(), config=config)
    with pytest.raises(RuntimeError, match="invalid configuration"):
        await ground_stability.run_ground_stability(ctx)
    assert not ctx.events and not ctx.failures


@pytest.mark.asyncio
@pytest.mark.parametrize("procedure", [ground_drop.run_ground_drop, ground_stability.run_ground_stability])
async def test_initial_clearance_is_a_required_fixture_condition(procedure):
    ctx = _Context(_observations())
    ctx.observations = iter([_bounds(0.05)])
    with pytest.raises(RuntimeError, match="initial proximity clearance"):
        await procedure(ctx)
    assert not ctx.failures and ctx.events[-1] == "stop"


@pytest.mark.asyncio
async def test_short_overlap_coverage_is_not_a_new_drop_pass():
    ctx = _Context(_observations(), config={"simulation_seconds": 0.3})
    with pytest.raises(RuntimeError, match="overlap observation window"):
        await ground_drop.run_ground_drop(ctx)
    assert not ctx.failures and "ground_drop_passed" not in ctx.metrics


@pytest.mark.asyncio
async def test_short_unsettled_coverage_is_not_a_stability_deadline_failure():
    ctx = _Context(_observations(moving=True), config={"simulation_seconds": 3})
    with pytest.raises(RuntimeError, match="stability deadline"):
        await ground_stability.run_ground_stability(ctx)
    assert not ctx.failures and "ground_stability_passed" not in ctx.metrics


def test_rest_cannot_use_pre_proximity_samples_or_tail_samples():
    config = dict(ground_drop.GROUND_DROP_KWARGS["config_defaults"])
    config.update({"physics_fps": 10, "rest_detection_hold_seconds": 2, "rest_detection_max_seconds": 2})
    result = _ground_trial.GroundTrial(config, _ground_trial.qualified_bounds_entry(_bounds(0.3)), stability=True)
    for frame in range(30):
        result.observe(frame, _ground_trial.qualified_bounds_entry(_bounds(0.2)))
    assert not result.touched and not result.rest_detected
    result.observe(30, _ground_trial.qualified_bounds_entry(_bounds()))
    assert len(result.contact_history) == 1 and not result.rest_detected
    # No full rest window can qualify before the deadline. A long video tail
    # eventually contains flat observations, but cannot reverse the deadline.
    for frame in range(31, 52):
        result.observe(frame, _ground_trial.qualified_bounds_entry(_bounds(x=frame * 0.03)))
    for frame in range(52, 80):
        result.observe(frame, _ground_trial.qualified_bounds_entry(_bounds(x=1.53)))
    assert result.rest_deadline_complete and not result.rest_detected


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["begin", "sample", "finish", "capture_annotation", "encode"])
@pytest.mark.parametrize("moving", [False, True])
async def test_optional_evidence_failures_do_not_change_measured_verdict(monkeypatch, failure, moving):
    from simready.foundation.tier_core.runtime_tests import motion_observer

    class BrokenEvidence:
        def __init__(self, *args, **kwargs):
            if failure == "begin":
                raise RuntimeError("optional begin failed")

        def sample(self, *args):
            if failure == "sample":
                raise RuntimeError("optional sample failed")

        def record_capture(self, *args):
            if failure == "capture_annotation":
                raise RuntimeError("optional annotation failed")

        def finish(self, *args):
            if failure == "finish":
                raise RuntimeError("optional finish failed")

    monkeypatch.setattr(motion_observer, "MotionObserver", BrokenEvidence)
    ctx = _Context(_observations(moving=moving))
    if failure == "encode":

        def encode_failure(*args, **kwargs):
            raise RuntimeError("optional encode failed")

        ctx.encode_video = encode_failure
    await ground_stability.run_ground_stability(ctx)
    assert ctx.metrics["ground_stability_passed"] == (0 if moving else 1)
    assert bool(ctx.failures) == moving and ctx.warnings
    assert ctx.events[-1] == "stop"


@pytest.mark.asyncio
@pytest.mark.parametrize("procedure", [ground_drop.run_ground_drop, ground_stability.run_ground_stability])
async def test_wrong_backend_fails_before_context_access(monkeypatch, procedure):
    def mismatch():
        raise engine_guard.PhysicsTestEngineMismatchError("setup mismatch")

    monkeypatch.setattr(engine_guard, "require_physx_test_engine", mismatch)
    with pytest.raises(engine_guard.PhysicsTestEngineMismatchError, match="setup mismatch"):
        await procedure(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("procedure", [ground_drop.run_ground_drop, ground_stability.run_ground_stability])
async def test_required_cleanup_failure_cannot_return_a_pass(procedure):
    ctx = _Context(_observations(), stop_error=RuntimeError("required stop failed"))
    with pytest.raises(RuntimeError, match="required stop failed"):
        await procedure(ctx)
    assert not ctx.failures and not any(name.endswith("_passed") for name in ctx.metrics)


@pytest.mark.asyncio
@pytest.mark.parametrize("primary", [RuntimeError("required step failed"), asyncio.CancelledError("cancelled")])
async def test_first_execution_failure_or_cancellation_survives_failed_cleanup(primary):
    ctx = _Context(_observations(), stop_error=RuntimeError("required stop failed"))

    async def broken_step():
        raise primary

    ctx.physics_step = broken_step
    with pytest.raises(type(primary)) as caught:
        await ground_stability.run_ground_stability(ctx)
    assert caught.value is primary
    assert not ctx.failures and ctx.events[-1] == "stop"
    assert any("cleanup also failed" in text for text in primary.__notes__)


@pytest.mark.asyncio
@pytest.mark.parametrize("procedure", [ground_drop.run_ground_drop, ground_stability.run_ground_stability])
async def test_rejected_physics_stop_records_required_worker_retirement(procedure):
    ctx = _Context(_observations(), stop_result=False)
    receipts = []
    ctx._engine_session = SimpleNamespace(record_required_cleanup_failure=receipts.append)
    with pytest.raises(RuntimeError, match="physics stop was rejected"):
        await procedure(ctx)
    assert receipts == ["FET003 required ground physics cleanup failed"]
    assert not ctx.failures and not any(name.endswith("_passed") for name in ctx.metrics)


def test_optional_window_plot_values_require_complete_post_proximity_history():
    config = dict(ground_drop.GROUND_DROP_KWARGS["config_defaults"])
    config.update({"physics_fps": 10, "rest_detection_hold_seconds": 0.2})
    result = _ground_trial.GroundTrial(config, _ground_trial.qualified_bounds_entry(_bounds(0.3)), stability=True)
    result.observe(0, _ground_trial.qualified_bounds_entry(_bounds()))
    assert _ground_trial._window_measurements(result) == (None, None)
    result.observe(1, _ground_trial.qualified_bounds_entry(_bounds(x=0.03)))
    assert _ground_trial._window_measurements(result) == (None, None)
    result.observe(2, _ground_trial.qualified_bounds_entry(_bounds(x=0.03)))
    center, corners = _ground_trial._window_measurements(result)
    assert center == pytest.approx(0.03) and corners == pytest.approx(0.03)


def test_ground_material_is_typed_bound_and_coefficients_unchanged():
    stage = Usd.Stage.CreateInMemory()
    collider = UsdGeom.Mesh.Define(stage, "/World/GroundPlane/CollisionMesh").GetPrim()
    UsdPhysics.CollisionAPI.Apply(collider)
    _REAL_APPLY_GROUND_MATERIAL("/World/GroundPlane", stage=stage)
    material, _ = UsdShade.MaterialBindingAPI(collider).ComputeBoundMaterial("physics")
    assert material and material.GetPrim().IsA(UsdShade.Material)
    physics = UsdPhysics.MaterialAPI(material.GetPrim())
    assert physics.GetStaticFrictionAttr().Get() == pytest.approx(0.5)
    assert physics.GetDynamicFrictionAttr().Get() == pytest.approx(0.4)
    assert physics.GetRestitutionAttr().Get() == pytest.approx(0.0)


def test_missing_ground_collision_api_is_a_setup_error():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Mesh.Define(stage, "/World/GroundPlane/CollisionMesh")
    with pytest.raises(RuntimeError, match="collision mesh/API"):
        _REAL_APPLY_GROUND_MATERIAL("/World/GroundPlane", stage=stage)


def test_disabled_ground_collision_is_a_setup_error():
    stage = Usd.Stage.CreateInMemory()
    collider = UsdGeom.Mesh.Define(stage, "/World/GroundPlane/CollisionMesh").GetPrim()
    UsdPhysics.CollisionAPI.Apply(collider).CreateCollisionEnabledAttr(False)
    with pytest.raises(RuntimeError, match="not enabled"):
        _REAL_APPLY_GROUND_MATERIAL("/World/GroundPlane", stage=stage)


@pytest.mark.asyncio
@pytest.mark.parametrize("procedure", [ground_drop.run_ground_drop, ground_stability.run_ground_stability])
async def test_authored_placement_then_pumped_live_observations(procedure):
    ctx = _Context(_observations())
    original_bounds = ctx.get_asset_bounds
    calls = []

    def guarded_bounds(authored=False):
        calls.append(authored)
        if not authored and "step" not in ctx.events:
            raise RuntimeError("live bounds unavailable before pumped physics")
        return original_bounds(authored=authored)

    ctx.get_asset_bounds = guarded_bounds
    await procedure(ctx)
    assert calls[0] is True and all(value is False for value in calls[1:])
    assert not ctx.failures and ctx.events[-1] == "stop"


def test_standalone_two_second_hold_requires_two_elapsed_seconds_at_one_hz():
    config = dict(ground_stability.GROUND_STABILITY_KWARGS["config_defaults"])
    config.update({"physics_fps": 1, "capture_fps": 1})
    result = _ground_trial.GroundTrial(config, _ground_trial.qualified_bounds_entry(_bounds(0.3)), stability=True)
    result.observe(0, _ground_trial.qualified_bounds_entry(_bounds()))
    result.observe(1, _ground_trial.qualified_bounds_entry(_bounds()))
    assert len(result.contact_history) == 2 and not result.rest_detected
    result.observe(2, _ground_trial.qualified_bounds_entry(_bounds()))
    assert result.rest_detected and result.rest_frame == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "procedure,prefix,rest_time",
    [
        (ground_drop.run_ground_drop, "ground_drop", 2.0),
        (ground_stability.run_ground_stability, "ground_stability", 2.1),
    ],
)
async def test_summary_times_match_recorded_observation_clock(procedure, prefix, rest_time):
    ctx = _Context([_bounds()] * 110)
    await procedure(ctx)
    assert ctx.metrics[prefix + "_touch_time"] == pytest.approx(0.1)
    assert ctx.metrics[prefix + "_rest_time"] == pytest.approx(rest_time)


@pytest.mark.asyncio
@pytest.mark.parametrize("procedure", [ground_drop.run_ground_drop, ground_stability.run_ground_stability])
@pytest.mark.parametrize(
    "config",
    [
        {"floor_level": 1e308, "floor_margin": 1e308},
        {"floor_level": -1e308, "floor_margin": 1e308},
        {"floor_level": 1e308, "minimum_drop_distance": 1e308},
        {"simulation_seconds": 1e308},
        {"penetration_check_seconds": 1e308},
        {"rest_detection_hold_seconds": 1e308},
        {"rest_detection_max_seconds": 1e308},
        {"simulate_after_result_seconds": 1e308},
        {"rest_tolerance": 1e308},
    ],
)
async def test_nonfinite_derived_gates_and_budgets_error_before_mutation(procedure, config):
    ctx = _Context(_observations(), config=config)
    with pytest.raises(RuntimeError, match="nonfinite derived"):
        await procedure(ctx)
    assert not ctx.events and not ctx.failures


@pytest.mark.asyncio
async def test_flat_midair_window_after_proximity_cannot_certify_ground_stability():
    rows = [_bounds(0.2), _bounds()] + [_bounds(0.4)] * 110
    drop, stability = _Context(rows), _Context(rows)
    await ground_drop.run_ground_drop(drop)
    await ground_stability.run_ground_stability(stability)
    assert drop.metrics["ground_drop_passed"] == 1
    assert stability.metrics["ground_stability_passed"] == 0
    assert stability.metrics["ground_stability_rest_detected"] == 0
    assert "floor-proximity" in stability.failures[0]


@pytest.mark.asyncio
async def test_return_from_midair_requires_full_new_floor_proximity_rest_window():
    rows = [_bounds(0.2), _bounds()] + [_bounds(0.4)] * 25 + [_bounds()] * 110
    ctx = _Context(rows)
    await ground_stability.run_ground_stability(ctx)
    assert ctx.metrics["ground_stability_passed"] == 1
    assert ctx.metrics["ground_stability_rest_time"] == pytest.approx(4.8)
    assert not ctx.failures


@pytest.mark.asyncio
@pytest.mark.parametrize("procedure", [ground_drop.run_ground_drop, ground_stability.run_ground_stability])
async def test_unrepresentable_integer_frame_budget_is_owned_configuration_error(procedure):
    ctx = _Context(_observations(), config={"simulation_seconds": 10**308})
    with pytest.raises(RuntimeError, match="nonfinite derived"):
        await procedure(ctx)
    assert not ctx.events and not ctx.failures
