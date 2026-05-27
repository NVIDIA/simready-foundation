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
import omni.asset_validator
import omni.capabilities as cap
from pxr import Sdf, Usd, UsdGeom, UsdShade


# TODO: Potential Refactor: Obtaining Hierarchy Root may be a common operation, do we want to move it to a helper function?
@omni.asset_validator.register_rule("Hierarchy")
@omni.asset_validator.register_requirements(cap.HierarchyRequirements.HI_001, override=True)
class HierarchyHasRootChecker(omni.asset_validator.BaseRuleChecker):
    """
    Validates that the prim hierarchy has a single root prim.

    This validator ensures that:
    - The stage has exactly one root prim (preventing scattered/disconnected hierarchies)

    This prevents scattered or disconnected prim hierarchies and ensures a clean,
    organized asset structure with a single entry point for the entire hierarchy.

    Note: Default prim validation is handled by HI.004 (stage-has-default-prim).
    """

    def CheckStage(self, usdStage: Usd.Stage) -> None:
        """
        Check that the stage has exactly one root prim.

        Args:
            usdStage: The USD stage to validate
        """
        # Check that stage has exactly one root prim (per HI.001 spec)
        root_children = usdStage.GetPseudoRoot().GetChildren()

        if len(root_children) == 0:
            self._AddFailedCheck(
                requirement=cap.HierarchyRequirements.HI_001,
                message="Prim hierarchy must have at least one root prim. Found no root prims.",
                at=usdStage,
            )
        elif len(root_children) > 1:
            # List the scattered root prims to help users identify the issue
            root_prim_names = [prim.GetName() for prim in root_children]
            self._AddFailedCheck(
                requirement=cap.HierarchyRequirements.HI_001,
                message=f"Prim hierarchy must have a single root prim. Found {len(root_children)} root prims: {', '.join(root_prim_names)}",
                at=usdStage,
            )


@omni.asset_validator.register_rule("Hierarchy")
@omni.asset_validator.register_requirements(cap.HierarchyRequirements.HI_002, override=True)
class ExclusiveXFormParentChecker(omni.asset_validator.BaseRuleChecker):
    EXCLUSIVE_XFORM_PARENT_REQUIREMENT = cap.HierarchyRequirements.HI_002

    def CheckPrim(self, prim: Usd.Prim) -> None:
        # if prim is UsdGeomPrim, check if it has a parent Xform
        if prim.IsA(UsdGeom.Gprim):
            parent = prim.GetParent()
            # parent should be valid Xform
            if not parent.IsValid():
                self._AddFailedCheck(
                    "Prim has no valid parent.", at=prim, requirement=self.EXCLUSIVE_XFORM_PARENT_REQUIREMENT
                )
                return
            if not parent.IsA(UsdGeom.Xform):
                self._AddFailedCheck(
                    "Prim Parent is not an Xform.", at=parent, requirement=self.EXCLUSIVE_XFORM_PARENT_REQUIREMENT
                )
                return
            # parent should have only one Gprim child
            children = parent.GetChildren()
            gprim_children = list(filter(lambda child: child.IsA(UsdGeom.Gprim), children))
            if len(gprim_children) > 1:
                self._AddFailedCheck(
                    "Prim Parent has multiple Gprim children.",
                    at=parent,
                    requirement=self.EXCLUSIVE_XFORM_PARENT_REQUIREMENT,
                )
                return

            # parent must have at least one xformop:translate, one xformop:rotate, scale is optional
            xform_ops = UsdGeom.Xformable(parent).GetOrderedXformOps()
            if not any("xformOp:translate" in op.GetAttr().GetName() for op in xform_ops):
                self._AddFailedCheck(
                    "Prim Parent has no xformOp:translate.",
                    at=parent,
                    requirement=self.EXCLUSIVE_XFORM_PARENT_REQUIREMENT,
                )
            if not any("xformOp:rotate" in op.GetAttr().GetName() for op in xform_ops):
                self._AddFailedCheck(
                    "Prim Parent has no xformOp:rotate.", at=parent, requirement=self.EXCLUSIVE_XFORM_PARENT_REQUIREMENT
                )


@omni.asset_validator.register_rule("Hierarchy")
@omni.asset_validator.register_requirements(cap.HierarchyRequirements.HI_003, override=True)
class RootPrimXformableChecker(omni.asset_validator.BaseRuleChecker):
    """
    Validates that the root prim of a placeable asset is strictly an Xformable prim.

    This is a stricter version of DefaultPrimChecker that enforces HI.003 requirement:
    The root prim must inherit UsdGeomXformable (such as Xform) and NOT be a Scope.

    This ensures:
    - The entire asset can be transformed as a single unit
    - Easy positioning and orientation when referencing into scenes
    - Consistent behavior for asset manipulation tools
    - Facilitated automated scene composition and layout workflows
    """

    def CheckStage(self, usdStage):
        """Check that the default prim is strictly Xformable."""
        default_prim = usdStage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck(
                "Stage has missing or invalid defaultPrim.",
                at=usdStage,
                requirement=cap.HierarchyRequirements.HI_003,
            )
            return

        if not default_prim.GetParent().IsPseudoRoot():
            self._AddFailedCheck(
                "The default prim must be a root prim.",
                at=default_prim,
                requirement=cap.HierarchyRequirements.HI_003,
            )
            return

        # Only Xformable prims are valid (Scope is NOT allowed for HI.003)
        if not default_prim.IsA(UsdGeom.Xformable):
            self._AddFailedCheck(
                f'The root prim <{default_prim.GetName()}> of type "{default_prim.GetTypeName()}" '
                "must be an Xformable prim (e.g., Xform) to allow transformation of the entire asset.",
                at=default_prim,
                requirement=cap.HierarchyRequirements.HI_003,
            )
            # Don't continue checking other conditions if not Xformable
            return

        if not default_prim.IsActive():
            self._AddFailedCheck(
                f"The default prim <{default_prim.GetName()}> should be active.",
                at=default_prim,
                requirement=cap.HierarchyRequirements.HI_003,
            )

        if default_prim.IsAbstract():
            self._AddFailedCheck(
                f"The default prim <{default_prim.GetName()}> should not be abstract.",
                at=default_prim,
                requirement=cap.HierarchyRequirements.HI_003,
            )


@omni.asset_validator.register_rule("Hierarchy")
@omni.asset_validator.register_requirements(cap.HierarchyRequirements.HI_004, override=True)
class StageHasDefaultPrimChecker(omni.asset_validator.BaseRuleChecker):
    STAGE_HAS_DEFAULT_PRIM_REQUIREMENT = cap.HierarchyRequirements.HI_004

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck(
                "Stage has no default prim.", at=stage, requirement=self.STAGE_HAS_DEFAULT_PRIM_REQUIREMENT
            )


# @omni.asset_validator.register_rule("Hierarchy")
# @omni.asset_validator.register_requirements(cap.HierarchyRequirements.HI_005, override=True)


@omni.asset_validator.register_rule("Hierarchy")
@omni.asset_validator.register_requirements(cap.HierarchyRequirements.HI_006, override=True)
class PlaceablePosableXformableChecker(omni.asset_validator.BaseRuleChecker):
    """Validates that all placeable/posable prims are Xformable"""

    def CheckPrim(self, prim: Usd.Prim) -> None:
        # Skip abstract prims and prims that don't need transformation
        if prim.IsAbstract() or not prim.IsActive():
            return

        # Check if this prim represents a distinct object/group that needs placement
        # This includes: Meshes, Xforms with children, Lights, Cameras, etc.
        needs_transform = False

        # Check if it's a geometry prim (Mesh, Cube, Sphere, etc.)
        if prim.IsA(UsdGeom.Gprim):
            needs_transform = True

        # Check if it's an Xform with children (represents a group)
        elif prim.IsA(UsdGeom.Xform) and prim.GetChildren():
            needs_transform = True

        # Check if it's a light or camera
        elif prim.GetTypeName() in [
            "SphereLight",
            "RectLight",
            "DiskLight",
            "CylinderLight",
            "DistantLight",
            "DomeLight",
            "Camera",
        ]:
            needs_transform = True

        # Check if it has geometry children (making it a distinct group)
        elif any(child.IsA(UsdGeom.Gprim) for child in prim.GetChildren()):
            needs_transform = True

        if needs_transform and not prim.IsA(UsdGeom.Xformable):
            self._AddFailedCheck(
                requirement=cap.HierarchyRequirements.HI_006,
                message=f"Prim '{prim.GetPath()}' represents a placeable/posable object but is not Xformable. "
                f"It is of type '{prim.GetTypeName()}'.",
                at=prim,
            )


@omni.asset_validator.register_rule("Hierarchy")
@omni.asset_validator.register_requirements(cap.HierarchyRequirements.HI_008, override=True)
class LogicalGeometryGroupingChecker(omni.asset_validator.BaseRuleChecker):
    """Validates logical grouping of geometry under parent Xforms"""

    def CheckPrim(self, prim: Usd.Prim) -> None:
        # Check if this is a Gprim (geometry primitive)
        if not prim.IsA(UsdGeom.Gprim):
            return

        # Check if it has a parent Xform
        parent = prim.GetParent()
        if not parent or not parent.IsValid():
            self._AddFailedCheck(
                requirement=cap.HierarchyRequirements.HI_008,
                message=f"Geometry prim '{prim.GetPath()}' has no valid parent.",
                at=prim,
            )
            return

        # Parent should be an Xform for logical grouping
        if not parent.IsA(UsdGeom.Xform):
            self._AddFailedCheck(
                requirement=cap.HierarchyRequirements.HI_008,
                message=f"Geometry prim '{prim.GetPath()}' parent is not an Xform for logical grouping.",
                at=prim,
            )
            return

        # Check if the parent has a meaningful name (not just numbered)
        parent_name = parent.GetName()
        if parent_name.isdigit() or parent_name in ["group", "grp", "node", "mesh"]:
            self._AddFailedCheck(
                requirement=cap.HierarchyRequirements.HI_008,
                message=f"Parent Xform '{parent.GetPath()}' has non-descriptive name '{parent_name}' for logical grouping.",
                at=parent,
            )

        # Check for overly deep nesting (more than 5 levels from default prim)
        depth = 0
        current = prim
        default_prim = prim.GetStage().GetDefaultPrim()
        while current and current != default_prim:
            depth += 1
            current = current.GetParent()
            if depth > 5:
                self._AddFailedCheck(
                    requirement=cap.HierarchyRequirements.HI_008,
                    message=f"Geometry prim '{prim.GetPath()}' is nested too deeply ({depth} levels from root).",
                    at=prim,
                )
                break


@omni.asset_validator.register_rule("Hierarchy")
@omni.asset_validator.register_requirements(cap.HierarchyRequirements.HI_009, override=True)
class KinematicChainHierarchyChecker(omni.asset_validator.BaseRuleChecker):
    """
    Validates that assets with articulated joints have proper kinematic chain hierarchy.

    This validator ensures that:
    - Assets with multiple linked parts organize their hierarchy to reflect kinematic relationships
    - Each transformable link in the kinematic chain has its own Xformable prim
    - Transform operations are properly defined at each link
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """
        Check HI.009: For assets with articulated joints, the hierarchy should reflect the kinematic chain,
        with appropriate Xforms for each transformable link.

        This checks for nested Xform structures that appear to represent kinematic chains
        and ensures they have proper transform operations.
        """
        # Skip non-Xform prims
        if not prim.IsA(UsdGeom.Xform):
            return

        # Skip root prim and inactive prims
        if prim == prim.GetStage().GetDefaultPrim() or not prim.IsActive():
            return

        # Check if this Xform has Xform children (suggesting a kinematic chain)
        xform_children = [child for child in prim.GetChildren() if child.IsA(UsdGeom.Xform)]

        # If this Xform has Xform children, it's likely part of a kinematic chain
        if xform_children:
            # Verify this link has proper transform operations
            xformable = UsdGeom.Xformable(prim)
            xform_ops = xformable.GetOrderedXformOps()

            if not xform_ops:
                self._AddFailedCheck(
                    requirement=cap.HierarchyRequirements.HI_009,
                    message=f"Kinematic chain link '{prim.GetPath()}' has no transform operations. "
                    f"Each transformable link should have appropriate xformOps for positioning and articulation.",
                    at=prim,
                )
                return

            # Check if the prim has geometry or Xform children (making it a valid link)
            has_geometry = any(child.IsA(UsdGeom.Gprim) for child in prim.GetChildren())

            # If it has neither geometry nor a meaningful name, it might be a redundant grouping
            if not has_geometry and not xform_children:
                return

            # Verify that the transform operations are ordered properly
            xform_op_order = xformable.GetXformOpOrderAttr()
            if not xform_op_order or not xform_op_order.Get():
                self._AddFailedCheck(
                    requirement=cap.HierarchyRequirements.HI_009,
                    message=f"Kinematic chain link '{prim.GetPath()}' has transform operations but no xformOpOrder. "
                    f"Transform operations must be properly ordered for kinematic chains.",
                    at=prim,
                )

        # Check if this Xform has geometry children but no transform ops (suggesting improper structure)
        has_geometry = any(child.IsA(UsdGeom.Gprim) for child in prim.GetChildren())
        parent = prim.GetParent()

        # If this is part of a nested Xform hierarchy (parent is also Xform) and has geometry
        if parent and parent.IsA(UsdGeom.Xform) and parent != prim.GetStage().GetDefaultPrim():
            xformable = UsdGeom.Xformable(prim)
            xform_ops = xformable.GetOrderedXformOps()

            # This prim represents a link in a kinematic chain, ensure it has transforms
            if has_geometry and not xform_ops:
                self._AddFailedCheck(
                    requirement=cap.HierarchyRequirements.HI_009,
                    message=f"Transformable link '{prim.GetPath()}' in kinematic hierarchy has no transform operations. "
                    f"Each link should have xformOps (translate, rotate) to support articulation and positioning.",
                    at=prim,
                )


@omni.asset_validator.register_rule("Hierarchy")
@omni.asset_validator.register_requirements(cap.HierarchyRequirements.HI_010, override=True)
class UndefinedPrimsChecker(omni.asset_validator.BaseRuleChecker):
    def CheckStage(self, stage: Usd.Stage) -> None:
        """
        Check HI.010: Look for 'over's of prims which are not defined in this stage.

        Undefined prims (overs) can cause issues and should generally be avoided unless
        they are part of a broken reference that will be fixed.
        """
        errors = []

        async def undefined_allowed(prim: Usd.Prim) -> bool:
            """Check if an undefined prim is whitelisted."""
            # Check if this over is inside a reference or payload that failed to load
            p = prim
            while p.GetParent().IsValid():
                p = p.GetParent()
                if p.HasAuthoredReferences() or p.HasAuthoredPayloads():
                    for spec in p.GetPrimStack():
                        lists_to_check = [
                            spec.referenceList.addedItems,
                            spec.referenceList.appendedItems,
                            spec.referenceList.explicitItems,
                            spec.referenceList.prependedItems,
                            spec.payloadList.addedItems,
                            spec.payloadList.appendedItems,
                            spec.payloadList.explicitItems,
                            spec.payloadList.prependedItems,
                        ]
                        for ref_list in lists_to_check:
                            for ref in ref_list:
                                folder = spec.layer.identifier[: spec.layer.identifier.replace("\\", "/").rfind("/")]
                                ref_path = combine_paths(folder, ref.assetPath)
                                if not file_exists(ref_path):
                                    # We have a reference (or payload) to a missing file,
                                    # so allow this "over" for now
                                    return True
            return False

        # Traverse all prims in the stage
        for prim in stage.TraverseAll():
            if not prim.IsDefined() and not undefined_allowed(prim):
                # This is an over of an undefined prim
                filename = get_prim_filepath(prim)
                errors.append(
                    f"Prim '{prim.GetPath()}' in file '{filename}' is an undefined 'over'. "
                    f"Undefined prims should be removed or properly defined."
                )

        return errors
