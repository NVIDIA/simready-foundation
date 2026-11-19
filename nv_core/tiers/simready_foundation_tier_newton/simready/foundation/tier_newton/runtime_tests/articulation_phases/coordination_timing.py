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
"""Newton-owned bounded nominal timing for coordinated smoothstep commands."""

import math
import time

from simready.foundation.tier_newton.runtime_tests.articulation_phases.config_validation import (
    finite_number,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.sweep_timing import (
    usable_velocity,
)

MAX_DURATION_SECONDS = 3600
MAX_TIMING_ITERATIONS = 64
MAX_TIMING_JOINTS = 256


def _ticks(seconds, fps, name):
    product = seconds * fps
    if not math.isfinite(product):
        raise ValueError("MJC %s tick budget must be finite" % name)
    return math.ceil(product)


class CoordinationTiming:
    """Preserve the configured hold while sharing the slowest required ramp."""

    def __init__(self, config):
        self.fps = finite_number(config.get("physics_fps", 240.0), "physics_fps", positive=True)
        motion = finite_number(config.get("motion_seconds", 2.0), "motion_seconds", positive=True)
        window = finite_number(config.get("max_settling_seconds", 8.0), "max_settling_seconds", positive=True)
        if window < motion:
            raise ValueError("MJC max_settling_seconds must not be less than motion_seconds")
        self.speed_scale = finite_number(
            config.get("coordination_speed_scale", 0.8), "coordination_speed_scale", positive=True, maximum=1.0
        )
        self.allowance = finite_number(
            config.get("coordination_settling_allowance_seconds", 0.25), "coordination_settling_allowance_seconds"
        )
        self.max_ramp_seconds = finite_number(
            config.get("max_coordination_ramp_seconds", 60.0), "max_coordination_ramp_seconds", positive=True
        )
        self.base_ramp_frames = max(1, _ticks(motion, self.fps, "motion_seconds"))
        if self.base_ramp_frames / self.fps > self.max_ramp_seconds:
            raise RuntimeError(
                "MJC configured ramp exceeds max_coordination_ramp_seconds; timing budget is insufficient"
            )
        # Retain the legacy 60-observation floor and the configured post-ramp
        # hold. A slow joint lengthens the ramp, never consumes that hold.
        self.hold_frames = max(60, _ticks(window, self.fps, "max_settling_seconds")) - self.base_ramp_frames
        settle = finite_number(config.get("settle_seconds", 1.0), "settle_seconds")
        self.settle_frames = _ticks(settle, self.fps, "settle_seconds")
        count = finite_number(config.get("num_iterations", 3), "num_iterations", positive=True)
        if not count.is_integer():
            raise ValueError("MJC num_iterations must be a positive integer")
        self.iterations = int(count)
        self.minimum_total_frames = self.settle_frames + self.iterations * (self.base_ramp_frames + self.hold_frames)

    def plan_iteration(self, start_positions, targets, valid_joints, velocity_hints):
        """Use required current state; hints pace commands, not solver guarantees."""
        duration = self.base_ramp_frames / self.fps
        travels = []
        for joint in valid_joints:
            index = joint["index"]
            start = float(start_positions[index])
            goal = float(targets[index])
            distance = abs(goal - start)
            if not all(math.isfinite(value) for value in (start, goal, distance)):
                raise ValueError("MJC requires finite goal travel from the current joint position")
            try:
                raw_velocity, source = velocity_hints[index]
                velocity = usable_velocity(raw_velocity)
            except (IndexError, TypeError, ValueError, OverflowError):
                velocity, source = None, "configured fallback duration"
            if velocity is None:
                source = "configured fallback duration"
            else:
                scaled_velocity = velocity * self.speed_scale
                travel = (
                    0.0 if distance == 0 else 1.5 * (distance / scaled_velocity) if scaled_velocity > 0 else math.inf
                )
                duration = max(duration, travel + self.allowance)
            if len(travels) < MAX_TIMING_JOINTS:
                travels.append((joint, distance, velocity, source))
        if not math.isfinite(duration) or duration > self.max_ramp_seconds:
            raise RuntimeError(
                "MJC ramp needs %.3g simulation seconds, exceeding max_coordination_ramp_seconds=%.3g; "
                "test timing budget is insufficient, not an evaluated asset failure" % (duration, self.max_ramp_seconds)
            )
        frames = (
            self.base_ramp_frames
            if duration <= self.base_ramp_frames / self.fps
            else max(self.base_ramp_frames, _ticks(duration, self.fps, "derived ramp"))
        )
        duration = frames / self.fps
        if not math.isfinite(duration) or duration > self.max_ramp_seconds:
            raise RuntimeError("MJC rounded ramp exceeds max_coordination_ramp_seconds")
        records = []
        for joint, distance, velocity, source in travels:
            peak = 1.5 * (distance / duration)
            if not math.isfinite(peak):
                raise ValueError("MJC estimated command peak must be finite")
            records.append(
                {
                    "name": str(joint["name"])[:256],
                    "index": joint["index"],
                    "velocity_hint": velocity,
                    "velocity_hint_source": str(source)[:256],
                    "displacement": distance,
                    "estimated_command_peak_speed": peak,
                }
            )
        total = frames + self.hold_frames
        return {
            "ramp_frames": frames,
            "hold_frames": self.hold_frames,
            "total_frames": total,
            "ramp_seconds": duration,
            "hold_seconds": self.hold_frames / self.fps,
            "observation_seconds": total / self.fps,
            "joints": records,
            "joints_omitted": max(0, len(valid_joints) - len(travels)),
        }


class CoordinationBudget:
    """Count completed nominal ticks, separately guarding elapsed wall time."""

    def __init__(self, config, started_at=None):
        self.fps = finite_number(config.get("physics_fps", 240.0), "physics_fps", positive=True)
        self.simulation_seconds = finite_number(
            config.get("max_coordination_simulation_seconds", 600.0),
            "max_coordination_simulation_seconds",
            positive=True,
        )
        self.wall_seconds = finite_number(
            config.get("max_coordination_wall_seconds", 3360.0), "max_coordination_wall_seconds", positive=True
        )
        if self.wall_seconds > MAX_DURATION_SECONDS - 60:
            raise ValueError("MJC max_coordination_wall_seconds must leave 60 seconds below registered max_duration")
        ticks = self.simulation_seconds * self.fps
        if not math.isfinite(ticks):
            raise ValueError("MJC simulation tick budget must be finite")
        self.max_ticks = math.floor(ticks)
        self.ticks = 0
        self.started_at = time.monotonic() if started_at is None else started_at

    def check_wall(self):
        if time.monotonic() - self.started_at >= self.wall_seconds:
            raise RuntimeError(
                "MJC max_coordination_wall_seconds exhausted; test execution is incomplete, not an evaluated asset failure"
            )

    def reserve(self, ticks):
        self.check_wall()
        if self.ticks + ticks > self.max_ticks:
            raise RuntimeError(
                "MJC max_coordination_simulation_seconds cannot fit the next complete window; "
                "test timing budget is insufficient, not an evaluated asset failure"
            )

    async def step_one(self, ctx):
        self.reserve(1)
        await ctx.step_one()
        self.ticks += 1
        self.check_wall()
