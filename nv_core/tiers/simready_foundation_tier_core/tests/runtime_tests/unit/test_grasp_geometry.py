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

import pytest
from simready_benchmark_kit_suite.fet005_grasp.grasp_geometry import (
    bounded_lift_height,
    contact_preloaded_close_travel,
    pad_ground_clearance_offset,
    pair_closure_reaches_contact,
    post_failure_stop_frame,
    resolve_test_fixture_mass,
    relative_offset_error,
    smooth_motion_envelope,
    smoothstep_progress,
)


def test_fixture_mass_sums_positive_finite_authored_values():
    mass, source, count = resolve_test_fixture_mass(
        [0.036, None, float("nan"), -1.0, 0.051, 0.657, 1.378],
        volume=0.033,
    )

    assert mass == pytest.approx(2.122)
    assert source == "authored_mass_api"
    assert count == 4


def test_smoothstep_progress_clamps_and_eases():
    assert smoothstep_progress(-1.0) == 0.0
    assert smoothstep_progress(0.5) == pytest.approx(0.5)
    assert smoothstep_progress(2.0) == 1.0


def test_bounded_lift_height_applies_minimum_and_maximum():
    assert bounded_lift_height(0.05, 2.0, 0.3, 0.5) == pytest.approx(0.3)
    assert bounded_lift_height(0.2, 2.0, 0.3, 0.5) == pytest.approx(0.4)
    assert bounded_lift_height(1.0, 2.0, 0.3, 0.5) == pytest.approx(0.5)


@pytest.mark.parametrize(
    "values",
    [
        (0.0, 2.0, 0.3, 0.5),
        (1.0, -1.0, 0.3, 0.5),
        (1.0, 2.0, 0.0, 0.5),
        (1.0, 2.0, 0.6, 0.5),
    ],
)
def test_bounded_lift_height_rejects_invalid_values(values):
    with pytest.raises(ValueError, match="lift"):
        bounded_lift_height(*values)


def test_contact_preload_adds_residual_drive_error():
    assert contact_preloaded_close_travel(0.10, 0.26, 0.01, 0.005) == pytest.approx(0.105)


def test_contact_preload_cannot_close_pads_through_each_other():
    assert contact_preloaded_close_travel(0.12, 0.26, 0.02, 0.02) == pytest.approx(0.12)


def test_contact_preload_rejects_negative_compression():
    with pytest.raises(ValueError, match="non-negative"):
        contact_preloaded_close_travel(0.10, 0.26, 0.01, -0.001)


def test_relative_offset_error_ignores_common_translation():
    assert relative_offset_error(
        (1.0, 2.0, 3.0),
        (0.0, 0.0, 0.0),
        (5.0, 7.0, 9.0),
        (4.0, 5.0, 6.0),
    ) == pytest.approx(0.0)


def test_relative_offset_error_detects_grip_separation():
    assert relative_offset_error(
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, -0.2),
        (0.0, 0.0, 0.0),
    ) == pytest.approx(0.2)


def test_fixture_mass_uses_volume_only_without_valid_authored_mass():
    mass, source, count = resolve_test_fixture_mass(
        [None, 0.0, float("inf")],
        volume=0.025,
    )

    assert mass == pytest.approx(200.0)
    assert source == "bbox_density_fallback"
    assert count == 0


@pytest.mark.parametrize("volume", [0.0, -1.0, float("nan")])
def test_fixture_mass_rejects_invalid_fallback_volume(volume):
    with pytest.raises(ValueError, match="asset volume"):
        resolve_test_fixture_mass([], volume=volume)


def test_motion_envelope_eases_in_holds_and_eases_out():
    assert smooth_motion_envelope(0.0, 1.5, 0.25) == 0.0
    assert smooth_motion_envelope(0.125, 1.5, 0.25) == pytest.approx(0.5)
    assert smooth_motion_envelope(0.25, 1.5, 0.25) == 1.0
    assert smooth_motion_envelope(0.75, 1.5, 0.25) == 1.0
    assert smooth_motion_envelope(1.375, 1.5, 0.25) == pytest.approx(0.5)
    assert smooth_motion_envelope(1.5, 1.5, 0.25) == 0.0


def test_motion_envelope_zero_ramp_only_zeroes_endpoints():
    assert smooth_motion_envelope(0.5, 1.0, 0.0) == 1.0
    assert smooth_motion_envelope(1.0, 1.0, 0.0) == 0.0


@pytest.mark.parametrize(
    ("duration", "ramp", "message"),
    [(0.0, 0.1, "duration"), (1.0, -0.1, "ramp")],
)
def test_motion_envelope_rejects_invalid_timing(duration, ramp, message):
    with pytest.raises(ValueError, match=message):
        smooth_motion_envelope(0.1, duration, ramp)


def test_pair_closure_accepts_stable_asymmetric_aperture():
    assert pair_closure_reaches_contact(
        left_position=-0.116680,
        right_position=-0.094843,
        expected_contact_travel=0.100682,
        contact_travel_tolerance=0.002,
    )


def test_pair_closure_rejects_insufficient_total_travel():
    assert not pair_closure_reaches_contact(
        left_position=-0.090,
        right_position=-0.090,
        expected_contact_travel=0.100682,
        contact_travel_tolerance=0.002,
    )


def test_pair_closure_rejects_non_finite_joint_position():
    assert not pair_closure_reaches_contact(
        left_position=float("nan"),
        right_position=-0.100,
        expected_contact_travel=0.100,
        contact_travel_tolerance=0.002,
    )


def test_pair_closure_rejects_negative_tolerance():
    with pytest.raises(ValueError, match="non-negative"):
        pair_closure_reaches_contact(-0.1, -0.1, 0.1, -0.001)


def test_post_failure_observation_adds_one_simulated_second():
    assert post_failure_stop_frame(720, 240, 1.0) == 960


def test_post_failure_observation_allows_zero_duration():
    assert post_failure_stop_frame(720, 240, 0.0) == 720


@pytest.mark.parametrize(
    ("frame", "fps", "seconds", "message"),
    [
        (-1, 240, 1.0, "frame"),
        (10, 0, 1.0, "fps"),
        (10, 240, -1.0, "seconds"),
        (10, 240, float("nan"), "seconds"),
    ],
)
def test_post_failure_observation_rejects_invalid_inputs(
    frame,
    fps,
    seconds,
    message,
):
    with pytest.raises(ValueError, match=message):
        post_failure_stop_frame(frame, fps, seconds)


def test_pad_above_ground_needs_no_offset():
    offset = pad_ground_clearance_offset(
        (-0.1, 0.0, 0.2),
        (0.1, 0.0, 0.2),
        (0.02, 0.10, 0.10),
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        clearance=0.002,
    )
    assert offset == 0.0


def test_low_horizontal_pads_are_raised_by_full_box_extent():
    offset = pad_ground_clearance_offset(
        (-0.1, 0.0, 0.03),
        (0.1, 0.0, 0.03),
        (0.02, 0.10, 0.10),
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        clearance=0.002,
    )
    assert offset == pytest.approx(0.022)


def test_oriented_pad_uses_all_local_axes_for_world_height():
    root_half = 2**-0.5
    offset = pad_ground_clearance_offset(
        (-0.1, 0.0, 0.04),
        (0.1, 0.0, 0.04),
        (0.02, 0.10, 0.10),
        ((root_half, 0.0, root_half), (0.0, 1.0, 0.0), (-root_half, 0.0, root_half)),
        floor_level=0.01,
        clearance=0.002,
    )
    expected_half_height = 0.5 * (0.02 * root_half + 0.10 * root_half)
    assert offset == pytest.approx(0.01 + 0.002 + expected_half_height - 0.04)


def test_negative_clearance_is_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        pad_ground_clearance_offset(
            (0.0, 0.0, 0.1),
            (0.0, 0.0, 0.1),
            (0.02, 0.10, 0.10),
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            clearance=-0.001,
        )
