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

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pxr
import pytest
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics
from simready.evaluate_engine_kit import fabric_utils
from simready.foundation.tier_core.runtime_tests.fet005_grasp.phase_dropping import DroppingPhase
from simready.foundation.tier_core.runtime_tests.fet005_grasp.phase_gripper_pos import (
    GripperPositioningPhase,
)
from simready.foundation.tier_core.runtime_tests.fet005_grasp.phase_opening import OpeningPhase


@pytest.fixture
def production_scene(monkeypatch):
    stage = Usd.Stage.CreateInMemory()
    warnings = []
    carb = ModuleType("carb")
    carb.log_warn = warnings.append
    omni = ModuleType("omni")
    omni.kit = ModuleType("omni.kit")
    omni.kit.app = ModuleType("omni.kit.app")
    omni.usd = ModuleType("omni.usd")
    omni.usd.get_context = lambda: SimpleNamespace(get_stage=lambda: stage)
    omni.physx = ModuleType("omni.physx")
    omni.physx.get_physx_scene_query_interface = lambda: None
    isaac = ModuleType("isaacsim")
    isaac.core = ModuleType("isaacsim.core")
    isaac.core.utils = ModuleType("isaacsim.core.utils")
    isaac.core.utils.stage = ModuleType("isaacsim.core.utils.stage")

    async def update_stage_async():
        pass

    isaac.core.utils.stage.update_stage_async = update_stage_async
    robot_module = ModuleType("simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_robot")
    robot_module.GraspRobot = SimpleNamespace(
        ROBOT_PATH="/World/Gripper",
        GANTRY_X="/World/Gripper/gantry_x",
        LEFT_PAD="/World/Gripper/left_pad",
        RIGHT_PAD="/World/Gripper/right_pad",
    )
    engine_module = ModuleType("simready.evaluate_engine_kit.physics_utils")
    engine_module.active_physics_engine = lambda: "physx"
    for module in (
        carb,
        omni,
        omni.kit,
        omni.kit.app,
        omni.usd,
        omni.physx,
        isaac,
        isaac.core,
        isaac.core.utils,
        isaac.core.utils.stage,
        robot_module,
        engine_module,
    ):
        monkeypatch.setitem(sys.modules, module.__name__, module)

    path = Path(__file__).resolve().parents[3] / "simready/foundation/tier_core/runtime_tests/fet005_grasp/grasp_scene.py"
    spec = importlib.util.spec_from_file_location("_fet005_fixture_scene_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    scene = module.GraspScene(SimpleNamespace(log=lambda _message: None), "/Asset/body/grasp_identifier_0", "/Asset")
    return SimpleNamespace(stage=stage, scene=scene, module=module, engine=engine_module, warnings=warnings)


def _pads(harness):
    paths = (harness.module.GraspRobot.LEFT_PAD, harness.module.GraspRobot.RIGHT_PAD)
    for path in paths:
        prim = UsdGeom.Cube.Define(harness.stage, path).GetPrim()
        UsdPhysics.CollisionAPI.Apply(prim).CreateCollisionEnabledAttr(True)
    return paths


def _grasp_curve(stage, path, points=((0, 0, 0), (1, 0, 0))):
    curve = UsdGeom.BasisCurves.Define(stage, path)
    curve.CreatePointsAttr([Gf.Vec3f(*point) for point in points])
    curve.CreateCurveVertexCountsAttr([len(points)])
    curve.CreateTypeAttr("linear")
    return curve


@pytest.mark.parametrize("wrapped", [False, True])
def test_official_direct_and_legacy_wrapped_segments_preserve_scaled_world_and_local_points(production_scene, wrapped):
    from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_checks import (
        discover_grasp_identifiers,
    )

    harness = production_scene
    body = UsdGeom.Xform.Define(harness.stage, "/Asset/body")
    UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
    body.AddTranslateOp().Set(Gf.Vec3d(10, -5, 3))
    body.AddScaleOp().Set(Gf.Vec3f(2, 3, 4))
    annotation = UsdGeom.Xform.Define(harness.stage, "/Asset/body/Annotations")
    annotation.AddTranslateOp().Set(Gf.Vec3d(1, 2, 3))
    identifier_path = "/Asset/body/Annotations/grasp_identifier_01"
    if wrapped:
        UsdGeom.Xform.Define(harness.stage, identifier_path)
        source_path = identifier_path + "/grasp_identifier_line"
    else:
        source_path = identifier_path
    curve = _grasp_curve(harness.stage, source_path)
    curve.AddTranslateOp().Set(Gf.Vec3d(0.5, -0.5, 1))
    curve.AddScaleOp().Set(Gf.Vec3f(0.5, 2, 1))
    harness.scene._identifier_path = identifier_path

    assert discover_grasp_identifiers(harness.stage, "/Asset") == [identifier_path]
    world = harness.scene._extract_world_grasp_points()
    assert np.asarray(world) == pytest.approx(np.asarray([[13, -0.5, 19], [14, -0.5, 19]]))
    local = harness.scene.compute_local_grasp_points("/Asset/body")
    assert np.asarray(local) == pytest.approx(np.asarray([[1.5, 1.5, 4], [2, 1.5, 4]]))
    harness.scene._parent_body_path = "/Asset/body"
    roundtrip = harness.scene.compute_world_grasp_points(*local, authored=True)
    assert np.asarray(roundtrip) == pytest.approx(np.asarray(world))
    harness.scene.init_tracking()
    assert harness.scene._parent_body_path == "/Asset/body"
    assert np.asarray([harness.scene._local_gp1, harness.scene._local_gp2]) == pytest.approx(np.asarray(local))


def test_named_wrapper_consumes_only_its_actual_segment_without_duplicate_trials(production_scene):
    from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_checks import (
        discover_grasp_identifiers,
    )

    stage = production_scene.stage
    UsdGeom.Xform.Define(stage, "/Asset/grasp_identifier_wrapper")
    _grasp_curve(stage, "/Asset/grasp_identifier_wrapper/grasp_identifier_first")
    _grasp_curve(stage, "/Asset/grasp_identifier_wrapper/grasp_identifier_second")
    _grasp_curve(stage, "/Asset/grasp_identifier_direct")
    _grasp_curve(stage, "/Asset/ordinary_curve")
    assert discover_grasp_identifiers(stage, "/Asset") == [
        "/Asset/grasp_identifier_wrapper",
        "/Asset/grasp_identifier_wrapper/grasp_identifier_second",
        "/Asset/grasp_identifier_direct",
    ]


def test_direct_identifier_inside_instance_proxy_is_discovered_and_transformed(production_scene):
    from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_checks import (
        discover_grasp_identifiers,
    )

    harness = production_scene
    prototype = UsdGeom.Xform.Define(harness.stage, "/Prototype")
    _grasp_curve(harness.stage, "/Prototype/grasp_identifier")
    instance = UsdGeom.Xform.Define(harness.stage, "/Asset/Instance")
    instance.GetPrim().GetReferences().AddInternalReference(str(prototype.GetPath()))
    instance.AddTranslateOp().Set(Gf.Vec3d(4, 5, 6))
    instance.GetPrim().SetInstanceable(True)
    identifier_path = "/Asset/Instance/grasp_identifier"
    assert harness.stage.GetPrimAtPath(identifier_path).IsInstanceProxy()
    assert discover_grasp_identifiers(harness.stage, "/Asset") == [identifier_path]
    harness.scene._identifier_path = identifier_path
    assert np.asarray(harness.scene._extract_world_grasp_points()) == pytest.approx(np.asarray([[4, 5, 6], [5, 5, 6]]))


@pytest.mark.parametrize("case", ["nan", "infinity", "coincident", "singular_transform", "non_real", "one_point"])
def test_direct_grasp_segment_cannot_invent_valid_geometry(production_scene, monkeypatch, case):
    harness = production_scene
    identifier = harness.scene.grasp_identifier_path
    curve = _grasp_curve(harness.stage, identifier)
    if case == "singular_transform":
        curve.AddScaleOp().Set(Gf.Vec3f(0, 1, 1))
    elif case == "non_real":
        # USD's typed schema itself rejects strings; exercise the required
        # extraction boundary if an external point reader is malformed too.
        monkeypatch.setattr(harness.module, "grasp_point_source", lambda _prim: (curve.GetPrim(), ["zero", "one"]))
    elif case == "one_point":
        curve.CreatePointsAttr([Gf.Vec3f(0)])
    else:
        value = {"nan": float("nan"), "infinity": float("inf"), "coincident": 0.0}[case]
        curve.CreatePointsAttr([Gf.Vec3f(0), Gf.Vec3f(value, 0, 0)])
    with pytest.raises(RuntimeError, match="grasp (segment|transform)|extract grasp points"):
        harness.scene.init_tracking()
    assert harness.scene.robot is None
    assert not harness.stage.GetPrimAtPath(harness.module.GraspRobot.ROBOT_PATH)


@pytest.mark.parametrize("enabled", [True, False])
def test_pad_collision_authoring_verifies_both_pads_without_claiming_native_application(production_scene, enabled):
    paths = _pads(production_scene)

    production_scene.scene._set_pad_collision_enabled(enabled)

    assert all(
        UsdPhysics.CollisionAPI.Get(production_scene.stage, path).GetCollisionEnabledAttr().Get() is enabled
        for path in paths
    )
    assert production_scene.scene.scene_properties["pad_collision_authoring"] == {
        "enabled": enabled,
        "pad_paths": list(paths),
        "source": "USD authored write/readback",
        "native_application_verified": False,
    }


@pytest.mark.parametrize("missing", ["prim", "api"])
def test_missing_second_pad_is_setup_error_before_any_pad_write(production_scene, missing):
    left, right = _pads(production_scene)
    if missing == "prim":
        production_scene.stage.RemovePrim(right)
    else:
        production_scene.stage.GetPrimAtPath(right).RemoveAPI(UsdPhysics.CollisionAPI)

    with pytest.raises(RuntimeError, match="Required generated gripper pad"):
        production_scene.scene.disable_gripper_pad_collisions()

    assert UsdPhysics.CollisionAPI.Get(production_scene.stage, left).GetCollisionEnabledAttr().Get() is True
    assert "pad_collision_authoring" not in production_scene.scene.scene_properties


@pytest.mark.parametrize("state", [None, 0, 1, "false", []])
def test_pad_state_requires_actual_boolean_before_authoring(production_scene, state):
    _pads(production_scene)
    with pytest.raises(RuntimeError, match="boolean"):
        production_scene.scene._set_pad_collision_enabled(state)


@pytest.mark.parametrize("written", [False, None, 1])
def test_rejected_pad_write_remains_setup_error(production_scene, monkeypatch, written):
    _pads(production_scene)
    original_api = UsdPhysics.CollisionAPI

    class CollisionAPI:
        @staticmethod
        def Get(stage, path):
            attribute = original_api.Get(stage, path).GetCollisionEnabledAttr()
            proxy = SimpleNamespace(IsValid=lambda: True, Set=lambda _enabled: written, Get=attribute.Get)
            return SimpleNamespace(GetCollisionEnabledAttr=lambda: proxy)

    monkeypatch.setattr(UsdPhysics, "CollisionAPI", CollisionAPI)
    with pytest.raises(RuntimeError, match="not authored and verified"):
        production_scene.scene.disable_gripper_pad_collisions()


@pytest.mark.parametrize("observed", [None, 0, 1, "false", True])
def test_missing_untyped_or_ineffective_pad_readback_remains_setup_error(production_scene, monkeypatch, observed):
    _pads(production_scene)

    class CollisionAPI:
        @staticmethod
        def Get(_stage, _path):
            attribute = SimpleNamespace(IsValid=lambda: True, Set=lambda _enabled: True, Get=lambda: observed)
            return SimpleNamespace(GetCollisionEnabledAttr=lambda: attribute)

    monkeypatch.setattr(UsdPhysics, "CollisionAPI", CollisionAPI)
    with pytest.raises(RuntimeError, match="not authored and verified"):
        production_scene.scene.disable_gripper_pad_collisions()


def _compiled_pad_model(harness, monkeypatch, enabled=False):
    paths = _pads(harness)
    harness.scene._set_pad_collision_enabled(enabled)
    _newton(harness)
    model = SimpleNamespace(
        shape_label=["/Unrelated", *paths],
        shape_count=3,
        shape_flags=SimpleNamespace(numpy=lambda: np.array([1, int(enabled), int(enabled)], dtype=np.int32)),
    )
    native_stage = SimpleNamespace(initialized=True, model=model)
    sdk = ModuleType("isaacsim.physics.newton")
    sdk.acquire_stage = lambda: native_stage
    newton = ModuleType("newton")
    newton.ShapeFlags = SimpleNamespace(COLLIDE_SHAPES=1)
    monkeypatch.setitem(sys.modules, sdk.__name__, sdk)
    monkeypatch.setitem(sys.modules, newton.__name__, newton)
    return SimpleNamespace(model=model, stage=native_stage, sdk=sdk, newton=newton, paths=paths)


@pytest.mark.parametrize("enabled", [True, False])
def test_compiled_owned_pad_flags_acknowledge_requested_state_without_contact_claim(
    production_scene, monkeypatch, enabled
):
    native = _compiled_pad_model(production_scene, monkeypatch, enabled)
    # Unrelated shapes remain collision enabled and must not affect this check.
    production_scene.scene.verify_gripper_collision_state(enabled)

    receipt = production_scene.scene.scene_properties["pad_collision_authoring"]
    assert receipt["enabled"] is enabled
    assert receipt["compiled_shape_flags_acknowledged"] is True
    assert receipt["native_application_verified"] is False
    assert receipt["contact_not_measured"] is True
    assert native.model.shape_flags.numpy().tolist() == [1, int(enabled), int(enabled)]


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("index", [1, 2])
def test_wrong_compiled_pad_state_is_setup_error_not_asset_verdict(production_scene, monkeypatch, enabled, index):
    native = _compiled_pad_model(production_scene, monkeypatch, enabled)
    flags = native.model.shape_flags.numpy()
    flags[index] = int(not enabled)
    native.model.shape_flags.numpy = lambda: flags
    with pytest.raises(RuntimeError, match="could not be acknowledged") as caught:
        production_scene.scene.verify_gripper_collision_state(enabled)
    assert "differs from the required compiled state" in str(caught.value.__cause__)
    assert (
        production_scene.scene.scene_properties["pad_collision_authoring"]["compiled_shape_flags_acknowledged"] is False
    )


@pytest.mark.parametrize(
    "case",
    [
        "no_stage",
        "not_initialized",
        "no_model",
        "no_flags",
        "missing_left",
        "missing_right",
        "duplicate_left",
        "duplicate_right",
        "label_type",
        "label_count",
        "count_bool",
        "count_float",
    ],
)
def test_unavailable_or_ambiguous_compiled_pad_model_is_setup_error(production_scene, monkeypatch, case):
    native = _compiled_pad_model(production_scene, monkeypatch)
    if case == "no_stage":
        native.sdk.acquire_stage = lambda: None
    elif case == "not_initialized":
        native.stage.initialized = False
    elif case == "no_model":
        native.stage.model = None
    elif case == "no_flags":
        native.model.shape_flags = None
    elif case.startswith("missing_"):
        index = 1 if case.endswith("left") else 2
        native.model.shape_label[index] = "/NotTheRequiredPad"
    elif case.startswith("duplicate_"):
        index = 1 if case.endswith("left") else 2
        native.model.shape_label[0] = native.paths[index - 1]
    elif case == "label_type":
        native.model.shape_label[0] = 123
    elif case == "label_count":
        native.model.shape_label = native.model.shape_label[:-1]
    elif case == "count_bool":
        native.model.shape_count = True
    else:
        native.model.shape_count = 3.0
    with pytest.raises(RuntimeError, match="could not be acknowledged"):
        production_scene.scene.verify_gripper_collision_disabled()
    assert (
        production_scene.scene.scene_properties["pad_collision_authoring"]["compiled_shape_flags_acknowledged"] is False
    )


@pytest.mark.parametrize(
    "flags",
    [
        np.array([[1, 0, 0]]),
        np.array([0, 0]),
        np.array([True, False, False]),
        np.array([1.0, 0.0, 0.0]),
        np.array([1, 0, 0], dtype=object),
        np.array(["1", "0", "0"]),
        np.array([1j, 0j, 0j]),
        np.array([1, 0, -1]),
        np.array([1, np.nan, 0]),
    ],
)
def test_compiled_flags_require_complete_raw_integer_vector(production_scene, monkeypatch, flags):
    native = _compiled_pad_model(production_scene, monkeypatch)
    native.model.shape_flags.numpy = lambda: flags
    with pytest.raises(RuntimeError, match="could not be acknowledged") as caught:
        production_scene.scene.verify_gripper_collision_disabled()
    assert "one-dimensional integer array" in str(caught.value.__cause__)


@pytest.mark.parametrize("cause", [OSError("native flag readback failed"), asyncio.CancelledError("stop requested")])
def test_compiled_flags_preserve_original_readback_cause_or_cancellation(production_scene, monkeypatch, cause):
    native = _compiled_pad_model(production_scene, monkeypatch)

    def failed():
        raise cause

    native.model.shape_flags.numpy = failed
    if isinstance(cause, asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError) as caught:
            production_scene.scene.verify_gripper_collision_disabled()
        assert caught.value is cause
    else:
        with pytest.raises(RuntimeError) as caught:
            production_scene.scene.verify_gripper_collision_disabled()
        assert caught.value.__cause__ is cause
        assert "reason=shape_flags_unavailable_or_invalid" in str(caught.value)
        assert "observed={}" in str(caught.value)
        assert str(cause) not in str(caught.value)


def test_compiled_pad_mismatch_has_bounded_durable_context_not_invented_state(production_scene, monkeypatch):
    native = _compiled_pad_model(production_scene, monkeypatch)
    native.model.shape_flags.numpy = lambda: np.array([1, 1, 1], dtype=np.int32)
    with pytest.raises(RuntimeError) as caught:
        production_scene.scene.verify_gripper_collision_disabled()
    message = str(caught.value)
    assert "expected_enabled=False" in message
    assert "reason=compiled_state_mismatch" in message
    assert "observed={'left': True}" in message
    assert "right" not in message  # Its state was never observed after left failed.
    assert native.paths[0] not in message


def test_physx_release_retains_authored_acknowledgment_without_importing_newton(production_scene, monkeypatch):
    _pads(production_scene)
    production_scene.scene.disable_gripper_pad_collisions()
    monkeypatch.setitem(sys.modules, "isaacsim.physics.newton", None)
    monkeypatch.setitem(sys.modules, "newton", None)
    production_scene.scene.verify_gripper_collision_disabled()
    assert "compiled_shape_flags_acknowledged" not in production_scene.scene.scene_properties["pad_collision_authoring"]


def test_drop_checks_compiled_release_only_on_first_existing_tick(production_scene, monkeypatch):
    native = _compiled_pad_model(production_scene, monkeypatch)
    flags = [np.array([1, 1, 1], dtype=np.int32)]
    calls = []

    def read():
        calls.append("read")
        return flags[0]

    native.model.shape_flags.numpy = read
    phase = DroppingPhase({"physics_fps": 10, "drop_check_seconds": 0.2})
    phase._compute_required_fall = lambda _scene: 0.05
    tracker = SimpleNamespace(center_history=[(0.0, 0.0, 1.0)])
    # Authoring does not query the native model before the normal loop advance.
    assert calls == []
    flags[0] = np.array([1, 0, 0], dtype=np.int32)
    assert phase.check_frame(11, 1.1, production_scene.scene, tracker) is None
    result = phase.check_frame(13, 1.3, production_scene.scene, tracker)
    assert result["failed"] is True  # Drop criterion is unchanged after qualified release.
    assert calls == ["read"]
    assert native.model.shape_flags.numpy().tolist() == [1, 0, 0]


def test_unacknowledged_release_aborts_before_drop_verdict_or_geometry(production_scene, monkeypatch):
    native = _compiled_pad_model(production_scene, monkeypatch)
    native.model.shape_flags.numpy = lambda: np.array([1, 1, 1], dtype=np.int32)
    phase = DroppingPhase({"physics_fps": 10, "drop_check_seconds": 0.0})
    phase._compute_required_fall = lambda _scene: pytest.fail("geometry should not precede release acknowledgment")
    with pytest.raises(RuntimeError, match="could not be acknowledged"):
        phase.check_frame(11, 1.1, production_scene.scene, SimpleNamespace(center_history=[(0.0, 0.0, 1.0)]))
    assert phase._start_frame is None
    assert phase._done is False


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["enabled", "disabled", "missing"])
async def test_rebuild_requires_enabled_compiled_pads_before_behavioral_evaluation(production_scene, monkeypatch, case):
    harness = production_scene
    native = _compiled_pad_model(harness, monkeypatch, enabled=True)
    if case == "disabled":
        native.model.shape_flags.numpy = lambda: np.array([1, 0, 1], dtype=np.int32)
    elif case == "missing":
        native.model.shape_label[1] = "/UnrelatedMissingPad"
    calls = []
    harness.scene._robot = SimpleNamespace(
        _edit_target=harness.stage.GetEditTarget(), teardown=lambda: calls.append("teardown")
    )
    monkeypatch.setattr(
        harness.scene, "get_current_world_grasp_points", lambda: (np.zeros(3), np.array([0.1, 0.0, 0.0]))
    )
    monkeypatch.setattr(harness.module.GraspRobot, "GANTRY_BASE", "/World/Gripper/base", raising=False)

    async def init(_ctx):
        calls.append("init")
        return True

    async def build(**_kwargs):
        calls.append("build")
        _pads(harness)
        UsdGeom.Xform.Define(harness.stage, harness.module.GraspRobot.GANTRY_BASE)
        return SimpleNamespace(scene_properties={}, init_newton_tensor_drive=init)

    async def settle(count):
        assert count == 1
        calls.append("existing_settle")

    monkeypatch.setattr(harness.module.GraspRobot, "build_for_asset", build, raising=False)
    harness.scene._ctx.settle = settle
    physics = SimpleNamespace(stop=lambda: calls.append("stop"), play=lambda: calls.append("play"))
    if case == "enabled":
        assert await harness.scene.rebuild_gripper_at_settled_position(physics) is True
        assert harness.scene.scene_properties["pad_collision_authoring"]["compiled_shape_flags_acknowledged"] is True
    else:
        with pytest.raises(RuntimeError, match="could not be acknowledged"):
            await harness.scene.rebuild_gripper_at_settled_position(physics)
        assert harness.scene.scene_properties["pad_collision_authoring"]["compiled_shape_flags_acknowledged"] is False
    assert calls == ["stop", "teardown", "build", "play", "existing_settle", "init"]


def _body(stage, path):
    prim = UsdGeom.Xform.Define(stage, path).GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(prim).CreateRigidBodyEnabledAttr(True)
    return prim


def _exact_mesh(stage, path, enabled=True):
    prim = UsdGeom.Mesh.Define(stage, path).GetPrim()
    UsdPhysics.CollisionAPI.Apply(prim).CreateCollisionEnabledAttr(enabled)
    UsdPhysics.MeshCollisionAPI.Apply(prim).CreateApproximationAttr("none")
    return prim


def _newton(harness):
    harness.engine.active_physics_engine = lambda: "newton"
    harness.scene._parent_body_path = "/Asset/body"


def test_empty_grasp_context_is_conditional_body_owned_authoring_not_contact_measurement(production_scene):
    harness = production_scene
    _newton(harness)
    _body(harness.stage, "/Asset/body")
    _exact_mesh(harness.stage, "/Asset/body/collider")
    _body(harness.stage, "/Asset/other")
    _exact_mesh(harness.stage, "/Asset/other/unrelated")

    message = harness.scene.empty_grasp_failure_message()

    assert "selected grasp body /Asset/body" in message
    assert "/Asset/body/collider" in message
    assert "author" in message
    assert "native dynamic contacts were not measured" in message
    assert "Newton generated no" not in message
    assert "/Asset/other/unrelated" not in message


@pytest.mark.parametrize("case", ["unrelated", "disabled", "nested_body", "disabled_body", "unresolved_body", "sdf"])
def test_empty_grasp_context_ignores_colliders_outside_selected_active_body(production_scene, case):
    harness = production_scene
    _newton(harness)
    body = _body(harness.stage, "/Asset/body")
    if case == "unrelated":
        _body(harness.stage, "/Asset/other")
        _exact_mesh(harness.stage, "/Asset/other/collider")
    elif case == "disabled":
        _exact_mesh(harness.stage, "/Asset/body/collider", enabled=False)
    elif case == "nested_body":
        _body(harness.stage, "/Asset/body/other")
        _exact_mesh(harness.stage, "/Asset/body/other/collider")
    else:
        mesh = _exact_mesh(harness.stage, "/Asset/body/collider")
        if case == "disabled_body":
            UsdPhysics.RigidBodyAPI(body).GetRigidBodyEnabledAttr().Set(False)
        elif case == "unresolved_body":
            harness.scene._parent_body_path = "/Asset"
        else:
            mesh.SetMetadata(
                "apiSchemas", Sdf.TokenListOp.CreateExplicit([*mesh.GetAppliedSchemas(), "NewtonSDFCollisionAPI"])
            )

    assert harness.scene.empty_grasp_failure_message() == "Grasping failed: pads touched (no object)"


def test_optional_collider_diagnostic_failure_keeps_measured_grasp_message(production_scene, monkeypatch):
    _newton(production_scene)

    def fail(*_args):
        raise RuntimeError("diagnostic inspection unavailable")

    monkeypatch.setattr(UsdPhysics.RigidBodyAPI, "GetRigidBodyEnabledAttr", fail)
    _body(production_scene.stage, "/Asset/body")
    assert production_scene.scene.empty_grasp_failure_message() == "Grasping failed: pads touched (no object)"
    assert production_scene.warnings


@pytest.mark.parametrize("body_scale", [1.0, 0.001, 0.0001])
@pytest.mark.parametrize("marker_scale", [1.0, 0.001])
def test_grasp_points_preserve_parent_and_marker_scales_through_local_world_roundtrip(
    production_scene, body_scale, marker_scale
):
    harness = production_scene
    parent = UsdGeom.Xform.Define(harness.stage, "/Asset")
    parent.AddScaleOp().Set(Gf.Vec3f(body_scale))
    body = UsdGeom.Xform.Define(harness.stage, "/Asset/body")
    body.AddTranslateOp().Set(Gf.Vec3d(10.0, 20.0, 30.0))
    marker = UsdGeom.Xform.Define(harness.stage, harness.scene.grasp_identifier_path)
    marker.AddScaleOp().Set(Gf.Vec3f(marker_scale))
    points = UsdGeom.Points.Define(harness.stage, harness.scene.grasp_identifier_path + "/line")
    points.CreatePointsAttr([Gf.Vec3f(-50.0, 0.0, 0.0), Gf.Vec3f(50.0, 0.0, 0.0)])
    harness.scene._parent_body_path = "/Asset/body"

    extracted = harness.scene._extract_world_grasp_points()
    expected = [
        (body_scale * (10.0 - 50.0 * marker_scale), body_scale * 20.0, body_scale * 30.0),
        (body_scale * (10.0 + 50.0 * marker_scale), body_scale * 20.0, body_scale * 30.0),
    ]
    assert np.array(extracted) == pytest.approx(np.array(expected))
    local = harness.scene.compute_local_grasp_points("/Asset/body")
    assert np.array(local) == pytest.approx(
        np.array([(-50.0 * marker_scale, 0.0, 0.0), (50.0 * marker_scale, 0.0, 0.0)])
    )
    assert np.array(harness.scene.compute_world_grasp_points(*local, authored=True)) == pytest.approx(
        np.array(expected)
    )


def test_required_newton_matrix_never_falls_back_to_authored_pose(production_scene, monkeypatch):
    _newton(production_scene)
    _body(production_scene.stage, "/Asset/body")
    monkeypatch.setattr(fabric_utils, "live_world_matrix", lambda *_args: None)

    with pytest.raises(RuntimeError, match="Required live grasp-body transform"):
        production_scene.scene._body_world_matrix("/Asset/body")
    assert production_scene.scene._body_world_matrix("/Asset/body", authored=True) == Gf.Matrix4d(1.0)


def test_live_newton_matrix_keeps_native_scale(production_scene, monkeypatch):
    _newton(production_scene)
    _body(production_scene.stage, "/Asset/body")
    matrix = Gf.Matrix4d(1.0)
    matrix.SetScale(0.001)
    matrix.SetRow(3, Gf.Vec4d(1.0, 2.0, 3.0, 1.0))
    monkeypatch.setattr(fabric_utils, "live_world_matrix", lambda *_args: matrix)

    observed = production_scene.scene._body_world_matrix("/Asset/body")
    assert observed.Transform(Gf.Vec3d(50.0, 0.0, 0.0)) == Gf.Vec3d(1.05, 2.0, 3.0)


@pytest.mark.parametrize("invalid", ["singular", "nan", "string", "non_affine", "shape"])
def test_invalid_grasp_matrix_is_setup_error(production_scene, invalid):
    rows = [[float(value) for value in row] for row in Gf.Matrix4d(1.0)]
    if invalid == "singular":
        rows[0][0] = 0.0
    elif invalid == "nan":
        rows[0][0] = float("nan")
    elif invalid == "string":
        rows[0][0] = "1"
    elif invalid == "non_affine":
        rows[0][3] = 1.0
    else:
        rows.append(rows[-1])
    with pytest.raises(RuntimeError, match="Required grasp transform is invalid"):
        production_scene.module._required_grasp_matrix(rows, "/Asset/body")


def test_opening_waits_for_full_ramp_even_with_shorter_release_check(production_scene):
    calls = []
    scene = production_scene.scene
    scene._robot = SimpleNamespace(
        get_gripper_joint_position=lambda: -0.02,
        close=lambda target: calls.append(("close", target)),
        open=lambda: calls.append(("open", None)),
    )
    _pads(production_scene)
    phase = OpeningPhase({"physics_fps": 10, "open_duration": 1.0, "release_check_seconds": 0.2})
    tracker = SimpleNamespace(center_history=[(0.0, 0.0, 1.0)])
    for frame in range(10):
        assert phase.check_frame(frame, frame / 10.0, scene, tracker) is None
    result = phase.check_frame(10, 1.0, scene, tracker)
    assert result["failed"] is False
    assert calls[-1] == ("open", None)
    assert scene.scene_properties["pad_collision_authoring"]["enabled"] is False


def test_opening_rejected_collision_release_is_not_success_or_asset_fail(production_scene):
    scene = production_scene.scene
    scene._robot = SimpleNamespace(get_gripper_joint_position=lambda: -0.02, open=lambda: None)
    phase = OpeningPhase({"physics_fps": 10, "open_duration": 0.0, "release_check_seconds": 0.0})
    with pytest.raises(RuntimeError, match="Required generated gripper pad"):
        phase.check_frame(0, 0.0, scene, SimpleNamespace(center_history=[(0.0, 0.0, 1.0)]))
    assert phase._done is False
    assert phase._fixture_released is False


def _drop_scene(harness):
    _body(harness.stage, "/Asset/body")
    cube = UsdGeom.Cube.Define(harness.stage, "/Asset/body/render_geo")
    cube.CreateSizeAttr(2.0)
    cube.CreatePurposeAttr(UsdGeom.Tokens.render)
    harness.scene._scene_properties = {"tracked_body_path": "/Asset/body"}
    return DroppingPhase({"physics_fps": 240, "fall_min_delta_z": 0.05})


def test_drop_uses_live_selected_body_height_not_authored_stale_height(production_scene, monkeypatch):
    phase = _drop_scene(production_scene)
    _newton(production_scene)
    queries = []

    def live(stage, root, select, require_complete=False):
        queries.append((stage, root, require_complete))
        return ((0.0, 0.0, 1.0), (0.1, 0.1, 1.2))

    monkeypatch.setattr(fabric_utils, "live_world_aabb", live)
    assert phase._compute_required_fall(production_scene.scene) == pytest.approx(0.2)
    assert queries == [(production_scene.stage, "/Asset/body", True)]


def test_physx_drop_height_includes_render_geometry(production_scene):
    phase = _drop_scene(production_scene)
    assert phase._compute_required_fall(production_scene.scene) == pytest.approx(2.0)


@pytest.mark.parametrize(
    "bounds",
    [
        None,
        ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0)),
        ((0.0, 0.0, 0.0), (1.0, 1.0, float("nan"))),
        ((0.0, 0.0, 1.0), (1.0, 1.0, 0.0)),
        ((0.0, 0.0, 0.0), (1.0, 1.0, "1")),
    ],
)
def test_unavailable_or_invalid_drop_bounds_do_not_relax_to_minimum(production_scene, monkeypatch, bounds):
    phase = _drop_scene(production_scene)
    _newton(production_scene)
    monkeypatch.setattr(fabric_utils, "live_world_aabb", lambda *_args, **_kwargs: bounds)
    with pytest.raises(RuntimeError, match="release/drop criterion"):
        phase._compute_required_fall(production_scene.scene)


def test_missing_drop_body_is_required_setup_error(production_scene):
    phase = DroppingPhase({"physics_fps": 240})
    production_scene.scene._scene_properties = {"tracked_body_path": "/Asset/missing"}
    with pytest.raises(RuntimeError, match="release/drop criterion"):
        phase._compute_required_fall(production_scene.scene)


@pytest.fixture
def production_robot(production_scene, monkeypatch):
    isaac = sys.modules["isaacsim"]
    isaac.core.api = ModuleType("isaacsim.core.api")
    isaac.core.api.materials = ModuleType("isaacsim.core.api.materials")
    material = ModuleType("isaacsim.core.api.materials.physics_material")
    material.PhysicsMaterial = SimpleNamespace
    action_module = ModuleType("isaacsim.core.utils.types")
    action_module.ArticulationAction = lambda **kwargs: SimpleNamespace(**kwargs)
    for module in (isaac.core.api, isaac.core.api.materials, material, action_module):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(pxr, "PhysxSchema", SimpleNamespace(), raising=False)
    path = Path(__file__).resolve().parents[3] / "simready/foundation/tier_core/runtime_tests/fet005_grasp/grasp_robot.py"
    spec = importlib.util.spec_from_file_location("_fet005_fixture_robot_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    robot = module.GraspRobot(production_scene.stage)
    return SimpleNamespace(harness=production_scene, module=module, robot=robot)


def _joint(harness, path, state=None, target=0.2):
    joint = UsdPhysics.PrismaticJoint.Define(harness.stage, path)
    UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear").CreateTargetPositionAttr(target)
    if state is not None:
        joint.GetPrim().CreateAttribute("state:linear:physics:position", Sdf.ValueTypeNames.Double).Set(state)
    return joint


def _tensor(robot_harness, positions):
    robot = robot_harness.robot
    actions = []
    robot._dof_index = {
        name: index for index, name in enumerate(("joint_x", "joint_y", "joint_z", "left_joint", "right_joint"))
    }
    robot._targets = np.zeros(5, dtype=np.float64)
    robot._tensor_art = SimpleNamespace(get_joint_positions=lambda: positions, apply_action=actions.append)
    robot_harness.harness.engine.active_physics_engine = lambda: "newton"
    return actions


@pytest.mark.parametrize("method", ["get_gripper_joint_position", "get_finger_joint_positions"])
def test_physx_missing_finger_state_never_substitutes_authored_target_or_zero(production_robot, method):
    robot = production_robot.robot
    _joint(production_robot.harness, robot.LEFT_JOINT, target=0.2)
    _joint(production_robot.harness, robot.GANTRY_X + "/right_joint", target=0.2)
    with pytest.raises(RuntimeError, match="joint readback is unavailable"):
        getattr(robot, method)()


def test_physx_getters_read_actual_state_not_target(production_robot):
    robot = production_robot.robot
    _joint(production_robot.harness, robot.LEFT_JOINT, state=-0.03, target=-0.05)
    _joint(production_robot.harness, robot.GANTRY_X + "/right_joint", state=-0.02, target=-0.05)
    assert robot.get_gripper_joint_position() == -0.03
    assert robot.get_finger_joint_positions() == (-0.03, -0.02)
    assert robot.get_gripper_joint_target() == pytest.approx(-0.05)


@pytest.mark.parametrize("method", ["get_gripper_joint_position", "get_finger_joint_positions"])
def test_newton_without_tensor_control_never_reads_stale_usd_state(production_robot, method):
    robot = production_robot.robot
    _joint(production_robot.harness, robot.LEFT_JOINT, state=-0.03)
    _joint(production_robot.harness, robot.GANTRY_X + "/right_joint", state=-0.02)
    production_robot.harness.engine.active_physics_engine = lambda: "newton"
    with pytest.raises(RuntimeError, match="live tensor control is unavailable"):
        getattr(robot, method)()


@pytest.mark.parametrize(
    "positions",
    [
        None,
        0.0,
        np.zeros((1, 5)),
        np.zeros(4),
        [0.0, 0.0, 0.0, float("nan"), 0.0],
        [0.0, 0.0, 0.0, float("inf"), 0.0],
        np.zeros(5, dtype=bool),
        np.zeros(5, dtype=complex),
        np.zeros(5, dtype=object),
        ["0"] * 5,
    ],
)
@pytest.mark.parametrize("method", ["get_gripper_joint_position", "get_finger_joint_positions"])
def test_tensor_getters_reject_invalid_raw_shape_dtype_and_finiteness(production_robot, positions, method):
    _tensor(production_robot, positions)
    with pytest.raises(RuntimeError, match="tensor"):
        getattr(production_robot.robot, method)()


@pytest.mark.parametrize("method", ["get_gripper_joint_position", "get_finger_joint_positions"])
def test_tensor_getters_preserve_readback_exception(production_robot, method):
    _tensor(production_robot, np.zeros(5))
    cause = OSError("native readback lost")

    def fail():
        raise cause

    production_robot.robot._tensor_art.get_joint_positions = fail
    with pytest.raises(OSError) as caught:
        getattr(production_robot.robot, method)()
    assert caught.value is cause


@pytest.mark.parametrize("index", [True, -1, 1.0, 5, None, 2])
def test_tensor_getter_requires_unambiguous_integer_joint_indices(production_robot, index):
    _tensor(production_robot, np.zeros(5))
    production_robot.robot._dof_index["left_joint"] = index
    with pytest.raises(RuntimeError, match="DOF"):
        production_robot.robot.get_finger_joint_positions()


def test_tensor_getters_preserve_generated_left_right_order(production_robot):
    _tensor(production_robot, np.array([0.0, 1.0, 2.0, -0.03, -0.02], dtype=np.float32))
    assert production_robot.robot.get_gripper_joint_position() == pytest.approx(-0.03)
    assert production_robot.robot.get_finger_joint_positions() == pytest.approx((-0.03, -0.02))


@pytest.mark.parametrize("command", [None, True, "0.1", float("nan"), float("inf"), complex(0.1)])
def test_tensor_commands_reject_invalid_values_before_dispatch_or_target_mutation(production_robot, command):
    actions = _tensor(production_robot, np.zeros(5))
    with pytest.raises(RuntimeError, match="joint value is invalid"):
        production_robot.robot.close(command)
    assert actions == []
    assert np.array_equal(production_robot.robot._targets, np.zeros(5))


def test_tensor_command_missing_dof_is_not_silent_partial_dispatch(production_robot):
    actions = _tensor(production_robot, np.zeros(5))
    production_robot.robot._dof_index["renamed_finger"] = production_robot.robot._dof_index.pop("right_joint")
    with pytest.raises(RuntimeError, match="command DOF is missing"):
        production_robot.robot.close(-0.02)
    assert actions == []
    assert np.array_equal(production_robot.robot._targets, np.zeros(5))


def test_tensor_commands_keep_both_generated_independent_jaws_and_gantry_indices(production_robot):
    actions = _tensor(production_robot, np.zeros(5))
    production_robot.robot.close(-0.02)
    assert actions[-1].joint_indices == [0, 1, 2, 3, 4]
    assert actions[-1].joint_positions == pytest.approx(np.array([0.0, 0.0, 0.0, -0.02, -0.02]))
    production_robot.robot.update_joint_target_positions(0.1, 0.2, 0.3)
    assert actions[-1].joint_positions == pytest.approx(np.array([0.1, 0.2, 0.3, -0.02, -0.02]))


def test_usd_missing_second_drive_does_not_silently_command_first(production_robot):
    robot = production_robot.robot
    _joint(production_robot.harness, robot.LEFT_JOINT, state=-0.03, target=-0.03)
    with pytest.raises(RuntimeError, match="joint is missing"):
        robot.close(-0.05)
    assert robot.get_joint_target(robot.LEFT_JOINT) == pytest.approx(-0.03)


def test_missing_usd_target_is_not_synthetic_zero(production_robot):
    with pytest.raises(RuntimeError, match="joint is missing"):
        production_robot.robot.get_gripper_joint_target()


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [RuntimeError, ImportError])
async def test_simulation_rebuild_errors_are_not_asset_failure_or_skip(production_scene, monkeypatch, error_type):
    harness = production_scene
    _body(harness.stage, "/Asset/body")
    harness.scene._parent_body_path = "/Asset/body"
    cause = error_type("fixture construction unavailable")

    async def fail(*_args, **_kwargs):
        raise cause

    async def step():
        pass

    harness.scene._ctx.physics_step = step
    harness.scene._ctx.step = lambda *_args: None
    tracker = SimpleNamespace(record_frame=lambda *_args: None)
    phases = SimpleNamespace(tracking_active=False, stability_complete=True)
    monkeypatch.setattr(harness.module, "AssetPoseTracker", lambda _fps: tracker)
    monkeypatch.setattr(harness.module, "GraspPhaseManager", lambda _cfg: phases)
    monkeypatch.setattr(harness.scene, "rebuild_gripper_at_settled_position", fail)
    with pytest.raises(error_type) as caught:
        await harness.scene.run_simulation({"physics_fps": 10}, "id", physics=object())
    assert caught.value is cause


@pytest.mark.asyncio
async def test_simulation_required_joint_readback_error_is_not_omitted(production_scene, monkeypatch):
    harness = production_scene
    _body(harness.stage, "/Asset/body")
    harness.scene._parent_body_path = "/Asset/body"
    cause = OSError("native joint observation unavailable")

    def fail():
        raise cause

    async def step():
        pass

    harness.scene._ctx.physics_step = step
    harness.scene._robot = SimpleNamespace(get_finger_joint_positions=fail)
    tracker = SimpleNamespace(
        record_frame=lambda *_args: None, record_finger_positions=lambda *_values, **_kwargs: None
    )
    monkeypatch.setattr(harness.module, "AssetPoseTracker", lambda _fps: tracker)
    monkeypatch.setattr(harness.module, "GraspPhaseManager", lambda _cfg: object())
    with pytest.raises(OSError) as caught:
        await harness.scene.run_simulation({"physics_fps": 10}, "id")
    assert caught.value is cause


def test_required_generated_controller_teardown_propagates_cause_and_clears_bridge(production_robot):
    _tensor(production_robot, np.zeros(5))
    cause = OSError("required native controller cleanup failed")
    calls = []

    def fail(*, required=False):
        calls.append(required)
        raise cause

    production_robot.robot._tensor_art.teardown = fail
    with pytest.raises(OSError) as caught:
        production_robot.robot.teardown()
    assert caught.value is cause
    assert calls == [True]
    assert production_robot.robot._tensor_art is None
    assert production_robot.robot._dof_index == {}
    assert production_robot.robot._targets is None


def test_generated_controller_teardown_success_is_required_and_clears_bridge(production_robot):
    _tensor(production_robot, np.zeros(5))
    calls = []
    production_robot.robot._tensor_art.teardown = lambda *, required=False: calls.append(required)
    production_robot.robot.teardown()
    assert calls == [True]
    assert production_robot.robot._tensor_art is None
    assert production_robot.robot._dof_index == {}
    assert production_robot.robot._targets is None


def test_opening_reports_first_movement_proxy_frame_not_completion_frame(production_scene):
    scene = production_scene.scene
    scene._robot = SimpleNamespace(
        get_gripper_joint_position=lambda: -0.02, close=lambda _target: None, open=lambda: None
    )
    _pads(production_scene)
    phase = OpeningPhase({"physics_fps": 10, "open_duration": 0.2, "release_check_seconds": 1.0})
    tracker = SimpleNamespace(center_history=[(0.0, 0.0, 1.0)])
    for frame in range(10):
        if frame == 5:
            tracker.center_history.append((0.01, 0.0, 1.0))
        assert phase.check_frame(frame, frame / 10.0, scene, tracker) is None
    result = phase.check_frame(10, 1.0, scene, tracker)
    assert result["object_release_frame"] == 5
    assert "movement detected" in result["message"]
    assert "object released" not in result["message"]


@pytest.mark.parametrize(
    "case", ["missing_robot", "missing_points", "invalid_points", "invalid_offset", "missing_live_pose"]
)
def test_positioning_required_setup_errors_are_not_asset_timeout(production_scene, monkeypatch, case):
    harness = production_scene
    harness.scene._robot = object() if case != "missing_robot" else None
    points = None if case == "missing_points" else (np.zeros(3), np.zeros(3))
    if case == "invalid_points":
        points = (np.array(["0", "0", "0"]), np.zeros(3))
    if case == "invalid_offset":
        harness.scene._scene_properties["pad_ground_offset_z"] = True
    monkeypatch.setattr(harness.scene, "get_current_world_grasp_points", lambda: points)
    if case == "missing_live_pose":
        _newton(harness)
        UsdGeom.Xform.Define(harness.stage, harness.module.GraspRobot.GANTRY_X)
        monkeypatch.setattr(fabric_utils, "live_world_matrix", lambda *_args: None)
    phase = GripperPositioningPhase({"physics_fps": 240})
    with pytest.raises(RuntimeError):
        phase.check_frame(0, 0.0, harness.scene, object())
    assert phase._done is False


def test_positioning_uses_live_gantry_and_generated_floor_offset(production_scene, monkeypatch):
    harness = production_scene
    _newton(harness)
    harness.scene._robot = object()
    harness.scene._scene_properties["pad_ground_offset_z"] = 0.02
    UsdGeom.Xform.Define(harness.stage, harness.module.GraspRobot.GANTRY_X)
    monkeypatch.setattr(
        harness.scene, "get_current_world_grasp_points", lambda: (np.array([-0.1, 0.0, 0.0]), np.array([0.1, 0.0, 0.0]))
    )
    matrix = Gf.Matrix4d(1.0)
    matrix.SetTranslate(Gf.Vec3d(0.0, 0.0, 0.02))
    monkeypatch.setattr(fabric_utils, "live_world_matrix", lambda *_args: matrix)
    result = GripperPositioningPhase({"physics_fps": 240}).check_frame(0, 0.0, harness.scene, object())
    assert result["failed"] is False
    assert "dist=0.0000m" in result["message"]


def test_positioning_authored_gantry_at_target_cannot_pass_wrong_live_pose(production_scene, monkeypatch):
    harness = production_scene
    _newton(harness)
    harness.scene._robot = object()
    UsdGeom.Xform.Define(harness.stage, harness.module.GraspRobot.GANTRY_X)
    monkeypatch.setattr(harness.scene, "get_current_world_grasp_points", lambda: (np.zeros(3), np.zeros(3)))
    matrix = Gf.Matrix4d(1.0)
    matrix.SetTranslate(Gf.Vec3d(1.0, 0.0, 0.0))
    monkeypatch.setattr(fabric_utils, "live_world_matrix", lambda *_args: matrix)
    phase = GripperPositioningPhase({"physics_fps": 10})
    assert phase.check_frame(0, 0.0, harness.scene, object()) is None
    result = phase.check_frame(20, 2.0, harness.scene, object())
    assert result["failed"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("cause", [False, OSError("stop rejected"), asyncio.CancelledError("stop requested")])
async def test_rebuild_stop_barrier_fails_closed_before_topology_or_build(production_scene, monkeypatch, cause):
    harness = production_scene
    stage = harness.stage
    path = harness.module.GraspRobot.ROBOT_PATH
    UsdGeom.Xform.Define(stage, path)
    calls = []
    retired = []
    harness.scene._ctx._engine_session = SimpleNamespace(record_required_cleanup_failure=retired.append)
    monkeypatch.setattr(harness.scene, "get_current_world_grasp_points", lambda: (np.zeros(3), np.ones(3)))

    def stop():
        calls.append("stop")
        if isinstance(cause, BaseException):
            raise cause
        return cause

    physics = SimpleNamespace(stop=stop, play=lambda: calls.append("play"))
    expected = type(cause) if isinstance(cause, BaseException) else RuntimeError
    with pytest.raises(expected) as caught:
        await harness.scene.rebuild_gripper_at_settled_position(physics)
    if isinstance(cause, BaseException):
        assert caught.value is cause
    assert stage.GetPrimAtPath(path)
    assert calls == ["stop"]
    assert retired == ["Required FET005 rebuild physics stop failed."]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["not_owned", "wrong_layer", "stronger_opinion", "teardown_error"])
async def test_rebuild_requires_owned_removal_ack_and_composed_absence(production_scene, monkeypatch, case):
    harness = production_scene
    stage = harness.stage
    path = harness.module.GraspRobot.ROBOT_PATH
    UsdGeom.Xform.Define(stage, path)
    retired = []
    harness.scene._ctx._engine_session = SimpleNamespace(record_required_cleanup_failure=retired.append)
    monkeypatch.setattr(harness.scene, "get_current_world_grasp_points", lambda: (np.zeros(3), np.ones(3)))
    physics = SimpleNamespace(stop=lambda: None, play=lambda: pytest.fail("unsafe restart"))
    if case != "not_owned":
        target = stage.GetEditTarget()
        if case in ("wrong_layer", "stronger_opinion"):
            layer = Sdf.Layer.CreateAnonymous("owned-fixture-layer")
            stage.GetRootLayer().subLayerPaths.append(layer.identifier)
            target = Usd.EditTarget(layer)
            if case == "stronger_opinion":
                with Usd.EditContext(stage, target):
                    UsdGeom.Xform.Define(stage, path)
        harness.scene._robot = SimpleNamespace(_edit_target=target, teardown=lambda: None)
        if case == "teardown_error":

            def fail():
                raise OSError("native controller removal failed")

            harness.scene._robot.teardown = fail
    with pytest.raises((RuntimeError, OSError)):
        await harness.scene.rebuild_gripper_at_settled_position(physics)
    assert stage.GetPrimAtPath(path)
    assert retired == ["Required FET005 old gripper removal failed."]


@pytest.mark.asyncio
async def test_rebuild_verified_owned_removal_precedes_new_fixture_construction(production_scene, monkeypatch):
    harness = production_scene
    stage = harness.stage
    path = harness.module.GraspRobot.ROBOT_PATH
    UsdGeom.Xform.Define(stage, path)
    calls = []
    harness.scene._robot = SimpleNamespace(
        _edit_target=stage.GetEditTarget(), teardown=lambda: calls.append("teardown")
    )
    monkeypatch.setattr(harness.scene, "get_current_world_grasp_points", lambda: (np.zeros(3), np.ones(3)))
    physics = SimpleNamespace(
        stop=lambda: calls.append("stop"), play=lambda: pytest.fail("restart after construction failure")
    )
    cause = ValueError("fixture construction error")

    async def build(**_kwargs):
        assert not stage.GetPrimAtPath(path)
        calls.append("build")
        raise cause

    monkeypatch.setattr(harness.module.GraspRobot, "build_for_asset", build, raising=False)
    with pytest.raises(ValueError) as caught:
        await harness.scene.rebuild_gripper_at_settled_position(physics)
    assert caught.value is cause
    assert calls == ["stop", "teardown", "build"]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["native_error", "missing_dof", "duplicate_dof"])
async def test_newton_partial_initialization_retains_handle_for_required_cleanup(production_robot, monkeypatch, case):
    created = []
    calls = []
    cause = OSError("native initialization failed")

    class RobotHandle:
        def __init__(self, *_args):
            created.append(self)
            self.dof_names = ["joint_x", "joint_y", "joint_z", "left_joint", "right_joint"]
            if case == "missing_dof":
                self.dof_names.pop()
            elif case == "duplicate_dof":
                self.dof_names.append("right_joint")

        async def initialize_newton(self, _ctx):
            self.manager_created = True
            if case == "native_error":
                raise cause

        def teardown(self, *, required=False):
            calls.append(required)
            self.manager_created = False

    module = ModuleType("simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle")
    module.RobotHandle = RobotHandle
    monkeypatch.setitem(sys.modules, module.__name__, module)
    expected = OSError if case == "native_error" else RuntimeError
    with pytest.raises(expected) as caught:
        await production_robot.robot.init_newton_tensor_drive(object())
    if case == "native_error":
        assert caught.value is cause
    assert production_robot.robot._tensor_art is created[0]
    assert created[0].manager_created is True
    assert production_robot.robot._targets is None
    with pytest.raises(RuntimeError, match="control is unavailable"):
        production_robot.robot.close(-0.01)
    production_robot.robot.teardown()
    assert calls == [True]
    assert created[0].manager_created is False


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_read", ["pose", "joint", "tracking"])
async def test_post_failure_observation_error_limits_tail_without_replacing_measured_fail(
    production_scene, monkeypatch, failed_read
):
    harness = production_scene
    _body(harness.stage, "/Asset/body")
    harness.scene._parent_body_path = "/Asset/body"
    ticks = []
    advances = []
    warnings = []
    cause = OSError("post-failure diagnostic unavailable")

    async def step():
        ticks.append("step")

    async def advance():
        advances.append("advance")

    def observe(*_args):
        if failed_read == "pose" and len(ticks) > 1:
            raise cause

    def joint():
        if failed_read == "joint" and len(ticks) > 1:
            raise cause
        return (0.0, 0.0)

    def tracking():
        if failed_read == "tracking" and len(ticks) > 1:
            raise cause

    tracker = SimpleNamespace(
        record_frame=observe, record_finger_positions=lambda *_values, **_kwargs: None, center_history=[(0.0, 0.0, 1.0)]
    )
    phases = SimpleNamespace(
        tracking_active=failed_read == "tracking",
        stability_complete=False,
        current_phase_name="Grasping",
        capture_active=False,
        check_frame=lambda frame, time, *_args: {
            "failed": True,
            "phase_name": "Grasping",
            "message": "measured empty grasp",
            "frame": frame,
            "time": time,
        },
    )
    harness.scene._ctx.physics_step = step
    harness.scene._ctx.physics_advance = advance
    harness.scene._ctx.warn = warnings.append
    harness.scene._ctx.step = lambda *_args: None
    harness.scene._ctx.add_metric = lambda *_args: None
    harness.scene._ctx.scene = SimpleNamespace(update_camera_follow=lambda **_kwargs: None)
    if failed_read == "joint":
        harness.scene._robot = SimpleNamespace(get_finger_joint_positions=joint)
    monkeypatch.setattr(harness.module, "AssetPoseTracker", lambda _fps: tracker)
    monkeypatch.setattr(harness.module, "GraspPhaseManager", lambda _cfg: phases)
    monkeypatch.setattr(harness.scene, "track_grasp_line", tracking)
    result = await harness.scene.run_simulation({"physics_fps": 1, "capture_fps": 1, "simulation_seconds": 3.0}, "id")
    assert result["failed"] is True
    assert result["message"] == "measured empty grasp"
    assert result["failure_observation_limited"] is True
    assert result["failure_observation_end_frame"] == 0
    assert ticks == ["step", "step"]
    assert advances == ["advance"]
    assert any("Post-failure" in warning for warning in warnings)


@pytest.mark.parametrize("sink", ["log", "add_metric"])
def test_optional_fixture_reporting_failure_does_not_suppress_required_execution(production_scene, sink):
    harness = production_scene
    harness.scene._scene_properties["gripper_pad_properties"] = {
        "mass_source": "authored",
        "authored_mass_count": 1,
        "mass": 0.1,
        "max_force": 1.0,
    }

    def fail(*_args):
        raise OSError("optional reporting unavailable")

    harness.scene._ctx.warn = lambda *_args: None
    harness.scene._ctx.add_metric = lambda *_args: None
    setattr(harness.scene._ctx, sink, fail)
    harness.scene._report_fixture_load("id")
    assert harness.scene._diagnostic_failures == {"fixture load report"}


@pytest.mark.parametrize("case", ["nan", "infinity", "coincident", "non_real"])
def test_authored_grasp_segment_rejects_invalid_points_before_fixture_creation(production_scene, case):
    harness = production_scene
    marker = UsdGeom.Xform.Define(harness.stage, harness.scene.grasp_identifier_path)
    if case == "non_real":
        child = harness.stage.DefinePrim(str(marker.GetPath()) + "/line", "Scope")
        child.CreateAttribute("points", Sdf.ValueTypeNames.StringArray).Set(["zero", "one"])
    else:
        value = {"nan": float("nan"), "infinity": float("inf"), "coincident": 0.0}[case]
        points = UsdGeom.Points.Define(harness.stage, str(marker.GetPath()) + "/line")
        points.CreatePointsAttr([Gf.Vec3f(0.0), Gf.Vec3f(value, 0.0, 0.0)])
    with pytest.raises(RuntimeError, match="Authored grasp segment is invalid"):
        harness.scene._extract_world_grasp_points()
    assert harness.scene.robot is None
    assert not harness.stage.GetPrimAtPath(harness.module.GraspRobot.ROBOT_PATH)


@pytest.mark.parametrize("purpose", [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy])
def test_fixture_pad_sizing_accepts_same_qualified_geometry_purposes(production_robot, monkeypatch, purpose):
    harness = production_robot.harness
    body = _body(harness.stage, "/Asset/body")
    UsdPhysics.MassAPI.Apply(body).CreateMassAttr(0.1)
    cube = UsdGeom.Cube.Define(harness.stage, "/Asset/body/geometry")
    cube.CreateSizeAttr(0.1)
    cube.CreatePurposeAttr(purpose)
    monkeypatch.setattr(production_robot.module.carb, "log_info", lambda _message: None, raising=False)

    props = production_robot.robot._compute_pad_properties("/Asset", "/Asset/body")

    assert props["asset_bbox_size_m"] == pytest.approx((0.1, 0.1, 0.1))
    assert props["scale"] == pytest.approx(0.01)
    assert props["mass"] == pytest.approx(0.1)
    assert props["mass_source"] == "authored_mass_api"
    assert props["max_force"] == pytest.approx(0.1 * 9.81 * 5.0)


def test_optional_native_fixture_log_failure_does_not_change_mass_or_force(production_robot, monkeypatch):
    harness = production_robot.harness
    body = _body(harness.stage, "/Asset/body")
    UsdPhysics.MassAPI.Apply(body).CreateMassAttr(0.1)
    UsdGeom.Cube.Define(harness.stage, "/Asset/body/geometry").CreateSizeAttr(0.1)

    def fail(_message):
        raise OSError("optional native logger unavailable")

    monkeypatch.setattr(production_robot.module.carb, "log_info", fail, raising=False)
    props = production_robot.robot._compute_pad_properties("/Asset", "/Asset/body")
    assert props["mass"] == pytest.approx(0.1)
    assert props["max_force"] == pytest.approx(0.1 * 9.81 * 5.0)
