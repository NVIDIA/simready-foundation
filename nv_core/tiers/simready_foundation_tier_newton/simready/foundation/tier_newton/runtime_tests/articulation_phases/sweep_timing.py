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
import time
from numbers import Real

import numpy as np

MAX_DURATION_SECONDS = 14400
_FLOAT32_MAX = 3.4028234663852886e38
SEGMENT_DEFAULTS = {
    "sweep_speed_scale": 0.8,
    "sweep_settling_allowance_seconds": 0.25,
    "max_sweep_segment_seconds": 60.0,
}


class SweepBudgetExceeded(RuntimeError):
    """An incomplete bounded execution, not an evaluated asset-response failure."""

    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason


def _finite(value, name, *, positive=False, phase="FRS"):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{phase} {name} must be a finite real number")
    value = float(value)
    quality = "positive" if positive else "non-negative"
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{phase} {name} must be {quality}")
    return value


def usable_velocity(value, *, native_angular=False):
    """Exclude SDK defaults only in their qualified native unit context.

    The angular native tensor uses rad/s, while the USD SDK default is
    float32-max degrees/s. Authored and unqualified values must not lose a
    rating merely because it equals that converted native default.
    """
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    value = float(value)
    if not math.isfinite(value) or value <= 0 or math.isclose(value, _FLOAT32_MAX, rel_tol=1e-6):
        return None
    if native_angular and math.isclose(value, math.radians(_FLOAT32_MAX), rel_tol=1e-6):
        return None
    return value


def native_angular_dof_indices(robot, scene_info):
    """Identify native rad/s coordinates from selected physical joint identity."""
    stage = scene_info.get("stage")
    root = scene_info.get("robot_root_prim") or scene_info.get("asset_prim")
    if stage is None or root is None:
        return frozenset()
    from pxr import UsdPhysics

    from .joint_identity import joint_for_native_name, selected_joint_prims

    names = list(robot.dof_names)
    root_path = getattr(robot, "prim_path", None) or str(root.GetPath())
    joints = selected_joint_prims(stage, root_path, names, scene_info.get("asset_prim"))
    return frozenset(
        index
        for index, name in enumerate(names)
        if (joint := joint_for_native_name(joints, name)) is not None and joint.IsA(UsdPhysics.RevoluteJoint)
    )


def resolve_velocity_hints(robot, scene_info):
    """Read optional timing hints without writing limits or guessing linear units.

    A distance/velocity ratio from the same native API has units of seconds
    even when its linear coordinate scale is unqualified. USD hints require
    unique joint identity and a verified conversion to those coordinates.
    Errors from a present runtime getter remain execution errors.
    """
    names = list(robot.dof_names)
    angular_indices = native_angular_dof_indices(robot, scene_info)
    candidates = [[] for _name in names]
    getter = getattr(robot, "get_joint_velocity_limits", None)
    if callable(getter):
        values = getter()
        if values is not None:
            try:
                values = np.asarray(values)
            except (TypeError, ValueError):
                values = np.asarray([])
            if values.ndim == 1 and len(values) == len(names) and values.dtype.kind in "iuf":
                for index, value in enumerate(values):
                    velocity = usable_velocity(value, native_angular=index in angular_indices)
                    if velocity is not None:
                        candidates[index].append((velocity, "runtime joint velocity ceiling"))

    stage = scene_info.get("stage")
    root = scene_info.get("asset_prim")
    if root is None:
        root = scene_info.get("robot_root_prim")
    if stage is not None and root is not None:
        from pxr import UsdPhysics

        from .joint_identity import joint_for_native_name, selected_joint_prims

        root_path = getattr(robot, "prim_path", None) or str(root.GetPath())
        joints = selected_joint_prims(stage, root_path, names, root)
        from simready.foundation.tier_newton.runtime_tests.motion_observer import (
            _newton_version_for_units,
        )

        sdk_version, _source = _newton_version_for_units()
        for index, name in enumerate(names):
            joint = joint_for_native_name(joints, name)
            if joint is None:
                continue
            angular = joint.IsA(UsdPhysics.RevoluteJoint)
            linear = joint.IsA(UsdPhysics.PrismaticJoint)
            if sdk_version != "1.2.1" or not (angular or linear):
                # Only this importer's authored/native conversion is qualified.
                continue
            attributes = ["physxJoint:maxJointVelocity"]
            for attribute_name in attributes:
                attribute = joint.GetAttribute(attribute_name)
                if not attribute or not attribute.HasAuthoredValue():
                    continue
                value = usable_velocity(attribute.Get())
                if value is None:
                    continue
                velocity = math.radians(value) if angular else value
                if usable_velocity(velocity) is not None:
                    candidates[index].append((velocity, "USD " + attribute_name))

    return [
        min(values, key=lambda item: item[0]) if values else (None, "configured fallback duration")
        for values in candidates
    ]


def segment_frames(seg_start, seg_end, observed_start, velocity, config, fallback_frames, *, phase="FRS"):
    """Pace profile peak speed below the hint, with configured response allowance."""
    fps = _finite(config.get("physics_fps", 240.0), "physics_fps", positive=True, phase=phase)
    scale = _finite(
        config.get("sweep_speed_scale", SEGMENT_DEFAULTS["sweep_speed_scale"]),
        "sweep_speed_scale",
        positive=True,
        phase=phase,
    )
    allowance = _finite(
        config.get("sweep_settling_allowance_seconds", SEGMENT_DEFAULTS["sweep_settling_allowance_seconds"]),
        "sweep_settling_allowance_seconds",
        phase=phase,
    )
    maximum = _finite(
        config.get("max_sweep_segment_seconds", SEGMENT_DEFAULTS["max_sweep_segment_seconds"]),
        "max_sweep_segment_seconds",
        positive=True,
        phase=phase,
    )
    if not all(math.isfinite(value) for value in (seg_start, seg_end, observed_start)):
        raise ValueError(f"{phase} segment requires finite commanded and observed positions")
    duration = fallback_frames / fps
    if velocity is not None:
        velocity = usable_velocity(velocity)
        if velocity is None:
            raise ValueError(f"{phase} resolved velocity hint is invalid")
        profile = str(config.get("interpolation_profile", "smoothstep")).lower()
        peak = {"smoothstep": 1.5, "smootherstep": 1.875, "trapezoidal": 2.0}.get(profile, 1.0)
        distance = max(abs(seg_end - seg_start), abs(seg_end - observed_start))
        scaled_velocity = velocity * min(1.0, scale)
        travel_seconds = (
            0.0 if distance == 0 else peak * distance / scaled_velocity if scaled_velocity > 0 else math.inf
        )
        duration = max(duration, travel_seconds + allowance)
    if not math.isfinite(duration) or duration > maximum:
        raise SweepBudgetExceeded(
            "segment_budget",
            f"{phase} segment needs %.3g simulation seconds, exceeding max_sweep_segment_seconds=%.3g; "
            "the test timing budget is insufficient, not an evaluated asset failure" % (duration, maximum),
        )
    ticks = duration * fps
    if not math.isfinite(ticks):
        raise ValueError(f"{phase} segment tick budget must be finite")
    frames = fallback_frames if velocity is None else max(2, math.ceil(ticks))
    if not math.isfinite(frames / fps) or frames / fps > maximum:
        raise SweepBudgetExceeded(
            "segment_budget", f"{phase} rounded segment tick budget exceeds max_sweep_segment_seconds"
        )
    return frames


class SweepBudget:
    """Keep nominal completed ticks separate from a monotonic wall-clock guard."""

    def __init__(self, config, started_at=None):
        self.fps = _finite(config.get("physics_fps", 240.0), "physics_fps", positive=True)
        self.simulation_seconds = _finite(
            config.get("max_sweep_simulation_seconds", 600.0), "max_sweep_simulation_seconds", positive=True
        )
        self.wall_seconds = _finite(
            config.get("max_sweep_wall_seconds", 3360.0), "max_sweep_wall_seconds", positive=True
        )
        if self.wall_seconds > MAX_DURATION_SECONDS - 60:
            raise ValueError("FRS max_sweep_wall_seconds must leave 60 seconds below registered max_duration")
        _finite(config.get("sweep_speed_scale", 0.8), "sweep_speed_scale", positive=True)
        for key, default in (
            ("settle_seconds", 1.0),
            ("pause_at_limits_seconds", 0.15),
            ("sweep_settling_allowance_seconds", 0.25),
        ):
            _finite(config.get(key, default), key)
        ticks = self.simulation_seconds * self.fps
        if not math.isfinite(ticks):
            raise ValueError("FRS simulation tick budget must be finite")
        self.max_ticks = math.floor(ticks)
        self.ticks = 0
        self.diagnostics = None
        self.started_at = time.monotonic() if started_at is None else started_at

    def check_wall(self):
        if time.monotonic() - self.started_at >= self.wall_seconds:
            raise SweepBudgetExceeded(
                "wall_budget",
                "FRS max_sweep_wall_seconds exhausted before completion; test execution is incomplete, "
                "not an evaluated asset failure",
            )

    def reserve(self, ticks):
        self.check_wall()
        if self.ticks + ticks > self.max_ticks:
            raise SweepBudgetExceeded(
                "simulation_budget",
                "FRS max_sweep_simulation_seconds cannot fit the next complete window; "
                "test timing budget is insufficient, not an evaluated asset failure",
            )

    async def step_one(self, ctx):
        self.reserve(1)
        if self.diagnostics is None:
            await ctx.step_one()
        else:
            with self.diagnostics.measure("stepping"):
                await ctx.step_one()
        self.ticks += 1
        if self.diagnostics is not None and self.ticks % 40 == 0:
            self.diagnostics.publish()
        self.check_wall()
