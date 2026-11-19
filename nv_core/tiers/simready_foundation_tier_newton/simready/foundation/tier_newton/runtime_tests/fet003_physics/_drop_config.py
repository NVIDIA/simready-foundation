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

import math
from numbers import Real


def _number(value, name, *, nonnegative=False, positive=False, whole=False):
    try:
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError("requires a finite real number, not a boolean/string")
        if (nonnegative and value < 0) or (positive and value <= 0):
            raise ValueError("requires a positive value" if positive else "requires a nonnegative value")
        if whole and value != int(value):
            raise ValueError("requires a whole-number count")
    except (TypeError, ValueError, OverflowError) as error:
        raise RuntimeError(f"FET003 invalid configuration: {name}: {error}") from error


def validate_drop_config(config, *, slope=False):
    """Reject invalid gate/setup inputs before mutation; preserve valid zeros."""
    _number(config.get("floor_level"), "floor_level")
    for name in ("physics_fps", "capture_fps"):
        _number(config.get(name), name, positive=True, whole=True)
    _number(config.get("settle_frames"), "settle_frames", nonnegative=True, whole=True)
    _number(config.get("asset_load_timeout"), "asset_load_timeout", positive=True)
    common = ("simulation_seconds", "floor_margin")
    ground = (
        "drop_height_factor",
        "minimum_drop_distance",
        "penetration_check_seconds",
        "rest_tolerance",
        "rest_detection_hold_seconds",
        "rest_detection_max_seconds",
        "simulate_after_result_seconds",
    )
    ramp = (
        "horizontal_movement_threshold",
        "post_horiz_seconds",
        "slope_contact_tolerance",
        "slope_penetration_tolerance",
        "maximum_slope_separation",
        "separation_confirmation_seconds",
        "minimum_slope_clearance",
        "slope_friction",
    )
    for name in common + (ramp if slope else ground):
        _number(config.get(name), name, nonnegative=True)
    if slope:
        _number(config.get("slope_angle_deg"), "slope_angle_deg")


def validate_slope_observation_config(config):
    """Qualify derived gates before the private observation loop steps."""
    _number(config.get("pen_threshold"), "pen_threshold")
    for name in ("horiz_threshold", "contact_tolerance", "slope_penetration_tolerance", "max_slope_separation"):
        _number(config.get(name), name, nonnegative=True)
