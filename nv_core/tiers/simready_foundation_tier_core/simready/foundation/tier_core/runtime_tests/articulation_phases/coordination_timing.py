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
"""Core-owned shared coordination pacing and bounded execution windows."""

import math
import time

from simready.foundation.tier_core.runtime_tests.articulation_phases.config_validation import (
    finite_number,
    validate_phase_config,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.settling import (
    nominal_settle_steps,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.sweep_timing import (
    usable_velocity,
)

MAX_DURATION_SECONDS = 3600
MAX_TIMING_JOINTS = 256
MAX_TIMING_ITERATIONS = 64


def _ticks(seconds, fps, name):
    value = seconds * fps
    if not math.isfinite(value):
        raise ValueError("MJC %s tick budget must be finite" % name)
    return max(1, math.ceil(value))


class CoordinationTiming:
    """Pace smoothstep commands, retaining the original post-ramp opportunity."""

    def __init__(self, config):
        validate_phase_config(config, "multi_joint_coordination")
        self.fps = finite_number(config.get("physics_fps", 240.0), "physics_fps", positive=True)
        motion = finite_number(config.get("motion_seconds", 2.0), "motion_seconds", positive=True)
        window = finite_number(config.get("max_settling_seconds", 8.0), "max_settling_seconds", positive=True)
        if window < motion:
            raise ValueError("MJC max_settling_seconds must not be shorter than motion_seconds")
        self.scale = finite_number(
            config.get("coordination_speed_scale", 0.8), "coordination_speed_scale", positive=True, maximum=1.0
        )
        self.allowance = finite_number(
            config.get("coordination_settling_allowance_seconds", 0.25), "coordination_settling_allowance_seconds"
        )
        self.maximum_ramp = finite_number(
            config.get("max_coordination_ramp_seconds", 60.0), "max_coordination_ramp_seconds", positive=True
        )
        self.base_ramp_frames = _ticks(motion, self.fps, "base ramp")
        self.hold_frames = max(60, _ticks(window, self.fps, "base observation")) - self.base_ramp_frames
        if self.base_ramp_frames / self.fps > self.maximum_ramp:
            raise RuntimeError(
                "MJC configured ramp exceeds max_coordination_ramp_seconds; execution budget is insufficient"
            )
        self.settle_frames = nominal_settle_steps(config.get("settle_seconds", 1.0), self.fps)
        self.iterations = int(config.get("num_iterations", 3))
        self.minimum_total_frames = self.settle_frames + self.iterations * (self.base_ramp_frames + self.hold_frames)

    def plan_iteration(self, start_positions, targets, valid_joints, velocity_hints):
        """Use this iteration's live start, not the preceding requested goal."""
        duration = self.base_ramp_frames / self.fps
        rows = []
        for joint in valid_joints:
            index = joint["index"]
            start = finite_number(start_positions[index], "start position", minimum=-math.inf)
            target = finite_number(targets[index], "target position", minimum=-math.inf)
            distance = abs(target - start)
            if not math.isfinite(distance):
                raise ValueError("MJC commanded displacement must be finite")
            velocity, source = (
                velocity_hints[index] if index < len(velocity_hints) else (None, "configured fallback duration")
            )
            velocity = usable_velocity(velocity)
            if velocity is None:
                source = "configured fallback duration"
            else:
                scaled = velocity * self.scale
                travel = 0.0 if distance == 0.0 else 1.5 * distance / scaled if scaled > 0 else math.inf
                duration = max(duration, travel + self.allowance)
            if len(rows) < MAX_TIMING_JOINTS:
                rows.append(
                    {
                        "name": str(joint["name"])[:256],
                        "index": index,
                        "displacement": distance,
                        "velocity_hint": velocity,
                        "velocity_hint_source": str(source)[:256],
                    }
                )
        if not math.isfinite(duration) or duration > self.maximum_ramp:
            raise RuntimeError(
                "MJC shared ramp requires %.3g nominal seconds, exceeding max_coordination_ramp_seconds=%.3g; "
                "execution budget is insufficient, not an evaluated asset failure" % (duration, self.maximum_ramp)
            )
        ramp_frames = (
            self.base_ramp_frames
            if duration <= self.base_ramp_frames / self.fps
            else max(self.base_ramp_frames, _ticks(duration, self.fps, "adapted ramp"))
        )
        ramp_seconds = ramp_frames / self.fps
        if not math.isfinite(ramp_seconds) or ramp_seconds > self.maximum_ramp:
            raise RuntimeError("MJC rounded shared ramp exceeds max_coordination_ramp_seconds")
        for row in rows:
            peak = 1.5 * (row["displacement"] / ramp_seconds)
            if not math.isfinite(peak):
                raise ValueError("MJC estimated command peak speed must be finite")
            row["estimated_command_peak_speed"] = peak
        total = ramp_frames + self.hold_frames
        return {
            "ramp_frames": ramp_frames,
            "hold_frames": self.hold_frames,
            "total_frames": total,
            "ramp_seconds": ramp_seconds,
            "hold_seconds": self.hold_frames / self.fps,
            "observation_seconds": total / self.fps,
            "joints": rows,
            "joints_omitted": max(0, len(valid_joints) - len(rows)),
        }


class CoordinationBudget:
    """Count completed nominal ticks; rendered captures consume wall time only."""

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
        self.started_at = time.monotonic() if started_at is None else finite_number(started_at, "started_at")

    def check_wall(self):
        if time.monotonic() - self.started_at >= self.wall_seconds:
            raise RuntimeError(
                "MJC max_coordination_wall_seconds exhausted; execution is incomplete, not an asset failure"
            )

    def reserve(self, ticks):
        self.check_wall()
        if self.ticks + ticks > self.max_ticks:
            raise RuntimeError(
                "MJC max_coordination_simulation_seconds cannot fit the next complete window; "
                "execution budget is insufficient, not an evaluated asset failure"
            )

    async def step_one(self, ctx):
        self.reserve(1)
        await ctx.step_one()
        self.ticks += 1
        self.check_wall()
