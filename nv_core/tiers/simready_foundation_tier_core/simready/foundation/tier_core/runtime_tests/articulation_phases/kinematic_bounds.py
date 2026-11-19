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
"""Conservative authored reach reference for a live articulation safety canary.

This freezes a setup reference, not authored poses as motion observations.
Unqualified layouts return no reference; callers must not treat volume growth
from an arbitrary initial pose as proof of an asset explosion.
"""

import math
from dataclasses import dataclass

from simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils import (
    note_secondary_error,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_targets import (
    _FLOAT32_LIMIT_SENTINEL,
    bounded_joint_range,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
)


def articulation_span_reference(prim):
    from pxr import Gf, Usd, UsdGeom, UsdPhysics

    if not isinstance(prim, Usd.Prim) or not prim or not prim.IsValid():
        return None
    nodes = list(Usd.PrimRange(prim, Usd.TraverseInstanceProxies()))
    bodies = {
        str(p.GetPath()): p
        for p in nodes
        if p.HasAPI(UsdPhysics.RigidBodyAPI) and UsdPhysics.RigidBodyAPI(p).GetRigidBodyEnabledAttr().Get() is not False
    }
    if not bodies:
        return None
    transforms = UsdGeom.XformCache(Usd.TimeCode.Default())
    bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy"])
    radii = dict.fromkeys(bodies, 0.0)
    matrices = {path: transforms.GetLocalToWorldTransform(body) for path, body in bodies.items()}
    for matrix in matrices.values():
        if not all(math.isfinite(float(matrix[i][j])) for i in range(4) for j in range(4)):
            return None
    for geometry in nodes:
        if not geometry.IsA(UsdGeom.Boundable):
            continue
        imageable = UsdGeom.Imageable(geometry)
        if imageable.ComputePurpose() not in (UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy):
            continue
        owner = geometry
        while owner and not owner.IsPseudoRoot() and str(owner.GetPath()) not in bodies:
            owner = owner.GetParent()
        if not owner or str(owner.GetPath()) not in bodies:
            return None
        owner_path = str(owner.GetPath())
        box = bounds.ComputeWorldBound(geometry).ComputeAlignedRange()
        if box.IsEmpty():
            return None
        origin = matrices[owner_path].ExtractTranslation()
        radius = max(
            math.hypot(
                *(float(box.GetMax()[i] if bits & (1 << i) else box.GetMin()[i]) - float(origin[i]) for i in range(3))
            )
            for bits in range(8)
        )
        if not math.isfinite(radius):
            return None
        radii[owner_path] = max(radii[owner_path], radius)
    adjacency = {path: set() for path in bodies}
    edge_lengths = []
    for candidate in nodes:
        if not candidate.IsA(UsdPhysics.Joint):
            continue
        joint = UsdPhysics.Joint(candidate)
        if joint.GetJointEnabledAttr().Get() is False:
            continue
        first, second = joint.GetBody0Rel().GetTargets(), joint.GetBody1Rel().GetTargets()
        if not first or not second:
            continue  # World anchor: global translation is irrelevant to span.
        if len(first) != 1 or len(second) != 1 or any(str(path) not in bodies for path in (first[0], second[0])):
            return None
        if not any(
            candidate.IsA(kind)
            for kind in (
                UsdPhysics.FixedJoint,
                UsdPhysics.RevoluteJoint,
                UsdPhysics.SphericalJoint,
                UsdPhysics.PrismaticJoint,
            )
        ):
            return None
        left, right = str(first[0]), str(second[0])
        offsets = [
            matrices[path].TransformDir(Gf.Vec3d(position))
            for path, position in ((left, joint.GetLocalPos0Attr().Get()), (right, joint.GetLocalPos1Attr().Get()))
        ]
        length = sum(math.hypot(*(float(v[i]) for i in range(3))) for v in offsets)
        if candidate.IsA(UsdPhysics.PrismaticJoint):
            linear = UsdPhysics.PrismaticJoint(candidate)
            lower = float(linear.GetLowerLimitAttr().Get())
            upper = float(linear.GetUpperLimitAttr().Get())
            limits = bounded_joint_range(lower, upper, 0.0)
            # A locked finite prismatic joint contributes its fixed offset,
            # unlike the movable-range helper where it is inapplicable.
            # SDK sentinel coordinates remain unqualified, not finite travel.
            if (
                limits is None
                and lower == upper
                and math.isfinite(lower)
                and not math.isclose(abs(lower), _FLOAT32_LIMIT_SENTINEL, rel_tol=1e-6, abs_tol=0.0)
            ):
                limits = (lower, upper)
            if limits is None:
                return None
            axis = str(linear.GetAxisAttr().Get())
            if axis not in ("X", "Y", "Z"):
                return None
            # The authored axis belongs to the joint frame, which can rotate
            # relative to either body through localRot0/1. The finite Frobenius
            # norm bounds every unit direction, including scaled/sheared body
            # frames, without making assumptions about that imported rotation.
            travel_scale = max(
                math.hypot(*(float(matrices[path][i][j]) for i in range(3) for j in range(3))) for path in (left, right)
            )
            length += max(abs(float(value)) for value in limits) * travel_scale
        if not math.isfinite(length):
            return None
        edge_lengths.append(length)
        adjacency[left].add(right)
        adjacency[right].add(left)
    reached, pending = set(), [next(iter(bodies))]
    while pending:
        path = pending.pop()
        if path not in reached:
            reached.add(path)
            pending.extend(adjacency[path] - reached)
    if reached != set(bodies):
        return None
    # Any two owned points are separated by at most two body radii plus
    # the sum of all edge spans. Summing a loop too is conservative.
    diameter = 2.0 * max(radii.values()) + sum(edge_lengths)
    return diameter if math.isfinite(diameter) and diameter > 0.0 else None


def check_articulation_span(current, diameter, ratio):
    """Check finite live extents against the frozen reach cube and volume margin."""
    if not math.isfinite(diameter) or diameter <= 0 or not math.isfinite(ratio) or ratio <= 0:
        raise RuntimeError("Articulation spatial guard requires a positive finite reference and ratio")
    extents = [float(current.max_point[i]) - float(current.min_point[i]) for i in range(3)]
    if not all(math.isfinite(value) and value >= 0.0 for value in extents):
        raise RuntimeError("Articulation spatial guard requires finite live bounds")
    extent = max(extents)
    if extent / diameter > ratio ** (1.0 / 3.0):
        return (
            f"live extent {extent:.4g} exceeds kinematic span {diameter:.4g} with configured volume margin {ratio:.4g}"
        )
    return None


@dataclass(frozen=True)
class SpatialGuardReference:
    """A frozen setup reference, distinct from a required live observation."""

    snapshot: object
    kinematic_span: object
    ctx: object
    phase: str

    @property
    def volume(self):
        return self.snapshot.volume

    @property
    def min_point(self):
        return self.snapshot.min_point

    @property
    def max_point(self):
        return self.snapshot.max_point


def _guard_metric(ctx, name, value, primary=None):
    """Optional context cannot disable a guard or replace its interruption."""
    try:
        ctx.add_metric(name, value)
    except BaseException as error:
        if primary is None and not isinstance(error, Exception):
            raise
        if primary is not None:
            note_secondary_error(primary, lambda error=error: f"{name} diagnostics unavailable: {error}")
        else:
            try:
                ctx.warn(f"{name} diagnostics unavailable; the spatial guard remains active.")
            except Exception:
                pass


def freeze_bbox_reference(snapshot, prim, ctx, phase):
    """Freeze an authored reach bound once, without changing simulation state."""
    if snapshot is None:
        return None
    span = articulation_span_reference(prim)
    reference = SpatialGuardReference(snapshot, span, ctx, phase)
    _guard_metric(
        ctx,
        phase + "_guard_reference",
        {
            "kinematic_span_stage_units": span,
            "qualified": span is not None,
            "basis": "kinematic_span" if span is not None else "unqualified_initial_volume_proxy",
            "reference_source": (
                "authored body geometry, joint anchor offsets and bounded prismatic travel; frozen setup reference"
                if span is not None
                else "initial live world-aligned bounding-box volume; topology reference could not be qualified"
            ),
        },
    )
    return reference


class SpatialGuardInterruption(RequiredReadbackError):
    """Required observation stopped by a safety guard, without a response verdict."""


def check_guard_reference(current, reference, ratio):
    """A safety trip interrupts observation; it is not a measured response FAIL."""
    if current is None:
        raise RequiredReadbackError(f"{reference.phase.upper()} spatial guard requires a live geometry observation")
    try:
        if reference.kinematic_span is not None:
            message = check_articulation_span(current, reference.kinematic_span, ratio)
        else:
            from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_utils import (
                check_bbox_explode,
            )

            message = check_bbox_explode(current, reference.snapshot, ratio)
    except RequiredReadbackError:
        raise
    except Exception as error:
        raise RequiredReadbackError(
            f"{reference.phase.upper()} required spatial-guard observation is invalid"
        ) from error
    if message:
        basis = "kinematic_span" if reference.kinematic_span is not None else "unqualified_initial_volume_proxy"
        interruption = SpatialGuardInterruption(
            f"{reference.phase.upper()} observation interrupted by spatial safety guard ({basis}): {message}. "
            "The response observation did not complete; this is not a completed asset-response failure "
            "or an asset-defect diagnosis."
        )
        _guard_metric(
            reference.ctx,
            reference.phase + "_guard_abort",
            {"reason": message, "basis": basis, "kinematic_span_stage_units": reference.kinematic_span},
            primary=interruption,
        )
        raise interruption
    return None
