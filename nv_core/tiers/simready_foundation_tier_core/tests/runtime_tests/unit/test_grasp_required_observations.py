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
import numpy as np
import pytest
from pxr import Usd, UsdGeom
from simready.evaluate_engine_kit import fabric_utils, physics_utils
from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_utils import AssetPoseTracker


def _body():
    stage = Usd.Stage.CreateInMemory()
    return stage, UsdGeom.Cube.Define(stage, "/Asset").GetPrim()


def _assert_unchanged(tracker, before):
    assert (tracker.center_history, tracker.min_z_history, tracker.times, tracker.pose_source) == before


def _snapshot(tracker):
    return (list(tracker.center_history), list(tracker.min_z_history), list(tracker.times), tracker.pose_source)


def test_newton_tracker_requests_complete_live_bounds(monkeypatch):
    stage, body = _body()
    calls = []
    monkeypatch.setattr(physics_utils, "active_physics_engine", lambda: "newton")

    def read(stage, root, select, require_complete=False):
        calls.append((stage, root, select, require_complete))
        return (-2.0, -4.0, -6.0), (4.0, 6.0, 8.0)

    monkeypatch.setattr(fabric_utils, "live_world_aabb", read)
    tracker = AssetPoseTracker(240)
    tracker.record_frame(body, 1.25)
    assert calls == [(body.GetStage(), "/Asset", fabric_utils.is_rigid_body, True)]
    assert tracker.center_history == [(1.0, 1.0, 1.0)]
    assert tracker.min_z_history == [-6.0]
    assert tracker.times == [1.25]
    assert tracker.pose_source == "fabric"


@pytest.mark.parametrize("with_prior", [False, True])
@pytest.mark.parametrize("failed_read", [None, RuntimeError("native geometry read failed")])
def test_newton_tracker_never_substitutes_usd_zero_or_prior_pose(monkeypatch, with_prior, failed_read):
    stage, body = _body()
    monkeypatch.setattr(physics_utils, "active_physics_engine", lambda: "newton")

    def read(*_args, **_kwargs):
        if isinstance(failed_read, BaseException):
            raise failed_read
        return failed_read

    monkeypatch.setattr(fabric_utils, "live_world_aabb", read)
    monkeypatch.setattr(UsdGeom, "BBoxCache", lambda *_args: pytest.fail("Authored fallback must not run"))
    tracker = AssetPoseTracker(240)
    if with_prior:
        tracker.center_history.append((1.0, 2.0, 3.0))
        tracker.min_z_history.append(2.0)
        tracker.times.append(0.1)
        tracker.pose_source = "fabric"
    before = _snapshot(tracker)
    with pytest.raises(RuntimeError) as captured:
        tracker.record_frame(body, 0.2)
    if failed_read is not None:
        assert captured.value is failed_read
    _assert_unchanged(tracker, before)


@pytest.mark.parametrize(
    "bound",
    [
        ((0.0, 1.0), (2.0, 3.0)),
        ((0.0, 0.0, 0.0), (float("nan"), 1.0, 1.0)),
        ((0.0, 0.0, 0.0), (float("inf"), 1.0, 1.0)),
        ((2.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
        ((False, 0.0, 0.0), (1.0, 1.0, 1.0)),
        (("0", 0.0, 0.0), (1.0, 1.0, 1.0)),
        (np.zeros(3, dtype=complex), np.ones(3, dtype=complex)),
        (np.zeros(3, dtype=object), np.ones(3, dtype=object)),
        (np.zeros(3, dtype=bool), np.ones(3, dtype=bool)),
    ],
)
def test_newton_tracker_rejects_malformed_original_bounds_atomically(monkeypatch, bound):
    stage, body = _body()
    monkeypatch.setattr(physics_utils, "active_physics_engine", lambda: "newton")
    monkeypatch.setattr(fabric_utils, "live_world_aabb", lambda *_args, **_kwargs: bound)
    tracker = AssetPoseTracker(240)
    before = _snapshot(tracker)
    with pytest.raises((ValueError, TypeError)):
        tracker.record_frame(body, 0.1)
    _assert_unchanged(tracker, before)


def test_physx_tracker_records_validated_current_usd_bound(monkeypatch):
    monkeypatch.setattr(physics_utils, "active_physics_engine", lambda: "physx")
    stage, body = _body()
    tracker = AssetPoseTracker(240)
    tracker.record_frame(body, 0.1)
    assert tracker.center_history == [(0.0, 0.0, 0.0)]
    assert tracker.min_z_history == [-1.0]
    assert tracker.pose_source == "usd"


@pytest.mark.parametrize("read_error", [RuntimeError("USD query failed"), ValueError("Invalid bound")])
def test_physx_read_errors_propagate_without_history(monkeypatch, read_error):
    stage, body = _body()
    monkeypatch.setattr(physics_utils, "active_physics_engine", lambda: "physx")

    def read(*_args):
        raise read_error

    monkeypatch.setattr(UsdGeom, "BBoxCache", read)
    tracker = AssetPoseTracker(240)
    with pytest.raises(type(read_error)) as captured:
        tracker.record_frame(body, 0.1)
    assert captured.value is read_error
    assert tracker.center_history == tracker.min_z_history == tracker.times == []


def test_physx_empty_bounds_are_execution_error(monkeypatch):
    monkeypatch.setattr(physics_utils, "active_physics_engine", lambda: "physx")
    stage = Usd.Stage.CreateInMemory()
    prim = UsdGeom.Xform.Define(stage, "/Empty").GetPrim()
    with pytest.raises(fabric_utils.LiveBoundsReadError, match="empty"):
        AssetPoseTracker(240).record_frame(prim, 0.1)


@pytest.mark.parametrize("invalid_body", [None, Usd.Prim()])
def test_unavailable_grasp_body_does_not_create_zero_pose(invalid_body):
    tracker = AssetPoseTracker(240)
    with pytest.raises(fabric_utils.LiveBoundsReadError, match="body is unavailable"):
        tracker.record_frame(invalid_body, 0.1)
    assert tracker.center_history == tracker.min_z_history == tracker.times == []


@pytest.mark.parametrize("value", [None, True, "0", 1j, float("nan"), float("inf"), np.bool_(False), np.array(1.0)])
def test_tracker_rejects_invalid_time_before_query(monkeypatch, value):
    stage, body = _body()
    monkeypatch.setattr(physics_utils, "active_physics_engine", lambda: "newton")
    monkeypatch.setattr(fabric_utils, "live_world_aabb", lambda *_args, **_kwargs: pytest.fail("Must not query"))
    with pytest.raises(ValueError, match="Observation time"):
        AssetPoseTracker(240).record_frame(body, value)


@pytest.mark.parametrize("value", [None, True, "0", 1j, float("nan"), float("inf"), np.bool_(False), np.array(1.0)])
def test_tracker_rejects_invalid_joint_values_without_coercion(value):
    tracker = AssetPoseTracker(240)
    with pytest.raises(ValueError, match="Finger joint position"):
        tracker.record_joint_position(value)
    assert tracker.joint_positions == []


def test_tracker_empty_joint_history_is_not_zero_observation():
    with pytest.raises(RuntimeError, match="history is unavailable"):
        AssetPoseTracker(240).get_most_closed_joint_position()


@pytest.mark.parametrize("value", [-0.5, np.float32(-0.75), np.float64(-0.25)])
def test_tracker_accepts_finite_real_joint_observations(value):
    tracker = AssetPoseTracker(240)
    tracker.record_joint_position(value)
    assert tracker.get_most_closed_joint_position() == float(value)
