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

"""Required-stop barriers and optional native carrier-trace isolation."""

import asyncio
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("pxr")
from pxr import Usd, UsdGeom, UsdPhysics  # noqa: E402
from simready.foundation.tier_core.runtime_tests.articulation_phases import (  # noqa: E402
    gripper_carrier as carrier,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import (  # noqa: E402
    RobotHandle,
)


def _rig():
    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/World/Gripper").GetPrim()
    base = UsdGeom.Xform.Define(stage, "/World/Gripper/base").GetPrim()
    finger = UsdGeom.Xform.Define(stage, "/World/Gripper/finger").GetPrim()
    for body in (base, finger):
        UsdPhysics.RigidBodyAPI.Apply(body)
    pin = UsdPhysics.FixedJoint.Define(stage, "/World/Gripper/joints/world_pin")
    pin.CreateBody1Rel().SetTargets([base.GetPath()])
    UsdPhysics.ArticulationRootAPI.Apply(pin.GetPrim())
    slider = UsdPhysics.PrismaticJoint.Define(stage, "/World/Gripper/joints/finger_slider")
    slider.CreateBody0Rel().SetTargets([base.GetPath()])
    slider.CreateBody1Rel().SetTargets([finger.GetPath()])
    actions = []

    async def initialize(ctx):
        actions.append("initialize")

    articulation = SimpleNamespace(
        get_world_pose=lambda: (np.zeros(3), np.array([1.0, 0.0, 0.0, 0.0])),
        get_joint_positions=lambda: np.zeros(1),
        set_default_state=lambda **kwargs: actions.append("set_default_state"),
        set_joints_default_state=lambda **kwargs: actions.append("set_joints_default_state"),
    )
    robot = SimpleNamespace(
        prim_path=str(pin.GetPath()), asset_prim=asset, articulation=articulation, initialize=initialize
    )
    return SimpleNamespace(stage=stage, base=base, pin=pin, robot=robot, actions=actions)


class _FailingStop:
    """Stop fails before the timeline state changes, unlike mutate-then-fail."""

    def __init__(self, playing=True):
        self.playing = playing
        self.failures = []
        self.plays = 0

    def is_playing(self):
        return self.playing

    def stop(self):
        error = RuntimeError("native timeline refuses to stop")
        self.failures.append(error)
        raise error

    def play(self):
        self.plays += 1
        self.playing = True


def _stage_snapshot(stage):
    return stage.GetRootLayer().ExportToString(), stage.GetSessionLayer().ExportToString()


def _partial_state(rig):
    root_path = "/World/_FET028_Gantry_partial"
    UsdGeom.Xform.Define(rig.stage, root_path)
    rig.pin.GetPrim().SetActive(False)
    return {
        "root_path": root_path,
        "physics_stopped": True,
        "physics_was_playing": True,
        "root_orientation_state": None,
        "articulation_default_state": (np.ones(3), None),
        "joint_default_state": (np.ones(1), None, None),
        "world_pin_paths": (str(rig.pin.GetPath()),),
    }


@pytest.mark.parametrize("initially_playing", [False, True])
def test_rollback_stop_failure_is_a_hard_barrier_to_all_restoration(monkeypatch, initially_playing):
    rig = _rig()
    state = _partial_state(rig)
    before = _stage_snapshot(rig.stage)
    physics = _FailingStop(initially_playing)
    restoration_attempts = []
    for name in (
        "_remove_existing_gantry",
        "_restore_root_orientation",
        "_restore_carrier_root_transfer",
        "_restore_default_state",
        "_restore_joint_default_state",
        "_require_world_pin_restore",
        "_cleanup_carrier_opinions",
    ):
        monkeypatch.setattr(carrier, name, lambda *args, operation=name: restoration_attempts.append(operation))

    errors = asyncio.run(carrier._rollback_partial_carrier(rig.stage, rig.robot, physics, state))

    assert len(errors) == 1
    assert "could not stop physics" in str(errors[0])
    assert errors[0].__cause__ is physics.failures[0]
    assert restoration_attempts == []
    assert rig.actions == []
    assert physics.plays == 0
    assert physics.playing is initially_playing
    assert _stage_snapshot(rig.stage) == before


@pytest.mark.parametrize("initially_playing", [False, True])
def test_real_attach_preserves_initial_stop_failure_without_rebinding(initially_playing):
    rig = _rig()
    before = _stage_snapshot(rig.stage)
    physics = _FailingStop(initially_playing)

    with pytest.raises(RuntimeError, match="native timeline refuses to stop") as caught:
        asyncio.run(carrier.attach_carrier(rig.stage, {"physics": physics}, rig.robot, str(rig.base.GetPath())))

    assert caught.value is physics.failures[0]
    assert len(physics.failures) == 2  # Initial attempt and one safe rollback retry.
    assert any("could not stop physics" in note for note in caught.value.__notes__)
    assert rig.actions == []
    assert physics.plays == 0
    assert physics.playing is initially_playing
    assert _stage_snapshot(rig.stage) == before


@pytest.mark.parametrize("cancelled", [False, True])
@pytest.mark.parametrize("broken_warning", [None, RuntimeError, asyncio.CancelledError])
def test_partial_attachment_preserves_primary_cause_and_cancellation(monkeypatch, cancelled, broken_warning):
    rig = _rig()
    physics = _FailingStop()
    primary = asyncio.CancelledError("attachment cancelled") if cancelled else RuntimeError("build failed")
    snapshot = []
    warnings = []

    async def failed_attach(stage, scene_info, robot, base, setup_state, **kwargs):
        setup_state.update(_partial_state(rig))
        snapshot.append(_stage_snapshot(stage))
        raise primary

    def warn(message):
        warnings.append(message)
        if broken_warning is not None:
            raise broken_warning("warning sink unavailable")

    monkeypatch.setattr(carrier, "_attach_carrier_impl", failed_attach)
    with pytest.raises(type(primary)) as caught:
        asyncio.run(
            carrier.attach_carrier(
                rig.stage, {"physics": physics}, rig.robot, str(rig.base.GetPath()), ctx=SimpleNamespace(warn=warn)
            )
        )

    assert caught.value is primary
    assert any("could not stop physics" in note for note in primary.__notes__)
    assert warnings and "could not stop physics" in warnings[0]
    assert _stage_snapshot(rig.stage) == snapshot[0]
    assert rig.actions == []
    assert physics.plays == 0


@pytest.mark.parametrize("broken_warning", [False, True])
def test_detach_reports_stop_failure_without_mutating_the_running_stage(broken_warning):
    rig = _rig()
    state = _partial_state(rig)
    physics = _FailingStop()
    before = _stage_snapshot(rig.stage)
    handle = carrier.CarrierHandle(
        robot=rig.robot,
        gripper_base_path=str(rig.base.GetPath()),
        physics=physics,
        initial_target_z=0.0,
        world_pin_was_present=True,
        root_path=state["root_path"],
        world_pin_paths=state["world_pin_paths"],
    )

    def warn(message):
        if broken_warning:
            raise RuntimeError("warning sink unavailable")

    with pytest.raises(RuntimeError, match="detach restoration failed.*could not stop physics") as caught:
        asyncio.run(carrier.detach_carrier(rig.stage, handle, ctx=SimpleNamespace(warn=warn)))

    assert caught.value.__cause__.__cause__ is physics.failures[0]
    assert physics.plays == 0
    assert physics.playing
    assert rig.actions == []
    assert _stage_snapshot(rig.stage) == before


@pytest.mark.parametrize("operation", ["rollback", "detach"])
def test_stop_cancellation_cannot_mutate_or_restart_the_running_stage(operation):
    rig = _rig()
    state = _partial_state(rig)
    physics = _FailingStop()
    before = _stage_snapshot(rig.stage)

    def cancelled_stop():
        raise asyncio.CancelledError("native stop cancelled")

    physics.stop = cancelled_stop
    if operation == "rollback":
        pending = carrier._rollback_partial_carrier(rig.stage, rig.robot, physics, state)
    else:
        handle = carrier.CarrierHandle(
            robot=rig.robot,
            gripper_base_path=str(rig.base.GetPath()),
            physics=physics,
            initial_target_z=0.0,
            world_pin_was_present=True,
            root_path=state["root_path"],
            world_pin_paths=state["world_pin_paths"],
        )
        pending = carrier.detach_carrier(rig.stage, handle)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(pending)
    assert physics.plays == 0
    assert physics.playing
    assert rig.actions == []
    assert _stage_snapshot(rig.stage) == before


def _translation(monkeypatch, effort_getter, log_error=None, warn_error=None):
    actions, logs, warnings, callbacks = [], [], [], []
    native = SimpleNamespace(
        dof_names=["finger_slider", "rail"],
        get_joint_positions=lambda: np.array([0.3, 0.0]),
        get_joint_position_targets=lambda: np.array([0.3, 0.0]),
        get_applied_joint_efforts=effort_getter,
    )
    robot = RobotHandle.__new__(RobotHandle)
    robot._articulation = native
    robot._newton_actuators = None
    handle = carrier.CarrierHandle(
        robot=robot,
        gripper_base_path="/World/Gripper/base",
        physics=None,
        initial_target_z=0.0,
        world_pin_was_present=False,
        joint_z_path="/World/_FET028_Gantry/rail",
    )

    def command(stage, controlled_handle, target):
        assert controlled_handle is handle
        actions.append(("command", target))

    async def step():
        actions.append(("step", None))

    async def on_substep(index, count):
        callbacks.append((index, count))

    def log(message):
        logs.append(message)
        if log_error is not None:
            raise log_error

    def warn(message):
        warnings.append(message)
        if warn_error is not None:
            raise warn_error

    monkeypatch.setattr(carrier, "set_carrier_target_z", command)
    ctx = SimpleNamespace(log=log, warn=warn, step_one=step)
    return SimpleNamespace(
        actions=actions,
        logs=logs,
        warnings=warnings,
        callbacks=callbacks,
        native=native,
        robot=robot,
        handle=handle,
        ctx=ctx,
        run=lambda: carrier.linear_translate(
            ctx, None, handle, np.array([0.0, 0.0, 0.2]), 1.0, fps=8, on_substep=on_substep
        ),
    )


def test_native_optional_effort_failure_keeps_identical_commands_steps_and_callbacks(monkeypatch):
    control = _translation(monkeypatch, lambda: np.array([1.0, 2.0]))
    asyncio.run(control.run())
    native_error = RuntimeError("native effort telemetry unavailable")

    def failed_efforts():
        raise native_error

    failed = _translation(monkeypatch, failed_efforts)
    asyncio.run(failed.run())

    assert failed.actions == control.actions
    assert len(failed.actions) == 16
    assert failed.callbacks == control.callbacks == [(index, 8) for index in range(1, 9)]
    assert len(failed.warnings) == 1
    assert "effort" in failed.warnings[0]
    assert failed.logs and all("efforts=None" in line for line in failed.logs)
    with pytest.raises(RuntimeError) as caught:
        failed.robot.get_applied_joint_efforts()
    assert caught.value is native_error  # The required native API was not globally weakened.


@pytest.mark.parametrize(
    "efforts",
    [None, [float("nan"), 1.0], [2.0], "not numeric", [False, True], ["0", "1"], [1j, 2j], [[1, 2], [3, 4]]],
)
def test_optional_incomplete_effort_readbacks_are_unavailable_not_zero(monkeypatch, efforts):
    run = _translation(monkeypatch, lambda: efforts)
    asyncio.run(run.run())
    assert len(run.actions) == 16
    assert len(run.warnings) == 1
    assert run.logs and all("efforts=None" in line for line in run.logs)


def test_missing_native_effort_getter_keeps_the_identical_control_sequence(monkeypatch):
    control = _translation(monkeypatch, lambda: [1.0, 2.0])
    asyncio.run(control.run())
    missing = _translation(monkeypatch, lambda: [1.0, 2.0])
    del missing.native.get_applied_joint_efforts

    assert missing.robot.get_applied_joint_efforts() is None
    asyncio.run(missing.run())

    assert missing.actions == control.actions
    assert missing.callbacks == control.callbacks
    assert len(missing.warnings) == 1
    assert missing.logs and all("efforts=None" in line for line in missing.logs)


def test_real_zero_efforts_remain_valid_carrier_trace_evidence(monkeypatch):
    run = _translation(monkeypatch, lambda: [0.0, 0.0])
    asyncio.run(run.run())
    assert len(run.actions) == 16
    assert run.warnings == []
    assert run.logs and all("efforts=[0.0, 0.0]" in line for line in run.logs)


@pytest.mark.parametrize("broken_warning", [False, True])
def test_optional_trace_log_failure_does_not_interrupt_control(monkeypatch, broken_warning):
    run = _translation(
        monkeypatch,
        lambda: [1.0, 2.0],
        log_error=RuntimeError("trace sink failed"),
        warn_error=RuntimeError("warning sink failed") if broken_warning else None,
    )
    asyncio.run(run.run())
    assert len(run.actions) == 16
    assert len(run.callbacks) == 8
    assert len(run.warnings) == 1


def test_optional_trace_log_lookup_failure_does_not_interrupt_control(monkeypatch):
    run = _translation(monkeypatch, lambda: [1.0, 2.0])

    class Context:
        @property
        def log(self):
            raise RuntimeError("trace logger property unavailable")

        warn = staticmethod(run.ctx.warn)
        step_one = staticmethod(run.ctx.step_one)

    asyncio.run(carrier.linear_translate(Context(), None, run.handle, np.array([0.0, 0.0, 0.2]), 1.0, fps=8))
    assert len(run.actions) == 16
    assert len(run.warnings) == 1
    assert "trace" in run.warnings[0]


@pytest.mark.parametrize("channel", ["position", "target", "names"])
def test_optional_state_and_name_traces_keep_the_identical_control_sequence(monkeypatch, channel):
    control = _translation(monkeypatch, lambda: [1.0, 2.0])
    asyncio.run(control.run())
    run = _translation(monkeypatch, lambda: [1.0, 2.0])
    diagnostic_error = RuntimeError("optional %s trace unavailable" % channel)

    def fail():
        raise diagnostic_error

    if channel == "position":
        run.native.get_joint_positions = fail
    elif channel == "target":
        run.robot.get_joint_position_targets = fail
    else:

        class TraceNamesRobot:
            names_reads = 0
            get_joint_positions = staticmethod(run.robot.get_joint_positions)
            get_joint_position_targets = staticmethod(run.robot.get_joint_position_targets)
            get_applied_joint_efforts = staticmethod(run.robot.get_applied_joint_efforts)

            @property
            def dof_names(self):
                self.names_reads += 1
                if self.names_reads == 1:
                    return ["finger_slider", "rail"]  # Required command identity resolves normally.
                raise diagnostic_error

        run.handle.robot = TraceNamesRobot()

    asyncio.run(run.run())

    assert run.actions == control.actions
    assert run.callbacks == control.callbacks
    assert len(run.warnings) == 1
    assert "trace" in run.warnings[0]
    assert run.logs == []
    if channel == "position":
        with pytest.raises(RuntimeError) as caught:
            run.robot.get_joint_positions()
        assert caught.value is diagnostic_error


@pytest.mark.parametrize("channel", ["position", "target", "effort", "log", "warning"])
def test_optional_trace_cancellation_propagates_before_any_command(monkeypatch, channel):
    cancellation = asyncio.CancelledError("diagnostic cancelled")

    def efforts():
        if channel == "effort":
            raise cancellation
        if channel == "warning":
            raise RuntimeError("native telemetry unavailable")
        return [1.0, 2.0]

    run = _translation(
        monkeypatch,
        efforts,
        log_error=cancellation if channel == "log" else None,
        warn_error=cancellation if channel == "warning" else None,
    )

    def cancelled_read():
        raise cancellation

    if channel == "position":
        run.native.get_joint_positions = cancelled_read
    elif channel == "target":
        run.robot.get_joint_position_targets = cancelled_read
    with pytest.raises(asyncio.CancelledError) as caught:
        asyncio.run(run.run())
    assert caught.value is cancellation
    assert run.actions == []
    assert run.callbacks == []


@pytest.mark.parametrize("channel", ["position", "command", "step"])
def test_required_carrier_reads_commands_and_steps_still_fail_honestly(monkeypatch, channel):
    run = _translation(monkeypatch, lambda: [1.0, 2.0])
    required_error = RuntimeError("required %s failed" % channel)

    def fail(*args):
        raise required_error

    async def fail_step():
        raise required_error

    if channel == "position":
        run.native.get_joint_positions = fail
        run.handle.rail_world_anchor = np.zeros(3)
    elif channel == "command":
        monkeypatch.setattr(carrier, "set_carrier_target_z", fail)
    else:
        run.ctx.step_one = fail_step

    with pytest.raises(RuntimeError) as caught:
        if channel == "position":
            carrier.carrier_world_position(run.handle)
        else:
            asyncio.run(run.run())
    if channel == "position":
        assert caught.value.__cause__ is required_error
    else:
        assert caught.value is required_error
    assert run.callbacks == []
    assert run.actions == ([] if channel != "step" else [("command", pytest.approx(0.00859375))])


def _production_physics_handle(monkeypatch, rig, stop_acknowledgement):
    """Exercise the companion adapter's actual stop acknowledgement barrier."""
    from simready.evaluate_engine_kit import physics_utils
    from simready.evaluate_engine_kit.physics_handle import PhysicsHandle

    calls = []

    class Timeline:
        playing = True

        def stop(self):
            calls.append("stop")
            if stop_acknowledgement is not False:
                self.playing = False
            return stop_acknowledgement

        def play(self, **kwargs):
            calls.append("play")
            self.playing = True

        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    timeline = Timeline()
    omni = ModuleType("omni")
    omni.__path__ = []
    timeline_module = ModuleType("omni.timeline")
    timeline_module.get_timeline_interface = lambda: timeline
    omni.timeline = timeline_module
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.timeline", timeline_module)
    monkeypatch.setattr(physics_utils, "configure_physx_determinism", lambda *args: {})
    physics = PhysicsHandle(rig.stage)
    return SimpleNamespace(handle=physics, timeline=timeline, calls=calls)


@pytest.mark.parametrize("operation", ["rollback", "attach", "detach"])
def test_production_adapter_stop_rejection_blocks_carrier_topology_and_rebinding(monkeypatch, operation):
    rig = _rig()
    native = _production_physics_handle(monkeypatch, rig, False)
    state = _partial_state(rig) if operation != "attach" else None
    before = _stage_snapshot(rig.stage)
    restoration_attempts = []
    for name in (
        "_remove_existing_gantry",
        "_restore_root_orientation",
        "_restore_carrier_root_transfer",
        "_restore_default_state",
        "_restore_joint_default_state",
        "_require_world_pin_restore",
        "_cleanup_carrier_opinions",
    ):
        monkeypatch.setattr(carrier, name, lambda *args, operation=name: restoration_attempts.append(operation))

    if operation == "rollback":
        errors = asyncio.run(carrier._rollback_partial_carrier(rig.stage, rig.robot, native.handle, state))
        assert len(errors) == 1 and "could not stop physics" in str(errors[0])
        assert "rejected the stop request" in str(errors[0].__cause__.__cause__)
    elif operation == "attach":
        with pytest.raises(RuntimeError, match="Could not stop the physics timeline") as caught:
            asyncio.run(
                carrier.attach_carrier(rig.stage, {"physics": native.handle}, rig.robot, str(rig.base.GetPath()))
            )
        assert "rejected the stop request" in str(caught.value.__cause__)
        assert any("could not stop physics" in note for note in caught.value.__notes__)
    else:
        handle = carrier.CarrierHandle(
            robot=rig.robot,
            gripper_base_path=str(rig.base.GetPath()),
            physics=native.handle,
            initial_target_z=0.0,
            world_pin_was_present=True,
            root_path=state["root_path"],
            world_pin_paths=state["world_pin_paths"],
        )
        with pytest.raises(RuntimeError, match="detach restoration failed.*could not stop physics"):
            asyncio.run(carrier.detach_carrier(rig.stage, handle))

    assert native.calls == (["stop", "stop"] if operation == "attach" else ["stop"])
    assert native.timeline.playing is True
    assert restoration_attempts == []
    assert rig.actions == []
    assert _stage_snapshot(rig.stage) == before


@pytest.mark.parametrize("acknowledgement", [None, True])
def test_production_adapter_successful_stop_allows_safe_carrier_restoration(monkeypatch, acknowledgement):
    rig = _rig()
    native = _production_physics_handle(monkeypatch, rig, acknowledgement)
    state = _partial_state(rig)

    async def reset():
        rig.actions.append("reset")

    rig.robot._world = SimpleNamespace(reset_async=reset)
    errors = asyncio.run(carrier._rollback_partial_carrier(rig.stage, rig.robot, native.handle, state))

    assert errors == []
    assert native.calls == ["stop", "play", "play"]
    assert "initialize" in rig.actions and "reset" in rig.actions
    assert not rig.stage.GetPrimAtPath(state["root_path"])
    assert rig.pin.GetPrim().IsActive()
    assert native.timeline.playing is True
