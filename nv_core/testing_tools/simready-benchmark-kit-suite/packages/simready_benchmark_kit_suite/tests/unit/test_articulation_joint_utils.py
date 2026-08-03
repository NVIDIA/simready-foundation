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
"""Tests for articulation_phases.joint_utils."""
from simready_benchmark_kit_suite.articulation_phases.joint_utils import (
    BBoxSnapshot,
    check_bbox_explode,
    safe_len,
)


def test_bbox_snapshot_volume():
    s = BBoxSnapshot(
        min_point=(0.0, 0.0, 0.0),
        max_point=(2.0, 3.0, 4.0),
    )
    assert abs(s.volume - 24.0) < 1e-9


def test_bbox_snapshot_zero_volume_for_degenerate():
    s = BBoxSnapshot(
        min_point=(0.0, 0.0, 0.0),
        max_point=(0.0, 0.0, 0.0),
    )
    assert s.volume == 0.0


def test_check_bbox_explode_returns_none_when_within_ratio():
    baseline = BBoxSnapshot((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    current = BBoxSnapshot((0.0, 0.0, 0.0), (2.0, 2.0, 2.0))
    assert check_bbox_explode(current, baseline, ratio=10.0) is None


def test_check_bbox_explode_returns_message_when_exceeds_ratio():
    baseline = BBoxSnapshot((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    current = BBoxSnapshot((0.0, 0.0, 0.0), (3.0, 3.0, 3.0))
    msg = check_bbox_explode(current, baseline, ratio=10.0)
    assert msg is not None
    assert "explode" in msg.lower() or "bbox" in msg.lower()


def test_check_bbox_explode_handles_zero_baseline():
    baseline = BBoxSnapshot((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    current = BBoxSnapshot((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    assert check_bbox_explode(current, baseline, ratio=10.0) is None


def test_safe_len_of_none_is_zero():
    assert safe_len(None) == 0


def test_safe_len_of_list():
    assert safe_len([1, 2, 3]) == 3


def test_safe_len_of_non_sized_object_is_zero():
    class NoLen:
        pass

    assert safe_len(NoLen()) == 0
