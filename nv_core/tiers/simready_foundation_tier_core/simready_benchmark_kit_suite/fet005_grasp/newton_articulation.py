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

"""
PhysX permits joints outside an articulation. Newton requires every non-world
joint to belong to one. This module infers roots from the authored joint graph,
applies articulation schemas only to the composed test stage, and restores the
previous schema state when the test exits.
"""

from typing import NamedTuple

NEWTON_TENSOR_DRIVE_SKIP = (
    "Newton could not initialize tensor articulation control for the generated "
    "gripper. Skipped instead of reporting a grasp failure because the gripper "
    "cannot close without that engine capability."
)


class NewtonTensorDriveUnavailable(RuntimeError):
    """Raised when Newton cannot control the generated gripper articulation."""


def compute_newton_pd_parameters(
    required_grip_force,
    pad_mass,
    static_friction,
    requested_max_velocity,
):
    """Return stable per-jaw parameters for the generated Newton gripper.

    ``required_grip_force`` is the legacy whole-gripper safety load. Newton
    controls two opposed jaws independently, so each jaw only needs half of
    that load after accounting for the friction authored on the generated
    pads. Deriving the gains from that per-jaw load prevents heavy assets from
    turning the low-mass test pads into high-acceleration projectiles.
    """
    import math

    # Do not credit coefficients above 1.0 when sizing normal force. Very high
    # authored fixture friction improves contact, but it does not eliminate
    # finite contact patches, eccentric torque, or solver loss. Treating mu=5
    # as a perfect 5x force multiplier left round and long assets at the edge
    # of gravity support even though ``required_grip_force`` already contains
    # the intended safety factor.
    friction = max(0.1, min(float(static_friction), 1.0))
    max_effort = max(0.05, float(required_grip_force) / (2.0 * friction))
    stiffness = max(100.0, min(max_effort / 0.005, 2000.0))
    damping = max(1.0, min(2.0 * math.sqrt(max(float(pad_mass), 1.0e-6) * stiffness), 100.0))
    max_velocity = max(0.01, min(float(requested_max_velocity), 0.5))
    return {
        "stiffness": stiffness,
        "damping": damping,
        "max_effort": max_effort,
        "max_velocity": max_velocity,
    }


def author_newton_pd_actuator(
    stage,
    actuator_path,
    joint_path,
    stiffness,
    damping,
    max_effort,
    max_velocity,
):
    """Author one Newton-native position actuator for a generated test joint.

    The actuator is placed below the generated articulation root by the caller
    so Newton's controller discovery can find it before the first physics cook.
    """
    import newton_usd_schemas  # noqa: F401 -- registers Newton USD schemas
    from pxr import Sdf

    joint_prim = stage.GetPrimAtPath(joint_path)
    if not joint_prim or not joint_prim.IsValid():
        raise ValueError("Newton actuator target joint is missing: " + str(joint_path))
    # NewtonJointAPI is recognized by Newton's USD importer in Isaac Sim 6.0,
    # but that build does not register it as an ApplyAPI-compatible Python
    # schema. Author the same apiSchemas tokens used by the working generated
    # carrier fixture instead of calling Prim.ApplyAPI().
    joint_prim.SetMetadata(
        "apiSchemas",
        Sdf.TokenListOp.Create(prependedItems=["NewtonJointAPI", "PhysicsJointStateAPI:linear"]),
    )
    joint_prim.CreateAttribute("newton:velocityLimit", Sdf.ValueTypeNames.Float).Set(float(max_velocity))

    actuator = stage.DefinePrim(actuator_path, "NewtonActuator")
    if not actuator or not actuator.IsValid():
        raise RuntimeError("Failed to define NewtonActuator at " + str(actuator_path))
    if not actuator.ApplyAPI("NewtonPDControlAPI"):
        raise RuntimeError("Failed to apply NewtonPDControlAPI to " + str(actuator_path))
    if not actuator.ApplyAPI("NewtonMaxEffortClampingAPI"):
        raise RuntimeError("Failed to apply NewtonMaxEffortClampingAPI to " + str(actuator_path))
    actuator.CreateRelationship("newton:targets").SetTargets([Sdf.Path(joint_path)])
    actuator.CreateAttribute("newton:kp", Sdf.ValueTypeNames.Float).Set(float(stiffness))
    actuator.CreateAttribute("newton:kd", Sdf.ValueTypeNames.Float).Set(float(damping))
    actuator.CreateAttribute("newton:maxEffort", Sdf.ValueTypeNames.Float).Set(float(max_effort))
    # Control prims are not scene geometry. Keeping them explicitly invisible
    # also prevents generic imageable/bounds traversal from treating them as
    # report content in Kit builds that expose typed actuator prims that way.
    actuator.CreateAttribute("visibility", Sdf.ValueTypeNames.Token).Set("invisible")
    return actuator


class TemporaryNewtonArticulation(NamedTuple):
    """Schema state needed to undo one temporary articulation root."""

    path: str
    added_physx_api: bool
    had_self_collisions_value: bool
    self_collisions_value: bool | None


def tensor_drive_skip_result(error):
    # type: (Exception) -> dict | None
    """Translate only a Newton controller capability error into a skip signal."""
    if isinstance(error, NewtonTensorDriveUnavailable):
        return {"skip": NEWTON_TENSOR_DRIVE_SKIP}
    return None


def infer_articulation_roots(joints):
    # type: (list[tuple[str, str | None, str | None]]) -> list[str]
    """Return one directed root body for each connected joint component."""
    adjacency = {}  # type: dict[str, set[str]]
    children = set()  # type: set[str]

    for joint_path, parent_body, child_body in joints:
        if not child_body:
            raise ValueError("%s has no resolved child rigid body" % joint_path)
        adjacency.setdefault(child_body, set())
        if parent_body:
            adjacency.setdefault(parent_body, set())
            adjacency[parent_body].add(child_body)
            adjacency[child_body].add(parent_body)
            children.add(child_body)

    roots = []
    remaining = set(adjacency)
    while remaining:
        seed = next(iter(remaining))
        component = set()
        pending = [seed]
        while pending:
            body = pending.pop()
            if body in component:
                continue
            component.add(body)
            pending.extend(adjacency[body].difference(component))
        remaining.difference_update(component)

        candidates = sorted(component.difference(children))
        if len(candidates) != 1:
            raise ValueError(
                "joint component has %d possible roots (%s)" % (len(candidates), ", ".join(candidates) or "cycle")
            )
        roots.append(candidates[0])

    return sorted(roots)


def _owning_rigid_body(prim):
    """Resolve a relationship target to its nearest rigid-body ancestor."""
    from pxr import UsdPhysics

    current = prim
    while current and current.IsValid():
        if current.HasAPI(UsdPhysics.RigidBodyAPI):
            return str(current.GetPath())
        current = current.GetParent()
    return None


def apply_temporary_newton_articulations(stage, asset_prim_path):
    # type: (object, str) -> list[TemporaryNewtonArticulation]
    """Apply missing articulation roots in the composed test stage.

    Returns the exact schema state changed by this call. Existing articulation
    authoring is preserved and never returned for cleanup. A pre-existing
    PhysX articulation schema is retained and its self-collision value is
    restored when the matching cleanup runs.
    """
    from pxr import Usd, UsdPhysics

    asset_prim = stage.GetPrimAtPath(asset_prim_path)
    if not asset_prim or not asset_prim.IsValid():
        raise ValueError("asset prim is missing: " + asset_prim_path)

    joints = []
    authored_roots = set()
    for prim in Usd.PrimRange(asset_prim):
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            authored_roots.add(str(prim.GetPath()))
        if not prim.IsA(UsdPhysics.Joint):
            continue
        joint = UsdPhysics.Joint(prim)
        body0 = joint.GetBody0Rel().GetTargets()
        body1 = joint.GetBody1Rel().GetTargets()
        parent = _owning_rigid_body(stage.GetPrimAtPath(body0[0])) if body0 else None
        child = _owning_rigid_body(stage.GetPrimAtPath(body1[0])) if body1 else None
        joints.append((str(prim.GetPath()), parent, child))

    if not joints or authored_roots:
        return []

    # Unsupported graphs (unresolved child, cycle, shared-child/multiple-root
    # component) are not asset grasp failures. Leave the stage untouched; the
    # post-play Newton scene guard will then skip if Newton cannot compile the
    # loose topology.
    try:
        inferred_roots = infer_articulation_roots(joints)
    except ValueError:
        return []

    root_prims = []
    for root_path in inferred_roots:
        root_prim = stage.GetPrimAtPath(root_path)
        if not root_prim or not root_prim.IsValid():
            return []
        root_prims.append((root_path, root_prim))

    from pxr import PhysxSchema

    applied = []
    for root_path, root_prim in root_prims:
        had_physx_api = root_prim.HasAPI(PhysxSchema.PhysxArticulationAPI)
        physx_api = PhysxSchema.PhysxArticulationAPI.Apply(root_prim)
        self_collisions_attr = physx_api.GetEnabledSelfCollisionsAttr()
        had_self_collisions_value = self_collisions_attr.HasAuthoredValueOpinion()
        self_collisions_value = self_collisions_attr.Get() if had_self_collisions_value else None

        UsdPhysics.ArticulationRootAPI.Apply(root_prim)
        physx_api.CreateEnabledSelfCollisionsAttr(False)
        applied.append(
            TemporaryNewtonArticulation(
                path=root_path,
                added_physx_api=not had_physx_api,
                had_self_collisions_value=had_self_collisions_value,
                self_collisions_value=self_collisions_value,
            )
        )
    return applied


def remove_temporary_newton_articulations(stage, mutations):
    # type: (object, list[TemporaryNewtonArticulation]) -> None
    """Restore only articulation schema state changed by the matching apply."""
    from pxr import PhysxSchema, UsdPhysics

    for mutation in mutations:
        prim = stage.GetPrimAtPath(mutation.path)
        if prim and prim.IsValid():
            prim.RemoveAPI(UsdPhysics.ArticulationRootAPI)
            if mutation.added_physx_api:
                prim.RemoveAPI(PhysxSchema.PhysxArticulationAPI)
                continue

            self_collisions_attr = PhysxSchema.PhysxArticulationAPI(prim).GetEnabledSelfCollisionsAttr()
            if mutation.had_self_collisions_value:
                self_collisions_attr.Set(mutation.self_collisions_value)
            else:
                self_collisions_attr.Clear()
