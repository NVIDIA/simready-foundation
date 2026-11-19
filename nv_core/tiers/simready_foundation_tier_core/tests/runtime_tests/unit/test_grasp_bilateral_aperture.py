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
from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_utils import (
    AssetPoseTracker,
    detect_pads_touching,
)

PROPS = {"gripper_position_info": {"grasp_distance": 0.2}, "gripper_pad_properties": {"scale": 0.01}}


def _record(tracker, pair, timestamp):
    tracker.times.append(timestamp)
    tracker.record_finger_positions(pair, current_time=timestamp)


@pytest.mark.parametrize("offset", [-0.001, 0.0, 0.001])
@pytest.mark.parametrize("tolerance", [0.0, 0.002])
def test_symmetric_pair_preserves_previous_per_jaw_boundary(offset, tolerance):
    tracker = AssetPoseTracker(240)
    old_threshold = -(0.2 / 2.0) + (0.01 / 2.0) + tolerance
    value = old_threshold + offset
    _record(tracker, (value, value), 0.1)
    assert detect_pads_touching(tracker, PROPS, tolerance) is (value <= old_threshold)


def test_asymmetric_jaws_are_not_reported_touching_when_total_aperture_is_open():
    tracker = AssetPoseTracker(240)
    _record(tracker, (-0.095, -0.01), 0.1)
    assert tracker.get_most_closed_joint_position() == -0.095
    assert detect_pads_touching(tracker, PROPS, 0.002) is False


def test_pairs_at_different_times_cannot_manufacture_simultaneous_closure():
    tracker = AssetPoseTracker(240)
    _record(tracker, (-0.095, -0.01), 0.1)
    _record(tracker, (-0.01, -0.095), 0.2)
    assert detect_pads_touching(tracker, PROPS, 0.002) is False


def test_minimum_actual_paired_aperture_retains_prior_closed_observation():
    tracker = AssetPoseTracker(240)
    _record(tracker, (-0.093, -0.093), 0.1)
    _record(tracker, (0.0, 0.0), 0.2)
    assert detect_pads_touching(tracker, PROPS, 0.002) is True


@pytest.mark.parametrize(
    "pair",
    [
        None,
        (),
        (0.0,),
        (0.0, 0.0, 0.0),
        (0.0, True),
        (0.0, "0"),
        (0.0, complex(0)),
        (0.0, float("nan")),
        np.zeros(2, dtype=object),
        np.zeros(2, dtype=complex),
        np.zeros((2, 1)),
    ],
)
def test_invalid_pair_is_rejected_before_either_jaw_is_retained(pair):
    tracker = AssetPoseTracker(240)
    tracker.times.append(0.1)
    with pytest.raises((ValueError, TypeError)):
        tracker.record_finger_positions(pair, current_time=0.1)
    assert tracker.finger_positions == tracker.finger_times == tracker.joint_positions == []


def test_unmatched_pair_timestamp_is_not_associated_with_old_observation():
    tracker = AssetPoseTracker(240)
    tracker.times.append(0.1)
    with pytest.raises(RuntimeError, match="must match"):
        tracker.record_finger_positions((0.0, 0.0), current_time=0.2)
    assert tracker.finger_positions == tracker.finger_times == tracker.joint_positions == []


def test_missing_object_observation_cannot_accept_finger_pair():
    with pytest.raises(RuntimeError, match="current object observation"):
        AssetPoseTracker(240).record_finger_positions((0.0, 0.0))


def test_left_only_legacy_history_cannot_establish_bilateral_contact():
    tracker = AssetPoseTracker(240)
    tracker.record_joint_position(-0.095)
    with pytest.raises(RuntimeError, match="bilateral finger history"):
        detect_pads_touching(tracker, PROPS, 0.002)
