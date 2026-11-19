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
"""Required-state and reference-frame regressions for the official Core tracker."""

import pytest
from pxr import Gf, Usd, UsdGeom
from test_fet004_joint_movement import joint_movement as _joint_movement_fixture


@pytest.fixture
def joint_movement(monkeypatch):
    return _joint_movement_fixture.__wrapped__(monkeypatch)


@pytest.mark.parametrize("scale", [Gf.Vec3d(2), Gf.Vec3d(2, 3, 4), Gf.Vec3d(1e-6)])
@pytest.mark.parametrize("angle", [30.0, 90.0, 179.0])
def test_scaled_child_rotation_is_measured_without_scale_contaminating_quaternion(joint_movement, scale, angle):
    initial = Gf.Matrix4d().SetScale(scale)
    current = initial * Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), angle))
    assert joint_movement._measure_relative_rotation_deg(initial, current) == pytest.approx(angle, abs=1e-8)


@pytest.mark.parametrize("bad", [None, Gf.Matrix4d(0), Gf.Matrix4d(float("nan"))])
@pytest.mark.parametrize("measurement", ["_measure_relative_rotation_deg", "_measure_relative_translation"])
def test_direct_required_measurement_rejects_missing_or_invalid_transform(joint_movement, bad, measurement):
    with pytest.raises(RuntimeError, match="required relative .* measurement failed"):
        getattr(joint_movement, measurement)(Gf.Matrix4d(1), bad)


@pytest.mark.parametrize("bad_quat", [Gf.Quatd(0, Gf.Vec3d(0)), Gf.Quatd(float("nan"), Gf.Vec3d(0))])
def test_invalid_decomposed_rotation_does_not_become_zero(joint_movement, monkeypatch, bad_quat):
    monkeypatch.setattr(Gf.Matrix4d, "ExtractRotationQuat", lambda *_: bad_quat)
    with pytest.raises(RuntimeError, match="required relative rotation measurement failed"):
        joint_movement._measure_relative_rotation_deg(Gf.Matrix4d(1), Gf.Matrix4d(1))


@pytest.mark.parametrize("scale", [Gf.Vec3d(1e-6, 1, 1), Gf.Vec3d(1e-9, 1, 1), Gf.Vec3d(1e6, 1, 1)])
def test_anisotropic_arbitrary_axis_rotation_cannot_silently_become_identity(joint_movement, scale):
    initial = Gf.Matrix4d().SetScale(scale)
    current = initial * Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(1, 1, 1), 90))
    assert joint_movement._measure_relative_rotation_deg(initial, current) == pytest.approx(90.0, abs=1e-8)


@pytest.mark.parametrize(
    "rotation", [Gf.Matrix4d().SetScale(Gf.Vec3d(2, 1, 1)), Gf.Matrix4d().SetScale(Gf.Vec3d(-1, 1, 1))]
)
def test_unqualified_rotation_factor_is_execution_error_not_zero_motion(joint_movement, monkeypatch, rotation):
    monkeypatch.setattr(
        Gf.Matrix4d, "Factor", lambda *_: (True, Gf.Matrix4d(1), Gf.Vec3d(1), rotation, Gf.Vec3d(0), Gf.Matrix4d(1))
    )
    with pytest.raises(RuntimeError, match="required relative rotation measurement failed"):
        joint_movement._measure_relative_rotation_deg(Gf.Matrix4d(1), Gf.Matrix4d(1))


def test_common_parent_motion_is_not_relative_child_motion(joint_movement):
    parent_start = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), 30))
    parent_start.SetTranslateOnly(Gf.Vec3d(5, 2, 0))
    local = Gf.Matrix4d().SetTranslate(Gf.Vec3d(1, 0, 0))
    parent_now = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), 90))
    parent_now.SetTranslateOnly(Gf.Vec3d(9, 7, 0))
    reference = joint_movement._compute_relative_transform(parent_start, local * parent_start)
    current = joint_movement._compute_relative_transform(parent_now, local * parent_now)
    assert joint_movement._measure_relative_translation(reference, current) == pytest.approx(0, abs=1e-12)
    assert joint_movement._measure_relative_rotation_deg(reference, current) == pytest.approx(0, abs=1e-5)


@pytest.mark.parametrize("bad", [None, Gf.Matrix4d(0), Gf.Matrix4d(float("nan"))])
def test_unavailable_or_invalid_parent_is_not_world_frame_fallback(joint_movement, bad):
    with pytest.raises(RuntimeError, match="required transform"):
        joint_movement._compute_relative_transform(bad, Gf.Matrix4d(1))


def test_missing_body_prim_is_runtime_error(joint_movement):
    with pytest.raises(RuntimeError, match="required body transform unavailable"):
        joint_movement._get_world_matrix(Usd.Stage.CreateInMemory(), "/missing")


def test_valid_small_scale_is_not_rejected_by_arbitrary_determinant_epsilon(joint_movement):
    matrix = Gf.Matrix4d().SetScale(Gf.Vec3d(1e-6))
    assert joint_movement._require_transform(matrix, "body") == matrix


def test_world_attached_joint_remains_supported(joint_movement):
    stage = Usd.Stage.CreateInMemory()
    body = UsdGeom.Xform.Define(stage, "/body")
    translation = body.AddTranslateOp()
    translation.Set(Gf.Vec3d(0))
    UsdGeom.Cube.Define(stage, "/body/mesh").CreateSizeAttr(0.01)
    tracker = joint_movement.JointTracker(stage, {"name": "world_joint", "child_body_path": "/body"})
    translation.Set(Gf.Vec3d(0.1, 0, 0))
    tracker.update()
    assert tracker.max_trans_m == pytest.approx(0.1)


@pytest.mark.parametrize("scale", [1e-12, 1e-6, 0.01, 1.0, 100.0])
def test_translation_percentage_uses_same_world_scale_as_child_bounds(joint_movement, scale):
    stage = Usd.Stage.CreateInMemory()
    parent = UsdGeom.Xform.Define(stage, "/parent")
    parent.AddScaleOp().Set(Gf.Vec3d(scale))
    child = UsdGeom.Xform.Define(stage, "/parent/child")
    translation = child.AddTranslateOp()
    translation.Set(Gf.Vec3d(0))
    UsdGeom.Cube.Define(stage, "/parent/child/mesh").CreateSizeAttr(0.01)
    tracker = joint_movement.JointTracker(
        stage, {"name": "j", "parent_body_path": "/parent", "child_body_path": "/parent/child"}
    )
    translation.Set(Gf.Vec3d(0.001, 0, 0))
    tracker.update()
    assert tracker.max_trans_m == pytest.approx(0.001 * scale)
    assert tracker.result()["translation_pct"] == pytest.approx(5.77)
    assert tracker.result()["moved"] is True
    assert tracker.result()["translation_unit"] == "stage_length"
    assert tracker.result()["translation_basis"] == "frozen_reference_world"
    assert tracker.result()["bbox_diagonal_unit"] == "stage_length"
    assert tracker.result()["translation_stage_units"] == tracker.max_trans_m
    assert tracker.result()["translation_stage_units"] == pytest.approx(0.001 * scale, rel=1e-6, abs=0.0)
    assert tracker.result()["translation_stage_units"] > 0.0
    assert tracker.result()["bbox_diagonal_stage_units"] > 0.0
    assert tracker.result()["bbox_diagonal_stage_units"] == tracker._bbox_diag
    assert tracker.result()["bbox_diagonal_stage_units"] == pytest.approx(3.0**0.5 * 0.01 * scale, rel=1e-6, abs=0.0)


@pytest.mark.parametrize("case", ["missing", "empty", "zero", "nan", "infinite"])
def test_required_child_bounds_are_not_a_fabricated_normalization(joint_movement, case):
    stage = Usd.Stage.CreateInMemory()
    body = UsdGeom.Xform.Define(stage, "/body")
    if case in ("zero", "nan", "infinite"):
        size = {"zero": 0.0, "nan": float("nan"), "infinite": float("inf")}[case]
        mesh = UsdGeom.Cube.Define(stage, "/body/mesh")
        mesh.CreateSizeAttr(size)
        # Explicit malformed bounds must not be repaired by a computed extent.
        if case in ("nan", "infinite"):
            mesh.CreateExtentAttr([Gf.Vec3f(-size), Gf.Vec3f(size)])
    path = "/missing" if case == "missing" else str(body.GetPath())
    with pytest.raises(RuntimeError, match="required child bounds unavailable"):
        joint_movement._get_bbox_diagonal(stage, path)


@pytest.mark.parametrize("purpose", ["default", "render", "proxy"])
def test_required_child_bound_covers_declared_visual_and_collision_purposes(joint_movement, purpose):
    stage = Usd.Stage.CreateInMemory()
    body = UsdGeom.Xform.Define(stage, "/body")
    translation = body.AddTranslateOp()
    translation.Set(Gf.Vec3d(0))
    mesh = UsdGeom.Cube.Define(stage, "/body/mesh")
    mesh.CreateSizeAttr(0.01)
    mesh.CreatePurposeAttr(purpose)
    tracker = joint_movement.JointTracker(stage, {"name": "j", "child_body_path": "/body"})
    translation.Set(Gf.Vec3d(0.001, 0, 0))
    tracker.update()
    result = tracker.result()
    assert result["bbox_purposes"] == ["default", "render", "proxy"]
    assert result["translation_pct"] == pytest.approx(5.77)
    assert result["moved"] is True


def test_translation_components_use_frozen_parent_basis_without_common_motion(joint_movement):
    parent_reference = Gf.Matrix4d().SetScale(Gf.Vec3d(2, 3, 4))
    parent_reference *= Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), 90))
    parent_reference.SetTranslateOnly(Gf.Vec3d(10, 20, 30))
    local_reference = Gf.Matrix4d().SetTranslate(Gf.Vec3d(1, 0, 0))
    local_now = Gf.Matrix4d().SetTranslate(Gf.Vec3d(1.01, 0, 0))
    parent_now = Gf.Matrix4d().SetScale(Gf.Vec3d(2, 3, 4))
    parent_now *= Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), 160))
    parent_now.SetTranslateOnly(Gf.Vec3d(100, -20, -30))
    reference = joint_movement._compute_relative_transform(parent_reference, local_reference * parent_reference)
    current = joint_movement._compute_relative_transform(parent_now, local_now * parent_now)
    delta = joint_movement._relative_translation_delta(reference, current, parent_reference)
    assert tuple(delta) == pytest.approx((0.0, 0.02, 0.0), abs=1e-12)
    assert joint_movement._measure_relative_translation(reference, current, parent_reference) == pytest.approx(0.02)


def test_observer_translation_components_match_scaled_verdict_basis(joint_movement):
    from types import SimpleNamespace

    stage = Usd.Stage.CreateInMemory()
    parent = UsdGeom.Xform.Define(stage, "/parent")
    parent.AddScaleOp().Set(Gf.Vec3d(2, 3, 4))
    parent.AddRotateZOp().Set(90)
    child = UsdGeom.Xform.Define(stage, "/parent/child")
    translation = child.AddTranslateOp()
    translation.Set(Gf.Vec3d(0))
    UsdGeom.Cube.Define(stage, "/parent/child/mesh").CreateSizeAttr(0.01)
    samples = []
    history = SimpleNamespace(
        sample=lambda _time, values, **_kwargs: samples.append(values),
        mark_partial=lambda reason: pytest.fail(reason),
    )
    ctx = SimpleNamespace(
        config={"physics_fps": 240},
        begin_motion_history=lambda *_args, **_kwargs: history,
        warn=lambda reason: pytest.fail(reason),
    )
    tracker = joint_movement.JointTracker(
        stage,
        {"name": "j", "prim_path": "/joint", "parent_body_path": "/parent", "child_body_path": "/parent/child"},
        ctx,
    )
    translation.Set(Gf.Vec3d(0.001, 0, 0))
    tracker.update()
    assert samples[0]["translation_delta"] == pytest.approx(tracker.max_trans_m)
    assert samples[0]["translation_x"] == pytest.approx(0.0, abs=1e-12)
    # USD's authored op order rotates local X onto the Y-scaled world axis.
    assert samples[0]["translation_y"] == pytest.approx(0.003)
    assert samples[0]["translation_z"] == pytest.approx(0.0, abs=1e-12)


def test_exact_measurements_survive_accumulation_native_metrics_and_event_summary(joint_movement):
    from types import SimpleNamespace

    stage = Usd.Stage.CreateInMemory()
    parent = UsdGeom.Xform.Define(stage, "/parent")
    parent.AddScaleOp().Set(Gf.Vec3d(1e-6))
    child = UsdGeom.Xform.Define(stage, "/parent/child")
    translation = child.AddTranslateOp()
    translation.Set(Gf.Vec3d(0))
    UsdGeom.Cube.Define(stage, "/parent/child/mesh").CreateSizeAttr(0.01)
    joint = {"name": "tiny_joint", "parent_body_path": "/parent", "child_body_path": "/parent/child"}
    tracker = joint_movement.JointTracker(stage, joint)
    translation.Set(Gf.Vec3d(0.001, 0, 0))
    tracker.update()
    accumulated = {}
    joint_movement._accumulate([joint], {joint["name"]: tracker}, accumulated)
    measurement = accumulated[joint["name"]]
    assert measurement["translation_m"] == 0.0  # compatible rounded alias
    assert measurement["translation_stage_units"] == tracker.max_trans_m > 0.0
    metrics = {}
    ctx = SimpleNamespace(add_metric=lambda key, value: metrics.update({key: value}))
    joint_movement._publish_joint_measurements(ctx, joint["name"], measurement)
    summary = joint_movement._joint_result_summary(joint, measurement, True)
    assert summary["translation_stage_units"] == metrics["jm_joint_tiny_joint_translation_stage_units"] > 0.0
    assert summary["bbox_diagonal_stage_units"] == metrics["jm_joint_tiny_joint_bbox_diagonal_stage_units"] > 0.0
    assert summary["translation_unit"] == metrics["jm_joint_tiny_joint_translation_unit"] == "stage_length"
    assert summary["translation_basis"] == metrics["jm_joint_tiny_joint_translation_basis"] == "frozen_reference_world"
    assert summary["translation_evidence_basis"] == "trial_with_maximum_normalized_translation"
    assert summary["bbox_purposes"] == ["default", "render", "proxy"]


def test_accumulated_raw_numerator_and_denominator_remain_one_observed_trial(joint_movement):
    from types import SimpleNamespace

    def result(distance, diagonal):
        return {
            "rotation_deg": 0.0,
            "translation_pct": round(distance / diagonal * 100, 2),
            "translation_m": round(distance, 4),
            "bbox_diag_m": round(diagonal, 4),
            "moved": True,
            "translation_stage_units": distance,
            "bbox_diagonal_stage_units": diagonal,
            "translation_unit": "stage_length",
            "translation_basis": "frozen_reference_world",
            "bbox_diagonal_unit": "stage_length",
            "bbox_purposes": ["default", "render", "proxy"],
        }

    joint = {"name": "joint"}
    trials = [result(1e-9, 1e-8), result(1e-8, 1e-6), result(2e-9, 1e-8)]
    accumulated = {}
    for trial in trials:
        tracker = SimpleNamespace(result=lambda trial=trial: trial)
        joint_movement._accumulate([joint], {"joint": tracker}, accumulated)
    final = accumulated["joint"]
    assert final["translation_pct"] == 20.0
    assert final["translation_stage_units"] == 2e-9
    assert final["bbox_diagonal_stage_units"] == 1e-8


def test_unobserved_joint_event_has_no_invented_raw_measurements(joint_movement):
    summary = joint_movement._joint_result_summary({"name": "joint"}, {}, False)
    assert summary["translation_stage_units"] is None
    assert summary["bbox_diagonal_stage_units"] is None
    assert summary["translation_evidence_basis"] is None


def test_duplicate_authored_joint_names_keep_distinct_motion_and_public_evidence(joint_movement):
    from types import SimpleNamespace

    from pxr import UsdPhysics

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Asset")
    translations = []
    for branch in ("first", "second"):
        UsdGeom.Xform.Define(stage, "/Asset/" + branch)
        base_path, child_path = f"/Asset/{branch}/base", f"/Asset/{branch}/child"
        base = UsdGeom.Xform.Define(stage, base_path)
        child = UsdGeom.Xform.Define(stage, child_path)
        UsdPhysics.RigidBodyAPI.Apply(base.GetPrim())
        UsdPhysics.RigidBodyAPI.Apply(child.GetPrim())
        translation = child.AddTranslateOp()
        translation.Set(Gf.Vec3d(0))
        translations.append(translation)
        UsdGeom.Cube.Define(stage, child_path + "/mesh").CreateSizeAttr(0.01)
        joint = UsdPhysics.RevoluteJoint.Define(stage, f"/Asset/{branch}/hinge")
        joint.CreateBody0Rel().SetTargets([base_path])
        joint.CreateBody1Rel().SetTargets([child_path])
    joints = joint_movement._qualify_joint_identities(joint_movement.discover_joints(stage, "/Asset"))
    assert len({joint["name"] for joint in joints}) == 2
    assert all(joint["authored_name"] == "hinge" for joint in joints)
    trackers = {joint["name"]: joint_movement.JointTracker(stage, joint) for joint in joints}
    translations[0].Set(Gf.Vec3d(0.001, 0, 0))
    for tracker in trackers.values():
        tracker.update()
    accumulated = {}
    joint_movement._accumulate(joints, trackers, accumulated)
    assert len(accumulated) == 2
    assert sum(measurement["moved"] for measurement in accumulated.values()) == 1
    metrics = {}
    ctx = SimpleNamespace(add_metric=lambda key, value: metrics.update({key: value}))
    event = {}
    for joint in joints:
        measurement = accumulated[joint["name"]]
        joint_movement._publish_joint_measurements(ctx, joint["name"], measurement)
        event[joint["name"]] = joint_movement._joint_result_summary(joint, measurement, measurement["moved"])
    assert len(event) == 2
    assert {row["prim_path"] for row in event.values()} == {"/Asset/first/hinge", "/Asset/second/hinge"}
    assert sum(row["moved"] for row in event.values()) == 1
    assert len([key for key in metrics if key.endswith("translation_stage_units")]) == 2
    # The aliases depend on the authored paths, not input discovery order.
    again = list(reversed(joint_movement.discover_joints(stage, "/Asset")))
    joint_movement._qualify_joint_identities(again)
    assert {joint["prim_path"]: joint["name"] for joint in again} == {
        joint["prim_path"]: joint["name"] for joint in joints
    }


def test_unique_authored_joint_names_keep_their_compatible_public_identity(joint_movement):
    joints = [{"name": "hinge", "prim_path": "/Asset/hinge"}, {"name": "slide", "prim_path": "/Asset/slide"}]
    assert joint_movement._qualify_joint_identities(joints) == joints
    assert [joint["name"] for joint in joints] == ["hinge", "slide"]
