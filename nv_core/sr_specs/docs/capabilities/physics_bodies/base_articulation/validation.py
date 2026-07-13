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
__all__ = ["BaseArticulationValidation"]

import typing

# from omni.physics.core import ContactEventType, get_physics_simulation_interface
# from omni.physx.bindings._physx import SETTING_UPDATE_TO_USD
from enum import Enum

import omni.asset_validator
from pxr import Usd, UsdPhysics

try:
    from pxr import PhysxSchema
except ImportError:
    PhysxSchema = None

from ... import Requirement


class BaseArticulationCapReq(Requirement, Enum):
    BA_001 = (
        "BA.001",
        "has-articulation-root",
        "Articulated assets must have exactly one ArticulationRootAPI applied to establish the physics simulation root.",
    )

    BA_002 = (
        "BA.002",
        "non-adjacent-collision-meshes-do-not-clash",
        "Collision meshes on non-adjacent links in the articulation hierarchy must not overlap or intersect at the default pose.",
    )


# Copied from Ales's code
def get_initial_collider_pairs(stage: Usd.Stage) -> typing.Set[typing.Tuple[str, str]]:
    """
    Get all collider pairs that are in contact in the physics simulation.

    This function performs a single physics simulation step and collects all collider pairs
    that are in contact. It temporarily modifies physics settings to ensure accurate contact
    detection and restores them after completion.

    The function:
    1. Creates a temporary session layer for contact reporting
    2. Enables contact reporting for all rigid bodies
    3. Runs a single physics simulation step
    4. Collects all collider pairs that are in contact
    5. Restores original physics settings

    Args:
        stage (Usd.Stage): The USD stage containing the physics scene to analyze.

    Returns:
        typing.Set[typing.Tuple[str, str]]: A set of tuples, where each tuple contains
            the paths of two colliders that are in contact. The paths in each tuple are
            sorted alphabetically to ensure consistent ordering regardless of which collider
            initiated the contact.

    Note:
        This function temporarily modifies physics settings and runs a simulation step.
        The original settings are restored after the function completes.
    """

    unique_collider_pairs = set()  # Use a set to store unique collider pairs
    """
    def on_contact_event(contact_headers, contact_data, friction_anchors):
        for contact_header in contact_headers:
            if contact_header.type == ContactEventType.CONTACT_FOUND:
                collider0 = str(PhysicsSchemaTools.intToSdfPath(contact_header.collider0))
                collider1 = str(PhysicsSchemaTools.intToSdfPath(contact_header.collider1))
                # Store as a tuple, ensuring consistent ordering
                pair = tuple(sorted([collider0, collider1]))
                unique_collider_pairs.add(pair)


    
    session_sub_layer = Sdf.Layer.CreateAnonymous()
    stage.GetSessionLayer().subLayerPaths.append(session_sub_layer.identifier)
    old_layer = stage.GetEditTarget().GetLayer()
    stage.SetEditTarget(Usd.EditTarget(session_sub_layer))

    # Added this to avoid stage not in cache error
    stageCache = UsdUtils.StageCache.Get()
    stageCache.Insert(stage)  # Register the stage

    stage_id = UsdUtils.StageCache.Get().GetId(stage).ToLongInt()
    usdrtStage = usdrt.Usd.Stage.Attach(stage_id)
    prim_paths = usdrtStage.GetPrimsWithAppliedAPIName("PhysicsRigidBodyAPI")

    for prim_path in prim_paths:
        prim = stage.GetPrimAtPath(str(prim_path))
        if prim:
            contact_report_api = PhysxSchema.PhysxContactReportAPI.Apply(prim)
            contact_report_api.CreateThresholdAttr().Set(0)

    settings = carb.settings.get_settings()
    write_usd = settings.get_as_bool(SETTING_UPDATE_TO_USD)
    write_fabric = settings.get_as_bool("/physics/fabricEnabled")

    settings.set(SETTING_UPDATE_TO_USD, False)
    settings.set("/physics/fabricEnabled", False)

    initial_attach = False
    if get_physics_simulation_interface().get_attached_stage() != stage_id:
        get_physics_simulation_interface().attach_stage(stage_id)
        initial_attach = True

    contact_report_sub = get_physics_simulation_interface().subscribe_physics_contact_report_events(on_contact_event)

    get_physics_simulation_interface().simulate(1.0 / 60.0, 0.0)
    get_physics_simulation_interface().fetch_results()

    if contact_report_sub:
        contact_report_sub = None

    if initial_attach:
        get_physics_simulation_interface().detach_stage()

    settings.set(SETTING_UPDATE_TO_USD, write_usd)
    settings.set("/physics/fabricEnabled", write_fabric)

    stage.SetEditTarget(old_layer)

    stage.GetSessionLayer().subLayerPaths.remove(session_sub_layer.identifier)
    session_sub_layer = None
    """
    return unique_collider_pairs


def ComputeAdjacentMeshDict(stage: Usd.Stage) -> dict:
    """Compute a dictionary mapping body paths to lists of adjacent body paths.

    Args:
        stage: The USD stage to analyze.

    Returns:
        A dictionary mapping body paths to lists of adjacent body paths.
    """
    # Traverse through the joints, log every pair of connected bodies
    defaultPrim = stage.GetDefaultPrim()
    if not defaultPrim or not defaultPrim.IsValid():
        return {}

    if PhysxSchema is None:
        raise RuntimeError("PhysxSchema is not available in this environment")

    adjacent_mesh_matrix = {}

    for prim in stage.Traverse():
        if prim.HasAPI(PhysxSchema.PhysxJointAPI):
            joint = UsdPhysics.Joint(prim)
            body0_targets = joint.GetBody0Rel().GetTargets()
            if not body0_targets:
                continue
            body0 = body0_targets[0]
            body1_targets = joint.GetBody1Rel().GetTargets()
            if not body1_targets:
                continue
            body1 = body1_targets[0]

            # body0 and body1 are adjacent, log into joint dict
            if body0 not in adjacent_mesh_matrix:
                adjacent_mesh_matrix[body0] = []
            if body1 not in adjacent_mesh_matrix:
                adjacent_mesh_matrix[body1] = []
            adjacent_mesh_matrix[body0].append(body1)
            adjacent_mesh_matrix[body1].append(body0)

    return adjacent_mesh_matrix


@omni.asset_validator.register_rule("BaseArticulation")
@omni.asset_validator.register_requirements(BaseArticulationCapReq.BA_001, override=True)
class HasArticulationRoot(omni.asset_validator.BaseRuleChecker):
    """Validates that none or more than one prim in the stage has the ArticulationRootAPI.

    This rule checks that the USD stage contains none or more than one prim with the
    UsdPhysics.ArticulationRootAPI applied. The ArticulationRootAPI is required for
    proper articulation simulation in physics.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check if the stage has none or more than one articulation root.

        Args:
            stage: The USD stage to validate.
        """
        roots = []
        for prim in stage.Traverse():
            if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
                roots.append(prim)
        if len(roots) == 0:
            self._AddFailedCheck(
                requirement=BaseArticulationCapReq.BA_001,
                message=f"Articulation Root API is not set on any prim in the stage",
                at=stage,
            )

        if len(roots) > 1:
            self._AddFailedCheck(
                requirement=BaseArticulationCapReq.BA_001,
                message=f"More than one Articulation Root API is set on the stage",
                at=stage,
            )


@omni.asset_validator.register_rule("BaseArticulation")
@omni.asset_validator.register_requirements(BaseArticulationCapReq.BA_002, override=True)
class NonAdjacentCollisionMeshesDoNotClash(omni.asset_validator.BaseRuleChecker):
    """Validates that non-adjacent collision meshes don't intersect.

    This rule checks that collision meshes that aren't connected by joints don't
    intersect each other, which can cause unstable physics simulation.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check for intersecting non-adjacent collision meshes.

        Args:
            stage: The USD stage to validate.
        """
        if PhysxSchema is None:
            self._AddError("PhysxSchema is not available in this environment; cannot check non-adjacent collision meshes")
            return
        self.adjacent_mesh_matrix = ComputeAdjacentMeshDict(stage)  # Sdf Path of all joints
        self.collisions_pairs = get_initial_collider_pairs(
            stage
        )  # Set of tuples of collider pairs in contact (Sdf Paths)

        for collision_pair in self.collisions_pairs:
            body0_prim = stage.GetPrimAtPath(collision_pair[0])
            body1_prim = stage.GetPrimAtPath(collision_pair[1])

            body0_parent_path = body0_prim.GetParent().GetPath()
            body1_parent_path = body1_prim.GetParent().GetPath()

            # check if the two bodies are adjacent
            if body1_parent_path in self.adjacent_mesh_matrix.get(body0_parent_path, []):
                continue
            else:
                self._AddFailedCheck(
                    requirement=BaseArticulationCapReq.BA_002,
                    message=f"Colliding meshes {body0_prim.GetPath()} and {body1_prim.GetPath()} are not adjacent",
                    at=body0_prim,
                )
