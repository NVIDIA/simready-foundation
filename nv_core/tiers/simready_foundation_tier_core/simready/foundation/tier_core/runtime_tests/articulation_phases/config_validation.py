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

"""Reject malformed verdict inputs before articulation discovery or excitation.

Only parameters consumed by the selected phase are checked. Unknown plugin
configuration remains available to its owner; diagnostic policies are retained.
Finite zero tolerances are valid exactness policies, not replaced by defaults.
"""

import math
from numbers import Real


def finite_number(value, name, *, minimum=0.0, positive=False, maximum=None):
    """Return a finite real without coercing booleans or numeric strings."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("%s must be a finite real number" % name)
    try:
        numeric = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError("%s must be a finite real number" % name) from exc
    if not math.isfinite(numeric):
        raise ValueError("%s must be a finite real number" % name)
    if numeric < minimum or (positive and numeric == minimum):
        relation = "greater than" if positive else "at least"
        raise ValueError("%s must be %s %g" % (name, relation, minimum))
    if maximum is not None and numeric > maximum:
        raise ValueError("%s must be at most %g" % (name, maximum))
    return numeric


def _integer(value, name, *, positive=False):
    numeric = finite_number(value, name, positive=positive)
    if not numeric.is_integer():
        raise ValueError("%s must be a %s integer" % (name, "positive" if positive else "nonnegative"))


# No arbitrary tighter limits on configurable tolerances: only finite values
# and mathematical domains are required. Zero tolerance remains permitted.
_NONNEGATIVE = {
    "velocity_limit": ("tolerance_percent", "settled_velocity_threshold"),
    "effort_limit": ("break_tolerance",),
    "state_accuracy": ("position_tolerance_deg",),
    "drive_gain_validation": (
        "max_overshoot_pct",
        "max_settling_seconds",
        "settling_tolerance",
        "settled_velocity_threshold",
    ),
    "mimic_joint": ("gear_ratio_tolerance",),
    "multi_joint_coordination": ("position_tolerance_deg",),
    "ik_target_reach": ("position_tolerance", "orientation_tolerance", "settle_seconds_after_apply"),
    "jacobian_ik": (
        "position_tolerance",
        "orientation_tolerance_deg",
        "damping_lambda",
        "hold_after_reach_seconds",
    ),
}
_POSITIVE = {
    "velocity_limit": ("test_duration_seconds",),
    "effort_limit": ("force_magnitude_newtons", "test_duration_seconds"),
    "state_accuracy": ("test_duration_seconds", "max_step_deg"),
    "drive_gain_validation": ("test_duration_seconds", "step_magnitude_deg"),
    "mimic_joint": ("sweep_seconds",),
    "multi_joint_coordination": ("max_settling_seconds", "motion_seconds"),
    "ik_target_reach": (
        "motion_seconds",
        "motion_min_seconds",
        "motion_max_seconds",
        "motion_velocity_scale",
        "motion_velocity_fallback",
        "motion_update_hz",
    ),
    "jacobian_ik": (
        "interpolation_seconds",
        "finite_difference_epsilon",
    ),
}
_POSITIVE_INTEGERS = {
    "multi_joint_coordination": ("num_iterations",),
    "ik_target_reach": ("num_reachable_targets",),
    "jacobian_ik": ("num_targets", "max_solver_iterations", "jacobian_propagation_steps"),
}
_NONNEGATIVE_INTEGERS = {
    "velocity_limit": ("capture_settled_grace_frames",),
    "drive_gain_validation": ("max_oscillations", "capture_settled_grace_frames"),
    "ik_target_reach": ("num_out_of_reach_targets",),
    "jacobian_ik": ("out_of_reach_count",),
}
_FRACTIONS = {
    "state_accuracy": (("step_range_fraction", True, 1.0),),
    "mimic_joint": (("sweep_margin_ratio", False, 0.5),),
    "multi_joint_coordination": (("target_margin_ratio", False, 0.5),),
    "ik_target_reach": (("min_success_rate", False, 1.0),),
    "jacobian_ik": (("min_pass_rate", False, 1.0),),
}
_BOOLEANS = {
    "effort_limit": ("bisection_enabled", "stop_on_first_break"),
    "drive_gain_validation": ("step_fatal",),
    "ik_target_reach": ("hemisphere_only", "show_target_spheres"),
    "jacobian_ik": ("show_target_spheres",),
}


def validate_phase_config(config, phase):
    """Validate supplied phase-owned settings before any scene work."""
    config = config or {}
    for name in ("physics_fps", "bbox_explode_ratio") + _POSITIVE.get(phase, ()):
        if name in config:
            finite_number(config[name], name, positive=True)
    for name in ("settle_seconds",) + _NONNEGATIVE.get(phase, ()):
        if name in config:
            finite_number(config[name], name)
    for name in ("capture_fps",) + _POSITIVE_INTEGERS.get(phase, ()):
        if name in config:
            _integer(config[name], name, positive=True)
    for name in _NONNEGATIVE_INTEGERS.get(phase, ()):
        if name in config:
            _integer(config[name], name)
    for name, positive, maximum in _FRACTIONS.get(phase, ()):
        if name in config:
            finite_number(config[name], name, positive=positive, maximum=maximum)
    for name in _BOOLEANS.get(phase, ()):
        if name in config and not isinstance(config[name], bool):
            raise ValueError("%s must be a boolean" % name)

    sequence_names = {
        "multi_joint_coordination": ("target_factors",),
        "ik_target_reach": ("radius_factors",),
    }.get(phase, ())
    for name in sequence_names:
        if name not in config:
            continue
        values = config[name]
        if not isinstance(values, (list, tuple)) or not values:
            raise ValueError("%s must contain at least one finite target factor" % name)
        for value in values:
            finite_number(value, name, positive=phase != "multi_joint_coordination", maximum=1.0)

    if phase == "jacobian_ik":
        # Preserve the existing merged-default plural/legacy-single precedence
        # and empty/unsupported-value fallback. These factors describe only a
        # headline radius metric, not the FK-generated workspace or verdict.
        factors = config.get("target_radius_factors", (0.5, 0.7, 0.9)) or config.get("target_radius_factor")
        if isinstance(factors, Real):
            factors = (factors,)
        elif not isinstance(factors, (list, tuple)) or not factors:
            factors = (0.5, 0.7, 0.9)
        for factor in factors:
            finite_number(factor, "target_radius_factors")

    if phase == "ik_target_reach" and "out_of_reach_factor" in config:
        finite_number(config["out_of_reach_factor"], "out_of_reach_factor", minimum=1.0, positive=True)
    if phase == "ik_target_reach":
        lower = config.get("motion_min_seconds", 1.5)
        upper = config.get("motion_max_seconds", 1.5)
        if lower > upper:
            raise ValueError("motion_min_seconds must not exceed motion_max_seconds")
