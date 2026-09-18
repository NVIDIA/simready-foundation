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
"""Pure geometry helpers for the generated FET005 gripper."""

import math


def smoothstep_progress(progress):
    # type: (float) -> float
    """Clamp a normalized progress value and apply cubic smoothstep."""
    value = float(progress)
    if not math.isfinite(value):
        raise ValueError("motion progress must be finite")
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def bounded_lift_height(max_dimension, multiplier, minimum, maximum):
    # type: (float, float, float, float) -> float
    """Return a finite, positive fixture lift bounded by configured limits."""
    values = tuple(float(value) for value in (max_dimension, multiplier, minimum, maximum))
    if not all(math.isfinite(value) for value in values):
        raise ValueError("lift geometry and limits must be finite")
    max_dimension, multiplier, minimum, maximum = values
    if max_dimension <= 0.0 or multiplier < 0.0:
        raise ValueError("lift geometry must be positive and multiplier non-negative")
    if minimum <= 0.0 or maximum < minimum:
        raise ValueError("lift limits must be positive and ordered")
    return min(max(max_dimension * multiplier, minimum), maximum)


def contact_preloaded_close_travel(surface_travel, grasp_distance, pad_scale, compression):
    # type: (float, float, float, float) -> float
    """Add contact preload without allowing the fixture pads to cross."""
    values = tuple(float(value) for value in (surface_travel, grasp_distance, pad_scale, compression))
    if not all(math.isfinite(value) for value in values):
        raise ValueError("grasp closure values must be finite")
    surface_travel, grasp_distance, pad_scale, compression = values
    if min(surface_travel, grasp_distance, pad_scale, compression) < 0.0:
        raise ValueError("grasp closure values must be non-negative")
    max_close = max(0.0, grasp_distance * 0.5 - pad_scale * 0.5)
    return min(max_close, surface_travel + compression)


def relative_offset_error(reference_a, reference_b, current_a, current_b):
    # type: (Sequence[float], Sequence[float], Sequence[float], Sequence[float]) -> float
    """Measure change in A relative to B, independent of common translation."""
    vectors = (reference_a, reference_b, current_a, current_b)
    if any(len(vector) != 3 for vector in vectors):
        raise ValueError("relative-offset inputs must be three-dimensional")
    values = tuple(float(value) for vector in vectors for value in vector)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("relative-offset inputs must be finite")
    ref = tuple(float(reference_a[i]) - float(reference_b[i]) for i in range(3))
    cur = tuple(float(current_a[i]) - float(current_b[i]) for i in range(3))
    return math.dist(ref, cur)


def resolve_test_fixture_mass(mass_values, volume, fallback_density=8000.0):
    # type: (Iterable[object], float, float) -> Tuple[float, str, int]
    """Resolve the target mass used to size the generated gripper drive.

    Positive, finite authored masses take precedence.  ``mass_values`` may
    contain unset or malformed USD attribute values; those do not make the
    fixture construction fail.  The historical volume estimate remains the
    fallback for assets with no usable authored mass.
    """
    authored = []
    for value in mass_values:
        try:
            mass = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(mass) and mass > 0.0:
            authored.append(mass)

    if authored:
        return sum(authored), "authored_mass_api", len(authored)

    volume = float(volume)
    fallback_density = float(fallback_density)
    if not math.isfinite(volume) or volume <= 0.0:
        raise ValueError("asset volume must be finite and positive when authored mass is unavailable")
    if not math.isfinite(fallback_density) or fallback_density <= 0.0:
        raise ValueError("fallback density must be finite and positive")
    return fallback_density * volume, "bbox_density_fallback", 0


def smooth_motion_envelope(elapsed_seconds, duration_seconds, ramp_seconds):
    # type: (float, float, float) -> float
    """Return a zero-velocity ease-in/out envelope in the range [0, 1]."""
    elapsed = float(elapsed_seconds)
    duration = float(duration_seconds)
    ramp = float(ramp_seconds)
    if not all(math.isfinite(value) for value in (elapsed, duration, ramp)):
        raise ValueError("shake timing values must be finite")
    if duration <= 0.0:
        raise ValueError("shake duration must be positive")
    if ramp < 0.0:
        raise ValueError("shake ramp must be non-negative")
    if elapsed <= 0.0 or elapsed >= duration:
        return 0.0
    ramp = min(ramp, duration * 0.5)
    if ramp <= 0.0:
        return 1.0
    edge_time = min(elapsed, duration - elapsed)
    if edge_time >= ramp:
        return 1.0
    t = max(0.0, min(1.0, edge_time / ramp))
    return smoothstep_progress(t)


def pair_closure_reaches_contact(
    left_position,
    right_position,
    expected_contact_travel,
    contact_travel_tolerance,
):
    # type: (float, float, float, float) -> bool
    """Return whether the two fingers achieved the required total closure.

    ``expected_contact_travel`` is the nominal travel of each finger for a
    centered object.  Real objects can settle off-center, so one finger may
    travel farther than the other while the final aperture is still correct.
    Comparing the pair's total travel preserves the authored aperture
    requirement without imposing artificial symmetry.
    """
    values = (
        float(left_position),
        float(right_position),
        float(expected_contact_travel),
        float(contact_travel_tolerance),
    )
    if not all(math.isfinite(value) for value in values):
        return False
    if contact_travel_tolerance < 0.0:
        raise ValueError("contact travel tolerance must be non-negative")

    required_per_finger = max(
        0.0,
        float(expected_contact_travel) - float(contact_travel_tolerance),
    )
    return abs(float(left_position)) + abs(float(right_position)) >= 2.0 * required_per_finger


def post_failure_stop_frame(failure_frame, physics_fps, observation_seconds):
    # type: (int, int, float) -> int
    """Return the inclusive frame at which failure observation can stop."""
    failure_frame = int(failure_frame)
    physics_fps = int(physics_fps)
    observation_seconds = float(observation_seconds)
    if failure_frame < 0:
        raise ValueError("failure frame must be non-negative")
    if physics_fps <= 0:
        raise ValueError("physics fps must be positive")
    if not math.isfinite(observation_seconds) or observation_seconds < 0.0:
        raise ValueError("failure observation seconds must be finite and non-negative")
    return failure_frame + int(round(observation_seconds * physics_fps))


def pad_ground_clearance_offset(
    left_center,
    right_center,
    pad_dimensions,
    local_axes,
    floor_level=0.0,
    clearance=0.0,
):
    # type: (Sequence[float], Sequence[float], Sequence[float], Sequence[Sequence[float]], float, float) -> float
    """Return the world-Z offset needed to keep both oriented pads above a floor."""
    centers = (left_center, right_center)
    if len(pad_dimensions) != 3 or len(local_axes) != 3:
        raise ValueError("pad dimensions and local axes must each contain three values")
    if any(len(center) != 3 for center in centers) or any(len(axis) != 3 for axis in local_axes):
        raise ValueError("pad centers and local axes must be three-dimensional")

    values = [
        *(float(value) for center in centers for value in center),
        *(float(value) for value in pad_dimensions),
        *(float(value) for axis in local_axes for value in axis),
        float(floor_level),
        float(clearance),
    ]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("ground-clearance geometry must contain finite values")
    if any(float(value) <= 0.0 for value in pad_dimensions):
        raise ValueError("pad dimensions must be positive")
    if clearance < 0.0:
        raise ValueError("pad ground clearance must be non-negative")

    half_world_z = 0.5 * sum(
        float(dimension) * abs(float(axis[2])) for dimension, axis in zip(pad_dimensions, local_axes)
    )
    current_bottom = min(float(center[2]) for center in centers) - half_world_z
    return max(0.0, float(floor_level) + float(clearance) - current_bottom)
