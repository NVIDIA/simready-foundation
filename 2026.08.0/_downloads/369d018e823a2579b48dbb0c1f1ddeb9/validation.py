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
import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Sdf, Usd, UsdGeom, UsdShade

_RENDER_SETTINGS_TYPES = frozenset({"RenderSettings", "RenderProduct", "RenderVar"})
_OV_RENDER_METADATA_KEYS = ("no_delete", "hide_in_stage_window")


def _has_truthy_metadata(prim: Usd.Prim, key: str) -> bool:
    """Return True when prim metadata or customData for key is present and truthy."""
    try:
        if prim.HasMetadata(key):
            return bool(prim.GetMetadata(key))
        if prim.HasCustomDataKey(key):
            return bool(prim.GetCustomDataByKey(key))
    except Exception:
        return False
    return False


def _has_render_settings_type(prim: Usd.Prim) -> bool:
    """Return True when prim or any descendant has an RTX render-settings schema type."""
    for child in Usd.PrimRange(prim):
        if child.GetTypeName() in _RENDER_SETTINGS_TYPES:
            return True
    return False


def _has_asset_content_under_render(prim: Usd.Prim) -> bool:
    """Return True when /Render contains asset geometry, transforms, or materials."""
    for child in Usd.PrimRange(prim):
        if child == prim:
            continue
        if child.IsA(UsdGeom.Xform) or child.IsA(UsdGeom.Gprim) or child.IsA(UsdShade.Material):
            return True
    return False


def _is_render_settings_root(prim: Usd.Prim) -> bool:
    """
    Return True when prim is the Omniverse-generated /Render render-settings scope.

    Excludes a root prim only when it is named Render, is not the default prim, and
    looks like OV render settings (no_delete/hide_in_stage_window metadata or render
    schema descendants) without asset Xforms, geometry, or materials underneath.
    """
    if prim.GetName() != "Render":
        return False
    if prim == prim.GetStage().GetDefaultPrim():
        return False
    if _has_asset_content_under_render(prim):
        return False
    if any(_has_truthy_metadata(prim, key) for key in _OV_RENDER_METADATA_KEYS):
        return True
    return _has_render_settings_type(prim)


@usd_validation_nvidia.register_rule("Hierarchy")
@usd_validation_nvidia.register_requirements(cap.HierarchyRequirements.HI_002, override=True)
class ExclusiveXFormParentChecker(usd_validation_nvidia.BaseRuleChecker):
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


@usd_validation_nvidia.register_rule("Hierarchy")
@usd_validation_nvidia.register_requirements(cap.HierarchyRequirements.HI_006, override=True)
class PlaceablePosableXformableChecker(usd_validation_nvidia.BaseRuleChecker):
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


@usd_validation_nvidia.register_rule("Hierarchy")
@usd_validation_nvidia.register_requirements(cap.HierarchyRequirements.HI_008, override=True)
class LogicalGeometryGroupingChecker(usd_validation_nvidia.BaseRuleChecker):
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


@usd_validation_nvidia.register_rule("Hierarchy")
@usd_validation_nvidia.register_requirements(cap.HierarchyRequirements.HI_009, override=True)
class KinematicChainHierarchyChecker(usd_validation_nvidia.BaseRuleChecker):
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


@usd_validation_nvidia.register_rule("Hierarchy")
@usd_validation_nvidia.register_requirements(cap.HierarchyRequirements.HI_010, override=True)
class UndefinedPrimsChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage: Usd.Stage) -> None:
        """
        Check HI.010: Look for 'over's of prims which are not defined in this stage.

        Undefined prims (overs) can cause issues and should generally be avoided unless
        they are part of a broken reference that will be fixed.
        """
        def undefined_allowed(prim: Usd.Prim) -> bool:
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
                self._AddFailedCheck(
                    requirement=cap.HierarchyRequirements.HI_010,
                    message=f"Prim '{prim.GetPath()}' in file '{filename}' is an undefined 'over'. "
                    f"Undefined prims should be removed or properly defined.",
                    at=prim,
                )
