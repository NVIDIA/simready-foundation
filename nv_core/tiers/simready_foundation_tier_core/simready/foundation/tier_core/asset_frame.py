# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Read and author explicit semantic facing in the prim's local coordinate space."""

from __future__ import annotations

import math
from pxr import Gf, Sdf, Usd, UsdGeom

FORWARD_DIRECTION = "simready:assetFrame:forwardDirection"
UNIT_TOLERANCE = 1e-4


def read_forward_direction(prim):
    """Return a validated local vector; missing or malformed data raises ValueError.

    Namespace parents do not supply facing. References, inherits and variants
    compose normally on the queried prim, including instance proxies.
    """
    if not prim or not UsdGeom.Xformable(prim):
        raise ValueError("Facing requires a valid UsdGeomXformable prim")
    attr = prim.GetAttribute(FORWARD_DIRECTION)
    if not attr or not attr.HasAuthoredValueOpinion():
        raise ValueError(f"{prim.GetPath()} must author {FORWARD_DIRECTION}")
    if attr.GetTypeName() != Sdf.ValueTypeNames.Vector3f or not attr.IsCustom():
        raise ValueError(f"{FORWARD_DIRECTION} must be custom vector3f")
    if attr.GetVariability() != Sdf.VariabilityUniform or attr.GetNumTimeSamples():
        raise ValueError(f"{FORWARD_DIRECTION} must be uniform without time samples")
    if attr.HasAuthoredConnections():
        raise ValueError(f"{FORWARD_DIRECTION} must have a value, not a connection")
    value = attr.Get(Usd.TimeCode.Default())
    if not isinstance(value, Gf.Vec3f) or not all(math.isfinite(x) for x in value):
        raise ValueError(f"{FORWARD_DIRECTION} must have a finite default vector")
    if abs(value.GetLength() - 1.0) > UNIT_TOLERANCE:
        raise ValueError(f"{FORWARD_DIRECTION} must be unit length (tolerance {UNIT_TOLERANCE})")
    return value


def world_forward_direction(prim, time=Usd.TimeCode.Default()):
    """Transform a local direction without translation and normalize after scaling."""
    local = read_forward_direction(prim)
    matrix = UsdGeom.XformCache(time).GetLocalToWorldTransform(prim)
    vector = matrix.TransformDir(Gf.Vec3d(local))
    length = vector.GetLength()
    if not all(math.isfinite(x) for x in vector) or not math.isfinite(length) or length <= 1e-12:
        raise ValueError(f"{prim.GetPath()} has a degenerate transformed forward direction")
    return vector / length


def author_forward_direction(prim, direction):
    """Author a caller-selected unit direction; never infer facing from geometry."""
    if not prim or not UsdGeom.Xformable(prim) or prim.IsInstanceProxy():
        raise ValueError("Author facing on an editable UsdGeomXformable prim")
    value = Gf.Vec3f(direction)
    if not all(math.isfinite(x) for x in value) or abs(value.GetLength() - 1.0) > UNIT_TOLERANCE:
        raise ValueError("The supplied direction must be finite and unit length")
    existing = prim.GetProperty(FORWARD_DIRECTION)
    if existing:
        # Validate first so this helper cannot silently repair conflicting data.
        read_forward_direction(prim)
    attr = prim.CreateAttribute(
        FORWARD_DIRECTION, Sdf.ValueTypeNames.Vector3f, custom=True, variability=Sdf.VariabilityUniform
    )
    attr.Set(value)
    return attr


def facing_camera_transform(prim, distance, time=Usd.TimeCode.Default()):
    """Place a camera on the front side, looking at the prim origin, using stage up."""
    if not math.isfinite(distance) or distance <= 0:
        raise ValueError("Camera distance must be finite and positive")
    forward = world_forward_direction(prim, time)
    matrix = UsdGeom.XformCache(time).GetLocalToWorldTransform(prim)
    target = matrix.Transform(Gf.Vec3d(0))
    if not all(math.isfinite(x) for x in target):
        raise ValueError("Camera target must have a finite world position")
    up = Gf.Vec3d(0, 1, 0) if UsdGeom.GetStageUpAxis(prim.GetStage()) == UsdGeom.Tokens.y else Gf.Vec3d(0, 0, 1)
    if abs(Gf.Dot(forward, up)) > 1 - 1e-8:
        raise ValueError("Facing is parallel to stage up; choose an explicit camera roll convention")
    return Gf.Matrix4d().SetLookAt(target + forward * distance, target, up).GetInverse()
