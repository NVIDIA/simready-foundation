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


"""Official Newton drop and stability procedures use held-fixed observations."""

import asyncio
import importlib
import sys
from types import SimpleNamespace

import pytest
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade
from simready.evaluate.core import decorator
from simready.foundation.tier_newton.runtime_tests import engine_guard, runtime_guard
from simready.foundation.tier_newton.runtime_tests.fet003_physics import (
    _ground_trial,
    ground_drop,
    ground_stability,
    physics_checks,
)


def _bounds(z=0.0, x=0.0):
    return SimpleNamespace(min=(x, 0.0, z), max=(x + 1.0, 1.0, z + 1.0))


def _config(**changes):
    result = dict(ground_stability.GROUND_STABILITY_KWARGS["config_defaults"])
    result.update(
        physics_fps=2,
        capture_fps=1,
        penetration_check_seconds=1,
        rest_detection_hold_seconds=2,
        rest_detection_max_seconds=4,
        simulation_seconds=7,
        simulate_after_result_seconds=1,
    )
    result.update(changes)
    return result


class _Context:
    def __init__(self, observations, config=None):
        self.config = config or _config()
        self.observations = observations
        self.index = -1
        self.steps = 0
        self.advances = 0
        self.asset_path = "fixture.usda"
        self.metrics = {}
        self.messages = []
        self.failures = []
        self.captures = []
        self.videos = []
        self.scene = SimpleNamespace(update_camera_follow=lambda: None)

    async def physics_step(self):
        self.index += 1
        self.steps += 1

    async def physics_advance(self):
        self.advances += 1

    def get_asset_bounds(self, *, authored=False):
        return _bounds(0.3) if authored else self.observations[min(self.index, len(self.observations) - 1)]

    async def capture_frame(self, **kwargs):
        self.captures.append(kwargs["label"])
        return "capture-%d.png" % len(self.captures)

    def encode_video(self, *args, **kwargs):
        self.videos.append(kwargs)

    def add_metric(self, name, value, **kwargs):
        self.metrics[name] = value

    def step(self, message):
        self.messages.append(message)

    log = warn = step

    def fail(self, message):
        self.failures.append(message)

    skip = precheck_failure = fail


@pytest.fixture
def no_optional_context(monkeypatch):
    monkeypatch.setattr(_ground_trial, "drop_metadata", lambda *args: {})


@pytest.mark.asyncio
@pytest.mark.parametrize("stable", [False, True])
async def test_held_fixed_trajectory_drop_and_stability_are_independent(no_optional_context, stable):
    rows = [_bounds(x=0.0 if stable else index * 0.1) for index in range(20)]
    drop = _Context(rows)
    stability = _Context(rows)
    drop_state = await _ground_trial.observe_ground(drop, drop.config, _bounds(0.3), "ground_drop")
    rest_state = await _ground_trial.observe_ground(stability, stability.config, _bounds(0.3), "ground_stability")
    _ground_trial.report_ground_result(drop, drop_state, label="ground_drop", require_rest=False)
    _ground_trial.report_ground_result(stability, rest_state, label="ground_stability", require_rest=True)
    assert drop.metrics["ground_drop_passed"] == 1 and not drop.failures
    assert stability.metrics["ground_stability_passed"] == int(stable)
    assert bool(stability.failures) is not stable
    assert stability.steps == drop.steps + int(stable)
    assert stability.advances == drop.advances + int(stable)
    assert set(drop.captures) == {"ground_drop"} and set(stability.captures) == {"ground_stability"}


@pytest.mark.asyncio
@pytest.mark.parametrize("rows", [[_bounds(0.2)] * 20, [_bounds(-0.11)] * 20])
@pytest.mark.parametrize("require_rest", [False, True])
async def test_missing_proximity_or_excessive_overlap_never_passes(no_optional_context, rows, require_rest):
    ctx = _Context(rows)
    label = "ground_stability" if require_rest else "ground_drop"
    state = await _ground_trial.observe_ground(ctx, ctx.config, _bounds(0.3), label)
    _ground_trial.report_ground_result(ctx, state, label=label, require_rest=require_rest)
    assert ctx.metrics[label + "_passed"] == 0 and len(ctx.failures) == 1
    assert "asset-authoring defect" in ctx.failures[0]


@pytest.mark.asyncio
async def test_first_sample_proximity_crossing_is_not_lost(no_optional_context):
    ctx = _Context([_bounds()] * 20)
    state = await _ground_trial.observe_ground(ctx, ctx.config, _bounds(0.3), "ground_stability")
    assert state["touch_frame"] == 0 and state["rest_detected"]
    _ground_trial.report_ground_result(ctx, state, label="ground_stability", require_rest=True)
    assert ctx.metrics["ground_stability_touch_time"] == 0.5


@pytest.mark.asyncio
async def test_flat_midair_window_after_proximity_cannot_certify_ground_stability(no_optional_context):
    rows = [_bounds()] + [_bounds(0.4)] * 20
    drop, rest = _Context(rows), _Context(rows)
    drop_state = await _ground_trial.observe_ground(drop, drop.config, _bounds(0.3), "ground_drop")
    rest_state = await _ground_trial.observe_ground(rest, rest.config, _bounds(0.3), "ground_stability")
    _ground_trial.report_ground_result(drop, drop_state, label="ground_drop", require_rest=False)
    _ground_trial.report_ground_result(rest, rest_state, label="ground_stability", require_rest=True)
    assert drop.metrics["ground_drop_passed"] == 1
    assert rest.metrics["ground_stability_passed"] == 0 and not rest_state["rest_detected"]
    assert "floor-proximity" in rest.failures[0]


@pytest.mark.asyncio
async def test_return_from_midair_requires_full_new_floor_proximity_rest_window(no_optional_context):
    rows = [_bounds()] + [_bounds(0.4)] * 4 + [_bounds()] * 20
    ctx = _Context(rows, _config(rest_detection_max_seconds=8, simulation_seconds=10))
    state = await _ground_trial.observe_ground(ctx, ctx.config, _bounds(0.3), "ground_stability")
    assert state["rest_frame"] == 9
    _ground_trial.report_ground_result(ctx, state, label="ground_stability", require_rest=True)
    assert ctx.metrics["ground_stability_passed"] == 1 and not ctx.failures


@pytest.mark.asyncio
@pytest.mark.parametrize("module", [ground_drop, ground_stability])
async def test_unrepresentable_integer_frame_budget_is_owned_configuration_error(module):
    ctx = _Context([], _config(simulation_seconds=10**308))
    with pytest.raises(RuntimeError, match="finite derived"):
        await (module.run_ground_drop(ctx) if module is ground_drop else module.run_ground_stability(ctx))
    assert not ctx.steps and not ctx.failures


@pytest.mark.asyncio
async def test_midair_history_is_not_part_of_post_proximity_hold(no_optional_context):
    ctx = _Context([_bounds(0.11)] * 5 + [_bounds()] * 20)
    state = await _ground_trial.observe_ground(ctx, ctx.config, _bounds(0.3), "ground_stability")
    assert state["touch_frame"] == 5
    assert state["rest_frame"] >= state["touch_frame"] + 4


@pytest.mark.asyncio
async def test_rest_after_deadline_during_video_tail_cannot_pass(no_optional_context):
    rows = [_bounds(x=index * 0.1) for index in range(9)] + [_bounds(x=0.8)] * 10
    ctx = _Context(rows, _config(simulate_after_result_seconds=3))
    state = await _ground_trial.observe_ground(ctx, ctx.config, _bounds(0.3), "ground_stability")
    assert state["last_frame"] > 8 and not state["rest_detected"]
    _ground_trial.report_ground_result(ctx, state, label="ground_stability", require_rest=True)
    assert ctx.metrics["ground_stability_passed"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("require_rest", [False, True])
async def test_short_overlap_window_is_execution_error_not_pass(no_optional_context, require_rest):
    ctx = _Context([_bounds()] * 20, _config(simulation_seconds=0.5))
    label = "ground_stability" if require_rest else "ground_drop"
    state = await _ground_trial.observe_ground(ctx, ctx.config, _bounds(0.3), label)
    with pytest.raises(RuntimeError, match="overlap window"):
        _ground_trial.report_ground_result(ctx, state, label=label, require_rest=require_rest)
    assert not ctx.failures and label + "_passed" not in ctx.metrics


@pytest.mark.asyncio
async def test_incomplete_rest_deadline_is_execution_error_not_measured_fail(no_optional_context):
    ctx = _Context([_bounds(x=index * 0.1) for index in range(20)], _config(simulation_seconds=2))
    state = await _ground_trial.observe_ground(ctx, ctx.config, _bounds(0.3), "ground_stability")
    with pytest.raises(RuntimeError, match="rest deadline"):
        _ground_trial.report_ground_result(ctx, state, label="ground_stability", require_rest=True)
    assert not ctx.failures


@pytest.mark.parametrize(
    "value",
    [
        None,
        _bounds(float("nan")),
        SimpleNamespace(min=(0, 0), max=(1, 1, 1)),
        SimpleNamespace(min=(2, 0, 0), max=(1, 1, 1)),
        SimpleNamespace(min=(0, 0, 0), max=(0, 0, 0)),
        SimpleNamespace(min=(False, 0, 0), max=(1, 1, 1)),
    ],
)
def test_required_geometry_is_qualified(value):
    with pytest.raises(RuntimeError, match="finite, ordered, nonempty"):
        _ground_trial.qualified_bounds(value)


@pytest.mark.parametrize(
    "key,value",
    [
        ("rest_detection_hold_seconds", 0),
        ("rest_detection_max_seconds", 0.1),
        ("simulation_seconds", 0),
        ("rest_tolerance", float("nan")),
        ("floor_margin", -1),
        ("physics_fps", True),
    ],
)
def test_invalid_stability_configuration_precedes_scene_work(key, value):
    with pytest.raises(RuntimeError):
        _ground_trial.validate_ground_config(_config(**{key: value}), require_rest=True)


def test_drop_retains_explicit_zero_diagnostic_hold_policy():
    _ground_trial.validate_ground_config(_config(rest_detection_hold_seconds=0), require_rest=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["construct", "sample", "record_capture", "finish"])
async def test_optional_motion_failure_does_not_change_verdict_or_stepping(monkeypatch, no_optional_context, fault):
    class BrokenObserver:
        def __init__(self, *args, **kwargs):
            if fault == "construct":
                raise RuntimeError("diagnostic unavailable")

        def __getattr__(self, name):
            def call(*args):
                if name == fault:
                    raise RuntimeError("diagnostic unavailable")

            return call

    monkeypatch.setattr(_ground_trial, "MotionObserver", BrokenObserver)
    ctx = _Context([_bounds()] * 20)
    state = await _ground_trial.observe_ground(ctx, ctx.config, _bounds(0.3), "ground_stability")
    _ground_trial.report_ground_result(ctx, state, label="ground_stability", require_rest=True)
    assert ctx.metrics["ground_stability_passed"] == 1 and ctx.steps == 7


@pytest.mark.asyncio
async def test_stability_plot_uses_only_existing_qualified_samples(monkeypatch, no_optional_context):
    samples = []
    definitions = []

    class Observer:
        def __init__(self, ctx, label, channels, **kwargs):
            definitions.append(channels)

        def sample(self, values, *args):
            samples.append(values)

        def record_capture(self, *args):
            pass

        def finish(self, *args):
            pass

    monkeypatch.setattr(_ground_trial, "MotionObserver", Observer)
    ctx = _Context([_bounds()] * 20)
    await _ground_trial.observe_ground(ctx, ctx.config, _bounds(0.3), "ground_stability")
    assert all(row["center_window_max_distance"] is None for row in samples[:4])
    assert samples[4]["center_window_max_distance"] == 0.0
    assert samples[4]["corner_window_max_variation"] == 0.0
    assert definitions[0]["rest_tolerance"]["source"] == "configured sampled rest tolerance"
    assert ctx.steps == len(samples)


@pytest.mark.parametrize(
    "module,name,version",
    [(ground_drop, "ground_drop_newton", "4.0.2"), (ground_stability, "ground_stability_newton", "3.0.2")],
)
def test_enabled_registration_and_unchanged_local_defaults(monkeypatch, module, name, version):
    monkeypatch.setattr(decorator, "_REGISTRY", [])
    importlib.reload(module)
    definition = decorator.get_registered_tests()[-1]
    assert definition.name == name and definition.version == version
    defaults = definition.config_defaults
    assert (
        defaults["floor_margin"],
        defaults["rest_tolerance"],
        defaults["rest_detection_hold_seconds"],
        defaults["rest_detection_max_seconds"],
    ) == (0.1, 0.02, 2.0, 8.0)


@pytest.mark.asyncio
@pytest.mark.parametrize("module", [ground_drop, ground_stability])
async def test_official_procedure_rejects_wrong_backend_before_fixture_work(monkeypatch, module):
    def mismatch():
        raise RuntimeError("test setup mismatch, not an asset diagnosis")

    monkeypatch.setattr(runtime_guard, "require_newton_backend", mismatch)
    with pytest.raises(RuntimeError, match="setup mismatch"):
        await getattr(module, "test_" + module.__name__.rsplit(".", 1)[1] + "_newton")(SimpleNamespace())


def _fixture(monkeypatch, ctx, *, readiness=True, material_error=None, cleanup_error=None):
    stop_calls = []
    physics = SimpleNamespace(play=lambda: None)

    def stop():
        stop_calls.append(True)
        if cleanup_error is not None:
            raise cleanup_error

    physics.stop = stop
    room = SimpleNamespace(
        auto_size=lambda *args: None,
        set_color=lambda *args: None,
        show_ground=lambda **kwargs: None,
        place_asset_above_ground=lambda **kwargs: None,
    )

    async def prepare():
        return {"status": "ok"}

    async def settle(**kwargs):
        pass

    ctx.floor_controls = []

    def ground_plane(**kwargs):
        ctx.floor_controls.append(kwargs)
        return "/World/GroundPlane"

    ctx.scene = SimpleNamespace(
        asset=object(),
        load_asset=lambda *args, **kwargs: None,
        add_room=lambda: room,
        lighting=SimpleNamespace(add_dome=lambda **kwargs: None),
        add_physics=lambda **kwargs: physics,
        enable_ground_plane=ground_plane,
        setup_camera_follow=lambda: None,
        update_camera_follow=lambda: None,
        prepare_physics=prepare,
    )
    ctx.set_settle_frames = lambda *args: None
    ctx.settle = settle
    monkeypatch.setattr(_ground_trial, "place_with_minimum_clearance", lambda *args, **kwargs: True)
    monkeypatch.setattr(physics_checks, "run_pre_checks", lambda ctx: None)

    def material(*args):
        if material_error is not None:
            raise material_error

    monkeypatch.setattr(_ground_trial, "apply_ground_physics_material", material)
    monkeypatch.setattr(engine_guard, "articulationize_loose_joints", lambda *args: None)
    monkeypatch.setattr(engine_guard, "newton_scene_initialized", lambda: readiness)
    monkeypatch.setitem(
        sys.modules,
        "simready.evaluate_engine_kit.physics_utils",
        SimpleNamespace(cook_skip_message=lambda status: None),
    )
    omni = SimpleNamespace(usd=SimpleNamespace(get_context=lambda: SimpleNamespace(get_stage=lambda: object())))
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.usd", omni.usd)
    return stop_calls


@pytest.mark.asyncio
async def test_required_material_error_stops_physics_and_preserves_original(monkeypatch):
    primary = RuntimeError("ground material unavailable")
    ctx = _Context([_bounds()])
    stops = _fixture(monkeypatch, ctx, material_error=primary, cleanup_error=RuntimeError("stop failed"))
    with pytest.raises(RuntimeError) as caught:
        await _ground_trial.run_ground_trial(ctx, label="ground_stability", require_rest=True)
    assert caught.value is primary and len(stops) == 1
    assert any("stop failed" in note for note in primary.__notes__)


@pytest.mark.asyncio
async def test_newton_readiness_error_never_becomes_asset_fail(monkeypatch):
    ctx = _Context([_bounds()])
    stops = _fixture(monkeypatch, ctx, readiness=False)
    with pytest.raises(engine_guard.NewtonSceneInitializationError):
        await _ground_trial.run_ground_trial(ctx, label="ground_stability", require_rest=True)
    assert len(stops) == 2 and not ctx.failures and ctx.steps == 0


@pytest.mark.asyncio
async def test_cancellation_preserved_through_required_stop_failure(monkeypatch):
    ctx = _Context([_bounds()])
    cancellation = asyncio.CancelledError()
    _fixture(monkeypatch, ctx, material_error=cancellation, cleanup_error=RuntimeError("stop failed"))
    with pytest.raises(asyncio.CancelledError) as caught:
        await _ground_trial.run_ground_trial(ctx, label="ground_stability", require_rest=True)
    assert caught.value is cancellation


def test_typed_verified_ground_material_keeps_friction_policy(monkeypatch):
    stage = Usd.Stage.CreateInMemory()
    ground = UsdGeom.Mesh.Define(stage, "/World/GroundPlane/CollisionMesh").GetPrim()
    UsdPhysics.CollisionAPI.Apply(ground)
    omni = SimpleNamespace(usd=SimpleNamespace(get_context=lambda: SimpleNamespace(get_stage=lambda: stage)))
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.usd", omni.usd)
    _ground_trial.apply_ground_physics_material()
    material, _ = UsdShade.MaterialBindingAPI(ground).ComputeBoundMaterial(materialPurpose="physics")
    assert material and material.GetPrim().GetTypeName() == "Material"
    physics = UsdPhysics.MaterialAPI(material.GetPrim())
    assert physics.GetStaticFrictionAttr().Get() == pytest.approx(0.5)
    assert physics.GetDynamicFrictionAttr().Get() == pytest.approx(0.4)
    assert physics.GetRestitutionAttr().Get() == 0.0


@pytest.mark.parametrize("collision", ["missing", "disabled", "blocked"])
def test_unqualified_ground_collision_is_execution_error(monkeypatch, collision):
    stage = Usd.Stage.CreateInMemory()
    ground = UsdGeom.Mesh.Define(stage, "/World/GroundPlane/CollisionMesh").GetPrim()
    if collision == "disabled":
        UsdPhysics.CollisionAPI.Apply(ground).CreateCollisionEnabledAttr(False)
    elif collision == "blocked":
        UsdPhysics.CollisionAPI.Apply(ground).CreateCollisionEnabledAttr().Block()
    omni = SimpleNamespace(usd=SimpleNamespace(get_context=lambda: SimpleNamespace(get_stage=lambda: stage)))
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.usd", omni.usd)
    with pytest.raises(RuntimeError, match="collision"):
        _ground_trial.apply_ground_physics_material()


@pytest.mark.asyncio
async def test_required_final_stop_failure_prevents_a_successful_public_result(monkeypatch, no_optional_context):
    ctx = _Context([_bounds()] * 20)
    _fixture(monkeypatch, ctx)
    cleanup_receipts = []
    ctx._engine_session = SimpleNamespace(record_required_cleanup_failure=cleanup_receipts.append)
    handle = ctx.scene.add_physics()
    stop_count = 0

    def stop():
        nonlocal stop_count
        stop_count += 1
        if stop_count == 2:
            raise RuntimeError("final required stop failed")

    handle.stop = stop
    with pytest.raises(RuntimeError, match="final required stop failed"):
        await ground_stability.run_ground_stability(ctx)
    assert cleanup_receipts == ["Ground fixture physics stop failed"]
    assert "ground_stability_passed" not in ctx.metrics and not ctx.failures


@pytest.mark.asyncio
async def test_required_live_geometry_error_is_not_converted_into_asset_failure(monkeypatch, no_optional_context):
    ctx = _Context([_bounds(float("nan"))])
    stops = _fixture(monkeypatch, ctx)
    with pytest.raises(RuntimeError, match="finite, ordered, nonempty"):
        await ground_drop.run_ground_drop(ctx)
    assert len(stops) == 2 and not ctx.failures


def test_finite_bounds_with_overflowing_center_are_unqualified():
    bounds = SimpleNamespace(min=(1e308, 0, 0), max=(1.5e308, 1, 1))
    with pytest.raises(RuntimeError, match="finite, ordered, nonempty"):
        _ground_trial.qualified_bounds(bounds)


def test_finite_config_with_overflowing_derived_gate_is_unqualified():
    with pytest.raises(RuntimeError, match="finite derived"):
        _ground_trial.validate_ground_config(_config(floor_level=1e308, floor_margin=1e308), require_rest=True)


@pytest.mark.asyncio
async def test_two_second_rest_needs_two_seconds_of_observed_intervals(no_optional_context):
    ctx = _Context(
        [_bounds()] * 20,
        _config(
            physics_fps=1,
            capture_fps=1,
            penetration_check_seconds=0,
            rest_detection_max_seconds=2,
            simulate_after_result_seconds=0,
        ),
    )
    state = await _ground_trial.observe_ground(ctx, ctx.config, _bounds(0.3), "ground_stability")
    assert state["rest_frame"] == state["touch_frame"] + 2
    assert ctx.steps == 3
    _ground_trial.report_ground_result(ctx, state, label="ground_stability", require_rest=True)
    assert ctx.metrics["ground_stability_passed"] == 1


@pytest.mark.asyncio
async def test_optional_video_encode_failure_keeps_public_stability_verdict(monkeypatch, no_optional_context):
    ctx = _Context([_bounds()] * 20)
    _fixture(monkeypatch, ctx)

    def encode(*args, **kwargs):
        raise RuntimeError("optional video encoder failed")

    ctx.encode_video = encode
    await ground_stability.run_ground_stability(ctx)
    assert ctx.metrics["ground_stability_passed"] == 1 and not ctx.failures
    assert any("could not be encoded" in message for message in ctx.messages)


@pytest.mark.asyncio
async def test_nonzero_floor_level_is_authored_into_collision_fixture(monkeypatch, no_optional_context):
    ctx = _Context([_bounds(-2.0)] * 20, _config(floor_level=-2.0))
    _fixture(monkeypatch, ctx)
    await ground_drop.run_ground_drop(ctx)
    assert ctx.floor_controls == [{"friction": 0.5, "position": (0.0, 0.0, -2.0)}]


@pytest.mark.asyncio
async def test_missing_optional_capture_does_not_send_fabricated_frame_to_encoder(monkeypatch, no_optional_context):
    ctx = _Context([_bounds()] * 20)
    _fixture(monkeypatch, ctx)

    async def capture(**kwargs):
        return None

    ctx.capture_frame = capture
    await ground_stability.run_ground_stability(ctx)
    assert ctx.metrics["ground_stability_passed"] == 1 and not ctx.videos


@pytest.mark.parametrize(
    "changes",
    [
        {"penetration_check_seconds": 1e308, "physics_fps": 2},
        {"simulate_after_result_seconds": 1e308, "physics_fps": 2},
        {"rest_tolerance": 1e200},
        {"floor_level": 6e307, "floor_margin": 6e307, "minimum_drop_distance": 6e307},
    ],
)
@pytest.mark.parametrize("require_rest", [False, True])
def test_every_overflowing_derived_ground_control_is_rejected_before_mutation(changes, require_rest):
    with pytest.raises(RuntimeError, match="finite derived"):
        _ground_trial.validate_ground_config(_config(**changes), require_rest=require_rest)


def test_required_stop_cleanup_uses_newton_owned_helpers_without_new_core_symbols(monkeypatch):
    monkeypatch.setitem(sys.modules, "simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils", None)
    receipts = []
    ctx = SimpleNamespace(_engine_session=SimpleNamespace(record_required_cleanup_failure=receipts.append))
    primary = RuntimeError("required observation failed")

    def stop():
        raise RuntimeError("required cleanup failed")

    _ground_trial.stop_physics(SimpleNamespace(stop=stop), ctx, primary)
    assert receipts == ["Ground fixture physics stop failed"]
    assert any("required cleanup failed" in note for note in primary.__notes__)
