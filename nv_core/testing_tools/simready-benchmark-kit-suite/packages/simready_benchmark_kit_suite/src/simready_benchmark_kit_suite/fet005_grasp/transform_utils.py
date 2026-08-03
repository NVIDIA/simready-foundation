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
"""Gripper orientation and transform utilities for grasp tests.

Ported from V1 FET005_grasp/transform_utils.py.
"""
import math

import numpy as np
from pxr import Gf, UsdGeom


def compute_gripper_orientation_from_grasp_points(
    grasp_point_1,  # type: List[float]
    grasp_point_2,  # type: List[float]
):
    # type: (...) -> Dict[str, Any]
    """Compute gripper base position, orientation, and pad positions.

    Args:
        grasp_point_1: First grasp point in world space [x, y, z].
        grasp_point_2: Second grasp point in world space [x, y, z].

    Returns:
        Dict with keys: gripper_base_position, gripper_orientation,
        grasp_direction, left_joint_world_pos, right_joint_world_pos,
        grasp_distance.
    """
    gp1 = np.array(grasp_point_1)
    gp2 = np.array(grasp_point_2)
    grasp_direction = gp2 - gp1
    grasp_distance = float(np.linalg.norm(grasp_direction))
    grasp_direction_normalized = grasp_direction / max(1e-9, grasp_distance)
    midpoint = (gp1 + gp2) / 2.0

    # Build orthonormal frame: X = grasp axis, Z = up, Y = cross
    gripper_x = grasp_direction_normalized
    world_up = np.array([0.0, 0.0, 1.0])
    gripper_z = world_up - np.dot(world_up, gripper_x) * gripper_x
    if np.linalg.norm(gripper_z) < 1e-6:
        gripper_z = np.array([0.0, 1.0, 0.0])
    else:
        gripper_z = gripper_z / np.linalg.norm(gripper_z)
    gripper_y = np.cross(gripper_z, gripper_x)
    gripper_y = gripper_y / np.linalg.norm(gripper_y)
    gripper_z = np.cross(gripper_x, gripper_y)
    gripper_z = gripper_z / np.linalg.norm(gripper_z)

    rotation_matrix = np.column_stack([gripper_x, gripper_y, gripper_z])
    quaternion = _rotation_matrix_to_quaternion(rotation_matrix)

    return {
        "gripper_base_position": midpoint.tolist(),
        "gripper_orientation": quaternion.tolist(),
        "grasp_direction": grasp_direction_normalized.tolist(),
        "left_joint_world_pos": gp1.tolist(),
        "right_joint_world_pos": gp2.tolist(),
        "grasp_distance": grasp_distance,
    }


def set_pose_from_transform(prim, pos, rot, scale=None):
    """Set translate + orient + scale on a USD prim.

    Args:
        prim: USD prim (must be Xformable).
        pos: [x, y, z] position.
        rot: [w, x, y, z] quaternion.
        scale: Optional Gf.Vec3d scale (defaults to (1,1,1)).
    """
    if scale is None:
        scale = Gf.Vec3d(1, 1, 1)
    xform = UsdGeom.Xformable(prim)
    xform.ClearXformOpOrder()
    xform_op_t = xform.AddXformOp(UsdGeom.XformOp.TypeTranslate, UsdGeom.XformOp.PrecisionDouble, "")
    xform_op_r = xform.AddXformOp(UsdGeom.XformOp.TypeOrient, UsdGeom.XformOp.PrecisionDouble, "")
    xform_op_s = xform.AddXformOp(UsdGeom.XformOp.TypeScale, UsdGeom.XformOp.PrecisionDouble, "")
    xform_op_t.Set(Gf.Vec3d(float(pos[0]), float(pos[1]), float(pos[2])))
    xform_op_r.Set(Gf.Quatd(float(rot[0]), float(rot[1]), float(rot[2]), float(rot[3])))
    xform_op_s.Set(Gf.Vec3d(scale[0], scale[1], scale[2]))


def _rotation_matrix_to_quaternion(rotation_matrix):
    # type: (np.ndarray) -> np.ndarray
    """Convert a 3x3 rotation matrix to [w, x, y, z] quaternion."""
    trace = np.trace(rotation_matrix)
    if trace > 0:
        s = math.sqrt(trace + 1.0) * 2
        w = 0.25 * s
        x = (rotation_matrix[2, 1] - rotation_matrix[1, 2]) / s
        y = (rotation_matrix[0, 2] - rotation_matrix[2, 0]) / s
        z = (rotation_matrix[1, 0] - rotation_matrix[0, 1]) / s
    elif rotation_matrix[0, 0] > rotation_matrix[1, 1] and rotation_matrix[0, 0] > rotation_matrix[2, 2]:
        s = math.sqrt(1.0 + rotation_matrix[0, 0] - rotation_matrix[1, 1] - rotation_matrix[2, 2]) * 2
        w = (rotation_matrix[2, 1] - rotation_matrix[1, 2]) / s
        x = 0.25 * s
        y = (rotation_matrix[0, 1] + rotation_matrix[1, 0]) / s
        z = (rotation_matrix[0, 2] + rotation_matrix[2, 0]) / s
    elif rotation_matrix[1, 1] > rotation_matrix[2, 2]:
        s = math.sqrt(1.0 + rotation_matrix[1, 1] - rotation_matrix[0, 0] - rotation_matrix[2, 2]) * 2
        w = (rotation_matrix[0, 2] - rotation_matrix[2, 0]) / s
        x = (rotation_matrix[0, 1] + rotation_matrix[1, 0]) / s
        y = 0.25 * s
        z = (rotation_matrix[1, 2] + rotation_matrix[2, 1]) / s
    else:
        s = math.sqrt(1.0 + rotation_matrix[2, 2] - rotation_matrix[0, 0] - rotation_matrix[1, 1]) * 2
        w = (rotation_matrix[1, 0] - rotation_matrix[0, 1]) / s
        x = (rotation_matrix[0, 2] + rotation_matrix[2, 0]) / s
        y = (rotation_matrix[1, 2] + rotation_matrix[2, 1]) / s
        z = 0.25 * s
    return np.array([w, x, y, z])
