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
"""Required runtime view guards, separate from optional motion observation."""

import numpy as np


class RequiredReadbackError(RuntimeError):
    """The required test view is unavailable; no asset-response verdict exists."""


def as_real_array(values):
    """Preserve real dtypes and reject booleans before sequence promotion.

    NumPy otherwise turns mixed Python/NumPy boolean and numeric lists into
    usable-looking float arrays. Inspect untyped containers first, including
    qualified single-articulation rows, without changing typed numeric arrays.
    """
    pending = [values]
    seen = set()
    while pending:
        value = pending.pop()
        if isinstance(value, (bool, np.bool_)):
            raise ValueError("boolean coordinates are not real numeric observations")
        if isinstance(value, (list, tuple)):
            if id(value) not in seen:
                seen.add(id(value))
                pending.extend(value)
        elif isinstance(value, np.ndarray) and value.dtype.kind not in "iuf":
            raise ValueError("view must contain real numeric coordinates, not %s" % value.dtype)
    array = np.asarray(values)
    if array.dtype.kind not in "iuf":
        raise ValueError("view must contain real numeric coordinates, not %s" % array.dtype)
    return array


def require_vector(values, phase, kind, expected_size=None):
    """Validate an existing read, preserving its array dtype and adding no reads."""
    try:
        if values is None:
            raise ValueError("view returned None")
        array = as_real_array(values)
        if array.dtype.kind not in "iuf":
            raise ValueError("view must contain real numeric coordinates, not %s" % array.dtype)
        numeric = np.asarray(values, dtype=np.float64)
        if numeric.ndim != 1 or (expected_size is not None and numeric.size != expected_size):
            raise ValueError("unexpected view shape %s" % (numeric.shape,))
        if numeric.size == 0 or not bool(np.isfinite(numeric).all()):
            raise ValueError("empty or nonfinite view")
    except Exception as exc:
        raise RequiredReadbackError(
            "%s runtime error: required %s readback is unavailable, nonfinite or has invalid shape; "
            "the response criterion was not evaluated." % (phase, kind)
        ) from exc
    return array


def _read_joints(robot, method_name, phase, kind):
    try:
        values = getattr(robot, method_name)()
    except RequiredReadbackError:
        raise
    except Exception as exc:
        raise RequiredReadbackError(
            "%s runtime error: required %s readback failed; the response criterion was not evaluated. %s"
            % (phase, kind, exc)
        ) from exc
    return require_vector(values, phase, kind, getattr(robot, "dof_count", None))


def required_positions(robot, phase):
    """Read required control/verdict positions once; optional hooks stay separate."""
    return _read_joints(robot, "get_joint_positions", phase, "joint position")


def required_velocities(robot, phase):
    """Read required control/verdict velocities once; optional hooks stay separate."""
    return _read_joints(robot, "get_joint_velocities", phase, "joint velocity")


def required_link_pose(robot, body_path, phase):
    """Read one required live link pose; USD authoring is not runtime evidence."""
    try:
        transforms = robot.get_link_world_transforms([body_path])
        pose = transforms.get(body_path) if transforms else None
        if pose is None:
            detail = getattr(robot, "_link_transform_resolve_detail", "")
            raise ValueError(
                "Live end-effector transform unavailable for %s%s" % (body_path, ": " + detail if detail else "")
            )
        position = require_vector(pose[0], phase, "end-effector position", 3)
        quaternion = require_vector(pose[1], phase, "end-effector quaternion", 4)
        norm = float(np.linalg.norm(quaternion))
        if not np.isfinite(norm) or norm <= 0.0:
            raise ValueError("invalid end-effector quaternion norm")
    except RequiredReadbackError:
        raise
    except Exception as exc:
        raise RequiredReadbackError(
            "%s runtime error: required live end-effector pose is unavailable; "
            "the response criterion was not evaluated. %s" % (phase, exc)
        ) from exc
    return position, quaternion
