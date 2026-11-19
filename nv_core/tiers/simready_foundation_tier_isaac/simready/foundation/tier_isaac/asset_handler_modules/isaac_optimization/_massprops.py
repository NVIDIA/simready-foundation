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
"""Rigid-body mass property aggregation for the fixed-joint merge.

The validator and adapter share this rigid-body composition:

    M = sum(m_i)
    C = sum(m_i * c_i) / M
    I = sum( R_i * I_i * R_i^T + m_i * ((d_i . d_i) * Identity - outer(d_i, d_i)) )
    d_i = c_i - C

with every quantity first transformed into the retained body's frame.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from pxr import Gf, Usd, UsdPhysics

from . import _massinfo

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class BodyMass:
    """Resolved mass properties of one rigid body, in that body's local frame."""

    path: str
    mass: float
    center_of_mass: FloatArray  # (3,)
    inertia: FloatArray  # (3, 3) about the centre of mass, in the body frame


@dataclass(frozen=True)
class AggregateMass:
    """Aggregate mass properties expressed in the retained body's frame."""

    mass: float
    center_of_mass: FloatArray  # (3,)
    inertia: FloatArray  # (3, 3) about the aggregate centre of mass
    diagonal_inertia: FloatArray  # (3,) eigenvalues, ascending by eigenvector order
    principal_axes: Gf.Quatf
    sources: tuple[str, ...]


class MassResolutionError(RuntimeError):
    """Raised when a body's mass properties cannot be resolved from authored data."""


def _matrix3(m: Gf.Matrix4d) -> FloatArray:
    # Gf transforms row vectors; tensor algebra below transforms columns.
    return np.array([[m[r][c] for c in range(3)] for r in range(3)], dtype=np.float64).T


def _quat_to_matrix(quat: Gf.Quatf | Gf.Quatd) -> FloatArray:
    imaginary = quat.GetImaginary()
    q = Gf.Quatd(float(quat.GetReal()), Gf.Vec3d(float(imaginary[0]), float(imaginary[1]), float(imaginary[2])))
    return np.array(Gf.Matrix3d(q), dtype=np.float64).T


def _has_shear_or_nonuniform_scale(
    rotation_part: FloatArray, tolerance: float = 1e-6
) -> bool:
    """A rigid transform's upper 3x3 must be orthogonal with unit determinant."""
    should_be_identity = rotation_part.T @ rotation_part
    if not np.allclose(should_be_identity, np.eye(3), atol=tolerance):
        return True
    return bool(abs(abs(np.linalg.det(rotation_part)) - 1.0) > tolerance)


def resolve_body_mass(prim: Usd.Prim) -> BodyMass:
    """Resolve authored or collider-derived mass using USD precedence rules.

    :mod:`._massinfo` supplies geometry measurements. Unsupported collider
    approximations require complete authored body properties.
    """
    path = str(prim.GetPath())

    mass_api = UsdPhysics.MassAPI(prim)
    attributes = [mass_api.GetMassAttr(), mass_api.GetDiagonalInertiaAttr(),
                  mass_api.GetCenterOfMassAttr(), mass_api.GetPrincipalAxesAttr()]
    values = [attr.Get() for attr in attributes]
    # Complete authored properties can cover shapes the callback cannot measure.
    complete = all(attr and attr.HasAuthoredValue() for attr in attributes)
    if complete:
        mass_value, diag, center_value, axes = values
        complete = (mass_value is not None and np.isfinite(mass_value) and mass_value > 0 and diag is not None
                    and all(np.isfinite(v) and v > 0 for v in diag) and np.all(np.isfinite(center_value))
                    and axes is not None and abs(axes.GetLength() - 1.) < 1e-5)
    approximated = _massinfo.shape_changing_mesh_colliders(prim)
    if approximated and not complete:
        shapes = ", ".join(f"<{shape}> ({approximation})" for shape, approximation in approximated)
        raise MassResolutionError(
            f"<{path}> derives mass properties from shape-changing mesh approximation(s) "
            f"{shapes}; author complete body physics:mass, physics:diagonalInertia, "
            "physics:centerOfMass, and physics:principalAxes before merging"
        )
    try:
        resolved = _massinfo.compute_body_mass(prim)
    except ValueError as error:
        if not complete:
            raise MassResolutionError(str(error)) from error
        resolved = tuple(values)
    if resolved is None:
        raise MassResolutionError(
            f"<{path}> has neither an authored physics:mass nor measurable collision geometry"
        )

    mass, diagonal_value, com_value, axes_value = resolved

    if not np.isfinite(mass) or mass <= 0.0:
        raise MassResolutionError(f"<{path}> resolved a non-positive or non-finite mass ({mass})")

    diagonal = np.array(
        [float(diagonal_value[0]), float(diagonal_value[1]), float(diagonal_value[2])],
        dtype=np.float64,
    )
    if not np.all(np.isfinite(diagonal)) or np.any(diagonal < 0.0):
        raise MassResolutionError(f"<{path}> resolved a non-finite or negative inertia {diagonal}")

    com = np.array(
        [float(com_value[0]), float(com_value[1]), float(com_value[2])], dtype=np.float64
    )
    rotation = _quat_to_matrix(axes_value)
    inertia = rotation @ np.diag(diagonal) @ rotation.T
    return BodyMass(path=path, mass=mass, center_of_mass=com, inertia=inertia)


def aggregate(
    bodies: list[tuple[BodyMass, Gf.Matrix4d]],
    retained_world: Gf.Matrix4d,
) -> AggregateMass:
    """Combine bodies into the retained body's frame.

    Args:
        bodies: each body's resolved local mass properties and its world transform.
        retained_world: world transform of the body the merge keeps.
    """
    if not bodies:
        raise MassResolutionError("no bodies to aggregate")

    retained_inverse = retained_world.GetInverse()

    total_mass = 0.0
    weighted_com: FloatArray = np.zeros(3, dtype=np.float64)
    placed: list[tuple[float, FloatArray, FloatArray]] = []

    # Sorted by prim path so the accumulation order is fixed.
    for body, body_world in sorted(bodies, key=lambda item: item[0].path):
        to_retained = body_world * retained_inverse
        rotation = _matrix3(to_retained)
        if _has_shear_or_nonuniform_scale(rotation):
            raise MassResolutionError(
                f"<{body.path}> has a non-rigid transform relative to the retained body "
                f"(shear or non-uniform scale), so its inertia cannot be transformed"
            )

        com_local = Gf.Vec3d(*(float(v) for v in body.center_of_mass))
        com_in_retained = to_retained.Transform(com_local)
        com = np.array([com_in_retained[0], com_in_retained[1], com_in_retained[2]], dtype=np.float64)

        inertia = rotation @ body.inertia @ rotation.T

        total_mass += body.mass
        weighted_com += body.mass * com
        placed.append((body.mass, com, inertia))

    if total_mass <= 0.0 or not np.isfinite(total_mass):
        raise MassResolutionError(f"aggregate mass is not positive and finite ({total_mass})")

    center = weighted_com / total_mass

    inertia_total: FloatArray = np.zeros((3, 3), dtype=np.float64)
    for mass, com, inertia in placed:
        offset = com - center
        inertia_total += inertia + mass * (float(offset @ offset) * np.eye(3) - np.outer(offset, offset))

    # Symmetrise before diagonalising to remove accumulated asymmetry.
    inertia_total = 0.5 * (inertia_total + inertia_total.T)
    eigenvalues, eigenvectors = np.linalg.eigh(inertia_total)

    # eigh returns an orthonormal basis but not necessarily right-handed.
    if np.linalg.det(eigenvectors) < 0:
        eigenvectors[:, 0] = -eigenvectors[:, 0]

    quat = Gf.Matrix3d(*(float(v) for v in eigenvectors.T.flatten())).ExtractRotation().GetQuat()
    principal = Gf.Quatf(
        float(quat.GetReal()),
        Gf.Vec3f(*(float(v) for v in quat.GetImaginary())),
    )

    return AggregateMass(
        mass=total_mass,
        center_of_mass=center,
        inertia=inertia_total,
        diagonal_inertia=eigenvalues,
        principal_axes=principal,
        sources=tuple(sorted(body.path for body, _ in bodies)),
    )


def reconstruct_inertia(
    diagonal: FloatArray, principal_axes: Gf.Quatf | Gf.Quatd
) -> FloatArray:
    """Rebuild the full inertia tensor from its diagonal and principal axes."""
    rotation = _quat_to_matrix(principal_axes)
    return rotation @ np.diag(np.asarray(diagonal, dtype=np.float64)) @ rotation.T
