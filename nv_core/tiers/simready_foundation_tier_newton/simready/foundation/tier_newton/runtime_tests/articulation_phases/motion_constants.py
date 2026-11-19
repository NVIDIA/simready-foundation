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
"""
Centralized motion constants for robot test phases.

These values are hardcoded to provide consistent, well-tested motion behavior
across all robot tests. If adjustments are needed, change them here rather than
adding configuration parameters.

This approach reduces configuration complexity while maintaining flexibility
by consolidating defaults in a single, easily discoverable location.
"""

from __future__ import annotations

# ============================================================================
# Motion Timing (seconds)
# ============================================================================

# Time to move between IK/JIK targets.
# Must be long enough for velocity-limited joints to traverse large arcs.
# UR10 shoulder joints at 120 deg/s need ~3s for a pi-radian move (with
# smoothstep factor).  4.0s gives comfortable headroom.  Early-exit in
# _interpolate_ik_motion / _interpolate_jik_motion ensures fast targets
# don't waste this full budget.
MOTION_DURATION_SECONDS = 4.0

# Time to settle after reaching target
SETTLE_DURATION_SECONDS = 0.25

# Time to hold after teleporting to reference position
HOLD_AFTER_RESET_SECONDS = 0.25

# ============================================================================
# Motion Control
# ============================================================================

# Controller update rate (commands per second)
# This controls how frequently we send position commands to the robot controller
MOTION_UPDATE_HZ = 60.0

# Whether to clamp interpolated positions to joint limits
ENFORCE_JOINT_LIMITS = True

# ============================================================================
# JIK Solver Parameters (Jacobian Inverse Kinematics)
# ============================================================================

# Damped least squares regularization factor
# Higher values = more damping, more stable but less accurate
# Lower values = less damping, more accurate but may be unstable
JIK_DAMPING_FACTOR = 0.05

# Maximum solver iterations for reachable targets
JIK_MAX_ITERATIONS = 1000

# Iteration limit for known out-of-reach targets
# Stops early to avoid wasting time on impossible targets
JIK_OUT_OF_REACH_MAX_ITERATIONS = 30

# Base step size for Jacobian updates (fraction of computed delta)
JIK_STEP_SIZE = 0.5

# Enable dynamic step scaling based on error improvement
JIK_DYNAMIC_STEP = True

# Minimum step scale multiplier (prevents steps from becoming too small)
JIK_STEP_SCALE_MIN = 0.5

# Maximum step scale multiplier (prevents overshooting)
JIK_STEP_SCALE_MAX = 1.25

# Iterations without improvement before declaring stall
JIK_STALL_PATIENCE = 30

# Minimum error improvement to avoid stall detection
JIK_MIN_IMPROVEMENT = 1e-5

# ============================================================================
# Target Generation Defaults
# ============================================================================

# Fibonacci sphere radius multipliers
# Targets are placed at these fractions of robot reach
# e.g., [0.5, 0.7, 0.9] creates targets at 50%, 70%, and 90% of max reach
DEFAULT_RADIUS_FACTORS = [0.5, 0.7, 0.9]

# Multiplier for out-of-reach targets (should be > 1.0)
# e.g., 1.3 = targets at 130% of max reach (deliberately unreachable)
DEFAULT_OUT_OF_REACH_FACTOR = 1.3

# Number of reachable IK targets to generate
DEFAULT_NUM_REACHABLE_TARGETS = 22

# Number of out-of-reach IK targets to generate
# These test that the solver correctly identifies impossible targets
DEFAULT_NUM_OUT_OF_REACH_TARGETS = 3
