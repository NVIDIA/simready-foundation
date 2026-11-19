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

"""Nominal initial settling shared by this tier's articulation phases.

This requests simulation ticks, not measured elapsed simulation or wall time.
It deliberately does not use the processing-only ``ctx.physics_steps`` API.
"""

import math
from numbers import Real


def nominal_settle_steps(settle_seconds, physics_fps):
    """Validate raw configuration and round a nominal settling interval up."""
    for name, value, positive in (
        ("settle_seconds", settle_seconds, False),
        ("physics_fps", physics_fps, True),
    ):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"{name} must be a finite real number")
        try:
            value = float(value)
        except (OverflowError, ValueError) as exc:
            raise ValueError(f"{name} must be a finite real number") from exc
        if not math.isfinite(value) or value < 0.0 or (positive and value == 0.0):
            qualifier = "positive" if positive else "nonnegative"
            raise ValueError(f"{name} must be finite and {qualifier}")
    ticks = float(settle_seconds) * float(physics_fps)
    if not math.isfinite(ticks):
        raise ValueError("Nominal settling tick count must be finite")
    # A positive subnormal duration/rate product may underflow to zero. It
    # still requests at least one tick rather than silently skipping settling.
    return max(1, math.ceil(ticks)) if settle_seconds > 0.0 else 0


async def settle_nominal(ctx, settle_seconds, physics_fps, phase="Robot"):
    """Request complete ticks; preserve step errors and cancellation unchanged."""
    count = nominal_settle_steps(settle_seconds, physics_fps)
    for index in range(count):
        await ctx.step_one()
        completed = index + 1
        if completed % 40 == 0 or completed == count:
            ctx.step(f"{phase}: nominal settle {completed}/{count} ticks")
    return count
