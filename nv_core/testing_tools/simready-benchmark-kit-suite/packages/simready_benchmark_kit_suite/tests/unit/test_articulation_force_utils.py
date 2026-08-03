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
"""Tests for articulation_phases.force_utils pure helpers."""
import math

from simready_benchmark_kit_suite.articulation_phases.force_utils import (
    ForceVector,
    bisect_break_force,
    generate_12_force_directions,
)


def test_generate_12_force_directions_length():
    vecs = generate_12_force_directions()
    assert len(vecs) == 12


def test_generate_12_force_directions_all_unit():
    for v in generate_12_force_directions():
        mag = math.sqrt(v.direction[0] ** 2 + v.direction[1] ** 2 + v.direction[2] ** 2)
        assert abs(mag - 1.0) < 1e-9, "non-unit vector for label %s" % v.label


def test_generate_12_force_directions_labels_unique():
    labels = [v.label for v in generate_12_force_directions()]
    assert len(set(labels)) == 12


def test_generate_12_force_directions_symmetric_pairs():
    by_label = {v.label: v.direction for v in generate_12_force_directions()}
    for pos_label in ("+X", "+Y", "+Z", "+XY", "+YZ", "+XZ"):
        neg_label = "-" + pos_label[1:]
        pos = by_label[pos_label]
        neg = by_label[neg_label]
        for a, b in zip(pos, neg):
            assert abs(a + b) < 1e-9, "pair %s / %s not opposite" % (pos_label, neg_label)


def test_bisect_break_force_returns_first_break_above_threshold():
    # probe(force) -> True means "broke at this force"
    def probe(force):
        return force >= 240.0

    result = bisect_break_force(lo=50.0, hi=500.0, max_iterations=6, probe=probe)
    assert 200.0 <= result <= 260.0


def test_bisect_break_force_no_break_returns_hi():
    def probe(force):
        return False

    result = bisect_break_force(lo=50.0, hi=500.0, max_iterations=6, probe=probe)
    assert result == 500.0


def test_bisect_break_force_always_breaks_returns_lo():
    def probe(force):
        return True

    result = bisect_break_force(lo=50.0, hi=500.0, max_iterations=6, probe=probe)
    assert result == 50.0


def test_force_vector_is_frozen_dataclass():
    v = ForceVector(direction=(1.0, 0.0, 0.0), label="+X")
    try:
        v.label = "-X"
    except Exception:
        return
    raise AssertionError("ForceVector should be frozen")


def test_read_contact_force_magnitude_returns_norm_of_force_vector():
    """If the underlying contact-force source returns [3, 4, 0], the
    magnitude should be 5.0."""
    from simready_benchmark_kit_suite.articulation_phases import force_utils

    class _StubRobot:
        def get_body_contact_force(self, body_path):
            assert body_path == "/W/A/finger_pad"
            return (3.0, 4.0, 0.0)

    f = force_utils.read_contact_force_magnitude(_StubRobot(), "/W/A/finger_pad")
    assert abs(f - 5.0) < 1e-6


def test_read_contact_force_magnitude_returns_none_when_untracked():
    from simready_benchmark_kit_suite.articulation_phases import force_utils

    class _StubRobot:
        def get_body_contact_force(self, body_path):
            return None

    f = force_utils.read_contact_force_magnitude(_StubRobot(), "/W/A/missing")
    assert f is None
