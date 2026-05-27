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
Validation rules for Visual Materials capability.
"""

import math
import os
from pathlib import Path
from typing import List, Optional

import omni.asset_validator
import omni.capabilities as cap
from omni.asset_validator import BaseRuleChecker, register_requirements
from pxr import Sdf, Sdr, Usd, UsdGeom, UsdShade

from .util.mdl_helpers import is_mdl_helper_available, get_mdl_module_parameter_descs

try:
    import omni.client
except ImportError:
    omni = None


@register_requirements(
    cap.MaterialsRequirements.VM_BIND_001,
    cap.MaterialsRequirements.VM_BIND_002,
    cap.MaterialsRequirements.VM_PS_001,
    cap.MaterialsRequirements.VM_MAT_001,
    cap.MaterialsRequirements.VM_MDL_001,
    cap.MaterialsRequirements.VM_MDL_002,
    cap.MaterialsRequirements.VM_TEX_001,
    cap.MaterialsRequirements.VM_TEX_002,
)
class VisualMaterialsCapabilityChecker(BaseRuleChecker):
    """Checker for Visual Materials capability requirements."""

    # USD Preview Surface specification attributes
    usd_preview_surface_attributes = {
        "inputs:diffuseColor": "color3f",
        "inputs:emissiveColor": "color3f",
        "inputs:specularColor": "color3f",
        "inputs:metallic": "float",
        "inputs:roughness": "float",
        "inputs:clearcoat": "float",
        "inputs:clearcoatRoughness": "float",
        "inputs:opacity": "float",
        "inputs:opacityThreshold": "float",
        "inputs:ior": "float",
        "inputs:normal": "normal3f",
        "inputs:displacement": "float",
        "inputs:occlusion": "float",
        "outputs:surface": "token",
        "outputs:displacement": "token",
    }

    # Allowed token values for USD Preview Surface
    allowed_tokens = {
        "inputs:sourceColorSpace": ["auto", "raw", "sRGB"],
        "inputs:wrapS": ["black", "clamp", "repeat", "mirror", "useMetadata"],
        "inputs:wrapT": ["black", "clamp", "repeat", "mirror", "useMetadata"],
    }

    # Color space requirements (VM.TEX.002)
    colorspace_srgb_list = [
        "inputs:UV_VertexColor",
        "inputs:Set1SuperAlbedo",
        "inputs:Set2SuperAlbedo",
    ]

    # Texture size limit (VM.TEX.001)
    max_texture_size = 16384  # 16K pixels

    # Cache for MDL validation (VM.BIND.002)
    _cache_existing_filepaths = set()
    _cache_mdl_specs = {}

    def CheckPrim(self, prim: Usd.Prim) -> None:
        stage = prim.GetStage()
        prim_path = prim.GetPath()

        # Check for VM.BIND.001: Material binding scope compliance
        errors = self.check_vm_bind_001_material_bind_scope(stage, prim_path)
        if errors:
            self._AddFailedCheck(
                message="Material binding scope compliance.",
                at=prim,
                requirement=cap.MaterialsRequirements.VM_BIND_001,
            )

        # Check for VM.MDL.001: MDL material source asset compliance
        self.check_vm_mdl_001_material_mdl_source_asset(stage, prim_path)

        # Check for VM.MDL.002: MDL schema compliance
        self.check_vm_mdl_002_material_mdl_schema(stage, prim_path)

        # Check for VM.PS.001: Material preview surface specification compliance
        self.check_vm_ps_001_material_preview_surface(stage, prim_path)

        # Check for VM.MAT.001: Mesh material binding compliance
        self.check_vm_mat_001_mesh_material_binding(stage, prim_path)

        # Check for VM.BIND.002: Shader inputs validation
        self.check_vm_bind_002_shader_inputs(stage, prim_path)

        # Check for VM.TEX.001: Texture size compliance
        self.check_vm_tex_001_texture_size(stage, prim_path)

        # Check for VM.TEX.002: Color space compliance
        self.check_vm_tex_002_colorspace(stage, prim_path)

    def check_vm_bind_001_material_bind_scope(self, stage, prim_path: str) -> List[str]:
        """Check VM.BIND.001: Material binding scope compliance."""
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            return errors

        # Check if material binding is properly scoped
        material_binding_api = UsdShade.MaterialBindingAPI(prim)
        if material_binding_api:
            # Check for proper material binding scope
            errors.extend(self._validate_material_binding_scope(material_binding_api, prim_path))

        return errors

    def _validate_material_binding_scope(
        self, material_binding_api: UsdShade.MaterialBindingAPI, prim_path: str
    ) -> List[str]:
        """Validate material binding scope compliance."""
        errors = []

        # Check for direct material bindings
        direct_bindings = material_binding_api.GetDirectBindingRel()
        if direct_bindings:
            # Validate that direct bindings are properly scoped
            for target in direct_bindings.GetTargets():
                if not self._is_valid_material_scope(target):
                    errors.append(f"Invalid material binding scope for direct binding: {target}")

        # Check for collection-based bindings (API differs: GetCollectionBindingRels() returns list, or GetCollectionBindingRel(bindingName, purpose) for one)
        collection_binding_rels = getattr(material_binding_api, "GetCollectionBindingRels", None)
        if callable(collection_binding_rels):
            for rel in collection_binding_rels():
                if rel:
                    for target in rel.GetTargets():
                        if not self._is_valid_collection_scope(target):
                            errors.append(f"Invalid collection binding scope: {target}")
        else:
            # Fallback: prim may have no collection bindings, or older API; skip to avoid ArgumentError
            pass

        # Check for proper scope hierarchy
        if not self._validate_binding_hierarchy(material_binding_api, prim_path):
            errors.append(f"Material binding hierarchy violation at: {prim_path}")

        return errors

    def _is_valid_material_scope(self, material_path) -> bool:
        """Check if material path is valid for binding scope."""
        if not material_path:
            return False

        # Material should be a valid path and not empty
        if str(material_path).strip() == "":
            return False

        # Check for proper material path format
        path_str = str(material_path)
        if not path_str.startswith("/"):
            return False

        return True

    def _is_valid_collection_scope(self, collection_path) -> bool:
        """Check if collection path is valid for binding scope."""
        if not collection_path:
            return False

        # Collection should be a valid path
        if str(collection_path).strip() == "":
            return False

        # Check for proper collection path format
        path_str = str(collection_path)
        if not path_str.startswith("/"):
            return False

        return True

    def _validate_binding_hierarchy(self, material_binding_api: UsdShade.MaterialBindingAPI, prim_path: str) -> bool:
        """Validate that material binding follows proper hierarchy rules."""
        # Check that bindings don't conflict with parent/child relationships
        # This is a simplified check - more complex hierarchy validation could be added

        # For now, just ensure the binding API is valid
        if not material_binding_api:
            return False

        # Check that we're not creating circular references
        # This would require more complex graph traversal in a full implementation
        return True

    def check_vm_mat_001_mesh_material_binding(self, stage, prim_path: str) -> List[str]:
        """Check VM.MAT.001: Mesh material binding compliance.

        Ensures that all renderable GPrims have a computed material bound to them.
        """
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            return errors

        # Skip non-GPrims and "non-renderable" prims such as proxies
        # This also skips GeomSubsets, because they are not GPrims
        # We will inspect GeomSubsets later as we check the GPrim
        if not UsdGeom.Gprim(prim) or not self._has_default_or_renderable_purpose(prim):
            return errors

        # Get the computed material for this prim
        prim_material, _ = self._get_material(prim)

        # Check for GeomSubsets which can have their own material bindings
        mtl_binding_api = UsdShade.MaterialBindingAPI(prim)
        geom_subsets = mtl_binding_api.GetMaterialBindSubsets() or []

        if not geom_subsets:
            # No subsets, check the prim itself
            if not prim_material:
                self._AddFailedCheck(
                    message=f"GPrim '{prim_path}' does not have a material binding",
                    at=prim,
                    requirement=cap.MaterialsRequirements.VM_MAT_001,
                )
                errors.append(f"Missing material binding for GPrim: {prim_path}")
        else:
            # Has subsets, check each subset
            for geom_subset in geom_subsets:
                geomsubset_material, _ = self._get_material(geom_subset)
                if not geomsubset_material:
                    self._AddFailedCheck(
                        message=f"GeomSubset '{geom_subset.GetPath()}' does not have a material binding",
                        at=geom_subset.GetPrim(),
                        requirement=cap.MaterialsRequirements.VM_MAT_001,
                    )
                    errors.append(f"Missing material binding for GeomSubset: {geom_subset.GetPath()}")

        return errors

    def _has_default_or_renderable_purpose(self, prim: Usd.Prim) -> bool:
        """Returns True if the prim is Imageable with default or renderable purpose."""
        imageable = UsdGeom.Imageable(prim)
        if not imageable:
            return False
        purpose = imageable.ComputePurpose()
        return purpose in (UsdGeom.Tokens.default_, UsdGeom.Tokens.render)

    def _get_material(self, prim_or_geom_subset) -> tuple:
        """Returns the computed "full" purpose material and the relationship of the prim/geomSubset."""
        return UsdShade.MaterialBindingAPI(prim_or_geom_subset).ComputeBoundMaterial(
            materialPurpose=UsdShade.Tokens.full
        )

    def check_vm_ps_001_material_preview_surface(self, stage, prim_path: str) -> List[str]:
        """Check VM.PS.001: Material Preview Surface specification compliance."""
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            return errors

        # Check if this is a material with UsdPreviewSurface
        if prim.GetTypeName() == "Material":
            # Find UsdPreviewSurface shaders
            for child in prim.GetChildren():
                if child.GetTypeName() == "Shader":
                    shader = UsdShade.Shader(child)
                    if shader.GetIdAttr().Get() == "UsdPreviewSurface":
                        errors.extend(self._validate_preview_surface_shader(shader))

        return errors

    def _validate_preview_surface_shader(self, shader: UsdShade.Shader) -> List[str]:
        """Validate UsdPreviewSurface shader attributes."""
        errors = []

        for attr_name, expected_type in self.usd_preview_surface_attributes.items():
            attr = shader.GetPrim().GetAttribute(attr_name)
            if attr:
                # Check attribute type
                actual_type = attr.GetTypeName()
                if actual_type != expected_type:
                    errors.append(
                        f"Attribute '{attr_name}' has incorrect type '{actual_type}', expected '{expected_type}'"
                    )

                # Check for time samples on token attributes
                if expected_type == "token" and attr.GetNumTimeSamples() > 0:
                    errors.append(f"Token attribute '{attr_name}' should not have time samples")

                # Check allowed token values
                if attr_name in self.allowed_tokens:
                    value = attr.Get()
                    if value not in self.allowed_tokens[attr_name]:
                        errors.append(
                            f"Attribute '{attr_name}' has invalid value '{value}', allowed values: {self.allowed_tokens[attr_name]}"
                        )

        return errors

    def check_vm_mdl_001_material_mdl_source_asset(self, stage, prim_path: str) -> List[str]:
        """Check VM.MDL.001: MDL material source asset compliance."""
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            return errors

        # Check if this is a material with MDL shader
        if prim.GetTypeName() == "Material":
            for child in prim.GetChildren():
                if child.GetTypeName() == "Shader":
                    shader = UsdShade.Shader(child)
                    implementation_source = shader.GetImplementationSourceAttr().Get()

                    if implementation_source == "sourceAsset":
                        errors.extend(self._validate_mdl_source_asset(shader))

        return errors

    def _validate_mdl_source_asset(self, shader: UsdShade.Shader) -> List[str]:
        """Validate MDL source asset attributes."""
        errors = []

        # Check for required MDL source asset attribute
        source_asset_attr = shader.GetPrim().GetAttribute("info:mdl:sourceAsset")
        if not source_asset_attr:
            errors.append("MDL shader missing required 'info:mdl:sourceAsset' attribute")
            self._AddFailedCheck(
                message="MDL shader missing required 'info:mdl:sourceAsset' attribute",
                at=shader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_MDL_001,
            )
            return errors

        source_asset = source_asset_attr.Get()
        if not source_asset:
            errors.append("MDL source asset path is empty")
            self._AddFailedCheck(
                message="MDL source asset path is empty",
                at=shader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_MDL_001,
            )
            return errors

        # Check file extension
        source_path = str(source_asset)

        # Remove leading and trailing @ symbols if present
        while source_path.startswith("@") and source_path.endswith("@"):
            source_path = source_path[1:-1]

        if not source_path.endswith(".mdl"):
            errors.append(f"MDL source asset must have .mdl extension: {source_asset}")
            self._AddFailedCheck(
                message=f"MDL source asset must have .mdl extension: {source_asset}",
                at=shader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_MDL_001,
            )

        # Check for relative path prefix
        if not source_path.startswith("./"):
            errors.append(f"MDL source asset path should start with './': {source_path}")
            self._AddFailedCheck(
                message=f"MDL source asset path should start with './': {source_path}",
                at=shader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_MDL_001,
            )

        # Check if the MDL file exists
        stage = shader.GetPrim().GetStage()
        mdl_path = source_asset.resolvedPath
        if not mdl_path and omni:
            mdl_path = omni.client.combine_urls(stage.GetRootLayer().identifier, source_asset.path)
        elif not mdl_path:
            mdl_path = source_asset.path

        mdl_path = mdl_path.replace("\\", "/")

        # Check if file exists (with caching)
        file_exists = False
        if mdl_path in self._cache_existing_filepaths:
            file_exists = True
        else:
            if omni:
                # Use omni.client for file checking
                result, _ = omni.client.stat(mdl_path)
                if result == omni.client.Result.OK:
                    file_exists = True
                    self._cache_existing_filepaths.add(mdl_path)
            else:
                # Fallback to os.path.exists for local files
                if os.path.exists(mdl_path):
                    file_exists = True
                    self._cache_existing_filepaths.add(mdl_path)

        if not file_exists:
            errors.append(f"MDL source asset file does not exist: {mdl_path}")
            self._AddFailedCheck(
                message=f"MDL source asset file does not exist: {mdl_path}",
                at=shader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_MDL_001,
            )

        return errors

    def check_vm_mdl_002_material_mdl_schema(self, stage, prim_path: str) -> List[str]:
        """Check VM.MDL.002: MDL schema compliance."""
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            return errors

        # Check if this is a material with MDL shader
        if prim.GetTypeName() == "Material":
            for child in prim.GetChildren():
                if child.GetTypeName() == "Shader":
                    shader = UsdShade.Shader(child)
                    implementation_source = shader.GetImplementationSourceAttr().Get()

                    if implementation_source == "sourceAsset":
                        errors.extend(self._validate_mdl_schema(shader))
                    elif implementation_source == "mdlMaterial":
                        errors.append(
                            "Deprecated MDL schema format detected. Use 'sourceAsset' instead of 'mdlMaterial'"
                        )

        return errors

    def _validate_mdl_schema(self, shader: UsdShade.Shader) -> List[str]:
        """Validate MDL schema format."""
        errors = []

        # Check for deprecated attributes
        if shader.GetPrim().GetAttribute("module"):
            errors.append("Deprecated 'module' attribute found. Use 'info:mdl:sourceAsset' instead")

        if shader.GetPrim().GetAttribute("name"):
            errors.append("Deprecated 'name' attribute found. Use 'info:mdl:materialType' instead")

        # Check for required new attributes
        if not shader.GetPrim().GetAttribute("info:mdl:sourceAsset"):
            errors.append("Missing required 'info:mdl:sourceAsset' attribute")

        if not shader.GetPrim().GetAttribute("info:mdl:materialType"):
            errors.append("Missing required 'info:mdl:materialType' attribute")

        return errors

    def check_vm_tex_002_colorspace(self, stage, prim_path: str) -> List[str]:
        """Check VM.TEX.002: Color space compliance."""
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            return errors

        # Check all attributes for color space requirements
        for attr in prim.GetAttributes():
            if attr.HasColorSpace():
                color_space = attr.GetColorSpace()
                attr_name = attr.GetName()

                # Check if this attribute requires sRGB color space
                if attr_name in self.colorspace_srgb_list:
                    if color_space != "sRGB":
                        self._AddFailedCheck(
                            message=f"Attribute '{attr_name}' has color space '{color_space}', expected 'sRGB'",
                            at=prim,
                            requirement=cap.MaterialsRequirements.VM_TEX_002,
                        )
                        errors.append(f"Incorrect color space for {attr_name}: {color_space} (expected sRGB)")
                else:
                    # All other attributes should use 'raw' color space
                    if color_space != "raw":
                        self._AddFailedCheck(
                            message=f"Attribute '{attr_name}' has color space '{color_space}', expected 'raw'",
                            at=prim,
                            requirement=cap.MaterialsRequirements.VM_TEX_002,
                        )
                        errors.append(f"Incorrect color space for {attr_name}: {color_space} (expected raw)")

        return errors

    def _validate_sdr_shader_inputs(self, prim: Usd.Prim, shader_prim: UsdShade.Shader) -> List[str]:
        """Validate non-MDL shader inputs using SDR (Shader Definition Registry).

        Args:
            prim: The shader prim being validated
            shader_prim: The UsdShade.Shader wrapper

        Returns:
            List of error messages
        """
        errors = []

        try:
            sdr_shader_node = shader_prim.GetShaderNodeForSourceType("mdl")

            if not sdr_shader_node:
                return errors

            # Validate shader inputs against SDR
            for usdshade_input in shader_prim.GetInputs():
                name = usdshade_input.GetBaseName()
                sdr_shader_property = sdr_shader_node.GetInput(name)

                if not sdr_shader_property:
                    continue

                ndr_sdr_type_indicator = sdr_shader_property.GetTypeAsSdfType()
                property_type = ndr_sdr_type_indicator[1] or ndr_sdr_type_indicator[0]

                input_type = usdshade_input.GetTypeName()

                if input_type != property_type:
                    error_msg = f"Type mismatch for: {usdshade_input.GetFullName()}\texpected: {property_type}\tactual: {input_type}"
                    self._AddFailedCheck(
                        message=error_msg,
                        at=prim,
                        requirement=cap.MaterialsRequirements.VM_BIND_002,
                    )
                    errors.append(error_msg)

        except Exception:
            # Silently skip if SDR validation fails
            pass

        return errors

    def _validate_mdl_shader_inputs(
        self, prim: Usd.Prim, shader_prim: UsdShade.Shader, stage: Usd.Stage, prim_path: str
    ) -> List[str]:
        """Validate MDL shader inputs against MDL specification.

        Args:
            prim: The shader prim being validated
            shader_prim: The UsdShade.Shader wrapper
            stage: The USD stage
            prim_path: Path to the shader prim

        Returns:
            List of error messages
        """
        errors = []

        mdl_path_attr = prim.GetAttribute("info:mdl:sourceAsset")

        # Check if this is an MDL shader
        if not mdl_path_attr:
            errors.append(f"Shader input 'info:mdl:sourceAsset' does not exist for {prim_path} {prim.GetTypeName()}")
            self._AddFailedCheck(
                message=f"Shader input 'info:mdl:sourceAsset' does not exist for {prim_path} {prim.GetTypeName()}",
                at=prim,
                requirement=cap.MaterialsRequirements.VM_BIND_002,
            )
            return errors

        mdl_asset = mdl_path_attr.Get()
        if not mdl_asset:
            errors.append(f"Shader input 'info:mdl:sourceAsset' has not value for {prim_path} {prim.GetTypeName()}")
            self._AddFailedCheck(
                message=f"Shader input 'info:mdl:sourceAsset' has not value for {prim_path} {prim.GetTypeName()}",
                at=prim,
                requirement=cap.MaterialsRequirements.VM_BIND_002,
            )
            return errors

        # Resolve MDL path
        mdl_path = mdl_asset.resolvedPath
        if not mdl_path and omni:
            mdl_path = omni.client.combine_urls(stage.GetRootLayer().identifier, mdl_asset.path)
        elif not mdl_path:
            mdl_path = mdl_asset.path

        mdl_path = mdl_path.replace("\\", "/")

        # Check if file exists (with caching)
        if mdl_path not in self._cache_existing_filepaths:
            if omni and omni.client.stat(mdl_path)[0] != omni.client.Result.OK:
                # File doesn't exist, skip validation
                return errors
            self._cache_existing_filepaths.add(mdl_path)

        # Get material subidentifier
        mdl_material_attr = prim.GetAttribute("info:mdl:sourceAsset:subIdentifier")
        mdl_material = mdl_material_attr.Get() if mdl_material_attr else None

        if not mdl_material:
            return errors

        # Validate shader inputs against MDL specification
        if not is_mdl_helper_available():
            # MDL helpers not available, skip the shader input checks.
            return errors

        try:
            mdl_key = f"{mdl_path}||||{mdl_material}"
            if mdl_key not in self._cache_mdl_specs:
                self._cache_mdl_specs[mdl_key] = get_mdl_module_parameter_descs(mdl_path, mdl_material)

            input_manifest = self._cache_mdl_specs[mdl_key]

            if input_manifest:
                for shader_input in shader_prim.GetInputs():
                    input_name = shader_input.GetBaseName()
                    expected_type = input_manifest.get(input_name)

                    if not expected_type:
                        continue

                    actual_type = shader_input.GetTypeName()
                    if expected_type != actual_type:
                        self._AddFailedCheck(
                            message=f"Shader input '{shader_input.GetAttr().GetName()}' has type '{actual_type}', expected '{expected_type}'",
                            at=prim,
                            requirement=cap.MaterialsRequirements.VM_BIND_002,
                        )
                        errors.append(f"Type mismatch for {input_name}: {actual_type} vs {expected_type}")

                    # Check for NaN and Inf in float values (use typeName string; .type can fail with TfType in some USD builds)
                    type_str = str(getattr(actual_type, "typeName", actual_type))
                    if type_str == "float":
                        value = shader_input.Get()
                        if value is not None and (math.isnan(value) or math.isinf(value)):
                            self._AddFailedCheck(
                                message=f"Shader input '{shader_input.GetAttr().GetName()}' contains invalid float value (NaN or Inf)",
                                at=prim,
                                requirement=cap.MaterialsRequirements.VM_BIND_002,
                            )
                            errors.append(f"Invalid float value for {input_name}: {value}")
            else:
                self._AddFailedCheck(
                    message=f"Cannot validate shader inputs: invalid material shader '{mdl_material}' in '{mdl_path}'",
                    at=prim,
                    requirement=cap.MaterialsRequirements.VM_BIND_002,
                )
                errors.append(f"Invalid material shader: {mdl_material}")

        except ImportError:
            # MDL helpers not available, skip this check
            pass

        return errors

    def check_vm_bind_002_shader_inputs(self, stage, prim_path: str) -> List[str]:
        """Check VM.BIND.002: Shader inputs validation."""
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim or prim.GetTypeName() != "Shader":
            # prim is not a shader, skip validation
            return errors

        shader_prim = UsdShade.Shader(prim)
        if not shader_prim:
            errors.append(f"No shader schema for {prim_path} {prim.GetTypeName()}")
            self._AddFailedCheck(
                message=f"No shader schema for {prim_path} {prim.GetTypeName()}",
                at=prim,
                requirement=cap.MaterialsRequirements.VM_BIND_002,
            )
            return errors

        id_attr = prim.GetAttribute("info:id")
        mdl_path_attr = prim.GetAttribute("info:mdl:sourceAsset")

        if id_attr and not mdl_path_attr:
            # Handle non-MDL shaders (built-in shaders, node graphs, etc.)
            errors.extend(self._validate_sdr_shader_inputs(prim, shader_prim))
        else:
            # Handle MDL shaders
            errors.extend(self._validate_mdl_shader_inputs(prim, shader_prim, stage, prim_path))

        return errors

    def check_vm_tex_001_texture_size(self, stage, prim_path: str) -> List[str]:
        """Check VM.TEX.001: Texture size compliance."""
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            return errors

        # Check all attributes for texture asset references
        for attr in prim.GetAttributes():
            # Check if attribute is an asset type
            if attr.GetTypeName() == Sdf.ValueTypeNames.Asset:
                asset_value = attr.Get()
                if not asset_value:
                    continue

                asset_path = asset_value.resolvedPath
                if not asset_path and omni:
                    asset_path = omni.client.combine_urls(stage.GetRootLayer().identifier, asset_value.path)
                elif not asset_path:
                    asset_path = asset_value.path

                # Check if this is an image file
                image_extensions = [".png", ".jpg", ".jpeg", ".exr", ".hdr", ".tga", ".bmp", ".tif", ".tiff"]
                if any(asset_path.lower().endswith(ext) for ext in image_extensions):
                    # Validate texture size
                    try:
                        # Try to get image dimensions using PIL if available
                        from PIL import Image

                        if os.path.exists(asset_path):
                            with Image.open(asset_path) as img:
                                width, height = img.size
                                if width > self.max_texture_size or height > self.max_texture_size:
                                    self._AddFailedCheck(
                                        message=f"Texture '{asset_path}' dimensions ({width}x{height}) exceed maximum size of {self.max_texture_size} pixels on either axis",
                                        at=prim,
                                        requirement=cap.MaterialsRequirements.VM_TEX_001,
                                    )
                                    errors.append(f"Texture too large: {asset_path} ({width}x{height})")
                    except ImportError:
                        # PIL not available, skip size check
                        pass
                    except Exception:
                        # Unable to read image, skip
                        pass

        return errors
