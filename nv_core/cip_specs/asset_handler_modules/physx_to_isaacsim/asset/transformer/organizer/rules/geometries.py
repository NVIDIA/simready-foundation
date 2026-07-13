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
from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple, Union

from isaacsim.asset.transformer import RuleConfigurationParam, RuleInterface
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

from . import utils

# Material binding purposes to check
_MATERIAL_PURPOSES: Tuple[str, ...] = ("", "physics", "preview", "full")

# Default Configuration Parameters
_DEFAULT_SCOPE: str = "/"
_DEFAULT_GEOMETRIES_LAYER_PATH: str = "geometries.usd"
_DEFAULT_INSTANCES_LAYER_PATH: str = "instances.usda"
_DEFAULT_DEDUPLICATE: bool = True
_DEFAULT_SAVE_BASE_AS_USDA: bool = True

# Prim paths and scope names
_GEOMETRIES_SCOPE_PATH: str = "/Geometries"
_INSTANCES_SCOPE_PATH: str = "/Instances"
_VISUAL_MATERIALS_SCOPE_NAME: str = "VisualMaterials"
_DEFAULT_ROOT_PRIM_PATH: str = "/World"

# Prim type names
_XFORM_TYPE_NAME: str = "Xform"
_SCOPE_TYPE_NAME: str = "Scope"
_MATERIAL_TYPE_NAME: str = "Material"

# Identifier for flattened prototype prims created during de-instancing
_FLATTENED_PROTOTYPE_IDENTIFIER: str = "Flattened_Prototype"

# Truncation length for geometry content hashes
_GEOMETRY_HASH_LENGTH: int = 32

# Number of decimal places for floating-point quantization in hash comparisons
# 6 decimal places provides ~1 micrometer precision at meter scale
_TRANSFORM_HASH_PRECISION: int = 6


@dataclass
class GeometrySource:
    """Tracks the source information for a geometry prim."""

    prim_path: str
    source_layer_id: str
    geometry_hash: str = ""
    type_name: str = ""


@dataclass
class GeometryEntry:
    """Represents a unique geometry stored in the geometries layer."""

    name: str
    geom_layer_path: str  # e.g., "/Geometries/mesh_a"
    geom_prim_path: str  # e.g., "/Geometries/mesh_a/mesh_a"
    type_name: str
    sources: List[GeometrySource] = field(default_factory=list)
    existing: bool = False  # True if this geometry was already in the layer


@dataclass
class InstanceEntry:
    """Represents a unique instance configuration in the instances layer."""

    name: str
    instance_layer_path: str  # e.g., "/Instances/mesh_a_0"
    geometry_entry: GeometryEntry
    delta_hash: str
    sources: List[GeometrySource] = field(default_factory=list)


class GeometriesRoutingRule(RuleInterface):
    """Route geometry prims to a shared layer and create an instances layer for overrides.

    This rule operates on a fully flattened stage (pre-processed to remove all references
    and instanceable prims). It identifies all geometry prims (Mesh, Gprim types),
    deduplicates identical geometries, moves their base definitions to a dedicated
    geometries layer under /Geometries/{name}/{name}, and creates an instances layer
    to capture material bindings, applied schemas, and other per-instance deltas.
    Identical delta groups are coalesced to reduce redundancy.
    """

    def get_configuration_parameters(self) -> List[RuleConfigurationParam]:
        return [
            RuleConfigurationParam(
                name="scope",
                display_name="Scope",
                param_type=str,
                description="The scope to limit the search for geometry prims",
                default_value=_DEFAULT_SCOPE,
            ),
            RuleConfigurationParam(
                name="geometries_layer",
                display_name="Geometries Layer",
                param_type=str,
                description="The path to the geometries layer",
                default_value=_DEFAULT_GEOMETRIES_LAYER_PATH,
            ),
            RuleConfigurationParam(
                name="instance_layer",
                display_name="Instances Layer",
                param_type=str,
                description="The path to the instances layer",
                default_value=_DEFAULT_INSTANCES_LAYER_PATH,
            ),
            RuleConfigurationParam(
                name="deduplicate",
                display_name="Deduplicate",
                param_type=bool,
                description="If True, check existing geometries in layer and reuse them if identical geometry already exists",
                default_value=_DEFAULT_DEDUPLICATE,
            ),
            RuleConfigurationParam(
                name="save_base_as_usda",
                display_name="Save Base as USD",
                param_type=bool,
                description="If True, save the base stage as a USD file",
                default_value=_DEFAULT_SAVE_BASE_AS_USDA,
            ),
            RuleConfigurationParam(
                name="verbose",
                display_name="Verbose Logging",
                param_type=bool,
                description="If True, log detailed transform decomposition information",
                default_value=False,
            ),
        ]

    # --- Helper Methods for Common Operations ---

    def _is_intrinsic_property(self, prop_name: str, intrinsic_props: FrozenSet[str]) -> bool:
        """Check if a property is intrinsic to the geometry's typed schema.

        Properties considered intrinsic:
        - Properties defined by the prim's typed schema (including inherited)
        - Texture coordinate primvars (primvars:st, primvars:st0, primvars:UV, etc.)
        - Surface normals (primvars:normals, primvars:normals:indices)
        - Tangent vectors (primvars:tangents, primvars:tangents:indices)

        Properties NOT intrinsic (go to instances layer):
        - Applied API schema properties (CollisionAPI, PhysicsAPI, etc.)
        - Custom non-texture attributes

        Args:
            prop_name: The property name to check.
            intrinsic_props: Set of intrinsic property names for this geometry type.

        Returns:
            True if the property is intrinsic to the geometry type.
        """
        if prop_name in intrinsic_props:
            return True

        # Texture coordinates are intrinsic to mesh geometry
        # Common patterns: primvars:st, primvars:st0, primvars:st1, primvars:UVMap, etc.
        # Also include their :indices variants for indexed primvars
        if prop_name.startswith("primvars:st") or prop_name.startswith("primvars:UV"):
            return True

        # Surface normals define the geometry's shading normals (smooth/hard edges)
        # primvars:normals takes precedence over the normals attribute for subdivision
        if prop_name == "primvars:normals" or prop_name == "primvars:normals:indices":
            return True

        # Tangent vectors are used for normal mapping and are tied to the geometry
        if prop_name == "primvars:tangents" or prop_name == "primvars:tangents:indices":
            return True

        return False

    def _is_xform_property(self, prop_name: str) -> bool:
        """Check if a property is an xformOp property.

        Args:
            prop_name: The property name to check.

        Returns:
            True if the property is an xformOp or xformOpOrder.
        """
        return prop_name.startswith("xformOp:") or prop_name == "xformOpOrder"

    def _format_matrix_for_log(self, matrix: Gf.Matrix4d) -> str:
        """Decompose a 4x4 matrix into translation and rotation components for logging."""
        translate = Gf.Vec3d(matrix.ExtractTranslation())
        rotation = matrix.ExtractRotation()
        quat = rotation.GetQuat()
        return (
            f"Translation: ({translate[0]:.4f}, {translate[1]:.4f}, {translate[2]:.4f}), "
            f"Rotation (quat): ({quat.GetReal():.4f}, {quat.GetImaginary()[0]:.4f}, "
            f"{quat.GetImaginary()[1]:.4f}, {quat.GetImaginary()[2]:.4f})"
        )

    def _format_quat_as_euler(self, quat: Gf.Quatd) -> str:
        """Convert quaternion to Euler angles (XYZ) for logging."""
        rotation = Gf.Rotation(quat)
        # Decompose to axis-angle first
        axis = rotation.GetAxis()
        angle = rotation.GetAngle()
        # For simple rotations, show axis-angle
        return f"axis=({axis[0]:.4f}, {axis[1]:.4f}, {axis[2]:.4f}), angle={angle:.2f}°"

    def _decompose_transform(
        self,
        transform: Gf.Matrix4d,
        log_context: str = "",
    ) -> Tuple[Gf.Vec3d, Gf.Quatd, Gf.Vec3d]:
        """Decompose a transform matrix into translate, orient, and scale components.

        Args:
            transform: The transform matrix to decompose.
            log_context: Optional context string for logging.

        Returns:
            Tuple of (translate, orient, scale) where:
            - translate: Gf.Vec3d translation
            - orient: Gf.Quatd rotation quaternion
            - scale: Gf.Vec3d scale factors
        """
        # Extract translation
        translate = Gf.Vec3d(transform.ExtractTranslation())

        # Extract scale from the length of basis vectors
        row0 = Gf.Vec3d(transform.GetRow3(0))
        row1 = Gf.Vec3d(transform.GetRow3(1))
        row2 = Gf.Vec3d(transform.GetRow3(2))

        scale_x = row0.GetLength()
        scale_y = row1.GetLength()
        scale_z = row2.GetLength()

        # Check for negative scale (determinant < 0)
        det = transform.GetDeterminant()
        if det < 0:
            scale_x = -scale_x

        scale = Gf.Vec3d(scale_x, scale_y, scale_z)

        # Build a normalized rotation matrix by removing scale from each row
        # ExtractRotation() on a scaled matrix gives incorrect results
        if abs(scale_x) > 1e-10:
            row0 = row0 / abs(scale_x)
        if abs(scale_y) > 1e-10:
            row1 = row1 / scale_y
        if abs(scale_z) > 1e-10:
            row2 = row2 / scale_z

        # Construct a pure rotation matrix (no scale, no translation)
        rotation_matrix = Gf.Matrix4d(
            row0[0],
            row0[1],
            row0[2],
            0.0,
            row1[0],
            row1[1],
            row1[2],
            0.0,
            row2[0],
            row2[1],
            row2[2],
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        )

        # Extract rotation as quaternion from the normalized matrix
        rotation = rotation_matrix.ExtractRotation()
        orient = rotation.GetQuat()

        if log_context and getattr(self, "_verbose", False):
            self.log_operation(
                f"_decompose_transform [{log_context}]:\n"
                f"  Input matrix: {self._format_matrix_for_log(transform)}\n"
                f"  Row0: ({row0[0]:.6f}, {row0[1]:.6f}, {row0[2]:.6f}), len={row0.GetLength():.6f}\n"
                f"  Row1: ({row1[0]:.6f}, {row1[1]:.6f}, {row1[2]:.6f}), len={row1.GetLength():.6f}\n"
                f"  Row2: ({row2[0]:.6f}, {row2[1]:.6f}, {row2[2]:.6f}), len={row2.GetLength():.6f}\n"
                f"  Determinant: {det:.6f}\n"
                f"  ExtractRotation result: {self._format_quat_as_euler(orient)}\n"
                f"  Output: translate=({translate[0]:.6f}, {translate[1]:.6f}, {translate[2]:.6f})\n"
                f"          orient=({orient.GetReal():.6f}, {orient.GetImaginary()[0]:.6f}, "
                f"{orient.GetImaginary()[1]:.6f}, {orient.GetImaginary()[2]:.6f})\n"
                f"          scale=({scale[0]:.6f}, {scale[1]:.6f}, {scale[2]:.6f})"
            )

        return translate, orient, scale

    def _log_xform_ops(self, xformable: UsdGeom.Xformable, context: str) -> None:
        """Log detailed xformOp information for debugging (only when verbose)."""
        if not getattr(self, "_verbose", False):
            return

        ordered_ops = xformable.GetOrderedXformOps()
        if not ordered_ops:
            self.log_operation(f"  {context}: No xformOps defined")
            return

        op_order = xformable.GetXformOpOrderAttr().Get()
        self.log_operation(f"  {context}: xformOpOrder = {list(op_order) if op_order else 'None'}")

        for op in ordered_ops:
            op_name = op.GetOpName()
            op_type = op.GetOpType()
            value = op.Get()
            self.log_operation(f"    {op_name} (type={op_type}): {value}")

    def _get_mesh_local_transform_decomposed(
        self,
        prim_path: str,
    ) -> Optional[Tuple[Gf.Vec3d, Gf.Quatd, Gf.Vec3d]]:
        """Get the local transform of a mesh prim decomposed into TOS.

        Computes the mesh's local transform (relative to its parent) and decomposes
        it into translate, orient (quaternion), and scale components.

        Args:
            prim_path: Path to the mesh prim.

        Returns:
            Tuple of (translate, orient, scale) if transform is non-identity,
            None if identity or prim is invalid.
        """
        mesh_prim = self.source_stage.GetPrimAtPath(prim_path)
        if not mesh_prim.IsValid():
            return None

        mesh_xformable = UsdGeom.Xformable(mesh_prim)
        if not mesh_xformable:
            return None

        # Log xformOps before getting composed transform (verbose only)
        if getattr(self, "_verbose", False):
            self.log_operation(f"_get_mesh_local_transform_decomposed: prim={prim_path}")
            self._log_xform_ops(mesh_xformable, "mesh xformOps")

        # Get the local transform at default time
        local_transform = mesh_xformable.GetLocalTransformation()

        if getattr(self, "_verbose", False):
            self.log_operation(f"  GetLocalTransformation() result: {self._format_matrix_for_log(local_transform)}")

        if self._is_identity_transform(local_transform):
            if getattr(self, "_verbose", False):
                self.log_operation(f"  -> Identity transform, returning None")
            return None

        return self._decompose_transform(local_transform, log_context=f"mesh_local: {prim_path}")

    def _is_identity_transform(self, transform: Gf.Matrix4d) -> bool:
        """Check if a transform matrix is approximately identity.

        Args:
            transform: The transform matrix to check.

        Returns:
            True if the transform is approximately identity within tolerance.
        """
        identity = Gf.Matrix4d(1.0)
        tolerance = 10 ** (-_TRANSFORM_HASH_PRECISION)
        for row in range(4):
            for col in range(4):
                if abs(transform[row, col] - identity[row, col]) > tolerance:
                    return False
        return True

    def _should_merge_with_parent(self, prim_path: str) -> bool:
        """Check if a prim should be merged with its parent.

        A prim should be merged with its parent if the parent has no other children
        besides this prim. This allows the reference to be placed directly on the
        parent with combined transforms.

        Args:
            prim_path: Path to the prim to check.

        Returns:
            True if the parent has only this prim as its child.
        """
        prim = self.source_stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            return False

        parent = prim.GetParent()
        if not parent or not parent.IsValid():
            return False

        # Don't merge if parent is the pseudo-root or default prim
        parent_path = parent.GetPath().pathString
        if parent_path == "/" or parent == self.source_stage.GetDefaultPrim():
            return False

        # Check if parent has exactly one child
        children = parent.GetChildren()
        return len(children) == 1

    def _get_combined_parent_child_transform(
        self,
        prim_path: str,
    ) -> Optional[Tuple[Gf.Vec3d, Gf.Quatd, Gf.Vec3d]]:
        """Compute the combined transform of a prim and its parent.

        Computes child_local_transform * parent_local_transform to get the
        forward transform from child's local space to grandparent's space,
        then decomposes it into TOS components.

        With USD row-vector convention (P' = P * M), matrix multiplication
        A * B applies A first, then B. To transform from child space to
        grandparent space: child_local (child→parent) then parent_local
        (parent→grandparent).

        Args:
            prim_path: Path to the child prim.

        Returns:
            Tuple of (translate, orient, scale) for the combined transform,
            or None if both transforms are identity.
        """
        prim = self.source_stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            return None

        parent = prim.GetParent()
        if not parent or not parent.IsValid():
            return None

        parent_path = parent.GetPath().pathString

        if getattr(self, "_verbose", False):
            self.log_operation(
                f"_get_combined_parent_child_transform:\n"
                f"  Child prim: {prim_path}\n"
                f"  Parent prim: {parent_path}"
            )

        # Get parent local transform
        parent_xformable = UsdGeom.Xformable(parent)
        parent_transform = Gf.Matrix4d(1.0)
        if parent_xformable:
            self._log_xform_ops(parent_xformable, f"parent ({parent_path}) xformOps")
            parent_transform = parent_xformable.GetLocalTransformation()

        # Get child local transform
        child_xformable = UsdGeom.Xformable(prim)
        child_transform = Gf.Matrix4d(1.0)
        if child_xformable:
            self._log_xform_ops(child_xformable, f"child ({prim_path}) xformOps")
            child_transform = child_xformable.GetLocalTransformation()

        if getattr(self, "_verbose", False):
            self.log_operation(
                f"  Child GetLocalTransformation(): {self._format_matrix_for_log(child_transform)}\n"
                f"  Parent GetLocalTransformation(): {self._format_matrix_for_log(parent_transform)}"
            )

        # Compute combined transform: child * parent
        # With row vectors, this applies child_transform first, then parent_transform
        combined_transform = child_transform * parent_transform

        if getattr(self, "_verbose", False):
            self.log_operation(f"  Combined (child * parent): {self._format_matrix_for_log(combined_transform)}")

        if self._is_identity_transform(combined_transform):
            if getattr(self, "_verbose", False):
                self.log_operation(f"  -> Identity transform, returning None")
            return None

        return self._decompose_transform(combined_transform, log_context=f"combined: {parent_path} + {prim_path}")

    def _apply_transform_to_prim_spec(
        self,
        prim_spec: Sdf.PrimSpec,
        translate: Gf.Vec3d,
        orient: Gf.Quatd,
        scale: Gf.Vec3d,
    ) -> None:
        """Apply a TOS transform to a prim spec.

        Creates xformOp:translate, xformOp:orient, xformOp:scale attributes
        and sets the xformOpOrder.

        Args:
            prim_spec: The prim spec to apply transform to.
            translate: Translation vector.
            orient: Orientation quaternion.
            scale: Scale vector.
        """
        # Create translate op
        translate_attr = Sdf.AttributeSpec(prim_spec, "xformOp:translate", Sdf.ValueTypeNames.Double3)
        if translate_attr:
            translate_attr.default = translate

        # Create orient op (quaternion)
        orient_attr = Sdf.AttributeSpec(prim_spec, "xformOp:orient", Sdf.ValueTypeNames.Quatd)
        if orient_attr:
            orient_attr.default = orient

        # Create scale op
        scale_attr = Sdf.AttributeSpec(prim_spec, "xformOp:scale", Sdf.ValueTypeNames.Double3)
        if scale_attr:
            scale_attr.default = scale

        # Set xformOpOrder (uniform variability)
        xform_op_order_attr = Sdf.AttributeSpec(
            prim_spec, "xformOpOrder", Sdf.ValueTypeNames.TokenArray, Sdf.VariabilityUniform
        )
        if xform_op_order_attr:
            xform_op_order_attr.default = ["xformOp:translate", "xformOp:orient", "xformOp:scale"]

    def _collect_material_paths(self, prim: Usd.Prim) -> List[Sdf.Path]:
        """Collect all material paths bound to a prim.

        Args:
            prim: The prim to check for material bindings.

        Returns:
            List of material paths.
        """
        paths = []
        if not prim.HasAPI(UsdShade.MaterialBindingAPI):
            return paths

        binding_api = UsdShade.MaterialBindingAPI(prim)
        for purpose in _MATERIAL_PURPOSES:
            if purpose == "":
                binding = binding_api.GetDirectBinding()
            else:
                binding = binding_api.GetDirectBinding(materialPurpose=purpose)
            mat_path = binding.GetMaterialPath()
            if mat_path:
                paths.append(mat_path)
        return paths

    def _clean_geomsubset_spec(self, subset_spec: Sdf.PrimSpec, subset_prim: Usd.Prim) -> None:
        """Clean a GeomSubset spec to only keep intrinsic properties.

        Removes non-intrinsic properties like material bindings and applied API schemas,
        keeping only the GeomSubset's intrinsic data (elementType, indices, familyName).

        Args:
            subset_spec: The GeomSubset prim spec to clean.
            subset_prim: The corresponding composed prim (for intrinsic attr lookup).
        """
        # Get intrinsic properties for GeomSubset
        intrinsic_props = self._get_intrinsic_attributes(subset_prim)

        # Remove non-intrinsic properties
        props_to_remove = []
        for prop in subset_spec.properties:
            if not self._is_intrinsic_property(prop.name, intrinsic_props):
                props_to_remove.append(prop.name)

        for prop_name in props_to_remove:
            del subset_spec.properties[prop_name]

        # Clear applied API schemas
        if subset_spec.HasInfo("apiSchemas"):
            subset_spec.ClearInfo("apiSchemas")

        # Clean schema metadata from remaining attributes
        utils.clean_schema_metadata(subset_spec)

        # Clear composition arcs
        utils.clear_composition_arcs(subset_spec)

    def _copy_geomsubset_to_layer(
        self,
        src_prim: Usd.Prim,
        dst_layer: Sdf.Layer,
        dst_path: str,
    ) -> bool:
        """Copy a GeomSubset prim to the geometries layer with only intrinsic properties.

        Args:
            src_prim: The source GeomSubset prim from composed stage.
            dst_layer: The destination layer (geometries layer).
            dst_path: The destination path in the layer.

        Returns:
            True if the copy succeeded, False otherwise.
        """
        if not src_prim.IsValid() or not src_prim.IsA(UsdGeom.Subset):
            return False

        # Create the prim spec
        prim_spec = Sdf.CreatePrimInLayer(dst_layer, dst_path)
        if not prim_spec:
            return False

        prim_spec.specifier = Sdf.SpecifierDef
        prim_spec.typeName = src_prim.GetTypeName()

        # Get intrinsic properties for GeomSubset
        intrinsic_props = self._get_intrinsic_attributes(src_prim)

        # Copy only intrinsic attributes
        for attr in src_prim.GetAttributes():
            if not attr.HasAuthoredValue():
                continue

            attr_name = attr.GetName()
            if not self._is_intrinsic_property(attr_name, intrinsic_props):
                continue

            try:
                attr_spec = Sdf.AttributeSpec(prim_spec, attr_name, attr.GetTypeName())
                if attr_spec:
                    value = attr.Get()
                    if value is not None:
                        attr_spec.default = value

                    if attr.GetVariability() == Sdf.VariabilityUniform:
                        attr_spec.variability = Sdf.VariabilityUniform
            except Exception:
                pass

        return True

    def _copy_geomsubset_deltas_to_instances(
        self,
        src_prim: Usd.Prim,
        dst_layer: Sdf.Layer,
        dst_path: str,
    ) -> bool:
        """Copy non-intrinsic properties of a GeomSubset to instances layer as overrides.

        GeomSubset intrinsic data (indices, elementType, familyName) is in the geometries
        layer. This method copies only the instance-specific data like material bindings
        and applied API schemas.

        Args:
            src_prim: The source GeomSubset prim from composed stage.
            dst_layer: The destination layer (instances layer).
            dst_path: The destination path in the layer.

        Returns:
            True if any deltas were copied, False otherwise.
        """
        if not src_prim.IsValid():
            return False

        # Get intrinsic properties to exclude
        intrinsic_props = self._get_intrinsic_attributes(src_prim)

        # Check if there are any non-intrinsic properties to copy
        has_deltas = False

        # Check for applied API schemas
        applied_schemas = src_prim.GetAppliedSchemas()
        if applied_schemas:
            has_deltas = True

        # Check for non-intrinsic attributes
        if not has_deltas:
            for attr in src_prim.GetAttributes():
                if not attr.HasAuthoredValue() and not attr.GetConnections():
                    continue
                if not self._is_intrinsic_property(attr.GetName(), intrinsic_props):
                    has_deltas = True
                    break

        # Check for relationships (like material bindings)
        if not has_deltas:
            for rel in src_prim.GetRelationships():
                if rel.HasAuthoredTargets():
                    has_deltas = True
                    break

        if not has_deltas:
            return False

        # Create the prim spec as an over
        prim_spec = Sdf.CreatePrimInLayer(dst_layer, dst_path)
        if not prim_spec:
            return False

        prim_spec.specifier = Sdf.SpecifierOver
        # Don't set typeName - it comes from the reference

        # Copy applied API schemas
        if applied_schemas:
            prim_spec.SetInfo("apiSchemas", Sdf.TokenListOp.CreateExplicit(list(applied_schemas)))

        # Copy non-intrinsic attributes
        for attr in src_prim.GetAttributes():
            if not attr.HasAuthoredValue() and not attr.GetConnections():
                continue

            attr_name = attr.GetName()
            if self._is_intrinsic_property(attr_name, intrinsic_props):
                continue

            try:
                attr_spec = Sdf.AttributeSpec(prim_spec, attr_name, attr.GetTypeName())
                if not attr_spec:
                    continue

                if attr.HasAuthoredValue():
                    value = attr.Get()
                    if value is not None:
                        attr_spec.default = value

                if attr.GetVariability() == Sdf.VariabilityUniform:
                    attr_spec.variability = Sdf.VariabilityUniform

                connections = attr.GetConnections()
                if connections:
                    for conn in connections:
                        attr_spec.connectionPathList.Prepend(conn)
            except Exception:
                pass

        # Copy relationships (material bindings, etc.)
        for rel in src_prim.GetRelationships():
            if not rel.HasAuthoredTargets():
                continue

            try:
                rel_spec = Sdf.RelationshipSpec(prim_spec, rel.GetName())
                if rel_spec:
                    for target in rel.GetTargets():
                        rel_spec.targetPathList.Prepend(target)
            except Exception:
                pass

        return True

    @staticmethod
    def _copy_attr_value_to_spec(prim_spec: Sdf.PrimSpec, attr: Usd.Attribute) -> bool:
        """Copy an attribute's value to a prim spec.

        Args:
            prim_spec: The prim spec to copy the attribute to.
            attr: The source attribute to copy.

        Returns:
            True if the attribute was copied successfully, False otherwise.
        """
        try:
            attr_spec = Sdf.AttributeSpec(prim_spec, attr.GetName(), attr.GetTypeName())
            if attr_spec:
                value = attr.Get()
                if value is not None:
                    attr_spec.default = value
                return True
        except Exception:
            pass
        return False

    def _remove_doc_metadata_from_layer(self, layer: Sdf.Layer) -> None:
        """Remove 'doc' metadata from all prims and properties in a layer.

        Traverses all prims in the layer and clears the 'doc' metadata from
        the prim specs themselves and all their attributes and relationships.

        Args:
            layer: The layer to process.
        """
        # Collect all prim paths using Traverse callback
        prim_paths = []
        layer.Traverse(Sdf.Path.absoluteRootPath, lambda path: prim_paths.append(path))

        for path in prim_paths:
            # Skip the pseudoRoot to preserve layer-level documentation
            if path == Sdf.Path.absoluteRootPath:
                continue

            prim_spec = layer.GetPrimAtPath(path)
            if not prim_spec:
                continue

            # Clear doc from prim spec itself
            if prim_spec.HasInfo("documentation"):
                prim_spec.ClearInfo("documentation")

            # Clear doc from all attributes
            for attr_name in list(prim_spec.attributes.keys()):
                attr_spec = prim_spec.attributes[attr_name]
                if attr_spec.HasInfo("doc"):
                    attr_spec.ClearInfo("doc")
                if attr_spec.HasInfo("documentation"):
                    attr_spec.ClearInfo("documentation")

            # Clear doc from all relationships
            for rel_name in list(prim_spec.relationships.keys()):
                rel_spec = prim_spec.relationships[rel_name]
                if rel_spec.HasInfo("doc"):
                    rel_spec.ClearInfo("doc")
                if rel_spec.HasInfo("documentation"):
                    rel_spec.ClearInfo("documentation")

    def _make_references_non_instanceable(self) -> None:
        """Pre-process the stage to make all instanceable references non-instanceable.

        This method recursively traverses the source stage to find all prims with
        instanceable=True. For each instanceable prim, it checks if there are any local
        overrides on children in the source layer. If local overrides exist, they are
        deleted first to avoid composition conflicts. Then the instanceable flag is
        removed from the prim.

        This ensures the stage is in a clean state for geometry processing, where all
        prim contents can be directly accessed and modified.
        """
        source_layer = self.source_stage.GetRootLayer()
        deleted_overrides_count = 0
        cleared_instanceable_count = 0

        def process_prim_recursive(prim: Usd.Prim) -> Tuple[int, int]:
            """Recursively process a prim and its children to clear instanceable flags.

            Args:
                prim: The prim to process.

            Returns:
                Tuple of (deleted_overrides_count, cleared_instanceable_count).
            """
            nonlocal source_layer
            deleted = 0
            cleared = 0

            # Check if this prim is instanceable
            if prim.IsInstanceable():
                prim_path = prim.GetPath()

                # Check for and delete local overrides on children
                # Children of instanceable prims are instance proxies in the composed stage,
                # but we need to check the source layer for override specs
                prim_spec = source_layer.GetPrimAtPath(prim_path)
                if prim_spec:

                    # Clear the instanceable flag
                    if prim_spec.HasInfo("instanceable") or prim_spec.instanceable:
                        # Recursively delete child override specs
                        # deleted += self._delete_child_overrides(prim_spec)
                        self.log_operation(f"Clearing instanceable flag on {prim_path}")
                        prim_spec.instanceable = False
                        cleared += 1
                else:
                    # Prim spec doesn't exist in source layer, create an over to clear instanceable
                    prim_spec = Sdf.CreatePrimInLayer(source_layer, prim_path)
                    if prim_spec:
                        prim_spec.specifier = Sdf.SpecifierOver
                        prim_spec.instanceable = False
                        cleared += 1
                # Process children
            for child in prim.GetChildren():
                child_deleted, child_cleared = process_prim_recursive(child)
                deleted += child_deleted
                cleared += child_cleared

            return deleted, cleared

        # Start recursive traversal from stage root

        for root_prim in self.source_stage.GetPseudoRoot().GetChildren():
            deleted, cleared = process_prim_recursive(root_prim)
            deleted_overrides_count += deleted
            cleared_instanceable_count += cleared

        if deleted_overrides_count > 0 or cleared_instanceable_count > 0:
            self.log_operation(
                f"Pre-processing: cleared instanceable on {cleared_instanceable_count} prims, "
                f"deleted {deleted_overrides_count} child override specs"
            )

            # Get the layer path before releasing references
            layer_path = source_layer.realPath

            # Flatten and export the stage to disk
            flattened_layer = self.source_stage.Flatten()
            flattened_layer.Export(layer_path)

            # Release stage reference to allow layer cleanup
            self.source_stage = None

            # Clear the USD layer cache for this path and reload from disk
            cached_layer = Sdf.Layer.Find(layer_path)
            if cached_layer:
                # Reload forces the layer to re-read from disk
                cached_layer.Reload(force=True)

            # Reopen the stage with the fresh layer data
            self.source_stage = Usd.Stage.Open(layer_path)
            if not self.source_stage:
                raise RuntimeError(f"Failed to reopen source stage from {layer_path}")

    def _delete_child_overrides(self, prim_spec: Sdf.PrimSpec) -> int:
        """Delete all child override specs from a prim spec.

        Recursively deletes all child prim specs that are overrides (not definitions).
        This is used to clean up local overrides on children of instanceable references
        before removing the instanceable flag.

        Args:
            prim_spec: The parent prim spec whose child overrides should be deleted.

        Returns:
            The number of child override specs deleted.
        """
        deleted_count = 0
        children_to_delete: List[str] = []

        for child_spec in prim_spec.nameChildren:
            # Recursively process grandchildren first
            deleted_count += self._delete_child_overrides(child_spec)

            # Check if this child is an override (not a definition)
            # Overrides have specifier Over, definitions have specifier Def
            if child_spec.specifier == Sdf.SpecifierOver:
                children_to_delete.append(child_spec.name)

        # Delete the collected override children
        for child_name in children_to_delete:
            if child_name in prim_spec.nameChildren:
                del prim_spec.nameChildren[child_name]
                deleted_count += 1

        return deleted_count

    def process_rule(self) -> Optional[str]:
        """Collect imageable geometries into a shared layer and create instance overrides.

        Performs the following operations:
        1. Pre-processes the stage to flatten all references and instanceable prims.
        2. Identifies all geometry prims (Mesh and Gprim types) in the flattened stage.
        3. If deduplicate is enabled, scans existing geometries in the layer first.
        4. Computes geometry hashes to deduplicate identical geometries.
        5. Moves unique geometry definitions to /Geometries/{name}/{name} in geometries layer.
        6. Creates Xform references at original locations pointing to geometry layer.
        7. Collects material bindings and schema overrides into an instances layer.
        8. Groups identical deltas together for deduplication.

        Args:
            params.geometries_layer: Path to the USD stage to save the geometries.
            params.instance_layer: Path to the USD stage to save updated references with deltas.
            params.scope: Optional root scope path to limit the search.
            params.deduplicate: If True (default), check existing geometries in layer and
                reuse them if identical geometry already exists.
        """
        params = self.args.get("params", {}) or {}
        scope = params.get("scope") or "/"
        save_base_as_usda = params.get("save_base_as_usda", _DEFAULT_SAVE_BASE_AS_USDA)
        self._verbose = params.get("verbose", False)

        # Pre-process: make all instanceable references non-instanceable
        # This clears local overrides on children and removes instanceable flags
        self.log_operation("Pre-processing: making all instanceable references non-instanceable")
        self._make_references_non_instanceable()
        self.log_operation("Pre-processing: done")

        geometries_layer_path = os.path.join(
            self.destination_path, params.get("geometries_layer") or _DEFAULT_GEOMETRIES_LAYER_PATH
        )
        instance_layer_path = os.path.join(
            self.destination_path, params.get("instance_layer") or _DEFAULT_INSTANCES_LAYER_PATH
        )
        deduplicate = params.get("deduplicate", True)

        self.log_operation(
            f"GeometriesRoutingRule start scope={scope} deduplicate={deduplicate} "
            f"geometries_layer={geometries_layer_path} instance_layer={instance_layer_path}"
        )

        # Track materials that are relocated to VisualMaterials scope for later cleanup
        self._relocated_material_sources: Set[str] = set()

        # Resolve output paths relative to package root
        geometries_output_path = os.path.join(self.package_root, geometries_layer_path)
        instance_output_path = os.path.join(self.package_root, instance_layer_path)

        # Ensure output directories exist
        os.makedirs(os.path.dirname(geometries_output_path), exist_ok=True)
        os.makedirs(os.path.dirname(instance_output_path), exist_ok=True)

        # Find all geometry prims and their sources
        geometry_sources = self._find_geometry_sources(scope)
        self.log_operation(f"Found {len(geometry_sources)} geometry prim usages")
        self.log_operation(f"Geometry sources: {[source.prim_path for source in geometry_sources]}")

        if not geometry_sources:
            self.log_operation("No geometry prims found, skipping")
            return None

        # Open or create geometries layer
        geometries_layer = Sdf.Layer.FindOrOpen(geometries_output_path)
        if not geometries_layer:
            geometries_layer = Sdf.Layer.CreateNew(geometries_output_path)
            self.log_operation(f"Created new geometries layer: {geometries_output_path}")
        else:
            self.log_operation(f"Opened existing geometries layer: {geometries_output_path}")
        utils.copy_stage_metadata(self.source_stage, geometries_layer)
        geom_stage = Usd.Stage.Open(geometries_layer)

        # Open or create instances layer
        instances_layer = Sdf.Layer.FindOrOpen(instance_output_path)
        if not instances_layer:
            instances_layer = Sdf.Layer.CreateNew(instance_output_path)
            self.log_operation(f"Created new instances layer: {instance_output_path}")
        else:
            self.log_operation(f"Opened existing instances layer: {instance_output_path}")
        utils.copy_stage_metadata(self.source_stage, instances_layer)
        inst_stage = Usd.Stage.Open(instances_layer)

        # Create /Geometries scope in geometries layer
        geom_stage.DefinePrim(_GEOMETRIES_SCOPE_PATH, _SCOPE_TYPE_NAME)

        # Group geometries by their content hash for deduplication
        geometry_by_hash: Dict[str, GeometryEntry] = {}
        geometry_name_counter: Dict[str, int] = defaultdict(int)

        # If deduplication is enabled, scan existing geometries in the layer first
        existing_count = 0
        if deduplicate:
            existing_geometries = self._scan_existing_geometries(geom_stage)
            for geom_hash, entry in existing_geometries.items():
                geometry_by_hash[geom_hash] = entry
                # Track name to avoid collisions
                geometry_name_counter[entry.name] += 1
            existing_count = len(existing_geometries)
            if existing_count > 0:
                self.log_operation(f"Found {existing_count} existing geometries in layer")

        new_count = 0
        reused_count = 0

        for source in geometry_sources:
            prim = self.source_stage.GetPrimAtPath(source.prim_path)
            if not prim.IsValid():
                continue

            # Compute geometry hash
            geom_hash = self._compute_geometry_hash(prim)
            source.geometry_hash = geom_hash
            source.type_name = prim.GetTypeName()

            if geom_hash in geometry_by_hash:
                # Geometry already exists (either from this run or existing in layer)
                existing_entry = geometry_by_hash[geom_hash]
                existing_entry.sources.append(source)
                if existing_entry.existing:
                    reused_count += 1
            else:
                # New unique geometry, create entry
                base_name = self._get_geometry_name(prim)
                geometry_name_counter[base_name] += 1
                if geometry_name_counter[base_name] > 1:
                    unique_name = f"{base_name}_{geometry_name_counter[base_name] - 1}"
                else:
                    unique_name = base_name

                entry = GeometryEntry(
                    name=unique_name,
                    geom_layer_path=f"{_GEOMETRIES_SCOPE_PATH}/{unique_name}",
                    geom_prim_path=f"{_GEOMETRIES_SCOPE_PATH}/{unique_name}/{unique_name}",
                    type_name=source.type_name,
                    sources=[source],
                    existing=False,
                )
                geometry_by_hash[geom_hash] = entry

                # Copy geometry to geometries layer
                self._copy_geometry_to_layer(prim, entry, geom_stage)
                new_count += 1

        self.log_operation(
            f"Processed {len(geometry_sources)} geometry usages: "
            f"{new_count} new, {reused_count} reused from existing layer, "
            f"{len(geometry_sources) - new_count - reused_count} deduplicated within batch"
        )

        # Create /Instances scope in instances layer for deduplicated instance definitions
        inst_stage.DefinePrim(_INSTANCES_SCOPE_PATH, _SCOPE_TYPE_NAME)

        # Group sources by (geometry_hash, delta_hash) for instance deduplication
        # This creates unique InstanceEntry objects for sources with identical overrides
        instance_by_key: Dict[Tuple[str, str], InstanceEntry] = {}
        instance_name_counter: Dict[str, int] = defaultdict(int)

        for geom_hash, entry in geometry_by_hash.items():
            for source in entry.sources:
                prim = self.source_stage.GetPrimAtPath(source.prim_path)
                if not prim.IsValid():
                    continue

                # Compute delta hash for instance deduplication
                delta_hash = self._compute_instance_delta_hash(prim)
                instance_key = (geom_hash, delta_hash)

                if instance_key in instance_by_key:
                    # Instance with same geometry and deltas already exists
                    instance_by_key[instance_key].sources.append(source)
                else:
                    # New unique instance configuration
                    base_name = entry.name
                    instance_name_counter[base_name] += 1
                    if instance_name_counter[base_name] > 1:
                        unique_name = f"{base_name}_{instance_name_counter[base_name] - 1}"
                    else:
                        unique_name = base_name

                    instance_entry = InstanceEntry(
                        name=unique_name,
                        instance_layer_path=f"{_INSTANCES_SCOPE_PATH}/{unique_name}",
                        geometry_entry=entry,
                        delta_hash=delta_hash,
                        sources=[source],
                    )
                    instance_by_key[instance_key] = instance_entry

        # Create deduplicated instance definitions in instances layer
        unique_instance_count = 0
        total_source_count = 0
        for instance_key, instance_entry in instance_by_key.items():
            # Use the first source as the template for copying deltas
            template_source = instance_entry.sources[0]
            template_prim = self.source_stage.GetPrimAtPath(template_source.prim_path)
            if not template_prim.IsValid():
                continue

            # Create the deduplicated instance definition
            self._create_deduplicated_instance(
                instance_entry,
                geometries_output_path,
                inst_stage,
                template_prim,
            )
            unique_instance_count += 1
            total_source_count += len(instance_entry.sources)

        deduplicated_count = total_source_count - unique_instance_count
        self.log_operation(
            f"Created {unique_instance_count} unique instance definitions "
            f"({deduplicated_count} deduplicated from {total_source_count} sources)"
        )

        # Remove "doc" metadata from all properties in both layers
        self._remove_doc_metadata_from_layer(geometries_layer)
        self._remove_doc_metadata_from_layer(instances_layer)

        # Final pass: add identity transforms to Xformable prims without xformOps
        self._finalize_instances_layer(instances_layer)

        # Deduplicate instances based on content hash (uses relative paths for material bindings)
        instance_remap = self._deduplicate_instances_layer(instances_layer, instance_by_key)

        # Export layers (Export does a clean serialization, Save can leave stale state in USDC)
        geometries_layer.Export(geometries_output_path)
        instances_layer.Export(instance_output_path)

        # Update source stage to reference the instances layer with instanceable references
        self._update_source_stage_references(
            instance_by_key,
            instance_output_path,
            instance_remap,
        )

        # Clean up flattened prototypes created during de-instancing
        self._cleanup_flattened_prototypes()

        # Delete source materials that were relocated to VisualMaterials scope
        self._delete_relocated_material_sources()

        # Export the source stage with updated references and cleaned prototypes
        # Force clean serialization to ensure no stale data from deleted mesh attributes
        source_layer = self.source_stage.GetRootLayer()
        original_path = source_layer.realPath
        export_path = original_path
        if save_base_as_usda:
            # Export directly as USDA for clean text serialization (no stale allocations)
            if original_path.endswith(".usda"):
                # Already USDA, export in place
                source_layer.Export(original_path)
            else:
                # Convert to USDA: export with new extension, delete original
                usda_path = os.path.splitext(original_path)[0] + ".usda"
                source_layer.Export(usda_path)
                self.add_affected_stage(usda_path)
                export_path = usda_path

                # Release the layer from USD's registry before deletion.
                # On Windows, files with open handles cannot be deleted.
                old_layer = Sdf.Layer.Find(original_path)
                if old_layer:
                    old_layer.Clear()

                try:
                    os.remove(original_path)
                except PermissionError:
                    # On Windows, the file may still be locked by USD's layer registry.
                    # Log warning and continue - temp files will be cleaned up eventually.
                    self.log_operation(f"Warning: Could not delete {original_path} - file may be locked")

                # Update instances layer references to point to the new source file
                self._update_instances_layer_source_references(
                    instances_layer,
                    original_path,
                    export_path,
                )
                instances_layer.Export(instance_output_path)
        else:
            # Keep original format but force clean serialization via temp file round-trip
            temp_path = original_path + ".tmp.usda"
            source_layer.Export(temp_path)

            clean_layer = Sdf.Layer.FindOrOpen(temp_path)
            if clean_layer:
                clean_layer.Export(original_path)
                # Clear the temp layer before deletion to release file handle
                clean_layer.Clear()

            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except PermissionError:
                    # Temp file cleanup failed - will be cleaned up eventually
                    pass

        self.add_affected_stage(geometries_layer_path)
        self.add_affected_stage(instance_layer_path)

        total_unique_geom = len(geometry_by_hash)
        new_geom_in_layer = total_unique_geom - existing_count
        self.log_operation(
            f"GeometriesRoutingRule completed: {total_unique_geom} unique geometries "
            f"({new_geom_in_layer} new, {existing_count} pre-existing), "
            f"{unique_instance_count} unique instances ({deduplicated_count} deduplicated)"
        )

        return export_path

    def _find_geometry_sources(self, scope: str | None) -> List[GeometrySource]:
        """Find all geometry prims and track their source information.

        Since the stage is fully flattened during pre-processing, all geometries
        are direct definitions with no references or instanceable prims.

        Args:
            scope: Optional root scope path to limit the search.

        Returns:
            List of GeometrySource objects describing each geometry usage.
        """
        geometry_sources = []
        root_prim = self.source_stage.GetPseudoRoot()

        if scope:
            scope_prim = self.source_stage.GetPrimAtPath(scope)
            if scope_prim.IsValid():
                root_prim = scope_prim
            else:
                self.log_operation(f"Scope path {scope} not found, using stage root")

        for prim in Usd.PrimRange(root_prim):
            if not (prim.IsA(UsdGeom.Mesh) or prim.IsA(UsdGeom.Gprim)):
                continue

            prim_path = prim.GetPath().pathString
            prim_stack = prim.GetPrimStack()
            source_layer_id = ""

            if prim_stack:
                strongest_spec = prim_stack[0]
                source_layer_id = strongest_spec.layer.identifier

            geometry_sources.append(
                GeometrySource(
                    prim_path=prim_path,
                    source_layer_id=source_layer_id,
                )
            )

        return geometry_sources

    def _scan_existing_geometries(self, geom_stage: Usd.Stage) -> Dict[str, GeometryEntry]:
        """Scan existing geometries in the geometries layer and compute their hashes.

        This enables deduplication against previously imported geometries.

        Args:
            geom_stage: The geometries stage to scan.

        Returns:
            Dictionary mapping geometry hashes to GeometryEntry objects for existing geometries.
        """
        existing: Dict[str, GeometryEntry] = {}

        geometries_scope = geom_stage.GetPrimAtPath(_GEOMETRIES_SCOPE_PATH)
        if not geometries_scope.IsValid():
            return existing

        for xform_prim in geometries_scope.GetChildren():
            if not xform_prim.IsValid():
                continue

            xform_path = xform_prim.GetPath().pathString
            xform_name = xform_prim.GetName()

            # Look for the geometry prim inside: /Geometries/{name}/{name}
            geom_prim_path = f"{xform_path}/{xform_name}"
            geom_prim = geom_stage.GetPrimAtPath(geom_prim_path)

            if not geom_prim.IsValid():
                # Try to find any geometry child
                for child in xform_prim.GetChildren():
                    if child.IsA(UsdGeom.Gprim):
                        geom_prim = child
                        geom_prim_path = child.GetPath().pathString
                        break

            if not geom_prim.IsValid() or not geom_prim.IsA(UsdGeom.Gprim):
                continue

            # Compute hash for this existing geometry
            geom_hash = self._compute_geometry_hash(geom_prim)

            entry = GeometryEntry(
                name=xform_name,
                geom_layer_path=xform_path,
                geom_prim_path=geom_prim_path,
                type_name=geom_prim.GetTypeName(),
                sources=[],
                existing=True,
            )
            existing[geom_hash] = entry

        return existing

    def _get_geometry_name(self, prim: Usd.Prim) -> str:
        """Generate a name for the geometry based on the prim.

        Args:
            prim: The geometry prim.

        Returns:
            A sanitized name suitable for use in the geometries layer.
        """
        name = prim.GetName()
        # Sanitize name for use in prim paths
        sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
        if not sanitized or sanitized[0].isdigit():
            sanitized = "geom_" + sanitized
        return sanitized

    def _compute_geometry_hash(self, prim: Usd.Prim) -> str:
        """Compute a hash of the geometry's intrinsic data for deduplication.

        Only includes authored attribute values in the hash to ensure proper
        deduplication of geometries with identical authored data.

        Args:
            prim: The geometry prim to hash.

        Returns:
            A hex string hash representing the geometry's intrinsic content.
        """
        hasher = hashlib.sha256()

        # Include type name
        hasher.update(prim.GetTypeName().encode())

        # Get intrinsic properties for this geometry type
        intrinsic_props = self._get_intrinsic_attributes(prim)

        # Hash only authored intrinsic attribute values
        for attr in sorted(prim.GetAttributes(), key=lambda a: a.GetName()):
            attr_name = attr.GetName()
            if self._is_intrinsic_property(attr_name, intrinsic_props) and attr.HasAuthoredValue():
                value = attr.Get()
                if value is not None:
                    hasher.update(attr_name.encode())
                    hasher.update(str(value).encode())

        return hasher.hexdigest()[:_GEOMETRY_HASH_LENGTH]

    def _compute_instance_delta_hash(self, prim: Usd.Prim) -> str:
        """Compute a hash of the instance-specific data (deltas) for deduplication.

        Hashes all non-intrinsic data that differentiates instances:
        - Applied API schemas (CollisionAPI, PhysicsAPI, etc.)
        - Non-intrinsic attributes (physics properties, custom attributes)
        - Relationships (material bindings, etc.)
        - Child prim deltas (GeomSubsets with material bindings)

        Args:
            prim: The geometry prim to compute delta hash for.

        Returns:
            A hex string hash representing the instance's delta content.
        """
        hasher = hashlib.sha256()

        # Get intrinsic properties to exclude
        intrinsic_props = self._get_intrinsic_attributes(prim)

        # Hash applied API schemas
        for schema in sorted(prim.GetAppliedSchemas()):
            hasher.update(schema.encode())

        # Hash non-intrinsic, non-xformOp attributes
        for attr in sorted(prim.GetAttributes(), key=lambda a: a.GetName()):
            attr_name = attr.GetName()
            if self._is_intrinsic_property(attr_name, intrinsic_props):
                continue
            if self._is_xform_property(attr_name):
                continue
            if not attr.HasAuthoredValue() and not attr.GetConnections():
                continue

            hasher.update(attr_name.encode())
            if attr.HasAuthoredValue():
                value = attr.Get()
                if value is not None:
                    hasher.update(str(value).encode())

            connections = attr.GetConnections()
            if connections:
                for conn in sorted(connections, key=lambda p: p.pathString):
                    hasher.update(conn.name.encode())

        # Hash relationships (material bindings, etc.)
        for rel in sorted(prim.GetRelationships(), key=lambda r: r.GetName()):
            rel_name = rel.GetName()
            if rel_name in intrinsic_props:
                continue
            if not rel.HasAuthoredTargets():
                continue

            hasher.update(rel_name.encode())
            for target in sorted(rel.GetTargets(), key=lambda p: p.pathString):
                hasher.update(target.name.encode())

        # Hash children deltas recursively (GeomSubsets, etc.)
        for child in sorted(prim.GetChildren(), key=lambda c: c.GetName()):
            hasher.update(child.GetName().encode())
            hasher.update(child.GetTypeName().encode())
            child_hash = self._compute_instance_delta_hash(child)
            hasher.update(child_hash.encode())

        return hasher.hexdigest()[:_GEOMETRY_HASH_LENGTH]

    def _copy_geometry_to_layer(
        self,
        prim: Usd.Prim,
        entry: GeometryEntry,
        geom_stage: Usd.Stage,
    ) -> None:
        """Copy a geometry prim to the geometries layer under /Geometries/{name}/{name}.

        Uses Sdf.CopySpec to preserve all attribute metadata (interpolation, etc.),
        then removes non-intrinsic attributes that belong in the instances layer.

        Args:
            prim: The source geometry prim.
            entry: The GeometryEntry describing where to store it.
            geom_stage: The geometries stage to copy to.
        """
        src_layer = self.source_stage.GetRootLayer()
        dst_layer = geom_stage.GetRootLayer()

        # Create the Xform wrapper: /Geometries/{name}
        geom_stage.DefinePrim(entry.geom_layer_path, _XFORM_TYPE_NAME)

        # Ensure parent path exists in destination layer
        parent_spec = Sdf.CreatePrimInLayer(dst_layer, entry.geom_layer_path)
        if parent_spec:
            parent_spec.specifier = Sdf.SpecifierDef
            parent_spec.typeName = _XFORM_TYPE_NAME

        # Find the layer that defines the prim (may be in a reference/payload)
        src_prim_path = prim.GetPath()
        copy_src_layer = None
        copy_src_path = None

        # First check root layer
        src_prim_spec = src_layer.GetPrimAtPath(src_prim_path)
        if src_prim_spec:
            copy_src_layer = src_layer
            copy_src_path = src_prim_path
        else:
            # Prim comes from reference/payload - find the defining layer
            prim_stack = prim.GetPrimStack()
            for spec in prim_stack:
                if spec.specifier == Sdf.SpecifierDef:
                    copy_src_layer = spec.layer
                    copy_src_path = spec.path
                    break

        if copy_src_layer and copy_src_path:
            # Copy the entire prim spec (preserves all metadata)
            Sdf.CopySpec(copy_src_layer, copy_src_path, dst_layer, Sdf.Path(entry.geom_prim_path))
        else:
            # Fallback: manually copy attributes from composed prim
            geom_prim = geom_stage.DefinePrim(entry.geom_prim_path, entry.type_name)
            self._copy_prim_attributes_with_metadata(prim, geom_prim, include_all=True)

        # Now remove non-intrinsic properties from the copied spec
        dst_prim_spec = dst_layer.GetPrimAtPath(entry.geom_prim_path)
        if dst_prim_spec:
            intrinsic_props = self._get_intrinsic_attributes(prim)
            props_to_remove = []

            # Remove non-intrinsic properties (custom attrs, applied schema props, bindings)
            for prop in dst_prim_spec.properties:
                if not self._is_intrinsic_property(prop.name, intrinsic_props):
                    props_to_remove.append(prop.name)

            for prop_name in props_to_remove:
                del dst_prim_spec.properties[prop_name]

            # Clear applied API schemas - geometry should only have its typed schema
            if dst_prim_spec.HasInfo("apiSchemas"):
                dst_prim_spec.ClearInfo("apiSchemas")

            # Clear xformOpOrder and all xformOp: attributes - geometry should not have transforms
            xform_props_to_remove = [
                prop.name for prop in dst_prim_spec.properties if self._is_xform_property(prop.name)
            ]
            for prop_name in xform_props_to_remove:
                del dst_prim_spec.properties[prop_name]

            # Clean up schema-level metadata from remaining attributes
            utils.clean_schema_metadata(dst_prim_spec)

            # Process child prims - keep GeomSubsets (with intrinsic props only), remove others
            children_to_remove = []
            for child_spec in dst_prim_spec.nameChildren:
                child_prim = prim.GetChild(child_spec.name)
                if child_prim and child_prim.IsA(UsdGeom.Subset):
                    # GeomSubset - keep it but strip non-intrinsic properties
                    self._clean_geomsubset_spec(child_spec, child_prim)
                else:
                    # Non-GeomSubset child - remove it
                    children_to_remove.append(child_spec.name)

            for child_name in children_to_remove:
                del dst_prim_spec.nameChildren[child_name]

            # Also copy GeomSubsets from composed stage that weren't in the layer spec
            # (e.g., from references or sublayers)
            for child_prim in prim.GetChildren():
                if child_prim.IsA(UsdGeom.Subset):
                    child_name = child_prim.GetName()
                    if child_name not in dst_prim_spec.nameChildren:
                        self._copy_geomsubset_to_layer(child_prim, dst_layer, f"{entry.geom_prim_path}/{child_name}")

            # Clear references/payloads/inherits (geometry should be self-contained)
            utils.clear_composition_arcs(dst_prim_spec)

        self.log_operation(f"Copied geometry {prim.GetPath()} to {entry.geom_prim_path}")

    def _copy_prim_attributes_with_metadata(
        self,
        src_prim: Usd.Prim,
        dst_prim: Usd.Prim,
        include_all: bool = False,
    ) -> None:
        """Copy attributes from source to destination prim, preserving metadata.

        Args:
            src_prim: Source prim to copy attributes from.
            dst_prim: Destination prim to copy attributes to.
            include_all: If True, copy all attributes. If False, only copy intrinsic properties.
        """
        intrinsic_props = self._get_intrinsic_attributes(src_prim)

        for attr in src_prim.GetAttributes():
            if not attr.HasAuthoredValue():
                continue

            attr_name = attr.GetName()
            if not include_all and not self._is_intrinsic_property(attr_name, intrinsic_props):
                continue

            # Create attribute with same type
            dst_attr = dst_prim.CreateAttribute(attr_name, attr.GetTypeName())

            # Copy value
            value = attr.Get()
            if value is not None:
                dst_attr.Set(value)

            # Copy metadata (skip schema metadata that shouldn't be on instances)
            for key in attr.GetAllMetadata():
                if key in utils.SCHEMA_METADATA_TO_REMOVE:
                    continue
                metadata_value = attr.GetMetadata(key)
                if metadata_value is not None:
                    dst_attr.SetMetadata(key, metadata_value)

    def _copy_instance_deltas_from_composed_stage(
        self,
        src_prim: Usd.Prim,
        dst_layer: Sdf.Layer,
        dst_path: str,
    ) -> bool:
        """Copy instance-specific data (deltas) from composed stage to instances layer.

        This method copies all non-intrinsic data from the composed stage:
        - Applied API schemas (CollisionAPI, PhysicsAPI, etc.)
        - Non-intrinsic attributes (physics properties, custom attributes)
        - Relationships (material bindings, etc.)

        Intrinsic geometry properties are NOT copied (those are in geometries layer).

        Args:
            src_prim: The source prim from the composed stage.
            dst_layer: The destination layer (instances layer).
            dst_path: The destination path in the layer.

        Returns:
            True if the copy succeeded, False otherwise.
        """
        if not src_prim.IsValid():
            return False

        # Create the prim spec
        prim_spec = Sdf.CreatePrimInLayer(dst_layer, dst_path)
        if not prim_spec:
            return False

        prim_spec.specifier = Sdf.SpecifierOver

        # Copy applied API schemas - these are instance-specific
        applied_schemas = src_prim.GetAppliedSchemas()
        if applied_schemas:
            prim_spec.SetInfo("apiSchemas", Sdf.TokenListOp.CreateExplicit(list(applied_schemas)))

        # Get intrinsic properties to filter out
        intrinsic_props = self._get_intrinsic_attributes(src_prim)

        # Copy non-intrinsic attributes from composed stage
        for attr in src_prim.GetAttributes():
            attr_name = attr.GetName()

            # Skip intrinsic geometry properties (they're in geometries layer)
            if self._is_intrinsic_property(attr_name, intrinsic_props):
                continue

            # Skip xformOp properties - they will be set by _apply_combined_properties_and_transform
            # for instanceable references with the relative transform
            if self._is_xform_property(attr_name):
                continue

            # Only copy if authored
            if not attr.HasAuthoredValue() and not attr.GetConnections():
                continue

            try:
                attr_spec = Sdf.AttributeSpec(prim_spec, attr_name, attr.GetTypeName())
                if not attr_spec:
                    continue

                # Copy value
                if attr.HasAuthoredValue():
                    value = attr.Get()
                    if value is not None:
                        attr_spec.default = value

                # Copy variability
                if attr.GetVariability() == Sdf.VariabilityUniform:
                    attr_spec.variability = Sdf.VariabilityUniform

                # Copy connections
                connections = attr.GetConnections()
                if connections:
                    for conn in connections:
                        attr_spec.connectionPathList.Prepend(conn)

                # Copy relevant metadata
                for key in attr.GetAllMetadata():
                    if key in ("typeName", "default", "variability", "connectionPaths"):
                        continue
                    if key in utils.SCHEMA_METADATA_TO_REMOVE:
                        continue
                    try:
                        metadata_value = attr.GetMetadata(key)
                        if metadata_value is not None:
                            attr_spec.SetInfo(key, metadata_value)
                    except Exception:
                        pass
            except Exception:
                pass

        # Copy relationships (material bindings, etc.)
        for rel in src_prim.GetRelationships():
            rel_name = rel.GetName()

            # Skip intrinsic relationships (like proxyPrim from Imageable)
            if rel_name in intrinsic_props:
                continue

            if not rel.HasAuthoredTargets():
                continue

            try:
                rel_spec = Sdf.RelationshipSpec(prim_spec, rel_name)
                if rel_spec:
                    for target in rel.GetTargets():
                        rel_spec.targetPathList.Prepend(target)
            except Exception:
                pass

        return True

    def _copy_parent_prim_to_instances(
        self,
        src_prim: Usd.Prim,
        dst_layer: Sdf.Layer,
        dst_path: str,
    ) -> bool:
        """Copy a parent prim's data from composed stage to instances layer.

        This copies all data from the parent prim including:
        - Applied API schemas
        - Attributes (xformOps, physics properties, etc.)
        - Relationships

        This is used when breaking references to preserve the reference prim's
        properties that would otherwise be lost.

        Args:
            src_prim: The source parent prim from the composed stage.
            dst_layer: The destination layer (instances layer).
            dst_path: The destination path in the layer.

        Returns:
            True if the copy succeeded, False otherwise.
        """
        if not src_prim or not src_prim.IsValid():
            # If no source prim, just create an Xform
            prim_spec = utils.create_prim_spec(dst_layer, dst_path, type_name=_XFORM_TYPE_NAME)
            return prim_spec is not None

        # Create or get the prim spec
        prim_spec = dst_layer.GetPrimAtPath(dst_path)
        if not prim_spec:
            prim_spec = Sdf.CreatePrimInLayer(dst_layer, dst_path)
        if not prim_spec:
            return False

        prim_spec.specifier = Sdf.SpecifierDef
        # Always use Xform as type - this prim references the geometry, it's not the geometry itself
        prim_spec.typeName = _XFORM_TYPE_NAME

        # Copy applied API schemas from composed stage
        applied_schemas = src_prim.GetAppliedSchemas()
        if applied_schemas:
            prim_spec.SetInfo("apiSchemas", Sdf.TokenListOp.CreateExplicit(list(applied_schemas)))

        # If source is a geometry prim, get intrinsic properties to skip
        # These properties belong to the geometry type and shouldn't be on the Xform
        intrinsic_props = self._get_intrinsic_attributes(src_prim) if src_prim.IsA(UsdGeom.Gprim) else frozenset()

        # Copy authored attributes, skipping geometry-intrinsic ones
        for attr in src_prim.GetAttributes():
            if not attr.HasAuthoredValue() and not attr.GetConnections():
                continue

            attr_name = attr.GetName()

            # Skip intrinsic geometry properties - they belong on the geometry, not the Xform
            if self._is_intrinsic_property(attr_name, intrinsic_props):
                continue

            # Skip if already exists
            if attr_name in prim_spec.attributes:
                continue

            try:
                attr_spec = Sdf.AttributeSpec(prim_spec, attr_name, attr.GetTypeName())
                if not attr_spec:
                    continue

                if attr.HasAuthoredValue():
                    value = attr.Get()
                    if value is not None:
                        attr_spec.default = value

                if attr.GetVariability() == Sdf.VariabilityUniform:
                    attr_spec.variability = Sdf.VariabilityUniform

                connections = attr.GetConnections()
                if connections:
                    for conn in connections:
                        attr_spec.connectionPathList.Prepend(conn)

                for key in attr.GetAllMetadata():
                    if key in ("typeName", "default", "variability", "connectionPaths"):
                        continue
                    if key in utils.SCHEMA_METADATA_TO_REMOVE:
                        continue
                    try:
                        metadata_value = attr.GetMetadata(key)
                        if metadata_value is not None:
                            attr_spec.SetInfo(key, metadata_value)
                    except Exception:
                        pass
            except Exception:
                pass

        # Copy relationships (but not material bindings or intrinsic relationships)
        for rel in src_prim.GetRelationships():
            rel_name = rel.GetName()

            # Skip material bindings - they're handled by _create_material_references
            if rel_name.startswith("material:binding"):
                continue

            # Skip intrinsic relationships (like proxyPrim from Imageable)
            if rel_name in intrinsic_props:
                continue

            if not rel.HasAuthoredTargets():
                continue

            # Skip if already exists
            if rel_name in prim_spec.relationships:
                continue

            try:
                rel_spec = Sdf.RelationshipSpec(prim_spec, rel_name)
                if rel_spec:
                    for target in rel.GetTargets():
                        rel_spec.targetPathList.Prepend(target)
            except Exception:
                pass

        return True

    def _create_children_overs_from_composed(
        self,
        src_prim: Usd.Prim,
        inst_prim_path: str,
        inst_layer: Sdf.Layer,
    ) -> None:
        """Recursively create children prims from composed stage for instance-specific data.

        For GeomSubsets: Only creates overrides with non-intrinsic properties (like
        material bindings), since their intrinsic data is in the geometries layer.

        For other children: Copies all data as full definitions.

        Args:
            src_prim: The source prim from composed stage whose children to process.
            inst_prim_path: The path in the instances layer.
            inst_layer: The instances layer.
        """
        for src_child in src_prim.GetChildren():
            child_name = src_child.GetName()
            child_inst_path = f"{inst_prim_path}/{child_name}"

            if src_child.IsA(UsdGeom.Subset):
                # GeomSubset - only copy non-intrinsic properties as overrides
                # Intrinsic data (indices, elementType, familyName) is in geometries layer
                self._copy_geomsubset_deltas_to_instances(src_child, inst_layer, child_inst_path)
            else:
                # Non-GeomSubset child - copy all data
                self._copy_child_from_composed_stage(src_child, inst_layer, child_inst_path)

            # Recursively process grandchildren
            self._create_children_overs_from_composed(src_child, child_inst_path, inst_layer)

    def _copy_child_from_composed_stage(
        self,
        src_prim: Usd.Prim,
        dst_layer: Sdf.Layer,
        dst_path: str,
    ) -> bool:
        """Copy a child prim (like GeomSubset) from composed stage to instances layer.

        Copies all data including applied schemas, attributes, and relationships.

        Args:
            src_prim: The source prim from composed stage.
            dst_layer: The destination layer (instances layer).
            dst_path: The destination path in the layer.

        Returns:
            True if the copy succeeded, False otherwise.
        """
        if not src_prim.IsValid():
            return False

        # Create the prim spec
        prim_spec = Sdf.CreatePrimInLayer(dst_layer, dst_path)
        if not prim_spec:
            return False

        prim_spec.specifier = Sdf.SpecifierDef
        prim_spec.typeName = src_prim.GetTypeName()

        # Copy applied API schemas
        applied_schemas = src_prim.GetAppliedSchemas()
        if applied_schemas:
            prim_spec.SetInfo("apiSchemas", Sdf.TokenListOp.CreateExplicit(list(applied_schemas)))

        # Copy all authored attributes
        for attr in src_prim.GetAttributes():
            if not attr.HasAuthoredValue() and not attr.GetConnections():
                continue

            try:
                attr_spec = Sdf.AttributeSpec(prim_spec, attr.GetName(), attr.GetTypeName())
                if not attr_spec:
                    continue

                if attr.HasAuthoredValue():
                    value = attr.Get()
                    if value is not None:
                        attr_spec.default = value

                if attr.GetVariability() == Sdf.VariabilityUniform:
                    attr_spec.variability = Sdf.VariabilityUniform

                connections = attr.GetConnections()
                if connections:
                    for conn in connections:
                        attr_spec.connectionPathList.Prepend(conn)

                for key in attr.GetAllMetadata():
                    if key in ("typeName", "default", "variability", "connectionPaths"):
                        continue
                    if key in utils.SCHEMA_METADATA_TO_REMOVE:
                        continue
                    try:
                        metadata_value = attr.GetMetadata(key)
                        if metadata_value is not None:
                            attr_spec.SetInfo(key, metadata_value)
                    except Exception:
                        pass
            except Exception:
                pass

        # Copy relationships
        for rel in src_prim.GetRelationships():
            if not rel.HasAuthoredTargets():
                continue

            try:
                rel_spec = Sdf.RelationshipSpec(prim_spec, rel.GetName())
                if rel_spec:
                    for target in rel.GetTargets():
                        rel_spec.targetPathList.Prepend(target)
            except Exception:
                pass

        return True

    def _create_deduplicated_instance(
        self,
        instance_entry: InstanceEntry,
        geometries_layer_abs_path: str,
        inst_stage: Usd.Stage,
        template_prim: Usd.Prim,
    ) -> None:
        """Create a deduplicated instance definition in the /Instances scope.

        Creates a single instance definition that can be referenced by multiple
        source prims that share the same geometry and delta configuration.

        Args:
            instance_entry: The InstanceEntry describing the unique instance.
            geometries_layer_abs_path: Absolute path to the geometries layer file.
            inst_stage: The instances stage to create the instance in.
            template_prim: The source prim to copy delta attributes from.
        """
        inst_layer = inst_stage.GetRootLayer()
        geom_entry = instance_entry.geometry_entry

        # Compute relative path from instances layer to geometries layer
        geometries_layer_rel_path = utils.get_relative_layer_path(inst_layer, geometries_layer_abs_path)

        # The instance definition path: /Instances/{name}
        instance_path = instance_entry.instance_layer_path

        # The child mesh path within the instance: /Instances/{name}/{geom_name}
        child_mesh_path = f"{instance_path}/{geom_entry.name}"

        # Ensure parent hierarchy exists for the child mesh path
        self._ensure_prim_hierarchy(inst_stage, child_mesh_path)

        # Copy instance-specific deltas from composed stage
        self._copy_instance_deltas_from_composed_stage(template_prim, inst_layer, child_mesh_path)

        # Create children (GeomSubsets, etc.) that have instance-specific data
        self._create_children_overs_from_composed(template_prim, child_mesh_path, inst_layer)

        # Clear composition arcs on the child prim (it will get geometry from reference)
        child_prim_spec = inst_layer.GetPrimAtPath(child_mesh_path)
        if child_prim_spec:
            utils.clear_composition_arcs(child_prim_spec)

        # Create the parent Xform prim that references the geometry wrapper
        parent_prim_spec = utils.create_prim_spec(inst_layer, instance_path, type_name=_XFORM_TYPE_NAME)
        if parent_prim_spec:
            reference = Sdf.Reference(geometries_layer_rel_path, geom_entry.geom_layer_path)
            parent_prim_spec.referenceList.Prepend(reference)

        # Create VisualMaterials scope with instanceable references to materials
        self._create_material_references(template_prim, child_mesh_path, inst_stage)

    def _create_material_references(
        self,
        src_prim: Usd.Prim,
        prim_path: str,
        inst_stage: Usd.Stage,
    ) -> None:
        """Create a single VisualMaterials scope with instanceable references to bound materials.

        This ensures material bindings properly resolve by creating local references
        to all materials used by this geometry and its children (subgeometries).
        A single VisualMaterials scope is created at the geometry root, and all
        bindings across the hierarchy point to materials in that scope.

        All materials are copied to the source stage's /<defaultPrim>/VisualMaterials
        scope to ensure deduplication, proper shader preservation, and consistent
        organization regardless of their original location.

        Args:
            src_prim: The source prim to get material bindings from.
            prim_path: The path of the prim in the instances layer.
            inst_stage: The instances stage to create material references in.
        """
        inst_layer = inst_stage.GetRootLayer()
        src_layer = self.source_stage.GetRootLayer()

        # Compute relative path from instances layer to source layer for material references
        src_layer_rel_path = utils.get_relative_layer_path(inst_layer, src_layer.identifier)

        # The VisualMaterials scope path at the parent of the geometry (Xform wrapper)
        parent_path = Sdf.Path(prim_path).GetParentPath().pathString
        materials_scope_path = f"{parent_path}/{_VISUAL_MATERIALS_SCOPE_NAME}"

        # Collect all materials from the prim hierarchy
        # Maps original material path -> local material path
        all_materials: Dict[str, str] = {}

        # Collect bindings per prim: maps inst_prim_path -> list of (orig_mat_path, purpose)
        prim_bindings: Dict[str, List[Tuple[str, str]]] = {}

        self._collect_material_bindings_recursive(
            src_prim, prim_path, materials_scope_path, all_materials, prim_bindings
        )

        if not all_materials:
            return

        # Always copy materials to source stage's VisualMaterials scope
        # This ensures deduplication, proper shader preservation, and consistent organization
        copied_material_paths = self._copy_materials_to_visual_materials_scope(all_materials.keys())

        # Create VisualMaterials scope at the geometry root
        utils.create_prim_spec(inst_layer, materials_scope_path, type_name=_SCOPE_TYPE_NAME)

        # Create instanceable reference for each unique material
        for orig_material_path, local_material_path in all_materials.items():
            material_spec = utils.create_prim_spec(
                inst_layer, local_material_path, type_name=_MATERIAL_TYPE_NAME, instanceable=True
            )
            if material_spec:
                # Reference the copied/deduplicated material in source stage's VisualMaterials
                ref_path = copied_material_paths.get(orig_material_path, orig_material_path)
                reference = Sdf.Reference(src_layer_rel_path, ref_path)
                material_spec.referenceList.Prepend(reference)

        # Update material bindings on each prim
        for inst_prim_path, bindings in prim_bindings.items():
            # Ensure the prim spec exists in the instances layer
            prim_spec = inst_layer.GetPrimAtPath(inst_prim_path)
            if not prim_spec:
                prim_spec = utils.create_prim_spec(inst_layer, inst_prim_path, specifier=Sdf.SpecifierOver)
                if not prim_spec:
                    continue

            for orig_material_path, purpose in bindings:
                local_material_path = all_materials[orig_material_path]

                if purpose == "":
                    binding_rel_name = "material:binding"
                else:
                    binding_rel_name = f"material:binding:{purpose}"

                # Get or create the relationship spec
                rel_spec = prim_spec.relationships.get(binding_rel_name)
                if rel_spec is None:
                    rel_spec = Sdf.RelationshipSpec(prim_spec, binding_rel_name)

                # Clear existing targets and set the new local material path
                rel_spec.targetPathList.ClearEdits()
                rel_spec.targetPathList.Prepend(Sdf.Path(local_material_path))

    def _copy_materials_to_visual_materials_scope(
        self,
        material_paths: Iterable[str],
    ) -> Dict[str, str]:
        """Copy all materials to the source stage's VisualMaterials scope.

        This method copies materials (including full shader content) to a central
        /<defaultPrim>/VisualMaterials scope in the source stage. This ensures:
        - Proper deduplication based on shader properties
        - Full shader content is preserved (handles instance proxies)
        - Consistent organization of materials

        Args:
            material_paths: Iterable of original material paths to copy.

        Returns:
            Dictionary mapping original material path -> copied material path in source.
        """
        src_layer = self.source_stage.GetRootLayer()
        default_prim = self.source_stage.GetDefaultPrim()

        if default_prim and default_prim.IsValid():
            default_prim_path = default_prim.GetPath().pathString
        else:
            default_prim_path = _DEFAULT_ROOT_PRIM_PATH

        visual_materials_scope = f"{default_prim_path}/{_VISUAL_MATERIALS_SCOPE_NAME}"
        copied_paths: Dict[str, str] = {}

        # Ensure VisualMaterials scope exists in source stage
        if not src_layer.GetPrimAtPath(visual_materials_scope):
            utils.create_prim_spec(src_layer, visual_materials_scope, type_name=_SCOPE_TYPE_NAME)

        # Build hash -> path map for existing materials in VisualMaterials scope
        existing_materials_by_hash: Dict[str, str] = {}
        scope_prim = self.source_stage.GetPrimAtPath(visual_materials_scope)
        if scope_prim and scope_prim.IsValid():
            for child in scope_prim.GetChildren():
                if child.IsA(UsdShade.Material):
                    mat_hash = self._compute_material_hash(child)
                    existing_materials_by_hash[mat_hash] = child.GetPath().pathString

        # Track hashes for materials being copied in this batch
        batch_materials_by_hash: Dict[str, str] = {}
        copied_count = 0
        reused_count = 0

        for orig_material_path in material_paths:
            # Get the material prim from the composed stage
            material_prim = self.source_stage.GetPrimAtPath(orig_material_path)
            if not material_prim.IsValid():
                continue

            # Check if this material is already in the VisualMaterials scope
            if orig_material_path.startswith(visual_materials_scope):
                copied_paths[orig_material_path] = orig_material_path
                continue

            # Compute hash for deduplication
            mat_hash = self._compute_material_hash(material_prim)

            # Check if identical material already exists in VisualMaterials scope
            if mat_hash in existing_materials_by_hash:
                copied_paths[orig_material_path] = existing_materials_by_hash[mat_hash]
                self._relocated_material_sources.add(orig_material_path)
                reused_count += 1
                continue

            if mat_hash in batch_materials_by_hash:
                copied_paths[orig_material_path] = batch_materials_by_hash[mat_hash]
                self._relocated_material_sources.add(orig_material_path)
                reused_count += 1
                continue

            # Material needs to be copied to VisualMaterials scope
            material_name = Sdf.Path(orig_material_path).name
            copied_material_path = f"{visual_materials_scope}/{material_name}"

            # Handle name collisions
            counter = 1
            base_copied_path = copied_material_path
            while src_layer.GetPrimAtPath(copied_material_path):
                copied_material_path = f"{base_copied_path}_{counter}"
                counter += 1

            # Always use composed stage copy to ensure shader children are captured
            # This handles instance proxies and materials from references properly
            copy_succeeded = utils.copy_prim_from_composed_stage(
                material_prim,
                src_layer,
                copied_material_path,
                remap_connections_from=orig_material_path,
                remap_connections_to=copied_material_path,
            )

            if not copy_succeeded:
                # Fallback: try Sdf.CopySpec if composed stage copy fails
                is_instance_proxy = material_prim.IsInstanceProxy()
                if not is_instance_proxy:
                    prim_stack = material_prim.GetPrimStack()
                    for prim_spec in prim_stack:
                        if prim_spec.specifier == Sdf.SpecifierDef:
                            src_material_layer = prim_spec.layer
                            src_material_path = prim_spec.path
                            Sdf.CopySpec(
                                src_material_layer, src_material_path, src_layer, Sdf.Path(copied_material_path)
                            )
                            copy_succeeded = True
                            break

            if not copy_succeeded:
                self.log_operation(f"Failed to copy material {orig_material_path}")
                continue

            # Clear instanceable flags recursively to ensure shader children are accessible
            copied_spec = src_layer.GetPrimAtPath(copied_material_path)
            if copied_spec:
                utils.clear_instanceable_recursive(copied_spec)

            copied_paths[orig_material_path] = copied_material_path
            batch_materials_by_hash[mat_hash] = copied_material_path
            existing_materials_by_hash[mat_hash] = copied_material_path
            self._relocated_material_sources.add(orig_material_path)
            copied_count += 1

        if copied_count > 0 or reused_count > 0:
            self.log_operation(
                f"Materials: {copied_count} copied, {reused_count} deduplicated to {visual_materials_scope}"
            )

        return copied_paths

    def _compute_material_hash(self, material_prim: Usd.Prim) -> str:
        """Compute a hash for a material based on its shader properties.

        The hash includes shader types, input values, and connections to enable
        deduplication of identical materials.

        Args:
            material_prim: The material prim to hash.

        Returns:
            SHA256 hash string representing the material's properties.
        """
        hasher = hashlib.sha256()

        def hash_prim_recursive(prim: Usd.Prim, depth: int = 0) -> None:
            # Hash prim type
            hasher.update(prim.GetTypeName().encode())

            # Hash all attributes (sorted for consistency)
            attrs = sorted(prim.GetAttributes(), key=lambda a: a.GetName())
            for attr in attrs:
                if not attr.HasAuthoredValue():
                    continue
                attr_name = attr.GetName()
                hasher.update(attr_name.encode())

                # Hash the value
                value = attr.Get()
                if value is not None:
                    hasher.update(str(value).encode())

                # Hash connections if any
                connections = attr.GetConnections()
                if connections:
                    for conn in sorted(connections, key=lambda p: p.pathString):
                        # Use relative path from material root for connections
                        hasher.update(conn.pathString.encode())

            # Hash relationships (sorted)
            rels = sorted(prim.GetRelationships(), key=lambda r: r.GetName())
            for rel in rels:
                if not rel.HasAuthoredTargets():
                    continue
                rel_name = rel.GetName()
                hasher.update(rel_name.encode())
                for target in sorted(rel.GetTargets(), key=lambda p: p.pathString):
                    hasher.update(target.pathString.encode())

            # Recursively hash children (shaders, etc.) - use GetFilteredChildren to traverse instance proxies
            for child in sorted(prim.GetChildren(), key=lambda c: c.GetName()):
                hasher.update(child.GetName().encode())
                hash_prim_recursive(child, depth + 1)

        hash_prim_recursive(material_prim)
        return hasher.hexdigest()

    def _collect_material_bindings_recursive(
        self,
        src_prim: Usd.Prim,
        inst_prim_path: str,
        materials_scope_path: str,
        all_materials: Dict[str, str],
        prim_bindings: Dict[str, List[Tuple[str, str]]],
    ) -> None:
        """Recursively collect material bindings from a prim and its children.

        Args:
            src_prim: The source prim to process.
            inst_prim_path: The corresponding path in the instances layer.
            materials_scope_path: The path to the VisualMaterials scope.
            all_materials: Dictionary to populate with orig_path -> local_path mappings.
            prim_bindings: Dictionary to populate with inst_prim_path -> bindings list.
        """
        bindings_list: List[Tuple[str, str]] = []

        # Don't check HasAPI - MaterialBindingAPI can work without explicit application
        # (e.g., GeomSubsets with material:binding relationships but no apiSchemas declaration).
        # Just create the binding API and query for bindings directly.
        binding_api = UsdShade.MaterialBindingAPI(src_prim)
        for purpose in _MATERIAL_PURPOSES:
            if purpose == "":
                binding = binding_api.GetDirectBinding()
            else:
                binding = binding_api.GetDirectBinding(materialPurpose=purpose)
            mat_path = binding.GetMaterialPath()
            if mat_path:
                orig_path = mat_path.pathString
                if orig_path not in all_materials:
                    material_name = Sdf.Path(orig_path).name
                    all_materials[orig_path] = f"{materials_scope_path}/{material_name}"
                bindings_list.append((orig_path, purpose))

        if bindings_list:
            prim_bindings[inst_prim_path] = bindings_list

        # Recursively process children
        for child in src_prim.GetChildren():
            child_name = child.GetName()
            child_inst_path = f"{inst_prim_path}/{child_name}"
            self._collect_material_bindings_recursive(
                child, child_inst_path, materials_scope_path, all_materials, prim_bindings
            )

    def _update_source_stage_references(
        self,
        instance_by_key: Dict[Tuple[str, str], InstanceEntry],
        instance_layer_abs_path: str,
        instance_remap: Optional[Dict[str, str]] = None,
    ) -> None:
        """Update the source stage to reference the deduplicated instances layer.

        For each geometry prim in the source stage, replaces it with an instanceable
        reference to the corresponding deduplicated instance in the instances layer.
        Multiple source prims with identical geometry and deltas will reference the
        same deduplicated instance definition.

        Args:
            instance_by_key: Dictionary mapping (geometry_hash, delta_hash) tuples to
                InstanceEntry objects containing deduplicated instance definitions.
            instance_layer_abs_path: Absolute path to the instances layer file.
            instance_remap: Optional dictionary mapping deleted instance paths to their
                replacement (kept) instance paths from deduplication.
        """
        if instance_remap is None:
            instance_remap = {}
        source_layer = self.source_stage.GetRootLayer()
        updated_count = 0

        # Open instances layer
        instances_layer = Sdf.Layer.FindOrOpen(instance_layer_abs_path)
        if not instances_layer:
            self.log_operation(f"Failed to open instances layer: {instance_layer_abs_path}")
            return

        # Compute relative path from source layer to instance layer
        instance_layer_rel_path = utils.get_relative_layer_path(source_layer, instance_layer_abs_path)

        self.log_operation(f"Reference path: {source_layer.identifier} -> {instance_layer_rel_path}")

        # Track processed paths to avoid duplicates
        processed_paths: Set[str] = set()

        for instance_key, instance_entry in instance_by_key.items():
            # The deduplicated instance path in the instances layer
            # Apply remap if this instance was deduplicated away
            dedup_instance_path = instance_entry.instance_layer_path
            if dedup_instance_path in instance_remap:
                dedup_instance_path = instance_remap[dedup_instance_path]

            for source in instance_entry.sources:
                update_path = source.prim_path

                # Skip if already processed
                if update_path in processed_paths:
                    continue
                processed_paths.add(update_path)

                # Check if we should merge this prim with its parent
                should_merge = self._should_merge_with_parent(update_path)

                if self._verbose:
                    self.log_operation(
                        f"Processing source reference update:\n"
                        f"  Prim path: {update_path}\n"
                        f"  Should merge with parent: {should_merge}"
                    )

                if should_merge:
                    # Merge child into parent: apply reference to parent with combined transform
                    parent_path = Sdf.Path(update_path).GetParentPath().pathString
                    child_name = Sdf.Path(update_path).name

                    if self._verbose:
                        self.log_operation(f"  MERGE MODE: Merging {child_name} into parent {parent_path}")

                    # Add parent path to processed paths to avoid reprocessing
                    processed_paths.add(parent_path)

                    # Ensure parent hierarchy exists for the parent's parent
                    self._ensure_source_prim_hierarchy(source_layer, parent_path)

                    parent_prim_spec = source_layer.GetPrimAtPath(parent_path)
                    if not parent_prim_spec:
                        parent_prim_spec = Sdf.CreatePrimInLayer(source_layer, parent_path)
                        if not parent_prim_spec:
                            self.log_operation(f"Failed to create parent prim spec for {parent_path}")
                            continue

                    # Compute combined parent + child transform before clearing
                    combined_transform = self._get_combined_parent_child_transform(update_path)

                    # Clear existing composition arcs on parent
                    utils.clear_composition_arcs(parent_prim_spec, make_explicit=True)

                    # Set type and clear properties on parent
                    parent_prim_spec.typeName = _XFORM_TYPE_NAME

                    props_to_remove = [prop.name for prop in parent_prim_spec.properties]
                    for prop_name in props_to_remove:
                        del parent_prim_spec.properties[prop_name]

                    # Clear applied API schemas on parent
                    if parent_prim_spec.HasInfo("apiSchemas"):
                        parent_prim_spec.ClearInfo("apiSchemas")

                    # Apply combined transform to parent
                    if combined_transform:
                        translate, orient, scale = combined_transform
                        if self._verbose:
                            self.log_operation(
                                f"  Applying combined transform to {parent_path}:\n"
                                f"    translate: ({translate[0]:.6f}, {translate[1]:.6f}, {translate[2]:.6f})\n"
                                f"    orient: ({orient.GetReal():.6f}, {orient.GetImaginary()[0]:.6f}, "
                                f"{orient.GetImaginary()[1]:.6f}, {orient.GetImaginary()[2]:.6f}) "
                                f"[{self._format_quat_as_euler(orient)}]\n"
                                f"    scale: ({scale[0]:.6f}, {scale[1]:.6f}, {scale[2]:.6f})"
                            )
                        self._apply_transform_to_prim_spec(parent_prim_spec, translate, orient, scale)

                    # Remove the child prim from parent
                    if child_name in parent_prim_spec.nameChildren:
                        del parent_prim_spec.nameChildren[child_name]

                    # Add reference to the deduplicated instance on the parent
                    reference = Sdf.Reference(instance_layer_rel_path, dedup_instance_path)
                    parent_prim_spec.referenceList.Prepend(reference)

                    # Set parent as instanceable
                    parent_prim_spec.instanceable = True

                    updated_count += 1
                else:
                    # Standard case: apply reference to the prim itself
                    self._ensure_source_prim_hierarchy(source_layer, update_path)

                    prim_spec = source_layer.GetPrimAtPath(update_path)

                    if not prim_spec:
                        # Prim spec doesn't exist in root layer, create an over
                        prim_spec = Sdf.CreatePrimInLayer(source_layer, update_path)
                        if not prim_spec:
                            self.log_operation(f"Failed to create prim spec for {update_path}")
                            continue

                    # Clear existing composition arcs (make explicit to override sublayers)
                    utils.clear_composition_arcs(prim_spec, make_explicit=True)

                    # Set type and clear properties (properties are now in the instances layer)
                    prim_spec.typeName = _XFORM_TYPE_NAME

                    # Capture the mesh's local transform before clearing properties
                    mesh_transform = self._get_mesh_local_transform_decomposed(source.prim_path)

                    props_to_remove = [prop.name for prop in prim_spec.properties]
                    for prop_name in props_to_remove:
                        del prim_spec.properties[prop_name]

                    # Clear applied API schemas - they belong on the child mesh in instances layer
                    if prim_spec.HasInfo("apiSchemas"):
                        prim_spec.ClearInfo("apiSchemas")

                    # Apply the mesh's local transform to the source prim (the Xform wrapper)
                    if mesh_transform:
                        translate, orient, scale = mesh_transform
                        if self._verbose:
                            self.log_operation(
                                f"  STANDARD MODE: Applying mesh local transform to {update_path}:\n"
                                f"    translate: ({translate[0]:.6f}, {translate[1]:.6f}, {translate[2]:.6f})\n"
                                f"    orient: ({orient.GetReal():.6f}, {orient.GetImaginary()[0]:.6f}, "
                                f"{orient.GetImaginary()[1]:.6f}, {orient.GetImaginary()[2]:.6f}) "
                                f"[{self._format_quat_as_euler(orient)}]\n"
                                f"    scale: ({scale[0]:.6f}, {scale[1]:.6f}, {scale[2]:.6f})"
                            )
                        self._apply_transform_to_prim_spec(prim_spec, translate, orient, scale)

                    # Clear child prims (geometry children are now in the referenced layer)
                    children_to_remove = [child.name for child in prim_spec.nameChildren]
                    for child_name in children_to_remove:
                        del prim_spec.nameChildren[child_name]

                    # Add reference to the deduplicated instance in the instances layer
                    reference = Sdf.Reference(instance_layer_rel_path, dedup_instance_path)
                    prim_spec.referenceList.Prepend(reference)

                    # Set as instanceable
                    prim_spec.instanceable = True

                    updated_count += 1

        # Remove "doc" metadata from all properties before final export
        self._remove_doc_metadata_from_layer(instances_layer)

        # Export the instances layer with the parent properties
        instances_layer.Export(instance_layer_abs_path)

        self.log_operation(f"Updated {updated_count} prims in source stage with instanceable references")

    def _cleanup_flattened_prototypes(self) -> None:
        """Clean up flattened prototypes created during de-instancing.

        USD creates Flattened_Prototypes prims when de-instancing. This method:
        1. Removes references to Flattened_Prototypes from all prims
        2. Deletes the Flattened_Prototypes prims themselves
        """
        source_layer = self.source_stage.GetRootLayer()

        # Find Flattened_Prototypes directly from root layer's pseudoRoot children
        # These are override specs at the root level, not composed prims
        prototype_names = []
        if source_layer.pseudoRoot:
            for child_spec in source_layer.pseudoRoot.nameChildren:
                if _FLATTENED_PROTOTYPE_IDENTIFIER in child_spec.name:
                    prototype_names.append(child_spec.name)

        if not prototype_names:
            return

        removed_refs = 0

        def has_prototype_path(item) -> bool:
            """Check if an item references a Flattened_Prototype."""
            # References and payloads have primPath attribute
            if hasattr(item, "primPath") and item.primPath:
                return _FLATTENED_PROTOTYPE_IDENTIFIER in item.primPath.pathString
            # Inherits and specializes are SdfPath directly
            if hasattr(item, "pathString"):
                return _FLATTENED_PROTOTYPE_IDENTIFIER in item.pathString
            return False

        def clean_list_op(list_op) -> int:
            """Remove prototype references from all sublists of a ListOp."""
            count = 0
            # All ListOp sublist accessors
            sublist_names = [
                "prependedItems",
                "appendedItems",
                "addedItems",
                "explicitItems",
                "orderedItems",
                "deletedItems",
            ]
            for sublist_name in sublist_names:
                sublist = getattr(list_op, sublist_name, None)
                if sublist is None:
                    continue
                items_to_remove = [item for item in sublist if has_prototype_path(item)]
                for item in items_to_remove:
                    sublist.remove(item)
                    count += 1
            return count

        def remove_prototype_refs(prim_spec):
            nonlocal removed_refs
            if prim_spec is None:
                return

            # Clean all composition arc lists
            removed_refs += clean_list_op(prim_spec.referenceList)
            removed_refs += clean_list_op(prim_spec.payloadList)
            removed_refs += clean_list_op(prim_spec.inheritPathList)
            removed_refs += clean_list_op(prim_spec.specializesList)

            # Recurse into children
            for child_spec in prim_spec.nameChildren:
                remove_prototype_refs(child_spec)

        # Start from root
        if source_layer.pseudoRoot:
            for child_spec in source_layer.pseudoRoot.nameChildren:
                remove_prototype_refs(child_spec)

        # Delete the Flattened_Prototypes prims directly from pseudoRoot
        for proto_name in prototype_names:
            if proto_name in source_layer.pseudoRoot.nameChildren:
                del source_layer.pseudoRoot.nameChildren[proto_name]

        self.log_operation(
            f"Cleaned up flattened prototypes: removed {removed_refs} references, "
            f"deleted {len(prototype_names)} prototype prims"
        )

    def _delete_relocated_material_sources(self) -> None:
        """Delete original material prims that were relocated to VisualMaterials scope.

        After all geometries are processed and materials have been copied to the
        central VisualMaterials scope, this method removes the original material
        definitions from the source layer to avoid duplication.

        Only deletes materials that:
        - Were tracked during relocation (in _relocated_material_sources)
        - Have a prim spec in the source layer (not from references/sublayers)
        - Are not inside the VisualMaterials scope (already relocated)
        """
        if not hasattr(self, "_relocated_material_sources") or not self._relocated_material_sources:
            return

        source_layer = self.source_stage.GetRootLayer()
        default_prim = self.source_stage.GetDefaultPrim()

        if default_prim and default_prim.IsValid():
            default_prim_path = default_prim.GetPath().pathString
        else:
            default_prim_path = _DEFAULT_ROOT_PRIM_PATH

        visual_materials_scope = f"{default_prim_path}/{_VISUAL_MATERIALS_SCOPE_NAME}"

        deleted_count = 0
        skipped_count = 0

        for material_path in self._relocated_material_sources:
            # Skip materials already in VisualMaterials scope
            if material_path.startswith(visual_materials_scope):
                continue

            # Only delete if the prim spec exists in the source layer
            # (not from references or sublayers)
            prim_spec = source_layer.GetPrimAtPath(material_path)
            if not prim_spec:
                skipped_count += 1
                continue

            # Delete the material prim spec
            parent_path = Sdf.Path(material_path).GetParentPath()
            parent_spec = source_layer.GetPrimAtPath(parent_path)
            if parent_spec and prim_spec.name in parent_spec.nameChildren:
                del parent_spec.nameChildren[prim_spec.name]
                deleted_count += 1

        if deleted_count > 0 or skipped_count > 0:
            self.log_operation(
                f"Deleted {deleted_count} relocated material sources, "
                f"skipped {skipped_count} (from references/sublayers)"
            )

        # Clear the tracking set
        self._relocated_material_sources.clear()

    def _update_instances_layer_source_references(
        self,
        instances_layer: Sdf.Layer,
        old_source_path: str,
        new_source_path: str,
    ) -> None:
        """Update references in the instances layer when source file path changes.

        When save_base_as_usda converts the source file from .usd to .usda,
        all references in the instances layer that point to the old source file
        need to be updated to point to the new file.

        Args:
            instances_layer: The instances layer to update.
            old_source_path: The original source file path.
            new_source_path: The new source file path after conversion.
        """
        # Compute old and new relative paths from instances layer perspective
        old_rel_path = utils.get_relative_layer_path(instances_layer, old_source_path)
        new_rel_path = utils.get_relative_layer_path(instances_layer, new_source_path)

        if old_rel_path == new_rel_path:
            return

        updated_count = 0

        # Traverse all prims in the layer
        prim_paths: List[Sdf.Path] = []
        instances_layer.Traverse(Sdf.Path.absoluteRootPath, lambda path: prim_paths.append(path))

        for prim_path in prim_paths:
            prim_spec = instances_layer.GetPrimAtPath(prim_path)
            if not prim_spec:
                continue

            # Get current prepended references
            old_prepended = list(prim_spec.referenceList.prependedItems)
            if not old_prepended:
                continue

            # Build new list with updated paths
            new_prepended = []
            changed = False
            for ref in old_prepended:
                if ref.assetPath == old_rel_path:
                    new_prepended.append(Sdf.Reference(new_rel_path, ref.primPath, ref.layerOffset, ref.customData))
                    changed = True
                    updated_count += 1
                else:
                    new_prepended.append(ref)

            if changed:
                # Clear and re-populate (reverse order since Prepend adds to front)
                prim_spec.referenceList.ClearEdits()
                for ref in reversed(new_prepended):
                    prim_spec.referenceList.Prepend(ref)

        if updated_count > 0:
            self.log_operation(
                f"Updated {updated_count} references in instances layer: {old_rel_path} -> {new_rel_path}"
            )

    def _finalize_instances_layer(self, instances_layer: Sdf.Layer) -> None:
        """Finalize the instances layer by normalizing and cleaning up xformOps.

        Performs a final pass on the instances layer:
        1. Normalizes negligible xformOp values to their identity values.
        2. Clears xformOps and xformOpOrder if they resolve to identity transform.
        3. Clears xformOpOrder if it exists but references no actual ops.

        Args:
            instances_layer: The instances layer to finalize.
        """
        # Collect all prim paths using Traverse callback
        prim_paths: List[Sdf.Path] = []
        instances_layer.Traverse(Sdf.Path.absoluteRootPath, lambda path: prim_paths.append(path))

        normalized_count = 0
        cleared_count = 0

        for prim_path in prim_paths:
            if prim_path == Sdf.Path.absoluteRootPath:
                continue

            prim_spec = instances_layer.GetPrimAtPath(prim_path)
            if not prim_spec:
                continue

            # Check for xformOps on this prim
            xform_op_names = [
                attr_name for attr_name in prim_spec.attributes.keys() if attr_name.startswith("xformOp:")
            ]
            has_xform_op_order = "xformOpOrder" in prim_spec.attributes

            # If xformOpOrder exists but no ops, clear xformOpOrder
            if has_xform_op_order and not xform_op_names:
                prim_spec.RemoveProperty(prim_spec.attributes["xformOpOrder"])
                cleared_count += 1
                continue

            # If no xformOps, nothing to do
            if not xform_op_names:
                continue

            # Normalize xformOp values and check if they resolve to identity
            is_identity = self._normalize_xform_ops(prim_spec, xform_op_names)

            if is_identity:
                # Clear all xformOps and xformOpOrder
                for attr_name in xform_op_names:
                    if attr_name in prim_spec.attributes:
                        prim_spec.RemoveProperty(prim_spec.attributes[attr_name])
                if has_xform_op_order:
                    prim_spec.RemoveProperty(prim_spec.attributes["xformOpOrder"])
                cleared_count += 1
            else:
                normalized_count += 1

        if normalized_count > 0 or cleared_count > 0:
            self.log_operation(
                f"Finalized instances layer: normalized {normalized_count} xform prims, "
                f"cleared {cleared_count} identity/empty xforms"
            )

    def _normalize_xform_ops(self, prim_spec: Sdf.PrimSpec, xform_op_names: List[str]) -> bool:
        """Normalize xformOp values and check if they resolve to identity.

        Normalizes negligible floating-point deviations to their identity values:
        - translate: values near 0 become exactly 0
        - scale: values near 1 become exactly 1
        - orient/rotate: quaternions/angles near identity become identity

        Args:
            prim_spec: The prim spec containing xformOps.
            xform_op_names: List of xformOp attribute names on the prim.

        Returns:
            True if all xformOps resolve to identity after normalization.
        """
        tolerance = 10 ** (-_TRANSFORM_HASH_PRECISION)
        all_identity = True

        for attr_name in xform_op_names:
            attr_spec = prim_spec.attributes.get(attr_name)
            if not attr_spec or not attr_spec.HasInfo("default"):
                continue

            value = attr_spec.default
            if value is None:
                continue

            normalized_value, is_identity = self._normalize_xform_value(attr_name, value, tolerance)

            # Update the attribute with normalized value
            if normalized_value is not None:
                attr_spec.default = normalized_value

            if not is_identity:
                all_identity = False

        return all_identity

    def _normalize_xform_value(self, attr_name: str, value, tolerance: float) -> Tuple[any, bool]:
        """Normalize a single xformOp value and check if it's identity.

        Args:
            attr_name: The xformOp attribute name (e.g., "xformOp:translate").
            value: The current attribute value.
            tolerance: Tolerance for floating-point comparison.

        Returns:
            Tuple of (normalized_value, is_identity).
        """
        # Determine the op type from the attribute name
        # Format: xformOp:<opType> or xformOp:<opType>:<suffix>
        parts = attr_name.split(":")
        if len(parts) < 2:
            return value, True

        op_type = parts[1]

        # Handle translate ops (identity is (0, 0, 0))
        if op_type == "translate":
            if isinstance(value, (Gf.Vec3d, Gf.Vec3f)):
                normalized = type(value)(
                    0.0 if abs(value[0]) < tolerance else value[0],
                    0.0 if abs(value[1]) < tolerance else value[1],
                    0.0 if abs(value[2]) < tolerance else value[2],
                )
                is_identity = all(abs(normalized[i]) < tolerance for i in range(3))
                return normalized, is_identity

        # Handle scale ops (identity is (1, 1, 1))
        elif op_type == "scale":
            if isinstance(value, (Gf.Vec3d, Gf.Vec3f)):
                normalized = type(value)(
                    1.0 if abs(value[0] - 1.0) < tolerance else value[0],
                    1.0 if abs(value[1] - 1.0) < tolerance else value[1],
                    1.0 if abs(value[2] - 1.0) < tolerance else value[2],
                )
                is_identity = all(abs(normalized[i] - 1.0) < tolerance for i in range(3))
                return normalized, is_identity

        # Handle orient ops (identity quaternion is (1, 0, 0, 0) - real=1, imaginary=0)
        elif op_type == "orient":
            if isinstance(value, (Gf.Quatd, Gf.Quatf)):
                real = value.GetReal()
                imag = value.GetImaginary()

                # Normalize near-identity quaternions
                norm_real = 1.0 if abs(real - 1.0) < tolerance else (-1.0 if abs(real + 1.0) < tolerance else real)
                norm_imag = type(imag)(
                    0.0 if abs(imag[0]) < tolerance else imag[0],
                    0.0 if abs(imag[1]) < tolerance else imag[1],
                    0.0 if abs(imag[2]) < tolerance else imag[2],
                )

                normalized = type(value)(norm_real, norm_imag)

                # Identity quaternion: real ≈ ±1, imaginary ≈ (0, 0, 0)
                is_identity = (abs(norm_real - 1.0) < tolerance or abs(norm_real + 1.0) < tolerance) and all(
                    abs(norm_imag[i]) < tolerance for i in range(3)
                )
                return normalized, is_identity

        # Handle rotateXYZ, rotateZYX, etc. (identity is (0, 0, 0))
        elif op_type.startswith("rotate"):
            if isinstance(value, (Gf.Vec3d, Gf.Vec3f)):
                normalized = type(value)(
                    0.0 if abs(value[0]) < tolerance else value[0],
                    0.0 if abs(value[1]) < tolerance else value[1],
                    0.0 if abs(value[2]) < tolerance else value[2],
                )
                is_identity = all(abs(normalized[i]) < tolerance for i in range(3))
                return normalized, is_identity
            elif isinstance(value, float):
                normalized = 0.0 if abs(value) < tolerance else value
                return normalized, abs(normalized) < tolerance

        # Handle transform matrix (identity is Gf.Matrix4d(1.0))
        elif op_type == "transform":
            if isinstance(value, (Gf.Matrix4d, Gf.Matrix4f)):
                identity = type(value)(1.0)
                is_identity = True
                for row in range(4):
                    for col in range(4):
                        if abs(value[row, col] - identity[row, col]) > tolerance:
                            is_identity = False
                            break
                    if not is_identity:
                        break
                # For matrices, we don't normalize individual elements - just check identity
                return value, is_identity

        # Unknown op type - don't modify, assume not identity
        return value, False

    def _deduplicate_instances_layer(
        self,
        instances_layer: Sdf.Layer,
        instance_by_key: Dict[Tuple[str, str], InstanceEntry],
    ) -> Dict[str, str]:
        """Deduplicate instances in the instances layer based on content hash.

        Computes a content hash for each instance using relative paths for material
        bindings. Instances with identical content are deduplicated: the first instance
        is kept and all others are deleted, with their source references remapped.

        Args:
            instances_layer: The instances layer containing instance definitions.
            instance_by_key: Dictionary mapping (geometry_hash, delta_hash) to InstanceEntry.

        Returns:
            Dictionary mapping deleted instance paths to their replacement (kept) instance paths.
        """
        # Collect all instance root prims in /Instances scope
        instances_scope_spec = instances_layer.GetPrimAtPath(_INSTANCES_SCOPE_PATH)
        if not instances_scope_spec:
            return {}

        # Compute content hash for each instance and group by hash
        hash_to_instances: Dict[str, List[str]] = defaultdict(list)

        for child_spec in instances_scope_spec.nameChildren:
            instance_path = child_spec.path.pathString
            content_hash = self._compute_instance_content_hash(instances_layer, instance_path)
            hash_to_instances[content_hash].append(instance_path)

        # Build remap dictionary: maps deleted instance paths to kept instance paths
        instance_remap: Dict[str, str] = {}
        instances_to_delete: List[str] = []

        for content_hash, instance_paths in hash_to_instances.items():
            if len(instance_paths) <= 1:
                continue

            # Keep the first instance, remap all others to it
            kept_instance = instance_paths[0]
            for duplicate_path in instance_paths[1:]:
                instance_remap[duplicate_path] = kept_instance
                instances_to_delete.append(duplicate_path)

        if not instances_to_delete:
            return {}

        # Delete duplicate instances from the layer
        for instance_path in instances_to_delete:
            instance_name = Sdf.Path(instance_path).name
            if instance_name in instances_scope_spec.nameChildren:
                del instances_scope_spec.nameChildren[instance_name]

        self.log_operation(
            f"Deduplicated instances: removed {len(instances_to_delete)} duplicates, "
            f"kept {len(hash_to_instances)} unique instances"
        )

        return instance_remap

    def _compute_instance_content_hash(self, layer: Sdf.Layer, instance_path: str) -> str:
        """Compute a content hash for an instance using relative paths for material bindings.

        Recursively hashes the entire instance subtree including:
        - Prim types and specifiers
        - Attributes and their values
        - Relationships with targets converted to relative paths
        - References (asset path and prim path)
        - Child prims

        Args:
            layer: The layer containing the instance.
            instance_path: The path to the instance root prim.

        Returns:
            SHA256 hash string representing the instance's content.
        """
        hasher = hashlib.sha256()
        instance_sdf_path = Sdf.Path(instance_path)
        precision = _TRANSFORM_HASH_PRECISION

        def quantize_value_for_hash(value) -> str:
            """Quantize numeric values for consistent hashing across floating-point precision."""
            if isinstance(value, (Gf.Vec3d, Gf.Vec3f)):
                return f"({round(value[0], precision)},{round(value[1], precision)},{round(value[2], precision)})"
            elif isinstance(value, (Gf.Quatd, Gf.Quatf)):
                real = round(value.GetReal(), precision)
                imag = value.GetImaginary()
                return f"({real},{round(imag[0], precision)},{round(imag[1], precision)},{round(imag[2], precision)})"
            elif isinstance(value, (Gf.Matrix4d, Gf.Matrix4f)):
                # Quantize each element of the matrix
                elements = []
                for row in range(4):
                    for col in range(4):
                        elements.append(round(value[row, col], precision))
                return str(elements)
            elif isinstance(value, float):
                return str(round(value, precision))
            else:
                return str(value)

        def hash_prim_recursive(prim_spec: Sdf.PrimSpec, depth: int = 0) -> None:
            if not prim_spec:
                return

            prim_path = prim_spec.path

            # Hash prim metadata
            hasher.update(prim_spec.typeName.encode())
            hasher.update(str(prim_spec.specifier).encode())

            # Hash references (use relative asset path, keep prim path as-is)
            refs = list(prim_spec.referenceList.GetAddedOrExplicitItems())
            refs.extend(prim_spec.referenceList.prependedItems)
            for ref in sorted(refs, key=lambda r: (r.assetPath, r.primPath.pathString if r.primPath else "")):
                hasher.update(ref.assetPath.encode())
                if ref.primPath:
                    hasher.update(ref.primPath.pathString.encode())

            # Hash applied API schemas
            if prim_spec.HasInfo("apiSchemas"):
                schemas = prim_spec.GetInfo("apiSchemas")
                for schema in sorted(schemas.GetAddedOrExplicitItems()):
                    hasher.update(schema.encode())

            # Hash attributes (sorted by name)
            for attr_name in sorted(prim_spec.attributes.keys()):
                attr_spec = prim_spec.attributes[attr_name]
                hasher.update(attr_name.encode())

                # Hash attribute value with quantization for xformOp attributes
                if attr_spec.HasInfo("default"):
                    value = attr_spec.default
                    if value is not None:
                        # Quantize xformOp values to avoid floating-point precision mismatches
                        if attr_name.startswith("xformOp:"):
                            value_str = quantize_value_for_hash(value)
                        else:
                            value_str = str(value)
                        hasher.update(value_str.encode())

                # Hash variability
                hasher.update(str(attr_spec.variability).encode())

            # Hash relationships with relative target paths
            for rel_name in sorted(prim_spec.relationships.keys()):
                rel_spec = prim_spec.relationships[rel_name]
                hasher.update(rel_name.encode())

                # Get all targets and convert to relative paths for hashing
                targets = []
                targets.extend(rel_spec.targetPathList.prependedItems)
                targets.extend(rel_spec.targetPathList.appendedItems)
                targets.extend(rel_spec.targetPathList.explicitItems)
                targets.extend(rel_spec.targetPathList.addedItems)

                for target in sorted(targets, key=lambda p: p.pathString):
                    # Convert absolute paths to relative for consistent hashing
                    if target.IsAbsolutePath():
                        relative_target = target.MakeRelativePath(prim_path)
                        hasher.update(relative_target.pathString.encode())
                    else:
                        hasher.update(target.pathString.encode())

            # Recursively hash children (sorted by name)
            for child_name in sorted(prim_spec.nameChildren.keys()):
                child_spec = prim_spec.nameChildren[child_name]
                hasher.update(child_name.encode())
                hash_prim_recursive(child_spec, depth + 1)

        prim_spec = layer.GetPrimAtPath(instance_path)
        if prim_spec:
            hash_prim_recursive(prim_spec)

        return hasher.hexdigest()[:_GEOMETRY_HASH_LENGTH]

    def _ensure_prim_hierarchy(self, stage: Usd.Stage, prim_path: str) -> None:
        """Ensure the parent hierarchy exists for a given prim path.

        Args:
            stage: The stage to create the hierarchy in.
            prim_path: The full prim path whose parents need to exist.
        """
        path = Sdf.Path(prim_path)
        parent_path = path.GetParentPath()

        if parent_path != Sdf.Path.absoluteRootPath:
            parent_prim = stage.GetPrimAtPath(parent_path)
            if not parent_prim.IsValid():
                self._ensure_prim_hierarchy(stage, parent_path.pathString)
                stage.DefinePrim(parent_path, _XFORM_TYPE_NAME)

    def _ensure_source_prim_hierarchy(self, layer: Sdf.Layer, prim_path: str) -> None:
        """Ensure the parent hierarchy for a prim path is fully defined in a layer.

        Creates missing parent prims and ensures existing ones have a type (Xform if untyped).

        Args:
            layer: The layer to create/update the hierarchy in.
            prim_path: The full prim path whose parents need to be defined.
        """
        path = Sdf.Path(prim_path)
        parent_path = path.GetParentPath()

        if parent_path == Sdf.Path.absoluteRootPath:
            return

        # Recursively ensure ancestors first
        self._ensure_source_prim_hierarchy(layer, parent_path.pathString)

        parent_spec = layer.GetPrimAtPath(parent_path)
        if not parent_spec:
            # Parent doesn't exist, create it as Xform
            parent_spec = Sdf.CreatePrimInLayer(layer, parent_path)
            if parent_spec:
                parent_spec.specifier = Sdf.SpecifierDef
                parent_spec.typeName = _XFORM_TYPE_NAME
        elif not parent_spec.typeName:
            # Parent exists but has no type, set to Xform
            parent_spec.typeName = _XFORM_TYPE_NAME

    def _get_intrinsic_attributes(self, prim: Usd.Prim) -> FrozenSet[str]:
        """Get the set of intrinsic attributes for a given geometry prim type.

        Uses USD's schema registry to get the typed schema properties (including
        inherited ones from parent schemas) without including properties from
        applied API schemas or custom attributes.

        Args:
            prim: The geometry prim to get intrinsic attributes for.

        Returns:
            Frozenset of attribute names that are intrinsic to this geometry type.
        """
        type_name = prim.GetTypeName()
        if not type_name:
            return frozenset()

        # FindConcretePrimDefinition returns the schema definition for the typed schema only,
        # excluding properties from applied API schemas
        prim_def = Usd.SchemaRegistry().FindConcretePrimDefinition(type_name)
        if prim_def:
            return frozenset(prim_def.GetPropertyNames())

        return frozenset()
