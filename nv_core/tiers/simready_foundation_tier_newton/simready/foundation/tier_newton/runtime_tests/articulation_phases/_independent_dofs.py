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

from numbers import Integral

import numpy as np
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
    require_vector,
)


def validate_indices(indices, count):
    result = set()
    for index in indices:
        if isinstance(index, (bool, np.bool_)) or not isinstance(index, Integral) or not 0 <= index < count:
            raise RequiredReadbackError("Articulation runtime error: excluded/selected DOF index is invalid")
        result.add(int(index))
    return result


def excluded_dof_indices(scene_info, count):
    return validate_indices(
        [
            index
            for key in ("passive_joint_indices", "mimic_follower_indices", "loop_joint_indices")
            for index in (scene_info.get(key) or ())
        ],
        count,
    )


def control_ownership(stage, asset_prim, root_path, dof_names, *, strict_sources=False):
    """Discover dependent coordinates; unexpected query errors fail closed.

    strict_sources qualifies markers through strict loop source reads; the
    default preserves existing control eligibility and coefficient policy.
    """
    from .joint_utils import detect_loop_joints
    from .mimic_joints import detect_mimic_follower_indices

    names = list(dof_names)
    try:
        followers = validate_indices(detect_mimic_follower_indices(stage, asset_prim, root_path, names), len(names))
    except Exception as exc:
        raise RuntimeError("Required mimic control ownership discovery failed; no independent-control verdict") from exc
    try:
        search_root = str(asset_prim.GetPath()) if asset_prim is not None else root_path
        from .joint_identity import selected_joint_prims

        selected_paths = {str(prim.GetPath()) for prim in selected_joint_prims(stage, root_path, names, asset_prim)}
        loops, _ = detect_loop_joints(
            stage,
            search_root,
            names,
            asset_prim=asset_prim,
            selected_joint_paths=selected_paths,
            **({"strict_sources": True} if strict_sources else {}),
        )
        loops = validate_indices(loops, len(names))
    except Exception as exc:
        raise RuntimeError("Required loop control ownership discovery failed; no independent-control verdict") from exc
    return followers, [str(names[i]) for i in sorted(followers)], loops, [str(names[i]) for i in sorted(loops)]


def selected_dof_values(values, indices, count):
    """Validate before conversion/dispatch, including duplicate sparse selections."""
    raw = list(indices)
    selected = validate_indices(raw, count)
    if len(selected) != len(raw):
        raise RequiredReadbackError("Articulation runtime error: selected DOF indices are repeated")
    vector = require_vector(values, "articulation", "indexed command", len(raw)).astype(np.float64)
    return vector, np.asarray(raw, dtype=np.int32)


def require_indexed_control(robot, excluded):
    """Reject unavailable sparse control before writing or advancing a probe."""
    if not excluded or len(excluded) == len(robot.dof_names):
        return
    check = getattr(robot, "require_indexed_joint_control", None)
    if callable(check):
        try:
            check(excluded=excluded)
        except TypeError:
            check()
    for name in ("set_joint_positions_indexed", "set_joint_position_targets_indexed", "set_joint_velocities_indexed"):
        if not callable(getattr(robot, name, None)):
            raise RequiredReadbackError(
                "Articulation runtime error: coupled articulation requires indexed joint control"
            )


def command_targets(robot, positions, excluded=()):
    """Send targets only for independent DOFs; other commands stay untouched."""
    values = require_vector(positions, "articulation", "joint target", len(robot.dof_names)).astype(np.float64)
    excluded = validate_indices(excluded, len(values))
    require_indexed_control(robot, excluded)
    if not excluded:
        robot.set_joint_position_targets(values)
    else:
        indices = np.asarray([i for i in range(len(values)) if i not in excluded], dtype=np.int32)
        if indices.size:
            robot.set_joint_position_targets_indexed(values[indices], indices)


def write_probe_state(robot, positions, excluded=()):
    """Teleport/synchronize only independent DOFs; never overwrite followers."""
    values = require_vector(positions, "articulation", "probe configuration", len(robot.dof_names)).astype(np.float64)
    excluded = validate_indices(excluded, len(values))
    require_indexed_control(robot, excluded)
    if not excluded:
        robot.set_joint_positions(values)
        robot.set_joint_position_targets(values)
        robot.set_joint_velocities(np.zeros_like(values))
    else:
        indices = np.asarray([i for i in range(len(values)) if i not in excluded], dtype=np.int32)
        if indices.size:
            robot.set_joint_positions_indexed(values[indices], indices)
            robot.set_joint_position_targets_indexed(values[indices], indices)
            robot.set_joint_velocities_indexed(np.zeros(len(indices), dtype=np.float64), indices)


def owned_articulation(robot, scene_info, extra_excluded=()):
    """Preserve independent holds without commanding coupled/passive coordinates."""
    raw = (
        [
            index
            for key in ("passive_joint_indices", "mimic_follower_indices", "loop_joint_indices")
            for index in (scene_info.get(key) or ())
        ]
        + list(extra_excluded)
        + list(getattr(robot, "_ik_excluded_indices", ()))
    )
    if not raw:
        return robot
    excluded = excluded_dof_indices(scene_info, len(robot.dof_names))
    excluded.update(validate_indices(extra_excluded, len(robot.dof_names)))
    excluded.update(validate_indices(getattr(robot, "_ik_excluded_indices", ()), len(robot.dof_names)))
    return IndependentRobot(robot, excluded) if excluded else robot


class IndependentRobot:
    """Phase-local sparse facade; native solver read/identity APIs still delegate."""

    def __init__(self, robot, excluded):
        self._control_robot = getattr(robot, "_control_robot", robot)
        self._ik_excluded_indices = validate_indices(excluded, len(self._control_robot.dof_names))
        require_indexed_control(self._control_robot, self._ik_excluded_indices)

    def __getattr__(self, name):
        return getattr(self._control_robot, name)

    def set_joint_positions(self, positions):
        values = require_vector(positions, "articulation", "probe configuration", len(self.dof_names)).astype(
            np.float64
        )
        indices = np.asarray([i for i in range(len(values)) if i not in self._ik_excluded_indices], dtype=np.int32)
        if indices.size:
            if self._ik_excluded_indices:
                self._control_robot.set_joint_positions_indexed(values[indices], indices)
            else:
                self._control_robot.set_joint_positions(values)

    def set_joint_position_targets(self, positions):
        command_targets(self._control_robot, positions, self._ik_excluded_indices)

    def set_joint_velocities(self, velocities):
        values = require_vector(velocities, "articulation", "probe velocity", len(self.dof_names)).astype(np.float64)
        indices = np.asarray([i for i in range(len(values)) if i not in self._ik_excluded_indices], dtype=np.int32)
        if indices.size:
            if self._ik_excluded_indices:
                self._control_robot.set_joint_velocities_indexed(values[indices], indices)
            else:
                self._control_robot.set_joint_velocities(values)


def sample_joint_motion(robot, observers, command, time_s, phase, excluded):
    """Observe uncommanded DOFs without inventing tracking targets or errors."""
    active = {i: observer for i, observer in observers.items() if observer.history is not None}
    if not active:
        return
    try:
        positions = robot.get_joint_positions()
    except Exception:
        positions = None
    for index, observer in active.items():
        values = {}
        try:
            position = float(positions[index]) if positions is not None else None
            if position is not None and not np.isfinite(position):
                position = None
            if position is None:
                observer._warn()
        except Exception:
            position = None
            observer._warn()
        values["position"] = position
        if index not in excluded:
            try:
                target = float(command[index]) if command is not None else None
                if target is not None and not np.isfinite(target):
                    target = None
                    observer._warn()
            except Exception:
                target = None
                observer._warn()
            values["target"] = target
            values["error"] = target - position if target is not None and position is not None else None
        observer.sample(values, time_s=time_s, phase=phase)
