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
"""Geometric mass information for collision shapes.

The callback supplies volume and unit-density inertia to
``UsdPhysics.RigidBodyAPI.ComputeMassProperties``, which applies authored mass,
collider density, physics material density, and default-density precedence.

Returned per shape, in the shape's own local frame:

* ``volume``     -- shape volume, or a negative number when it cannot be measured
* ``inertia``    -- inertia at unit density, about the shape's centre of mass
* ``centerOfMass``, ``localPos``, ``localRot`` -- pose relative to the body

Scale cannot be expressed in ``localPos``/``localRot``, so it is baked into the
geometry here.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

FloatArray = NDArray[np.float64]
ShapeMass = tuple[float, FloatArray]
MeshMass = tuple[float, FloatArray, FloatArray]
MassProperties = tuple[float, Gf.Vec3f, Gf.Vec3f, Gf.Quatf]
MassInformationFn = Callable[
    [Usd.Prim], UsdPhysics.RigidBodyAPI.MassInformation
]

# Canonical tetrahedron covariance, used for exact mesh integration.
_TET_COVARIANCE = np.array([[2.0, 1.0, 1.0], [1.0, 2.0, 1.0], [1.0, 1.0, 2.0]], dtype=np.float64) / 120.0


def _decompose(matrix: Gf.Matrix4d) -> tuple[Gf.Vec3f, Gf.Quatf, FloatArray]:
    """Split a local-to-body transform into translation, rotation, and scale."""
    transform = Gf.Transform(matrix)
    translation = transform.GetTranslation()
    rotation = transform.GetRotation().GetQuat()
    scale = transform.GetScale()
    return (
        Gf.Vec3f(*(float(v) for v in translation)),
        Gf.Quatf(float(rotation.GetReal()), Gf.Vec3f(*(float(v) for v in rotation.GetImaginary()))),
        np.array([float(scale[0]), float(scale[1]), float(scale[2])], dtype=np.float64),
    )


def _inertia_from_covariance(covariance: FloatArray) -> FloatArray:
    return np.array(
        np.trace(covariance) * np.eye(3) - covariance, dtype=np.float64
    )


def _axis_index(prim: Usd.Prim, default: str = "Z") -> int:
    attr = prim.GetAttribute("axis")
    axis = str(attr.Get()) if attr and attr.Get() else default
    return {"X": 0, "Y": 1, "Z": 2}.get(axis.upper(), 2)


def _diag_about_axis(axis: int, along: float, across: float) -> FloatArray:
    values = [across, across, across]
    values[axis] = along
    return np.diag(values)


def _cube(prim: Usd.Prim, scale: FloatArray) -> ShapeMass:
    attr = UsdGeom.Cube(prim).GetSizeAttr()
    size = float(attr.Get()) if attr and attr.Get() is not None else 2.0
    extents = np.abs(scale) * size
    volume = float(np.prod(extents))
    x, y, z = extents
    inertia = np.diag(
        [
            volume * (y * y + z * z) / 12.0,
            volume * (x * x + z * z) / 12.0,
            volume * (x * x + y * y) / 12.0,
        ]
    )
    return volume, inertia


def _sphere(prim: Usd.Prim, scale: FloatArray) -> ShapeMass:
    attr = UsdGeom.Sphere(prim).GetRadiusAttr()
    radius = float(attr.Get()) if attr and attr.Get() is not None else 1.0
    radius *= float(np.mean(np.abs(scale)))
    volume = 4.0 / 3.0 * math.pi * radius**3
    value = 0.4 * volume * radius * radius
    return volume, np.diag([value, value, value])


def _cylinder(prim: Usd.Prim, scale: FloatArray) -> ShapeMass:
    cylinder = UsdGeom.Cylinder(prim)
    radius = float(cylinder.GetRadiusAttr().Get())
    height = float(cylinder.GetHeightAttr().Get())
    axis = _axis_index(prim)
    radial = float(np.mean([abs(scale[i]) for i in range(3) if i != axis]))
    radius *= radial
    height *= abs(scale[axis])
    volume = math.pi * radius * radius * height
    along = 0.5 * volume * radius * radius
    across = volume * (3.0 * radius * radius + height * height) / 12.0
    return volume, _diag_about_axis(axis, along, across)


def _capsule(prim: Usd.Prim, scale: FloatArray) -> ShapeMass:
    capsule = UsdGeom.Capsule(prim)
    radius = float(capsule.GetRadiusAttr().Get())
    height = float(capsule.GetHeightAttr().Get())
    axis = _axis_index(prim)
    radial = float(np.mean([abs(scale[i]) for i in range(3) if i != axis]))
    radius *= radial
    height *= abs(scale[axis])

    cylinder_volume = math.pi * radius * radius * height
    sphere_volume = 4.0 / 3.0 * math.pi * radius**3
    volume = cylinder_volume + sphere_volume

    cylinder_along = 0.5 * cylinder_volume * radius * radius
    cylinder_across = cylinder_volume * (3.0 * radius * radius + height * height) / 12.0

    sphere_along = 0.4 * sphere_volume * radius * radius
    # Each hemisphere's sphere-center moment must first be shifted to its own
    # COM, then to its position at the end of the cylinder.
    offset = height / 2.0 + 3.0 * radius / 8.0
    sphere_across = sphere_along + sphere_volume * (offset * offset - (3.0 * radius / 8.0) ** 2)

    return volume, _diag_about_axis(
        axis, cylinder_along + sphere_along, cylinder_across + sphere_across
    )


def _cone(prim: Usd.Prim, scale: FloatArray) -> ShapeMass:
    cone = UsdGeom.Cone(prim)
    radius = float(cone.GetRadiusAttr().Get())
    height = float(cone.GetHeightAttr().Get())
    axis = _axis_index(prim)
    radial = float(np.mean([abs(scale[i]) for i in range(3) if i != axis]))
    radius *= radial
    height *= abs(scale[axis])
    volume = math.pi * radius * radius * height / 3.0
    along = 0.3 * volume * radius * radius
    across = volume * (3.0 * radius * radius / 20.0 + 3.0 * height * height / 80.0)
    return volume, _diag_about_axis(axis, along, across)


def _shape_changing_mesh_approximation(prim: Usd.Prim) -> str | None:
    """Return the approximation only when it changes the authored surface."""
    if not prim.HasAPI(UsdPhysics.MeshCollisionAPI):
        return None
    attr = UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr()
    approximation = str(attr.Get() or "none") if attr else "none"
    return approximation if approximation not in {"none", "sdf"} else None


def shape_changing_mesh_colliders(body_prim: Usd.Prim) -> list[tuple[str, str]]:
    """Mesh colliders whose runtime shape differs from their authored surface."""
    found: list[tuple[str, str]] = []
    prim_range = Usd.PrimRange(
        body_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)
    )
    iterator = iter(prim_range)
    for prim in iterator:
        if prim != body_prim and prim.HasAPI(UsdPhysics.RigidBodyAPI):
            iterator.PruneChildren()
            continue
        if not (
            prim.IsA(UsdGeom.Mesh)
            and prim.HasAPI(UsdPhysics.CollisionAPI)
        ):
            continue
        approximation = _shape_changing_mesh_approximation(prim)
        if approximation is not None:
            found.append((str(prim.GetPath()), approximation))
    return found


def _mesh(prim: Usd.Prim, scale: FloatArray) -> MeshMass:
    """Exact volume, centroid, and inertia of a closed mesh by tetrahedron integration.

    Each triangle forms a tetrahedron with the origin; signed contributions
    cancel for concavities, so the result is exact for any closed manifold.
    Return an unmeasurable marker for shape-changing approximations such as a
    convex hull, decomposition, or simplification. SDF samples the authored
    surface for distance queries, so that surface remains measurable here.
    """
    if _shape_changing_mesh_approximation(prim) is not None:
        return -1.0, np.eye(3), np.zeros(3)

    mesh = UsdGeom.Mesh(prim)
    points_attr = mesh.GetPointsAttr()
    counts_attr = mesh.GetFaceVertexCountsAttr()
    indices_attr = mesh.GetFaceVertexIndicesAttr()
    if not (points_attr and counts_attr and indices_attr):
        return -1.0, np.eye(3), np.zeros(3)

    points = np.array(points_attr.Get() or [], dtype=np.float64)
    counts = np.array(counts_attr.Get() or [], dtype=np.int64)
    indices = np.array(indices_attr.Get() or [], dtype=np.int64)
    if points.size == 0 or counts.size == 0 or indices.size == 0:
        return -1.0, np.eye(3), np.zeros(3)

    if (points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all()
            or np.any(counts < 3) or counts.sum() != len(indices)
            or np.any(indices < 0) or np.any(indices >= len(points))):
        raise ValueError(f"<{prim.GetPath()}> has invalid collision mesh topology")
    # Exporters may split coincident points along UV or normal seams. Check
    # closure by exact geometric vertices rather than requiring welded indices.
    _, vertices = np.unique(points, axis=0, return_inverse=True)
    edges = Counter()
    cursor = 0
    for count in counts:
        face = vertices[indices[cursor:cursor + count]]
        cursor += count
        for a, b in zip(face, np.roll(face, -1)):
            edges[(int(a), int(b))] += 1
    if any(a == b or n != 1 or edges[(b, a)] != 1 for (a, b), n in edges.items()):
        raise ValueError(
            f"<{prim.GetPath()}> collision mesh must be closed and consistently wound "
            "to derive solid mass; author complete body mass properties otherwise"
        )

    points = points * scale

    total_volume = 0.0
    weighted_centroid: FloatArray = np.zeros(3, dtype=np.float64)
    covariance: FloatArray = np.zeros((3, 3), dtype=np.float64)

    offset = 0
    for count in counts:
        face = indices[offset : offset + count]
        offset += count
        if count < 3:
            continue
        # Fan-triangulate; correct for convex faces and standard for USD meshes.
        for i in range(1, count - 1):
            a, b, c = points[face[0]], points[face[i]], points[face[i + 1]]
            jacobian = np.column_stack((a, b, c))
            determinant = float(np.linalg.det(jacobian))
            if determinant == 0.0:
                continue
            total_volume += determinant / 6.0
            weighted_centroid += (determinant / 6.0) * (a + b + c) / 4.0
            covariance += determinant * (jacobian @ _TET_COVARIANCE @ jacobian.T)

    if abs(total_volume) < 1e-18:
        return -1.0, np.eye(3), np.zeros(3)

    if total_volume < 0.0:
        # Reversed winding; flip so volume and inertia are positive.
        total_volume = -total_volume
        weighted_centroid = -weighted_centroid
        covariance = -covariance

    centroid = weighted_centroid / total_volume
    inertia = _inertia_from_covariance(covariance)

    # Shift from the origin to the centroid (parallel axis, unit density).
    offset_outer = total_volume * (float(centroid @ centroid) * np.eye(3) - np.outer(centroid, centroid))
    return total_volume, inertia - offset_outer, centroid


_HANDLERS = (
    (UsdGeom.Cube, _cube),
    (UsdGeom.Sphere, _sphere),
    (UsdGeom.Capsule, _capsule),
    (UsdGeom.Cylinder, _cylinder),
    (UsdGeom.Cone, _cone),
)


def make_mass_information_fn(body_prim: Usd.Prim) -> MassInformationFn:
    """Build the ``MassInformationFn`` callback for one rigid body."""
    cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    body_world = cache.GetLocalToWorldTransform(body_prim)
    body_inverse = body_world.GetInverse()

    def mass_information(
        prim: Usd.Prim,
    ) -> UsdPhysics.RigidBodyAPI.MassInformation:
        info = UsdPhysics.RigidBodyAPI.MassInformation()
        shape_world = cache.GetLocalToWorldTransform(prim)
        local = shape_world * body_inverse
        translation, rotation, scale = _decompose(local)
        reconstructed = np.diag(scale) @ np.asarray(Gf.Matrix3d(Gf.Quatd(rotation)))
        if not np.allclose(reconstructed, np.asarray(local)[:3, :3], atol=1e-6):
            raise ValueError(f"<{prim.GetPath()}> has collider shear that cannot be measured safely")
        if prim.IsA(UsdGeom.Sphere) and not np.allclose(np.abs(scale), abs(scale[0]), atol=1e-6):
            raise ValueError(f"<{prim.GetPath()}> has non-uniform sphere scale; author complete body mass properties")
        if any(prim.IsA(schema) for schema in (UsdGeom.Capsule, UsdGeom.Cylinder, UsdGeom.Cone)):
            radial = [abs(scale[i]) for i in range(3) if i != _axis_index(prim)]
            if not np.isclose(*radial, atol=1e-6):
                raise ValueError(f"<{prim.GetPath()}> has non-uniform radial scale; author complete body mass properties")

        info.localPos = translation
        info.localRot = rotation
        info.centerOfMass = Gf.Vec3f(0.0, 0.0, 0.0)
        info.volume = -1.0
        info.inertia = Gf.Matrix3f(1.0)

        centroid: FloatArray = np.zeros(3)
        volume = -1.0
        inertia: FloatArray = np.eye(3)

        if prim.IsA(UsdGeom.Mesh):
            volume, inertia, centroid = _mesh(prim, scale)
        else:
            for schema, handler in _HANDLERS:
                if prim.IsA(schema):
                    volume, inertia = handler(prim, scale)
                    if schema == UsdGeom.Cone:
                        axis = _axis_index(prim)
                        centroid[axis] = -float(UsdGeom.Cone(prim).GetHeightAttr().Get()) * scale[axis] / 4.0
                    break

        if volume is not None and volume > 0.0:
            info.volume = float(volume)
            info.inertia = Gf.Matrix3f(*(float(v) for v in np.asarray(inertia).flatten()))
            info.centerOfMass = Gf.Vec3f(*(float(v) for v in centroid))

        return info

    return mass_information


# Retain only the current composition's scratch stage, so processing a batch
# does not keep every prior asset alive. Different session selections are distinct.
_DEINSTANCED: dict[tuple[str, str], Usd.Stage] = {}


def _deinstanced(stage: Usd.Stage) -> Usd.Stage | None:
    """Resolve USD 25.05's skipped instance colliders in a scratch session layer.

    Prim paths and source layers stay unchanged. Sublayering the original session
    preserves its variant selections; the cache retains only this composition.
    """
    root = stage.GetRootLayer()
    session = stage.GetSessionLayer()
    key = (root.identifier, session.identifier if session else "")
    scratch = _DEINSTANCED.get(key)
    found = scratch is not None
    if scratch is None:
        scratch_session = Sdf.Layer.CreateAnonymous("deinstanced.usda")
        if session:
            scratch_session.subLayerPaths.append(session.identifier)
        scratch = Usd.Stage.Open(root, scratch_session, Usd.Stage.LoadAll)
        if scratch is None:
            return None
        scratch.SetEditTarget(scratch.GetSessionLayer())

    # Source composition can acquire more instances between resolutions.
    for prim in Usd.PrimRange(
        scratch.GetPseudoRoot(), Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)
    ):
        if prim.IsInstance():
            prim.SetInstanceable(False)
            found = True
    if not found:
        return None

    _DEINSTANCED.clear()
    _DEINSTANCED[key] = scratch
    return scratch


def compute_body_mass(prim: Usd.Prim) -> MassProperties | None:
    """Resolve one body's mass properties the way a runtime would.

    Returns ``(mass, diagonal_inertia, center_of_mass, principal_axes)`` in the
    body's local frame, or ``None`` when the body has neither authored mass nor
    measurable collision geometry.
    """
    rigid_body = UsdPhysics.RigidBodyAPI(prim)
    if not rigid_body:
        return None

    # Older USD versions skip instance-proxy colliders even when direct
    # colliders produce a positive, but incomplete, result. Resolve the whole
    # body on the expanded view before accepting any mass properties.
    if prim.IsInstanceProxy() or any(child.IsInstance() for child in Usd.PrimRange(prim)):
        scratch = _deinstanced(prim.GetStage())
        if scratch is None:
            return None
        prim = scratch.GetPrimAtPath(prim.GetPath())
        rigid_body = UsdPhysics.RigidBodyAPI(prim)
        if not rigid_body:
            return None
    # The Python wrapper returns the out-parameters as a tuple.
    return _valid(rigid_body.ComputeMassProperties(make_mass_information_fn(prim)))


def _valid(result: MassProperties | None) -> MassProperties | None:
    if not result:
        return None
    mass, diagonal, center, principal = result
    if mass is None or not math.isfinite(float(mass)) or float(mass) <= 0.0:
        return None
    return float(mass), diagonal, center, principal
