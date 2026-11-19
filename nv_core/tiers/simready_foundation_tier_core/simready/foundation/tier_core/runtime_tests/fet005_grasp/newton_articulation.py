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

import math
from numbers import Real
from typing import NamedTuple


def _fixture_number(value, label, *, positive=False):
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
        or not math.isfinite(value)
        or (value <= 0.0 if positive else value < 0.0)
    ):
        raise ValueError("%s must be a finite %s real value" % (label, "positive" if positive else "nonnegative"))
    return float(value)


def _author_fixture_attribute(prim, name, value_type, value):
    """Verify authored state only; this is not native solver acknowledgment."""
    attribute = prim.CreateAttribute(name, value_type)
    if not attribute or attribute.Set(value) is not True:
        raise RuntimeError("Generated Newton fixture rejected attribute " + name)
    observed = attribute.Get()
    if isinstance(value, float):
        valid = (
            not isinstance(observed, bool)
            and isinstance(observed, Real)
            and math.isfinite(observed)
            and math.isclose(observed, value, rel_tol=1.0e-6, abs_tol=1.0e-8)
        )
    else:
        valid = type(observed) is type(value) and observed == value
    if not valid:
        raise RuntimeError("Generated Newton fixture attribute was not retained: " + name)
    return attribute


def _author_fixture_api(prim, name):
    if not prim.ApplyAPI(name) or not prim.HasAPI(name):
        raise RuntimeError("Generated Newton fixture failed to apply " + name)


NEWTON_TENSOR_DRIVE_SKIP = (
    "Newton could not initialize tensor articulation control for the generated "
    "gripper. Skipped instead of reporting a grasp failure because the gripper "
    "cannot close without that engine capability."
)


class NewtonTensorDriveUnavailable(RuntimeError):
    """Raised when Newton cannot control the generated gripper articulation."""


def author_newton_fixture_collision(prim, contact_gap):
    """Add Newton contact authoring to generated test-only collision geometry."""
    import newton_usd_schemas  # noqa: F401 -- registers Newton USD schemas
    from pxr import Sdf

    contact_gap = _fixture_number(contact_gap, "Newton fixture contact gap")
    if not prim or not prim.IsValid():
        raise ValueError("Newton fixture collision prim is missing")
    _author_fixture_api(prim, "NewtonCollisionAPI")
    _author_fixture_attribute(prim, "newton:contactMargin", Sdf.ValueTypeNames.Float, 0.0)
    _author_fixture_attribute(prim, "newton:contactGap", Sdf.ValueTypeNames.Float, contact_gap)


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

    stiffness = _fixture_number(stiffness, "Newton fixture stiffness")
    damping = _fixture_number(damping, "Newton fixture damping")
    max_effort = _fixture_number(max_effort, "Newton fixture maximum effort", positive=True)
    max_velocity = _fixture_number(max_velocity, "Newton fixture maximum velocity", positive=True)
    joint_prim = stage.GetPrimAtPath(joint_path)
    if not joint_prim or not joint_prim.IsValid():
        raise ValueError("Newton actuator target joint is missing: " + str(joint_path))
    # NewtonJointAPI is recognized by Newton's USD importer in Isaac Sim 6.0,
    # but that build does not register it as an ApplyAPI-compatible Python
    # schema. Author the same apiSchemas tokens used by the working generated
    # carrier fixture instead of calling Prim.ApplyAPI().
    previous_schemas = joint_prim.GetMetadata("apiSchemas")
    previous_items = list(previous_schemas.GetAppliedItems()) if previous_schemas is not None else []
    schema_items = list(dict.fromkeys(previous_items + ["NewtonJointAPI", "PhysicsJointStateAPI:linear"]))
    if joint_prim.SetMetadata("apiSchemas", Sdf.TokenListOp.Create(prependedItems=schema_items)) is not True:
        raise RuntimeError("Generated Newton fixture rejected joint schema authoring")
    observed_schemas = joint_prim.GetMetadata("apiSchemas")
    if observed_schemas is None or list(observed_schemas.GetAppliedItems()) != schema_items:
        raise RuntimeError("Generated Newton fixture joint schemas were not retained")
    _author_fixture_attribute(joint_prim, "newton:velocityLimit", Sdf.ValueTypeNames.Float, max_velocity)

    actuator = stage.DefinePrim(actuator_path, "NewtonActuator")
    if not actuator or not actuator.IsValid():
        raise RuntimeError("Failed to define NewtonActuator at " + str(actuator_path))
    _author_fixture_api(actuator, "NewtonPDControlAPI")
    _author_fixture_api(actuator, "NewtonMaxEffortClampingAPI")
    targets = actuator.CreateRelationship("newton:targets")
    expected_targets = [Sdf.Path(joint_path)]
    if not targets or targets.SetTargets(expected_targets) is not True or targets.GetTargets() != expected_targets:
        raise RuntimeError("Generated Newton fixture actuator targets were not retained")
    _author_fixture_attribute(actuator, "newton:kp", Sdf.ValueTypeNames.Float, stiffness)
    _author_fixture_attribute(actuator, "newton:kd", Sdf.ValueTypeNames.Float, damping)
    _author_fixture_attribute(actuator, "newton:maxEffort", Sdf.ValueTypeNames.Float, max_effort)
    # Control prims are not scene geometry. Keeping them explicitly invisible
    # also prevents generic imageable/bounds traversal from treating them as
    # report content in Kit builds that expose typed actuator prims that way.
    _author_fixture_attribute(actuator, "visibility", Sdf.ValueTypeNames.Token, "invisible")
    return actuator


class TemporaryNewtonArticulation(NamedTuple):
    """Schema state needed to undo one temporary articulation root."""

    path: str
    added_physx_api: bool
    had_self_collisions_value: bool
    self_collisions_value: bool | None
    snapshot: object | None = None


def _temporary_root_snapshot(stage, prim, physx_api):
    """Capture only the exact local opinions this temporary setup may change."""
    from pxr import Sdf

    edit_target = stage.GetEditTarget()
    layer = edit_target.GetLayer()
    spec_path = edit_target.MapToSpecPath(prim.GetPath())
    if not spec_path or not layer:
        raise RuntimeError("Temporary Newton articulation has no writable mapped authoring target")
    local_prim = layer.GetPrimAtPath(spec_path)
    had_api_opinion = bool(local_prim and local_prim.HasInfo("apiSchemas"))
    api_opinion = local_prim.GetInfo("apiSchemas") if had_api_opinion else None
    collision_name = physx_api.GetEnabledSelfCollisionsAttr().GetName()
    collision_path = spec_path.AppendProperty(collision_name)
    local_attribute = layer.GetAttributeAtPath(collision_path)
    copied_attribute = None
    if local_attribute:
        copied_attribute = Sdf.Layer.CreateAnonymous("fet005-original-self-collision")
        Sdf.CreatePrimInLayer(copied_attribute, "/Original")
        if not Sdf.CopySpec(
            layer, collision_path, copied_attribute, Sdf.Path("/Original").AppendProperty(collision_name)
        ):
            raise RuntimeError("Temporary Newton articulation could not capture prior self-collision authoring")
    return {
        "edit_target": edit_target,
        "layer": layer,
        "spec_path": spec_path,
        "had_prim_spec": bool(local_prim),
        "had_api_opinion": had_api_opinion,
        "api_opinion": api_opinion,
        "collision_name": collision_name,
        "collision_path": collision_path,
        "attribute_snapshot": copied_attribute,
    }


def _restore_temporary_root_opinions(stage, prim, snapshot):
    from pxr import Sdf

    if snapshot["had_api_opinion"]:
        if prim.SetMetadata("apiSchemas", snapshot["api_opinion"]) is not True:
            raise RuntimeError("Temporary Newton articulation rejected prior schema opinion restoration")
    elif prim.ClearMetadata("apiSchemas") is not True:
        raise RuntimeError("Temporary Newton articulation rejected schema opinion cleanup")
    local_prim = snapshot["layer"].GetPrimAtPath(snapshot["spec_path"])
    has_api_opinion = bool(local_prim and local_prim.HasInfo("apiSchemas"))
    if has_api_opinion != snapshot["had_api_opinion"] or (
        has_api_opinion and local_prim.GetInfo("apiSchemas") != snapshot["api_opinion"]
    ):
        raise RuntimeError("Temporary Newton articulation schema opinion was not restored")

    original_attribute = snapshot["attribute_snapshot"]
    if original_attribute is not None:
        original_path = Sdf.Path("/Original").AppendProperty(snapshot["collision_name"])
        if not Sdf.CopySpec(original_attribute, original_path, snapshot["layer"], snapshot["collision_path"]):
            raise RuntimeError("Temporary Newton articulation rejected prior self-collision property restoration")
        restored = snapshot["layer"].GetAttributeAtPath(snapshot["collision_path"])
        original = original_attribute.GetAttributeAtPath(original_path)
        if (
            not restored
            or set(restored.ListInfoKeys()) != set(original.ListInfoKeys())
            or any(restored.GetInfo(key) != original.GetInfo(key) for key in original.ListInfoKeys())
        ):
            raise RuntimeError("Temporary Newton articulation self-collision property was not restored")
    elif snapshot["layer"].GetAttributeAtPath(snapshot["collision_path"]):
        if prim.RemoveProperty(snapshot["collision_name"]) is not True:
            raise RuntimeError("Temporary Newton articulation rejected generated self-collision property removal")
        if snapshot["layer"].GetAttributeAtPath(snapshot["collision_path"]):
            raise RuntimeError("Temporary Newton articulation generated property remains authored")

    # A reference-only body may have needed a new local over. Remove it only
    # when no foreign properties, children or metadata appeared there.
    local_prim = snapshot["layer"].GetPrimAtPath(snapshot["spec_path"])
    if not snapshot["had_prim_spec"] and local_prim:
        if local_prim.properties or local_prim.nameChildren or set(local_prim.ListInfoKeys()) != {"specifier"}:
            raise RuntimeError("Temporary Newton articulation local override contains unowned authoring")
        if local_prim.specifier != Sdf.SpecifierOver or stage.RemovePrim(str(prim.GetPath())) is not True:
            raise RuntimeError("Temporary Newton articulation could not remove its empty local override")
        if snapshot["layer"].GetPrimAtPath(snapshot["spec_path"]):
            raise RuntimeError("Temporary Newton articulation local override remains authored")


def _temporary_cleanup_failed(primary, secondary):
    """Preserve the first cause while exposing required rollback retirement."""
    try:
        primary._fet005_required_cleanup_failed = True
        primary.add_note("Required temporary Newton articulation rollback failed (%s)." % type(secondary).__name__)
    except BaseException:
        pass


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
    # post-play Newton scene guard will then report a blocking runtime error if
    # Newton cannot compile the loose topology.
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

    try:
        from pxr import PhysxSchema
    except ImportError:
        from physx_usd_schemas import PhysxSchema

    pending_mutations = []
    for root_path, root_prim in root_prims:
        had_physx_api = root_prim.HasAPI("PhysxArticulationAPI")
        physx_api = PhysxSchema.PhysxArticulationAPI(root_prim)
        self_collisions_attr = physx_api.GetEnabledSelfCollisionsAttr()
        had_self_collisions_value = self_collisions_attr.HasAuthoredValueOpinion()
        self_collisions_value = self_collisions_attr.Get() if had_self_collisions_value else None
        if had_self_collisions_value and type(self_collisions_value) is not bool:
            raise ValueError("Temporary Newton articulation prior self-collision value is malformed")
        pending_mutations.append(
            TemporaryNewtonArticulation(
                path=root_path,
                added_physx_api=not had_physx_api,
                had_self_collisions_value=had_self_collisions_value,
                self_collisions_value=self_collisions_value,
                snapshot=_temporary_root_snapshot(stage, root_prim, physx_api),
            )
        )
    applied = []
    try:
        for mutation in pending_mutations:
            # Record ownership before the first write so partial apply failures
            # still have an exact rollback ledger.
            applied.append(mutation)
            with Usd.EditContext(stage, mutation.snapshot["edit_target"]):
                root_prim = stage.GetPrimAtPath(mutation.path)
                physx_api = PhysxSchema.PhysxArticulationAPI.Apply(root_prim)
                if not physx_api or not root_prim.HasAPI("PhysxArticulationAPI"):
                    raise RuntimeError("Temporary Newton articulation PhysX schema was not applied")
                root_api = UsdPhysics.ArticulationRootAPI.Apply(root_prim)
                if not root_api or not root_prim.HasAPI(UsdPhysics.ArticulationRootAPI):
                    raise RuntimeError("Temporary Newton articulation root schema was not applied")
                attribute = physx_api.CreateEnabledSelfCollisionsAttr()
                if not attribute or attribute.Set(False) is not True or attribute.Get() is not False:
                    raise RuntimeError("Temporary Newton articulation self-collision write was not retained")
    except BaseException as primary:
        try:
            remove_temporary_newton_articulations(stage, applied)
        except BaseException as secondary:
            _temporary_cleanup_failed(primary, secondary)
        raise
    return applied


def remove_temporary_newton_articulations(stage, mutations):
    # type: (object, list[TemporaryNewtonArticulation]) -> None
    """Restore only articulation schema state changed by the matching apply."""
    from pxr import Usd, UsdPhysics

    try:
        from pxr import PhysxSchema
    except ImportError:
        from physx_usd_schemas import PhysxSchema

    first_error = None
    for mutation in mutations:
        try:
            target = mutation.snapshot["edit_target"] if mutation.snapshot is not None else stage.GetEditTarget()
            with Usd.EditContext(stage, target):
                prim = stage.GetPrimAtPath(mutation.path)
                if not prim or not prim.IsValid():
                    raise RuntimeError(
                        "Temporary Newton articulation restoration root is unavailable: " + mutation.path
                    )
                if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
                    if prim.RemoveAPI(UsdPhysics.ArticulationRootAPI) is not True or prim.HasAPI(
                        UsdPhysics.ArticulationRootAPI
                    ):
                        raise RuntimeError("Temporary Newton articulation root schema removal was rejected")
                if mutation.added_physx_api:
                    if prim.HasAPI("PhysxArticulationAPI") and (
                        prim.RemoveAPI("PhysxArticulationAPI") is not True or prim.HasAPI("PhysxArticulationAPI")
                    ):
                        raise RuntimeError("Temporary Newton articulation PhysX schema removal was rejected")
                else:
                    attribute = PhysxSchema.PhysxArticulationAPI(prim).GetEnabledSelfCollisionsAttr()
                    if mutation.had_self_collisions_value:
                        if (
                            attribute.Set(mutation.self_collisions_value) is not True
                            or attribute.Get() is not mutation.self_collisions_value
                        ):
                            raise RuntimeError("Temporary Newton articulation self-collision restoration was rejected")
                    elif attribute.Clear() is not True:
                        raise RuntimeError("Temporary Newton articulation self-collision cleanup was rejected")
                if mutation.snapshot is not None:
                    _restore_temporary_root_opinions(stage, prim, mutation.snapshot)
                prim = stage.GetPrimAtPath(mutation.path)
                if not prim or not prim.IsValid() or prim.HasAPI(UsdPhysics.ArticulationRootAPI):
                    raise RuntimeError("Temporary Newton articulation original body state was not restored")
                if prim.HasAPI("PhysxArticulationAPI") is mutation.added_physx_api:
                    raise RuntimeError("Temporary Newton articulation original PhysX schema state was not restored")
                if not mutation.added_physx_api:
                    attribute = PhysxSchema.PhysxArticulationAPI(prim).GetEnabledSelfCollisionsAttr()
                    if attribute.HasAuthoredValueOpinion() is not mutation.had_self_collisions_value or (
                        mutation.had_self_collisions_value and attribute.Get() is not mutation.self_collisions_value
                    ):
                        raise RuntimeError(
                            "Temporary Newton articulation original self-collision state was not restored"
                        )
        except BaseException as error:
            if first_error is None:
                first_error = error
            else:
                _temporary_cleanup_failed(first_error, error)
    if first_error is not None:
        _temporary_cleanup_failed(first_error, first_error)
        raise first_error
