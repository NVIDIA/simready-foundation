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

from simready.foundation.tier_core.runtime_tests.motion_observer import MotionObserver, joint_metadata


def make_joint_observer(ctx, scene_info, joint_name, name, channel_specs, metadata=None, sample_stride=4):
    """Resolve a joint's identity and units without guessing from its name.

    ``{joint}`` units resolve to radians or ``unknown_native``. Core's linear
    tensor scale is unqualified; stage scale alone does not establish it.
    Callers supply actual commands/readbacks and monotonically increasing
    nominal step times; rendering/settling gaps must not be called solver time.
    Older runners without recording support require no USD metadata reads.
    """
    identity = {"joint_name": joint_name, "unit": "unknown_native", "identity_resolved": False}
    partial = False
    if callable(getattr(ctx, "begin_motion_history", None)):
        try:
            root = scene_info.get("asset_prim")
            if root is None:
                root = scene_info.get("robot_root_prim")
            selected_root = scene_info.get("robot_root_prim")
            identity = joint_metadata(
                scene_info.get("stage"),
                root,
                joint_name,
                root_path=str(selected_root.GetPath()) if selected_root else None,
            )
            partial = not identity.get("identity_resolved", False)
        except Exception:
            partial = True
    channels = {}
    for channel, spec in channel_specs.items():
        channels[channel] = dict(spec)
        channels[channel]["unit"] = spec["unit"].replace("{joint}", identity["unit"])
    context = {
        "clock_basis": "nominal observed physics-step index / configured physics_fps; render and setup ticks excluded",
        **(metadata or {}),
        **identity,
    }
    if partial:
        context["context_partial"] = True
    observer = MotionObserver(ctx, name, channels, metadata=context, sample_stride=sample_stride)
    if partial:
        observer._warn()
    return observer


def sample_joint_observers(robot, observers, command, time_s, phase):
    """Optional playback diagnostics, separate from required verdict readbacks.

    Only positions are requested here. Tests needing velocity/effort evidence
    pass their existing required measurements directly to the observer instead.
    A missing readback remains null and marks evidence partial, not a verdict.
    """
    active = {index: observer for index, observer in observers.items() if observer.history is not None}
    if not active:
        return
    try:
        positions = robot.get_joint_positions()
    except Exception:
        positions = None
    for index, observer in active.items():
        position, target = None, None
        try:
            if command is not None:
                target = float(command[index])
            if positions is not None:
                position = float(positions[index])
                if not math.isfinite(position):
                    position = None
                    observer._warn()
            else:
                observer._warn()
            if target is not None and not math.isfinite(target):
                target = None
                observer._warn()
        except Exception:
            observer._warn()
        observer.sample(
            {
                "position": position,
                "target": target,
                "error": target - position if target is not None and position is not None else None,
            },
            time_s=time_s,
            phase=phase,
        )


def record_joint_captures(observers, path):
    for observer in observers.values():
        observer.record_capture(path)


def finish_joint_observers(observers, reason):
    for observer in observers.values():
        observer.finish(reason)
