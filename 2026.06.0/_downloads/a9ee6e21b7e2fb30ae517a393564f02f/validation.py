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
Validation rules for Naming and Paths capability.
"""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

try:
    import omni.client
except ImportError:
    omni_client = None

import omni.capabilities as cap
import usd_validation_nvidia
from pxr import Sdf, Usd

# Global caches for path validation
CACHE_EXISTING_FILEPATHS = set()
CACHE_FOLDER_CONTENTS = {}

# Common naming patterns
CAMEL_CASE_PATTERN = re.compile(r"^[a-z][a-zA-Z0-9]*$")
SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
VALID_PRIM_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
VALID_FILE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")

# Reserved names (Windows)
RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

# Path length limits
MAX_PATH_LENGTH = 260  # Windows default limit
MAX_FILENAME_LENGTH = 255


def file_path(path: str) -> str:
    """Extract the directory path from a file path."""
    return os.path.dirname(path)


def combine_paths(base_path: str, relative_path: str) -> str:
    """Combine base and relative paths."""
    return os.path.normpath(os.path.join(base_path, relative_path)).replace("\\", "/")


def file_exists(path: str) -> bool:
    """Check if a file exists asynchronously."""
    if "omniverse://" in path:
        if omni.client:
            result, _ = omni.client.stat(path)
            return result == omni.client.Result.OK
        return False
    return os.path.exists(path)


def get_prim_filepath(prim: Usd.Prim) -> str:
    """Get the file path for a prim."""
    for spec in prim.GetPrimStack():
        if spec:
            return spec.layer.identifier.replace("\\", "/")
    return ""


def is_absolute_path(path: str) -> bool:
    """Check if a path is absolute."""
    if not path:
        return False

    # Check for Unix-style absolute paths
    if path.startswith("/"):
        return True

    # Check for Windows-style absolute paths
    if len(path) >= 2 and path[1] == ":":
        return True

    # Check for UNC/network paths
    if path.startswith("//") or path.startswith("\\\\"):
        return True

    return False


@usd_validation_nvidia.register_rule("NamingPaths")
@usd_validation_nvidia.register_requirements(cap.NamingPathsRequirements.NP_001, override=True)
class PrimNamingConventionChecker(usd_validation_nvidia.BaseRuleChecker):
    """Check NP.001: Prim naming convention compliance."""

    def CheckPrim(self, prim: Usd.Prim) -> None:
        """Check prim naming convention."""
        prim_name = prim.GetName()

        # Check for valid prim name pattern
        if not VALID_PRIM_NAME_PATTERN.match(prim_name):
            self._AddFailedCheck(
                requirement=cap.NamingPathsRequirements.NP_001,
                message=f"Prim '{prim_name}' contains invalid characters. Use only letters, numbers, and underscores.",
                at=prim,
            )

        # Check for reserved keywords
        if prim_name.upper() in RESERVED_NAMES:
            self._AddFailedCheck(
                requirement=cap.NamingPathsRequirements.NP_001,
                message=f"Prim '{prim_name}' uses a reserved name.",
                at=prim,
            )

        # Check for consistent naming convention (either camelCase or snake_case)
        if not (CAMEL_CASE_PATTERN.match(prim_name) or SNAKE_CASE_PATTERN.match(prim_name)):
            self._AddFailedCheck(
                requirement=cap.NamingPathsRequirements.NP_001,
                message=f"Prim '{prim_name}' does not follow consistent naming convention (camelCase or snake_case).",
                at=prim,
            )


@usd_validation_nvidia.register_rule("NamingPaths")
@usd_validation_nvidia.register_requirements(cap.NamingPathsRequirements.NP_002, override=True)
class FileNamingConventionChecker(usd_validation_nvidia.BaseRuleChecker):
    """Check NP.002: File naming convention compliance."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check file naming convention."""
        # Get the stage's file path
        stage_path = stage.GetRootLayer().identifier
        if not stage_path:
            return

        filename = os.path.basename(stage_path)

        # Check for valid file name pattern
        if not VALID_FILE_NAME_PATTERN.match(filename):
            self._AddFailedCheck(
                requirement=cap.NamingPathsRequirements.NP_002,
                message=f"File '{filename}' contains invalid characters. Use only letters, numbers, dots, hyphens, and underscores.",
                at=stage,
            )

        # Check for reserved names
        name_without_ext = os.path.splitext(filename)[0].upper()
        if name_without_ext in RESERVED_NAMES:
            self._AddFailedCheck(
                requirement=cap.NamingPathsRequirements.NP_002,
                message=f"File '{filename}' uses a reserved name.",
                at=stage,
            )

        # Check file extension
        if not filename.lower().endswith((".usd", ".usda", ".usdc", ".usdz")):
            self._AddFailedCheck(
                requirement=cap.NamingPathsRequirements.NP_002,
                message=f"File '{filename}' does not have a valid USD extension.",
                at=stage,
            )

        # Check filename length
        if len(filename) > MAX_FILENAME_LENGTH:
            self._AddFailedCheck(
                requirement=cap.NamingPathsRequirements.NP_002,
                message=f"File '{filename}' exceeds maximum filename length ({MAX_FILENAME_LENGTH} characters).",
                at=stage,
            )


@usd_validation_nvidia.register_rule("NamingPaths")
@usd_validation_nvidia.register_requirements(cap.NamingPathsRequirements.NP_003, override=True)
class DirectoryStructureChecker(usd_validation_nvidia.BaseRuleChecker):
    """Check NP.003: Directory naming and organization compliance.

    NP.003 is scoped to *directory naming* only: each directory component in the
    asset path must use valid characters and must not be a reserved name. It does
    not enforce the overall asset folder layout (root folder, intermediate folder,
    and main asset file placement) - that is owned by NP.005
    (AssetFolderStructureChecker), which is the single source of truth for the
    asset folder layout.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check directory naming for each folder in the asset path."""
        # Get the stage's file path
        stage_path = stage.GetRootLayer().identifier
        if not stage_path:
            return

        # Validate directory names only (skip filesystem root e.g. "C:\" on Windows so we only validate folder names)
        dir_path = os.path.dirname(stage_path)
        if dir_path:
            path_obj = Path(dir_path)
            root_anchor = path_obj.anchor  # e.g. "C:\" on Windows, "" or "/" on Posix
            dirs = [p for p in path_obj.parts if p and p != root_anchor]
            for dir_name in dirs:
                if not VALID_FILE_NAME_PATTERN.match(dir_name):
                    self._AddFailedCheck(
                        requirement=cap.NamingPathsRequirements.NP_003,
                        message=f"Directory '{dir_name}' contains invalid characters.",
                        at=stage,
                    )

                if dir_name.upper() in RESERVED_NAMES:
                    self._AddFailedCheck(
                        requirement=cap.NamingPathsRequirements.NP_003,
                        message=f"Directory '{dir_name}' uses a reserved name.",
                        at=stage,
                    )


@usd_validation_nvidia.register_rule("NamingPaths")
@usd_validation_nvidia.register_requirements(cap.NamingPathsRequirements.NP_004, override=True)
class PathLengthLimitsChecker(usd_validation_nvidia.BaseRuleChecker):
    """Check NP.004: Path length limits compliance."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check path length limits."""
        # Get the stage's file path
        stage_path = stage.GetRootLayer().identifier
        if not stage_path:
            return

        # Check absolute path length
        abs_path = os.path.abspath(stage_path)
        if len(abs_path) > MAX_PATH_LENGTH:
            self._AddFailedCheck(
                requirement=cap.NamingPathsRequirements.NP_004,
                message=f"File path exceeds maximum length ({MAX_PATH_LENGTH} characters): {abs_path}",
                at=stage,
            )

        # Check relative path length (skip on Windows when stage is on a different drive than CWD)
        try:
            rel_path = os.path.relpath(stage_path)
            if len(rel_path) > MAX_PATH_LENGTH:
                self._AddFailedCheck(
                    requirement=cap.NamingPathsRequirements.NP_004,
                    message=f"Relative path exceeds maximum length ({MAX_PATH_LENGTH} characters): {rel_path}",
                    at=stage,
                )
        except ValueError:
            pass


@usd_validation_nvidia.register_rule("NamingPaths")
@usd_validation_nvidia.register_requirements(cap.NamingPathsRequirements.NP_005, override=True)
class AssetFolderStructureChecker(usd_validation_nvidia.BaseRuleChecker):
    """Check NP.005: Asset folder structure compliance."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check asset folder structure."""
        # Get the stage's file path
        stage_path = stage.GetRootLayer().identifier.replace("\\", "/")
        asset_file_name = os.path.basename(stage_path)
        if not stage_path:
            return

        # Get the directory containing the USD file
        current_dir = os.path.dirname(stage_path)
        if not current_dir:
            return

        # Get the main USD file name (without extension)
        main_usd_file = os.path.basename(stage_path)
        main_usd_name = os.path.splitext(main_usd_file)[0]

        # Check 1: The main asset file must live inside an intermediate folder whose
        # parent (the asset root folder) is named after the asset.
        # Structure: asset_folder/intermediate_folder/asset_file.usd
        #
        # The intermediate folder is the file's immediate parent (current_dir); the
        # asset root folder is its grandparent. Per NP.005 the main asset file name
        # must contain the asset root folder name. Enforcing that containment is what
        # distinguishes a correctly nested asset from a flat layout where the file
        # sits directly in the asset root (no intermediate folder), is nested too
        # deep, or is named inconsistently with its asset folder.
        path_obj = Path(current_dir)
        asset_folder_name = path_obj.parent.name if path_obj.parent else None

        if not asset_folder_name:
            self._AddFailedCheck(
                requirement=cap.NamingPathsRequirements.NP_005,
                message="Asset must be in a folder structure with at least one intermediate folder",
                at=stage,
            )
            return

        if asset_folder_name.lower() not in main_usd_name.lower():
            self._AddFailedCheck(
                requirement=cap.NamingPathsRequirements.NP_005,
                message=(
                    f"Main asset file '{main_usd_file}' must reside in an intermediate folder "
                    f"under an asset root folder whose name the file name contains. Expected the "
                    f"file name to contain the asset root folder name '{asset_folder_name}' "
                    f"(structure: {asset_folder_name}/<intermediate>/<name containing "
                    f"'{asset_folder_name}'>.usd)."
                ),
                at=stage,
            )
            return

        # Check 2: The intermediate folder must contain exactly one USD file:
        # the main asset file. Subfolders may contain any number of USD files.
        intermediate_usd_files = sorted(
            f
            for f in os.listdir(current_dir)
            if os.path.isfile(os.path.join(current_dir, f)) and f.endswith((".usd", ".usda"))
        )
        if len(intermediate_usd_files) > 1:
            intermediate_folder = os.path.basename(current_dir)
            self._AddFailedCheck(
                requirement=cap.NamingPathsRequirements.NP_005,
                message=(
                    f"Exactly one USD file is allowed in the intermediate folder "
                    f"'{intermediate_folder}' (the main asset file). "
                    f"Found {len(intermediate_usd_files)}: "
                    f"{', '.join(intermediate_usd_files)}"
                ),
                at=stage,
            )


@usd_validation_nvidia.register_rule("NamingPaths")
@usd_validation_nvidia.register_requirements(cap.NamingPathsRequirements.NP_006, override=True)
class MetadataLocationChecker(usd_validation_nvidia.BaseRuleChecker):
    """Check NP.006: Metadata location compliance."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check metadata location."""
        # Get the stage's file path
        stage_path = stage.GetRootLayer().identifier
        if not stage_path:
            return

        # Get the directory containing the USD file
        current_dir = os.path.dirname(stage_path)
        if not current_dir:
            return

        # Get the main USD file name (without extension)
        main_usd_file = os.path.basename(stage_path)
        main_usd_name = os.path.splitext(main_usd_file)[0]

        # Check for simready_metadata in custom layer data
        has_simready_metadata = False
        root_layer = stage.GetRootLayer()
        if root_layer:
            custom_layer_data = root_layer.customLayerData
            if custom_layer_data and "SimReady_Metadata" in custom_layer_data:
                has_simready_metadata = True

        # extend to check asset_name, profile, profile_version, source_asset (and that it exists).

        # Check if sidecar JSON file exists
        sidecar_json_path = os.path.join(current_dir, f"{main_usd_name}.json")
        has_sidecar_metadata = os.path.exists(sidecar_json_path)

        # Validate sidecar JSON if it exists
        if has_sidecar_metadata:
            try:
                with open(sidecar_json_path, "r") as f:
                    import json

                    json.load(f)  # Validate JSON format
            except (json.JSONDecodeError, IOError) as e:
                self._AddFailedCheck(
                    requirement=cap.NamingPathsRequirements.NP_006,
                    message=f"Sidecar JSON file '{sidecar_json_path}' is not valid JSON: {str(e)}",
                    at=stage,
                )
                has_sidecar_metadata = False

        # Check if at least one metadata source exists
        if not has_sidecar_metadata and not has_simready_metadata:
            self._AddFailedCheck(
                requirement=cap.NamingPathsRequirements.NP_006,
                message=f"Asset '{main_usd_name}' has no metadata. Metadata must be stored in custom layer data as 'simready_metadata' or a sidecar JSON file.",
                at=stage,
            )


def _extract_all_references_or_payload_lists(reference_or_payload_list):
    items = []
    items.extend(reference_or_payload_list.explicitItems)
    items.extend(reference_or_payload_list.prependedItems)
    items.extend(reference_or_payload_list.addedItems)
    items.extend(reference_or_payload_list.appendedItems)
    return items


@usd_validation_nvidia.register_rule("NamingPaths")
@usd_validation_nvidia.register_requirements(cap.NamingPathsRequirements.NP_007, override=True)
class RelativePathsChecker(usd_validation_nvidia.BaseRuleChecker):
    """Check NP.007: Relative paths compliance."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check relative paths."""
        # Get the stage's file path
        stage_path = stage.GetRootLayer().identifier
        if not stage_path:
            return

        # Get the directory containing the USD file
        current_dir = os.path.dirname(stage_path)
        if not current_dir:
            return

        # Check all prims in the stage (use prim stack + referenceList/payloadList; GetReferences() is not iterable in this USD build)
        for prim in stage.Traverse():
            if prim.HasAuthoredReferences():
                for primspec in prim.GetPrimStack():
                    if not primspec or not primspec.referenceList:
                        continue

                    reference_prims_paths = _extract_all_references_or_payload_lists(primspec.referenceList)

                    for item in reference_prims_paths:
                        ref_path = item.assetPath
                        if ref_path and is_absolute_path(ref_path):
                            self._AddFailedCheck(
                                requirement=cap.NamingPathsRequirements.NP_007,
                                message=f"Prim '{prim.GetPath()}' has absolute path reference: '{ref_path}'. Use relative paths instead.",
                                at=prim,
                            )

            if prim.HasAuthoredPayloads():
                for primspec in prim.GetPrimStack():
                    if not primspec or not primspec.payloadList:
                        continue

                    payload_prims_paths = _extract_all_references_or_payload_lists(primspec.payloadList)

                    for item in payload_prims_paths:
                        payload_path = item.assetPath
                        if payload_path and is_absolute_path(payload_path):
                            self._AddFailedCheck(
                                requirement=cap.NamingPathsRequirements.NP_007,
                                message=f"Prim '{prim.GetPath()}' has absolute path payload: '{payload_path}'. Use relative paths instead.",
                                at=prim,
                            )

            # Check subLayers (GetMetadata can return None if not authored)
            sublayers = prim.GetMetadata("subLayers")
            if sublayers is not None:
                for sublayer in sublayers:
                    if is_absolute_path(sublayer):
                        self._AddFailedCheck(
                            requirement=cap.NamingPathsRequirements.NP_007,
                            message=f"Prim '{prim.GetPath()}' has absolute path subLayer: '{sublayer}'. Use relative paths instead.",
                            at=prim,
                        )

        # Check custom layer data for absolute paths
        root_layer = stage.GetRootLayer()
        if root_layer:
            custom_layer_data = root_layer.customLayerData
            if custom_layer_data:
                for key, value in custom_layer_data.items():
                    if isinstance(value, str) and is_absolute_path(value):
                        self._AddFailedCheck(
                            requirement=cap.NamingPathsRequirements.NP_007,
                            message=f"Custom layer data '{key}' contains absolute path: '{value}'. Use relative paths instead.",
                            at=stage,
                        )


@usd_validation_nvidia.register_rule("NamingPaths")
@usd_validation_nvidia.register_requirements(cap.NamingPathsRequirements.NP_008, override=True)
class PathsExistChecker(usd_validation_nvidia.BaseRuleChecker):
    """
    Check NP.008: Verify all asset, reference and payload paths resolve to files that exist.

    This validates that all referenced files (assets, references, payloads, sublayers)
    actually exist on disk or in Omniverse.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        """Check that all referenced paths exist."""
        root_prim = stage.GetDefaultPrim()
        if not root_prim:
            return

        num_prims_inspected = 0
        for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)):
            num_prims_inspected += 1

            filename = get_prim_filepath(prim)

            # Validate all asset attribute paths
            for attr in prim.GetAttributes():
                if attr.GetTypeName().type.typeName == "SdfAssetPath":
                    attr_value = attr.Get()
                    if attr_value and attr_value.path:
                        resolved_path = attr_value.resolvedPath
                        if not resolved_path:
                            # Try to resolve it manually
                            resolved_path = combine_paths(file_path(filename), attr_value.path)

                        if not file_exists(resolved_path):
                            self._AddFailedCheck(
                                requirement=cap.NamingPathsRequirements.NP_008,
                                message=f"Asset path '{attr_value.path}' on attribute '{attr.GetName()}' at prim '{prim.GetPath()}' does not resolve to an existing file.",
                                at=prim,
                            )

            # Validate all references
            if prim.HasAuthoredReferences():
                for primspec in prim.GetPrimStack():
                    if not primspec or not primspec.referenceList:
                        continue

                    reference_prims_paths = _extract_all_references_or_payload_lists(primspec.referenceList)
                    for item in reference_prims_paths:
                        if item.assetPath:
                            item_resolved_path = combine_paths(file_path(primspec.layer.identifier), item.assetPath)
                            if not file_exists(item_resolved_path):
                                self._AddFailedCheck(
                                    requirement=cap.NamingPathsRequirements.NP_008,
                                    message=f"Reference path '{item.assetPath}' at prim '{prim.GetPath()}' in file '{primspec.layer.identifier}' does not resolve to an existing file.",
                                    at=prim,
                                )

            # Validate all payloads
            if prim.HasAuthoredPayloads():
                for primspec in prim.GetPrimStack():
                    if not primspec or not primspec.payloadList:
                        continue

                    payload_prims_paths = _extract_all_references_or_payload_lists(primspec.payloadList)
                    for item in payload_prims_paths:
                        if item.assetPath:
                            item_resolved_path = combine_paths(file_path(primspec.layer.identifier), item.assetPath)
                            if not file_exists(item_resolved_path):
                                self._AddFailedCheck(
                                    requirement=cap.NamingPathsRequirements.NP_008,
                                    message=f"Payload path '{item.assetPath}' at prim '{prim.GetPath()}' in file '{primspec.layer.identifier}' does not resolve to an existing file.",
                                    at=prim,
                                )

        # Validate sublayers
        root_layer = stage.GetRootLayer()
        for sublayer_path in root_layer.subLayerPaths:
            if sublayer_path:
                resolved_sublayer = combine_paths(file_path(root_layer.identifier), sublayer_path)
                if not file_exists(resolved_sublayer):
                    self._AddFailedCheck(
                        requirement=cap.NamingPathsRequirements.NP_008,
                        message=f"Sublayer path '{sublayer_path}' in root layer does not resolve to an existing file.",
                        at=stage,
                    )
