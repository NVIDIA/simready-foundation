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
"""Optional, bounded wall-service diagnostics; never change sweep control."""
import asyncio
import math
import time
from contextlib import contextmanager

_COSTS = ("stepping", "captures", "bounds", "camera", "optional_motion", "commands", "encoding")


class SweepDiagnostics:
    """Measure existing calls, not PhysX CPU time or extra physics observations."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.budget = None
        self.phase_started_at = None
        self.setup_elapsed_seconds = None
        self.planned_ticks = None
        self.plan_estimate_status = "pending"
        self.planning_omitted_joints = 0
        self.active_joint = None
        self.active_segment = "configuration"
        self.stop_reason = "running"
        self.costs = {key: {"wall_seconds": 0.0, "attempts": 0} for key in _COSTS}
        self.warned = False

    def _warn(self):
        if self.warned:
            return
        self.warned = True
        try:
            self.ctx.warn("FRS execution timing diagnostics unavailable; original test behavior retained.")
        except Exception:
            pass

    def _now(self):
        try:
            value = time.monotonic()
            if isinstance(value, bool) or not math.isfinite(value):
                raise ValueError("Unavailable monotonic clock")
            return float(value)
        except Exception:
            self._warn()
            return None

    @staticmethod
    def _elapsed(now, started):
        if now is None or started is None:
            return None
        value = max(0.0, now - started)
        return value if math.isfinite(value) else None

    def attach(self, budget):
        try:
            self.budget = budget
            budget.diagnostics = self
            self.phase_started_at = self._now()
            if self.phase_started_at is not None:
                self.setup_elapsed_seconds = self._elapsed(self.phase_started_at, budget.started_at)
        except Exception:
            self._warn()

    @contextmanager
    def measure(self, name):
        """Include attempted calls, preserving an operation's original exception."""
        started = self._now()
        try:
            yield
        finally:
            try:
                ended = self._now()
                row = self.costs[name]
                row["attempts"] += 1
                duration = self._elapsed(ended, started)
                if duration is not None:
                    total = row["wall_seconds"] + duration
                    if math.isfinite(total):
                        row["wall_seconds"] = total
                    else:
                        self._warn()
            except Exception:
                self._warn()

    def position(self, joint, segment):
        try:
            self.active_joint = str(joint)[:128] if joint is not None else None
            self.active_segment = str(segment)[:32]
        except Exception:
            self._warn()

    def estimate_plan(
        self,
        joints,
        lowers,
        uppers,
        positions,
        hints,
        config,
        parameters,
        segments,
        frames,
        newton_convergence_seconds=0.0,
    ):
        """Reuse required post-settle snapshots; no native queries or control."""
        try:
            if len(joints) > 1024:
                self.planning_omitted_joints = len(joints)
                self.plan_estimate_status = "omitted_joint_limit"
                return
            total = self.budget.ticks
            for index, name in joints:
                lo, hi = float(lowers[index]), float(uppers[index])
                params = parameters(
                    lo,
                    hi,
                    config.get("sweep_margin_ratio", 0.10),
                    config.get("max_sweep_range", math.tau),
                    config.get("sweep_speed_scale", 0.8),
                    config.get("pause_at_limits_seconds", 0.15),
                    self.budget.fps,
                    name,
                )
                start = float(positions[index])
                for origin, goal, _name in segments(start, params):
                    total += frames(origin, goal, origin, hints[index][0], config, params["seg_frames"])
                    total += params["pause_frames"]
                if newton_convergence_seconds > 0.0:
                    total += max(1, int(newton_convergence_seconds * self.budget.fps))
            self.planned_ticks = int(total)
            self.plan_estimate_status = "estimated"
        except Exception:
            self.planned_ticks = None
            self.plan_estimate_status = "unavailable"
            self._warn()

    def publish(self):
        """Snapshots have fixed keys/no per-tick lists and are best-effort only."""
        if self.budget is None:
            return
        # The original numeric progress metric is useful even when the
        # structured record cannot be calculated or its sink rejects it.
        try:
            self.ctx.add_metric("frs_completed_nominal_simulation_seconds", self.budget.ticks / self.budget.fps)
        except Exception:
            self._warn()
        try:
            now = self._now()
            elapsed = self._elapsed(now, self.budget.started_at)
            phase_elapsed = self._elapsed(now, self.phase_started_at)
            ticks = self.budget.ticks
            service = phase_elapsed / ticks if phase_elapsed is not None and ticks else None
            if service is not None and not math.isfinite(service):
                service = None
            remaining_ticks = max(0, self.planned_ticks - ticks) if self.planned_ticks is not None else None
            if self.stop_reason == "procedure_completed":
                # A conservative Newton convergence allowance can exceed
                # actual ticks; completed execution has no remaining work.
                remaining_ticks = 0
            remaining = remaining_ticks * service if remaining_ticks is not None and service is not None else None
            if remaining is not None and not math.isfinite(remaining):
                remaining = None
            wall_remaining = max(0.0, self.budget.wall_seconds - elapsed) if elapsed is not None else None
            self.ctx.add_metric(
                "frs_execution_timing",
                {
                    "completed_nominal_ticks": ticks,
                    "planned_nominal_ticks_estimate": self.planned_ticks,
                    "plan_estimate_status": self.plan_estimate_status,
                    "planning_omitted_joints": self.planning_omitted_joints,
                    "active_joint": self.active_joint,
                    "active_segment": self.active_segment,
                    "stop_reason": self.stop_reason,
                    "elapsed_wall_seconds": elapsed,
                    "setup_elapsed_wall_seconds": self.setup_elapsed_seconds,
                    "configured_wall_budget_seconds": self.budget.wall_seconds,
                    "remaining_wall_budget_seconds": wall_remaining,
                    "observed_service_seconds_per_nominal_tick": service,
                    "estimated_remaining_wall_seconds": remaining,
                    "estimated_budget_insufficient": (
                        remaining > wall_remaining if remaining is not None and wall_remaining is not None else None
                    ),
                    "estimate_basis": "initial required post-settle joint/limit snapshots and speed hints; actual missed endpoints or bounded Newton convergence can change tick totals; phase wall/tick includes all service overhead",
                    "cost_basis": "elapsed monotonic wall time around existing calls, including waits/rendering; not native solver CPU time; attempted calls counted",
                    "costs": {key: dict(value) for key, value in self.costs.items()},
                },
            )
        except Exception:
            self._warn()

    def finish(self, error=None):
        try:
            self.stop_reason = (
                "cancelled"
                if isinstance(error, asyncio.CancelledError)
                else getattr(error, "reason", "execution_error") if error is not None else "procedure_completed"
            )
            self.publish()
        except Exception:
            self._warn()
