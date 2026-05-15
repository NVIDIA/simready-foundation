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
__all__ = ["RobotCoreValidation"]

from enum import Enum

import omni.asset_validator
from pxr import Usd, UsdPhysics

from ... import Requirement


class RobotCoreCapReq(Requirement, Enum):
    RC_001 = (
        "RC.001",
        "clean-folder",
        "Robot asset folders contain only referenced, required files. No stray or unused content. At the main level of a robot asset, only the interface layer is present. All other required content is bundled on subfolders related to it specific usage.",
    )

    RC_002 = (
        "RC.002",
        "no-overrides",
        "Robot assets avoid local override layers that mask upstream schemas or physics.",
    )

    RC_003 = (
        "RC.003",
        "robot-naming",
        "Canonical robot and prim naming conventions for stable references and tools.",
    )

    RC_004 = (
        "RC.004",
        "thumbnail-exist",
        "The robot interface asset file should contain a thumbnail. The thumbnail should be representative of the robot.",
    )

    RC_005 = (
        "RC.005",
        "verify-robot-physics-attribute-source-layer",
        "Validates that physics attributes are authored in the physics layer.",
    )

    RC_006 = (
        "RC.006",
        "verify-robot-physics-schema-source-layer",
        "Validates that robot physics schema are correctly authored.",
    )

    RC_007 = (
        "RC.007",
        "robot-schema",
        "Robot USDs declare and use the required schemas and physics attributes.",
    )

    RC_008 = (
        "RC.008",
        "robot-type",
        "Robot USDs declare and use the required robot type.",
    )

    RC_009 = (
        "RC.009",
        "root-joint-pinned",
        "The root joint is pinned according to the robot type.",
    )


def get_overridden_attributes(prim):
    """Get list of attribute names that have overridden values.

    Args:
        prim: The USD prim to check for overridden attributes.

    Returns:
        List of attribute names that have overridden values.
    """
    overridden_attrs = []

    for attr in prim.GetAttributes():
        # Check if this attribute has authored value in the current edit target
        if attr.HasAuthoredValue():
            # Get the layer where the value is authored
            layer_stack = prim.GetStage().GetLayerStack()
            for layer in layer_stack:
                attr_spec = layer.GetAttributeAtPath(attr.GetPath())
                if attr_spec and attr_spec.HasDefaultValue():
                    overridden_attrs.append(attr.GetName())
                    break

    return overridden_attrs


@omni.asset_validator.register_rule("RobotCore")
@omni.asset_validator.register_requirements(RobotCoreCapReq.RC_001, override=True)
class CleanFolder(omni.asset_validator.BaseRuleChecker):
    """Validates that robot asset folders don't contain unexpected files.

    This rule checks that the folder containing a robot asset doesn't contain
    unexpected files that might cause confusion or conflicts.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        folders = stage.GetRootLayer().realPath.replace("\\", "/").split("/")
        folder = "/".join(folders[:-1])
        res, entries = omni.client.list(folder)
        if res != omni.client.Result.OK:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_001,
                message=f"Failed to list folder <{folder}>",
                at=stage,
            )
            return
        for entry in entries:
            if entry.relative_path.lower() == folders[-1].lower():
                continue
            if entry.flags & omni.client.ItemFlags.CAN_HAVE_CHILDREN:
                continue
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_001,
                message=f"Folder <{folder}> contains unexpected file <{entry.relative_path}>",
                at=stage,
            )


@omni.asset_validator.register_rule("RobotCore")
@omni.asset_validator.register_requirements(RobotCoreCapReq.RC_002, override=True)
class NoOverrides(omni.asset_validator.BaseRuleChecker):
    """Validates that prims don't have overridden attributes.

    This rule checks that prims don't have attributes with the SpecifierOver specifier,
    which can cause unexpected behavior in robot assets. This only applies for the open stage.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if "/Render" in prim.GetPath().pathString:
            return

        attrs = get_overridden_attributes(prim)
        if len(attrs) > 0:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_002,
                message=f"Prim is overridden: {prim.GetPath()}, {attrs}",
                at=prim,
            )


@omni.asset_validator.register_rule("RobotCore")
@omni.asset_validator.register_requirements(RobotCoreCapReq.RC_003, override=True)
class RobotNaming(omni.asset_validator.BaseRuleChecker):
    """Validates that robot assets follow the standard naming convention.

    This rule checks that robot assets follow the naming convention of
    <Manufacturer>/<robot>/<robot.usd> or <Manufacturer>/<robot>/<version>/<robot.usd>.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check if the robot asset follows proper naming conventions.

        Args:
            stage: The USD stage to validate.
        """
        path = stage.GetRootLayer().realPath

        parts = path.replace("\\", "/").split("/")

        if len(parts) < 3:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_003,
                message=f"Robot not nested in enough folders: must be at least <Manufacturer>/<robot>/<robot.usd>: <{path}>",
                at=stage,
            )
            return

        # try Manufacturer/Robot/Robot.usd
        if parts[-2].lower() != parts[-1].split(".")[0].lower():
            # Does not match parts[-2]; try this format Manufacturer/Robot/Version/Robot.usd
            if len(parts) >= 4:
                if parts[-3].lower() == parts[-1].split(".")[0].lower():
                    # nothing wrong; we do match parts[-3]
                    return
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_003,
                message=f"Folder name does not match Robot name: <{parts[-2]}> != <{parts[-1]}>",
                at=stage,
            )


@omni.asset_validator.register_rule("RobotCore")
@omni.asset_validator.register_requirements(RobotCoreCapReq.RC_004, override=True)
class ThumbnailExists(omni.asset_validator.BaseRuleChecker):
    """Validates that robot assets have a thumbnail image.

    This rule checks that robot assets have a thumbnail image at the expected
    path, which is used for display in asset browsers.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        folders = stage.GetRootLayer().realPath.replace("\\", "/").split("/")
        folder = "/".join(folders[:-1])
        thumbnail_path = f"{folder}/.thumbs/256x256/{folders[-1]}.png"
        if omni.client.stat(thumbnail_path)[0] != omni.client.Result.OK:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_004,
                message=f"No thumbnail found at {thumbnail_path} for robot asset <{stage.GetRootLayer().realPath}>",
                at=stage,
            )


@omni.asset_validator.register_rule("RobotCore")
@omni.asset_validator.register_requirements(RobotCoreCapReq.RC_005, override=True)
class VerifyRobotPhysicsAttributesSourceLayer(omni.asset_validator.BaseRuleChecker):
    """Validates that physics attributes are authored in the physics layer.

    This rule checks that physics attributes in robot assets are authored in
    the physics layer (_physics.usd), following the recommended layer structure.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        # examine every physics attribute in the stage and ensure that they are authored in the physics layer
        for prim in stage.Traverse():
            for attr in prim.GetAttributes():
                property_stack = attr.GetPropertyStack()
                for stack_item in property_stack:
                    if attr.GetName().startswith("physics:") and not stack_item.layer.identifier.endswith(
                        "_physics.usd"
                    ):
                        self._AddFailedCheck(
                            requirement=RobotCoreCapReq.RC_005,
                            message=f"Physics Attribute {attr.GetName()} in robot asset <{stage.GetRootLayer().realPath}> has authored value NOT in the physics layer",
                            at=attr,
                        )


@omni.asset_validator.register_rule("RobotCore")
@omni.asset_validator.register_requirements(RobotCoreCapReq.RC_006, override=True)
class VerifyRobotPhysicsSchemaSourceLayer(omni.asset_validator.BaseRuleChecker):
    """Validates that physics schemas are applied in the physics layer.

    This rule checks that physics schemas in robot assets are applied in
    the physics layer (_physics.usd), following the recommended layer structure.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        # examine every prim schema in the stage and ensure that they are authored in the physics layer
        for prim in stage.Traverse():
            for layer in stage.GetLayerStack():
                prim_spec = layer.GetPrimAtPath(prim.GetPath())

                if not prim_spec:
                    continue

                api_schemas = prim_spec.GetInfo("apiSchemas")

                if api_schemas:
                    for applied_api in api_schemas.GetAppliedItems():
                        if (
                            applied_api.startswith("Physx") or applied_api.startswith("Physics")
                        ) and not layer.identifier.endswith("_physics.usd"):
                            self._AddFailedCheck(
                                requirement=RobotCoreCapReq.RC_006,
                                message=f"Physics Schema [{applied_api}] on {prim.GetPath()} in robot asset <{stage.GetRootLayer().realPath}> has applied schema NOT in the physics layer",
                                at=prim,
                            )


@omni.asset_validator.register_rule("RobotCore")
@omni.asset_validator.register_requirements(RobotCoreCapReq.RC_007, override=True)
class RobotSchema(omni.asset_validator.BaseRuleChecker):
    """Validates that robot assets have the required RobotAPI and relationships.

    This rule checks that robot assets have a default prim with the RobotAPI applied
    and the required robotLinks and robotJoints relationships defined.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim = stage.GetDefaultPrim()
        if not prim:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_007,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> is not set",
                at=stage,
            )
            return
        # JW: lazy load the schema as we dont have it and its breaking workspace
        from usd.schema.isaac import robot_schema

        if not prim.HasAPI(robot_schema.Classes.ROBOT_API.value):
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_007,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> does not have a RobotAPI",
                at=prim,
            )

        links_rel = prim.GetRelationship(robot_schema.Relations.ROBOT_LINKS.name)
        if links_rel:
            if len(links_rel.GetTargets()) == 0:
                self._AddFailedCheck(
                    requirement=RobotCoreCapReq.RC_007,
                    message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> has no entries in isaac:physics:robotLinks",
                    at=links_rel,
                )
        else:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_007,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> does not have a isaac:physics:robotLinks relationship",
                at=prim,
            )

        joints_rel = prim.GetRelationship(robot_schema.Relations.ROBOT_JOINTS.name)
        if joints_rel:
            if len(joints_rel.GetTargets()) == 0:
                self._AddFailedCheck(
                    requirement=RobotCoreCapReq.RC_007,
                    message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> has no entries in isaac:physics:robotJoints",
                    at=links_rel,
                )
        else:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_007,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> does not have a isaac:physics:robotJoints relationship",
                at=prim,
            )


@omni.asset_validator.register_rule("RobotCore")
@omni.asset_validator.register_requirements(RobotCoreCapReq.RC_008, override=True)
class RobotType(omni.asset_validator.BaseRuleChecker):
    """Validates that robot assets have the required robot type.

    This rule checks that robot assets have the required robot type and that it is one of the allowed values.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim = stage.GetDefaultPrim()
        if not prim:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_008,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> is not set",
                at=stage,
            )
            return
        robot_type = prim.GetAttribute("isaac:robotType")
        if not robot_type:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_008,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> does not have a isaac:robotType attribute",
                at=prim,
            )
            return

        # copied from source\extensions\isaacsim.robot.schema\robot_schema\RobotSchema.usda
        allowed_values = [
            "Default",
            "End Effector",
            "Manipulator",
            "Humanoid",
            "Wheeled",
            "Holonomic",
            "Quadruped",
            "Mobile Manipulators",
            "Aerial",
        ]
        if allowed_values is None:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_008,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> has a invalid isaac:robotType attribute: {robot_type.Get()}, but the schema does not specify allowed values",
                at=prim,
            )

        if robot_type.Get() not in allowed_values:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_008,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> has a invalid isaac:robotType attribute: {robot_type.Get()}",
                at=prim,
            )
            return

        if robot_type.Get() == "Default":
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_008,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> is set to Default, which is not a valid robot type",
                at=prim,
            )
            return


@omni.asset_validator.register_rule("RobotCore")
@omni.asset_validator.register_requirements(RobotCoreCapReq.RC_009, override=True)
class RootJointPinned(omni.asset_validator.BaseRuleChecker):
    """Validates that the root joint is pinned according to the robot type.

    This rule checks that the root joint is pinned according to the robot type.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        prim = stage.GetDefaultPrim()
        if not prim:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_009,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> is not set",
                at=stage,
            )
            return
        root_joints = prim.GetRelationship("isaac:physics:robotJoints")

        if not root_joints or len(root_joints.GetTargets()) == 0:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_009,
                at=prim,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> does not have a isaac:physics:robotJoints relationship",
            )
            return

        root_joint_path = root_joints.GetTargets()[0]
        root_joint_prim = stage.GetPrimAtPath(root_joint_path)
        root_joint = UsdPhysics.Joint(root_joint_prim)
        if not root_joint:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_009,
                at=prim,
                message=f"Root joint prim at <{root_joint_path}> is not a valid UsdPhysics.Joint",
            )
            return

        root_joint_target_0 = None
        root_joint_target_1 = None
        if len(root_joint.GetBody0Rel().GetTargets()) > 0:
            root_joint_target_0_path = root_joint.GetBody0Rel().GetTargets()[0]
            root_joint_target_0 = stage.GetPrimAtPath(root_joint_target_0_path)
        if len(root_joint.GetBody1Rel().GetTargets()) > 0:
            root_joint_target_1_path = root_joint.GetBody1Rel().GetTargets()[0]
            root_joint_target_1 = stage.GetPrimAtPath(root_joint_target_1_path)

        root_joint_target_0_is_pinned = root_joint_target_0 == None or not root_joint_target_0.HasAPI(
            UsdPhysics.RigidBodyAPI
        )
        root_joint_target_1_is_pinned = root_joint_target_1 == None or not root_joint_target_1.HasAPI(
            UsdPhysics.RigidBodyAPI
        )

        is_root_pinned = root_joint_target_0_is_pinned or root_joint_target_1_is_pinned
        robot_types_with_pinned_root_joint = ["Manipulator", "End Effector"]
        robot_type = prim.GetAttribute("isaac:robotType")
        if not robot_type:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_009,
                at=prim,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> does not have a isaac:robotType attribute",
            )
            return

        if robot_type.Get() == "Default":
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_009,
                at=prim,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> is set to Default, which is not a valid robot type",
            )
            return
        if robot_type.Get() in robot_types_with_pinned_root_joint and is_root_pinned == False:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_009,
                at=prim,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> has a isaac:physics:robotJoints relationship, but the root joint is not pinned",
            )
            return
        if robot_type.Get() not in robot_types_with_pinned_root_joint and is_root_pinned == True:
            self._AddFailedCheck(
                requirement=RobotCoreCapReq.RC_009,
                at=prim,
                message=f"DefaultPrim in robot asset <{stage.GetRootLayer().realPath}> has a isaac:physics:robotJoints relationship, but the root joint is pinned",
            )
            return
