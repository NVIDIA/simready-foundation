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
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple, Union

from isaacsim.asset.transformer import RuleConfigurationParam, RuleInterface
from pxr import Sdf, Usd, UsdShade

from . import utils

# Material binding purposes to check
_MATERIAL_PURPOSES: Tuple[str, ...] = ("", "physics", "preview", "full")

# Default Configuration Parameters
_DEFAULT_SCOPE: str = "/"
_DEFAULT_MATERIALS_LAYER_PATH: str = "materials.usda"
_DEFAULT_TEXTURES_FOLDER: str = "Textures"
_DEFAULT_DEDUPLICATE: bool = True
_DEFAULT_DOWNLOAD_TEXTURES: bool = False

# Prim paths and scope names
_MATERIALS_SCOPE_PATH: str = "/Materials"

# Prim type names
_SCOPE_TYPE_NAME: str = "Scope"
_MATERIAL_TYPE_NAME: str = "Material"

# Truncation length for material content hashes
_MATERIAL_HASH_LENGTH: int = 32

# File extensions that should be transferred (textures, images, etc.)
_TRANSFERABLE_ASSET_EXTENSIONS: FrozenSet[str] = frozenset(
    (
        ".png",
        ".jpg",
        ".jpeg",
        ".tga",
        ".bmp",
        ".gif",
        ".tiff",
        ".tif",
        ".exr",
        ".hdr",
        ".dds",
        ".ktx",
        ".ktx2",
        ".webp",
    )
)


@dataclass
class MaterialSource:
    """Tracks the source information for a material prim."""

    prim_path: str
    defining_layer_id: str  # Layer where the material is defined
    defining_prim_path: str  # Prim path within the defining layer
    material_hash: str = ""


@dataclass
class MaterialEntry:
    """Represents a unique material stored in the materials layer."""

    name: str
    material_layer_path: str  # e.g., "/Materials/Material_001"
    sources: List[MaterialSource] = field(default_factory=list)
    existing: bool = False  # True if this material was already in the layer
    asset_paths: List[str] = field(default_factory=list)  # List of asset paths used by the material


@dataclass
class MaterialBinding:
    """Tracks a material binding on a prim."""

    prim_path: str
    material_path: str
    purpose: str  # "" for allPurpose, or specific purpose like "physics", "preview", "full"


class MaterialsRoutingRule(RuleInterface):
    """Route material prims to a shared layer and create instanceable references at original locations.

    This rule identifies all material prims, tracks their sources including referenced materials,
    deduplicates identical materials based on their shader properties and attributes, moves their
    definitions to a dedicated materials layer under /Materials/{name}, creates instanceable
    references at original locations, and transfers texture assets to a designated folder.
    Materials that are not bound to any surface after processing are removed.
    """

    def get_configuration_parameters(self) -> List[RuleConfigurationParam]:
        """Return the configuration parameters for this rule.

        Returns:
            List of configuration parameters for scope, materials layer path,
            textures folder, and deduplication settings.
        """
        return [
            RuleConfigurationParam(
                name="scope",
                display_name="Scope",
                param_type=str,
                description="The scope to limit the search for material prims",
                default_value=_DEFAULT_SCOPE,
            ),
            RuleConfigurationParam(
                name="materials_layer",
                display_name="Materials Layer",
                param_type=str,
                description="The path to the materials layer",
                default_value=_DEFAULT_MATERIALS_LAYER_PATH,
            ),
            RuleConfigurationParam(
                name="textures_folder",
                display_name="Textures Folder",
                param_type=str,
                description="Folder name for texture assets at the root of the destination path",
                default_value=_DEFAULT_TEXTURES_FOLDER,
            ),
            RuleConfigurationParam(
                name="deduplicate",
                display_name="Deduplicate",
                param_type=bool,
                description="If True, deduplicate identical materials based on shader properties",
                default_value=_DEFAULT_DEDUPLICATE,
            ),
            RuleConfigurationParam(
                name="download_textures",
                display_name="Download Textures",
                param_type=bool,
                description="If True, download remote textures (e.g., from Nucleus) to local textures folder",
                default_value=_DEFAULT_DOWNLOAD_TEXTURES,
            ),
        ]

    def process_rule(self) -> Optional[str]:
        """Move materials to a shared layer and create instanceable references.

        Order of operations:
        1. Find all material prims and their defining layers.
        2. Resolve file paths for supporting assets FIRST.
        3. Compute material hashes using resolved asset paths (before transferring).
        4. Transfer all supporting assets to the designated folder (globally deduplicated).
        5. Create materials in materials layer with updated relative asset paths.
        6. Update materials in their defining layers with instanceable references.
        7. Update material bindings to point to deduplicated materials.
        8. Ensure MaterialBindingAPI is applied to all prims with material bindings.
        9. Remove material references that are not bound to any surface.

        Returns:
            None (this rule does not change the working stage).
        """
        params = self.args.get("params", {}) or {}
        scope = params.get("scope") or "/"
        materials_layer_path = os.path.join(
            self.destination_path, params.get("materials_layer") or _DEFAULT_MATERIALS_LAYER_PATH
        )
        textures_folder = params.get("textures_folder") or _DEFAULT_TEXTURES_FOLDER
        deduplicate = params.get("deduplicate", True)
        download_textures = params.get("download_textures", False)

        self.log_operation(
            f"MaterialsRoutingRule start scope={scope} deduplicate={deduplicate} "
            f"materials_layer={materials_layer_path} textures_folder={textures_folder} "
            f"download_textures={download_textures}"
        )

        # Resolve output paths relative to package root
        materials_output_path = os.path.join(self.package_root, materials_layer_path)
        textures_output_path = os.path.join(self.package_root, textures_folder)
        materials_layer_dir = os.path.dirname(materials_output_path)

        # Ensure output directories exist
        os.makedirs(materials_layer_dir, exist_ok=True)
        os.makedirs(textures_output_path, exist_ok=True)

        # PHASE 1: Find all material prims and their sources (including defining layer info)
        material_sources = self._find_material_sources(scope)
        self.log_operation(f"Found {len(material_sources)} material prims")

        if not material_sources:
            self.log_operation("No material prims found, skipping")
            return None

        # PHASE 2: Collect all asset paths and compute hashes BEFORE transferring
        # This ensures we use resolved paths for proper deduplication
        source_asset_paths: Dict[str, List[str]] = {}  # source.prim_path -> resolved asset paths
        source_hashes: Dict[str, str] = {}  # source.prim_path -> hash

        for source in material_sources:
            prim = self.source_stage.GetPrimAtPath(source.prim_path)
            if not prim.IsValid():
                continue

            # Collect asset paths FIRST (using resolved paths)
            asset_paths = self._collect_asset_paths(prim, include_remote=download_textures)
            source_asset_paths[source.prim_path] = asset_paths

            # Compute hash using resolved asset paths for proper deduplication
            mat_hash = self._compute_material_hash(prim, asset_paths)
            source.material_hash = mat_hash
            source_hashes[source.prim_path] = mat_hash

        # PHASE 3: Transfer all unique assets globally BEFORE creating materials
        # This deduplicates assets across all materials
        all_asset_paths: Set[str] = set()
        for paths in source_asset_paths.values():
            all_asset_paths.update(paths)

        # Transfer assets and get mapping from original resolved path -> new relative path
        asset_path_mapping = self._transfer_all_assets(
            list(all_asset_paths),
            textures_output_path,
            materials_layer_dir,
            download_remote=download_textures,
        )
        self.log_operation(f"Transferred {len(asset_path_mapping)} unique assets")

        # Open or create materials layer
        materials_layer = Sdf.Layer.FindOrOpen(materials_output_path)
        if not materials_layer:
            materials_layer = Sdf.Layer.CreateNew(materials_output_path)
            self.log_operation(f"Created new materials layer: {materials_output_path}")
        else:
            self.log_operation(f"Opened existing materials layer: {materials_output_path}")
        utils.copy_stage_metadata(self.source_stage, materials_layer)
        mat_stage = Usd.Stage.Open(materials_layer)

        # Create /Materials scope in materials layer
        mat_stage.DefinePrim(_MATERIALS_SCOPE_PATH, _SCOPE_TYPE_NAME)

        # Group materials by their content hash for deduplication
        material_by_hash: Dict[str, MaterialEntry] = {}
        material_name_counter: Dict[str, int] = defaultdict(int)

        # If deduplication is enabled, scan existing materials in the layer first
        existing_count = 0
        if deduplicate:
            existing_materials = self._scan_existing_materials(mat_stage)
            for mat_hash, entry in existing_materials.items():
                material_by_hash[mat_hash] = entry
                material_name_counter[entry.name] += 1
            existing_count = len(existing_materials)
            if existing_count > 0:
                self.log_operation(f"Found {existing_count} existing materials in layer")

        new_count = 0
        reused_count = 0

        # PHASE 4: Group materials by hash and create entries in materials layer
        for source in material_sources:
            prim = self.source_stage.GetPrimAtPath(source.prim_path)
            if not prim.IsValid():
                continue

            mat_hash = source_hashes.get(source.prim_path)
            if not mat_hash:
                continue

            if mat_hash in material_by_hash:
                # Material already exists (either from this run or existing in layer)
                material_by_hash[mat_hash].sources.append(source)
                if material_by_hash[mat_hash].existing:
                    reused_count += 1
            else:
                # New unique material, create entry
                base_name = utils.sanitize_prim_name(prim.GetName(), prefix="mat_")
                material_name_counter[base_name] += 1
                if material_name_counter[base_name] > 1:
                    unique_name = f"{base_name}_{material_name_counter[base_name] - 1}"
                else:
                    unique_name = base_name

                entry = MaterialEntry(
                    name=unique_name,
                    material_layer_path=f"{_MATERIALS_SCOPE_PATH}/{unique_name}",
                    sources=[source],
                    existing=False,
                )
                material_by_hash[mat_hash] = entry
                entry.asset_paths = source_asset_paths.get(source.prim_path, [])

                # Copy material to materials layer with updated asset paths
                self._copy_material_to_layer(prim, entry, mat_stage, asset_path_mapping)
                new_count += 1

        self.log_operation(
            f"Processed {len(material_sources)} materials: "
            f"{new_count} new, {reused_count} reused from existing layer, "
            f"{len(material_sources) - new_count - reused_count} deduplicated within batch"
        )

        # Export materials layer
        materials_layer.Export(materials_output_path)

        # Collect all material bindings in the stage
        all_bindings = self._collect_all_material_bindings(scope)
        self.log_operation(f"Found {len(all_bindings)} material bindings")

        # PHASE 5: Update materials in their defining layers with instanceable references
        self._update_defining_layers(material_by_hash, materials_output_path)

        # PHASE 6: Ensure MaterialBindingAPI is applied to all prims with material bindings
        self._ensure_material_binding_api(all_bindings)

        # PHASE 7: Check for unused materials and remove their instanceable references
        self._cleanup_unused_material_references(material_by_hash, all_bindings)

        self.add_affected_stage(materials_layer_path)

        total_unique = len(material_by_hash)
        new_in_layer = total_unique - existing_count
        self.log_operation(
            f"MaterialsRoutingRule completed: {total_unique} unique materials in layer "
            f"({new_in_layer} new, {existing_count} pre-existing), "
            f"{len(all_bindings)} bindings updated"
        )

        return None

    def _get_scope_root(self, scope: str | None) -> Usd.Prim:
        """Get the root prim for the given scope.

        Args:
            scope: Optional root scope path to limit the search.

        Returns:
            The root prim to start traversal from.
        """
        if scope and scope != "/":
            scope_prim = self.source_stage.GetPrimAtPath(scope)
            if scope_prim.IsValid():
                return scope_prim
            self.log_operation(f"Scope path {scope} not found, using stage root")
        return self.source_stage.GetPseudoRoot()

    def _find_defining_layer(self, prim: Usd.Prim) -> Tuple[str, str]:
        """Find the layer where a prim is defined (has SpecifierDef).

        Args:
            prim: The prim to find the defining layer for.

        Returns:
            Tuple of (layer_identifier, prim_path_in_layer).
        """
        prim_path = prim.GetPath().pathString
        prim_stack = prim.GetPrimStack()

        if prim_stack:
            # Find the layer where this prim is actually defined
            for spec in prim_stack:
                if spec.specifier == Sdf.SpecifierDef:
                    return spec.layer.identifier, spec.path.pathString

            # Fallback to strongest opinion layer
            return prim_stack[0].layer.identifier, prim_path

        return self.source_stage.GetRootLayer().identifier, prim_path

    def _find_material_sources(self, scope: str | None) -> List[MaterialSource]:
        """Find all material prims and track their source information.

        Args:
            scope: Optional root scope path to limit the search.

        Returns:
            List of MaterialSource objects describing each material.
        """
        material_sources = []
        root_prim = self._get_scope_root(scope)

        for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies()):
            if not prim.IsA(UsdShade.Material):
                continue

            prim_path = prim.GetPath().pathString
            defining_layer_id, defining_prim_path = self._find_defining_layer(prim)

            material_sources.append(
                MaterialSource(
                    prim_path=prim_path,
                    defining_layer_id=defining_layer_id,
                    defining_prim_path=defining_prim_path,
                )
            )

        return material_sources

    def _scan_existing_materials(self, mat_stage: Usd.Stage) -> Dict[str, MaterialEntry]:
        """Scan existing materials in the materials layer and compute their hashes.

        This enables deduplication against previously imported materials.

        Args:
            mat_stage: The materials stage to scan.

        Returns:
            Dictionary mapping material hashes to MaterialEntry objects for existing materials.
        """
        existing: Dict[str, MaterialEntry] = {}

        materials_scope = mat_stage.GetPrimAtPath(_MATERIALS_SCOPE_PATH)
        if not materials_scope.IsValid():
            return existing

        for material_prim in materials_scope.GetChildren():
            if not material_prim.IsValid() or not material_prim.IsA(UsdShade.Material):
                continue

            material_path = material_prim.GetPath().pathString
            material_name = material_prim.GetName()

            # Compute hash for this existing material
            mat_hash = self._compute_material_hash(material_prim)

            entry = MaterialEntry(
                name=material_name,
                material_layer_path=material_path,
                sources=[],
                existing=True,
            )
            existing[mat_hash] = entry

        return existing

    def _compute_material_hash(self, prim: Usd.Prim, resolved_asset_paths: Optional[List[str]] = None) -> str:
        """Compute a hash of the material's properties for deduplication.

        Uses resolved (absolute) asset paths for hashing to ensure materials using
        identical assets hash the same regardless of how paths are written in USD.

        Args:
            prim: The material prim to hash.
            resolved_asset_paths: Optional list of resolved asset paths for consistent hashing.

        Returns:
            A hex string hash representing the material's content.
        """
        hasher = hashlib.sha256()
        material_root_path = prim.GetPath().pathString

        # Create a mapping from filename to resolved path for consistent hashing
        asset_by_filename: Dict[str, str] = {}
        if resolved_asset_paths:
            for resolved_path in sorted(resolved_asset_paths):
                asset_by_filename[os.path.basename(resolved_path)] = resolved_path

        def make_relative_path(abs_path: str) -> str:
            """Convert absolute path to relative path from material root."""
            if abs_path.startswith(material_root_path):
                return abs_path[len(material_root_path) :]
            return Sdf.Path(abs_path).name

        def hash_prim_recursive(p: Usd.Prim) -> None:
            hasher.update(p.GetTypeName().encode())

            for attr in sorted(p.GetAttributes(), key=lambda a: a.GetName()):
                if not attr.HasAuthoredValue() and not attr.GetConnections():
                    continue

                hasher.update(attr.GetName().encode())
                value = attr.Get()
                if value is not None:
                    if isinstance(value, Sdf.AssetPath):
                        filename = os.path.basename(value.path) if value.path else ""
                        hasher.update(asset_by_filename.get(filename, filename).encode())
                    else:
                        hasher.update(str(value).encode())

                for conn in sorted(attr.GetConnections(), key=lambda c: c.pathString):
                    hasher.update(make_relative_path(conn.pathString).encode())

            for rel in sorted(p.GetRelationships(), key=lambda r: r.GetName()):
                if not rel.HasAuthoredTargets():
                    continue
                hasher.update(rel.GetName().encode())
                for target in sorted(rel.GetTargets(), key=lambda t: t.pathString):
                    hasher.update(make_relative_path(target.pathString).encode())

            for child in sorted(p.GetFilteredChildren(Usd.TraverseInstanceProxies()), key=lambda c: c.GetName()):
                hasher.update(child.GetName().encode())
                hash_prim_recursive(child)

        hash_prim_recursive(prim)
        return hasher.hexdigest()[:_MATERIAL_HASH_LENGTH]

    def _collect_asset_paths(self, prim: Usd.Prim, include_remote: bool = False) -> List[str]:
        """Collect transferable asset paths used by a material and its shader children.

        Scans all attributes for asset path values and filters to only include
        transferable assets (textures, images). MDL files and other shader
        definitions are excluded as they have system dependencies.

        Args:
            prim: The material prim to scan for asset paths.
            include_remote: If True, include remote paths (e.g., omniverse://) for download.

        Returns:
            List of asset paths that should be transferred.
        """
        asset_paths: List[str] = []
        layer = prim.GetStage().GetRootLayer()
        layer_dir = os.path.dirname(layer.identifier)

        def is_transferable_asset(path: str) -> bool:
            """Check if an asset should be transferred based on its extension."""
            if not path:
                return False
            ext = os.path.splitext(path)[1].lower()
            return ext in _TRANSFERABLE_ASSET_EXTENSIONS

        def is_remote_path(path: str) -> bool:
            """Check if a path is a remote URL (not a local file)."""
            if not path:
                return False
            return path.startswith(("omniverse://", "http://", "https://"))

        def collect_from_prim(p: Usd.Prim) -> None:
            for attr in p.GetAttributes():
                if not attr.HasAuthoredValue():
                    continue

                value = attr.Get()
                if value is None:
                    continue

                if isinstance(value, Sdf.AssetPath):
                    raw_path = value.path
                    resolved_path = value.resolvedPath

                    if not is_transferable_asset(raw_path) and not is_transferable_asset(resolved_path):
                        continue

                    # Check for local file first
                    if resolved_path and os.path.exists(resolved_path):
                        asset_paths.append(resolved_path)
                    elif raw_path:
                        # Try resolving relative to layer
                        abs_path = os.path.normpath(os.path.join(layer_dir, raw_path))
                        if os.path.exists(abs_path):
                            asset_paths.append(abs_path)
                        elif include_remote and is_remote_path(raw_path):
                            # Include remote path for download
                            asset_paths.append(raw_path)
                        elif include_remote and is_remote_path(resolved_path):
                            asset_paths.append(resolved_path)

            for child in p.GetFilteredChildren(Usd.TraverseInstanceProxies()):
                collect_from_prim(child)

        collect_from_prim(prim)
        return list(set(asset_paths))

    def _is_remote_path(self, path: str) -> bool:
        """Check if a path is a remote URL."""
        return path.startswith(("omniverse://", "http://", "https://"))

    def _download_remote_asset(self, src_url: str, dst_path: str) -> bool:
        """Download a remote asset using omni.client.

        Args:
            src_url: The remote URL to download from.
            dst_path: The local destination path.

        Returns:
            True if download succeeded, False otherwise.
        """
        try:
            import omni.client

            result, _, content = omni.client.read_file(src_url)
            if result != omni.client.Result.OK:
                self.log_operation(f"Failed to read remote asset {src_url}: {result}")
                return False

            with open(dst_path, "wb") as f:
                f.write(memoryview(content))

            self.log_operation(f"Downloaded asset: {src_url} -> {dst_path}")
            return True
        except ImportError:
            self.log_operation("omni.client not available, cannot download remote assets")
            return False
        except Exception as e:
            self.log_operation(f"Failed to download asset {src_url}: {e}")
            return False

    def _transfer_all_assets(
        self,
        asset_paths: List[str],
        assets_output_path: str,
        materials_layer_dir: str,
        download_remote: bool = False,
    ) -> Dict[str, str]:
        """Transfer all assets to the designated folder, deduplicating globally.

        This transfers assets BEFORE materials are created, ensuring all materials
        reference the same transferred files.

        Args:
            asset_paths: List of absolute/resolved asset paths to transfer.
            assets_output_path: Absolute path to the assets output folder.
            materials_layer_dir: Directory of the materials layer (for relative path computation).
            download_remote: If True, download remote assets using omni.client.

        Returns:
            Dictionary mapping original resolved path -> new relative path from materials layer.
        """
        path_mapping: Dict[str, str] = {}
        used_filenames: Dict[str, str] = {}

        for src_path in sorted(set(asset_paths)):
            if not src_path:
                continue

            is_remote = self._is_remote_path(src_path)

            # Skip remote paths if download is disabled
            if is_remote and not download_remote:
                continue

            # Skip local paths that don't exist
            if not is_remote and not os.path.exists(src_path):
                continue

            filename = os.path.basename(src_path)
            dst_path = os.path.join(assets_output_path, filename)

            # Handle filename collisions
            if filename in used_filenames:
                existing_src = used_filenames[filename]
                if existing_src == src_path:
                    rel_path = os.path.relpath(dst_path, materials_layer_dir)
                    path_mapping[src_path] = rel_path
                    continue
                elif not is_remote and os.path.exists(dst_path) and utils.files_are_identical(src_path, dst_path):
                    rel_path = os.path.relpath(dst_path, materials_layer_dir)
                    path_mapping[src_path] = rel_path
                    continue
                else:
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while filename in used_filenames or os.path.exists(dst_path):
                        filename = f"{base}_{counter}{ext}"
                        dst_path = os.path.join(assets_output_path, filename)
                        counter += 1

            # Transfer the file if not already there
            if not os.path.exists(dst_path):
                if is_remote:
                    if not self._download_remote_asset(src_path, dst_path):
                        continue
                else:
                    try:
                        shutil.copy2(src_path, dst_path)
                        self.log_operation(f"Copied asset: {src_path} -> {dst_path}")
                    except Exception as e:
                        self.log_operation(f"Failed to copy asset {src_path}: {e}")
                        continue

            used_filenames[filename] = src_path
            rel_path = os.path.relpath(dst_path, materials_layer_dir)
            path_mapping[src_path] = rel_path

        return path_mapping

    def _copy_material_to_layer(
        self,
        prim: Usd.Prim,
        entry: MaterialEntry,
        mat_stage: Usd.Stage,
        asset_path_mapping: Dict[str, str],
    ) -> None:
        """Copy a material prim to the materials layer.

        Uses composed stage copy as primary method to handle instance proxies
        and materials from references properly. Falls back to Sdf.CopySpec
        if composed stage copy fails.

        Args:
            prim: The source material prim.
            entry: The MaterialEntry describing where to store it.
            mat_stage: The materials stage to copy to.
            asset_path_mapping: Mapping from original resolved path to new relative path.
        """
        dst_layer = mat_stage.GetRootLayer()
        src_prim_path = prim.GetPath().pathString

        # Primary: Use composed stage copy to ensure shader children are captured
        # This handles instance proxies and materials from references properly
        copy_succeeded = utils.copy_prim_from_composed_stage(
            prim,
            dst_layer,
            entry.material_layer_path,
            remap_connections_from=src_prim_path,
            remap_connections_to=entry.material_layer_path,
        )

        if not copy_succeeded:
            # Fallback: try Sdf.CopySpec if composed stage copy fails
            is_instance_proxy = prim.IsInstanceProxy()
            if not is_instance_proxy:
                prim_stack = prim.GetPrimStack()
                for prim_spec in prim_stack:
                    if prim_spec.specifier == Sdf.SpecifierDef:
                        src_material_layer = prim_spec.layer
                        src_material_path = prim_spec.path
                        Sdf.CopySpec(
                            src_material_layer, src_material_path, dst_layer, Sdf.Path(entry.material_layer_path)
                        )
                        copy_succeeded = True
                        break

        if not copy_succeeded:
            self.log_operation(f"Failed to copy material {src_prim_path}")
            return

        # Clear instanceable flags recursively to ensure shader children are accessible
        copied_spec = dst_layer.GetPrimAtPath(entry.material_layer_path)
        if copied_spec:
            utils.clear_instanceable_recursive(copied_spec)

        # Update asset paths to point to transferred files
        if asset_path_mapping:
            self._update_asset_paths_in_material(entry.material_layer_path, dst_layer, asset_path_mapping)

        self.log_operation(f"Copied material {prim.GetPath()} to {entry.material_layer_path}")

    def _update_asset_paths_in_material(
        self,
        material_path: str,
        layer: Sdf.Layer,
        path_mapping: Dict[str, str],
    ) -> None:
        """Update asset paths in a material spec.

        Args:
            material_path: Path to the material in the layer.
            layer: The layer containing the material.
            path_mapping: Dictionary mapping old resolved paths to new relative paths.
        """
        # Build lookup tables for fast matching
        by_resolved: Dict[str, str] = path_mapping.copy()
        by_filename: Dict[str, str] = {}
        for src_path, new_rel_path in path_mapping.items():
            filename = os.path.basename(src_path)
            by_filename[filename] = new_rel_path

        def update_spec_recursive(prim_spec: Sdf.PrimSpec) -> None:
            if prim_spec is None:
                return

            for attr_name in list(prim_spec.attributes.keys()):
                attr_spec = prim_spec.attributes[attr_name]
                if attr_spec.default is None:
                    continue

                # Check if this is an asset attribute
                value = attr_spec.default
                if isinstance(value, Sdf.AssetPath):
                    old_path = value.path
                    old_resolved = value.resolvedPath
                    new_rel_path = None

                    # Try matching by resolved path first
                    if old_resolved and old_resolved in by_resolved:
                        new_rel_path = by_resolved[old_resolved]
                    elif old_path and old_path in by_resolved:
                        new_rel_path = by_resolved[old_path]
                    else:
                        # Fall back to filename matching
                        filename = os.path.basename(old_path) if old_path else None
                        if filename and filename in by_filename:
                            new_rel_path = by_filename[filename]

                    if new_rel_path:
                        attr_spec.default = Sdf.AssetPath(new_rel_path)

            # Recurse into children
            for child_spec in prim_spec.nameChildren:
                update_spec_recursive(child_spec)

        material_spec = layer.GetPrimAtPath(material_path)
        if material_spec:
            update_spec_recursive(material_spec)

    def _collect_all_material_bindings(self, scope: str | None) -> List[MaterialBinding]:
        """Collect all material bindings in the stage.

        Args:
            scope: Optional root scope path to limit the search.

        Returns:
            List of MaterialBinding objects describing each binding.
        """
        bindings: List[MaterialBinding] = []
        root_prim = self._get_scope_root(scope)

        for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies()):
            # Check for material bindings via API or relationships
            has_binding_api = prim.HasAPI(UsdShade.MaterialBindingAPI)
            has_binding_rel = any(r.GetName().startswith("material:binding") for r in prim.GetRelationships())

            if not has_binding_api and not has_binding_rel:
                continue

            binding_api = UsdShade.MaterialBindingAPI(prim)
            prim_path = prim.GetPath().pathString

            for purpose in _MATERIAL_PURPOSES:
                binding = binding_api.GetDirectBinding(materialPurpose=purpose)
                mat_path = binding.GetMaterialPath()
                if mat_path:
                    bindings.append(MaterialBinding(prim_path, mat_path.pathString, purpose))

        return bindings

    def _get_or_open_layer(
        self,
        layer_id: str,
        layer_cache: Dict[str, Sdf.Layer],
    ) -> Optional[Sdf.Layer]:
        """Get a layer from cache or open it.

        Args:
            layer_id: The layer identifier.
            layer_cache: Cache of opened layers (modified in place).

        Returns:
            The layer, or None if it could not be opened.
        """
        if layer_id in layer_cache:
            return layer_cache[layer_id]

        source_layer = self.source_stage.GetRootLayer()
        if layer_id == source_layer.identifier:
            layer_cache[layer_id] = source_layer
            return source_layer

        layer = Sdf.Layer.FindOrOpen(layer_id)
        if layer:
            layer_cache[layer_id] = layer
        return layer

    def _update_defining_layers(
        self,
        material_by_hash: Dict[str, MaterialEntry],
        materials_layer_abs_path: str,
    ) -> None:
        """Update materials in their defining layers with instanceable references.

        Args:
            material_by_hash: Dictionary mapping material hashes to MaterialEntry objects.
            materials_layer_abs_path: Absolute path to the materials layer file.
        """
        source_layer = self.source_stage.GetRootLayer()
        layer_cache: Dict[str, Sdf.Layer] = {}
        processed_paths: Set[str] = set()
        processed_count = 0

        with Sdf.ChangeBlock():
            for entry in material_by_hash.values():
                for source in entry.sources:
                    if source.prim_path in processed_paths:
                        continue
                    processed_paths.add(source.prim_path)

                    target_layer = self._get_or_open_layer(source.defining_layer_id, layer_cache)
                    if not target_layer:
                        self.log_operation(f"Could not open layer {source.defining_layer_id}")
                        continue

                    # Get or create prim spec
                    prim_spec = target_layer.GetPrimAtPath(source.defining_prim_path)
                    if not prim_spec:
                        utils.ensure_prim_hierarchy(target_layer, source.defining_prim_path)
                        prim_spec = utils.create_prim_spec(
                            target_layer, source.defining_prim_path, type_name=_MATERIAL_TYPE_NAME
                        )

                    if prim_spec:
                        # Clear existing content
                        utils.clear_composition_arcs(prim_spec, make_explicit=True)
                        for child_name in [c.name for c in prim_spec.nameChildren]:
                            del prim_spec.nameChildren[child_name]
                        for prop_name in [p.name for p in prim_spec.properties]:
                            del prim_spec.properties[prop_name]

                        # Add instanceable reference to materials layer
                        prim_spec.referenceList.ClearEdits()
                        rel_path = utils.get_relative_layer_path(target_layer, materials_layer_abs_path)
                        prim_spec.referenceList.Prepend(Sdf.Reference(rel_path, entry.material_layer_path))
                        prim_spec.instanceable = True
                        processed_count += 1

        # Save modified layers (except source layer)
        for layer_id, layer in layer_cache.items():
            if layer != source_layer:
                layer.Save()
                self.add_affected_stage(layer_id)
                self.log_operation(f"Saved modified layer: {layer_id}")

        self.log_operation(f"Updated {processed_count} materials in their defining layers")

    def _ensure_material_binding_api(self, all_bindings: List[MaterialBinding]) -> None:
        """Ensure MaterialBindingAPI is applied to all prims with material bindings.

        Args:
            all_bindings: List of all material bindings in the stage.
        """
        source_layer = self.source_stage.GetRootLayer()
        applied_count = 0

        # Get unique prim paths with bindings
        prim_paths_with_bindings: Set[str] = {binding.prim_path for binding in all_bindings}

        with Sdf.ChangeBlock():
            for prim_path in prim_paths_with_bindings:
                prim = self.source_stage.GetPrimAtPath(prim_path)
                if not prim.IsValid():
                    continue

                # Check if MaterialBindingAPI is already applied
                if prim.HasAPI(UsdShade.MaterialBindingAPI):
                    continue

                # Apply MaterialBindingAPI
                prim_spec = source_layer.GetPrimAtPath(prim_path)
                if not prim_spec:
                    prim_spec = Sdf.CreatePrimInLayer(source_layer, prim_path)
                    if prim_spec:
                        prim_spec.specifier = Sdf.SpecifierOver

                if prim_spec:
                    # Add MaterialBindingAPI to applied schemas
                    existing_schemas = prim_spec.GetInfo("apiSchemas")
                    if existing_schemas:
                        schema_list = list(existing_schemas.GetAppliedItems())
                    else:
                        schema_list = []

                    if "MaterialBindingAPI" not in schema_list:
                        schema_list.append("MaterialBindingAPI")
                        prim_spec.SetInfo("apiSchemas", Sdf.TokenListOp.CreateExplicit(schema_list))
                        applied_count += 1

        if applied_count > 0:
            self.log_operation(f"Applied MaterialBindingAPI to {applied_count} prims")

    def _cleanup_unused_material_references(
        self,
        material_by_hash: Dict[str, MaterialEntry],
        all_bindings: List[MaterialBinding],
    ) -> None:
        """Remove instanceable references for materials that are not bound to any surface.

        Args:
            material_by_hash: Dictionary mapping material hashes to MaterialEntry objects.
            all_bindings: List of all material bindings in the stage.
        """
        source_layer = self.source_stage.GetRootLayer()
        bound_material_paths: Set[str] = {b.material_path for b in all_bindings}
        layer_cache: Dict[str, Sdf.Layer] = {}
        removed_count = 0

        with Sdf.ChangeBlock():
            for entry in material_by_hash.values():
                for source in entry.sources:
                    if source.prim_path in bound_material_paths:
                        continue

                    target_layer = self._get_or_open_layer(source.defining_layer_id, layer_cache)
                    if not target_layer:
                        continue

                    prim_spec = target_layer.GetPrimAtPath(source.defining_prim_path)
                    if prim_spec:
                        parent_spec = target_layer.GetPrimAtPath(Sdf.Path(source.defining_prim_path).GetParentPath())
                        if parent_spec and prim_spec.name in parent_spec.nameChildren:
                            del parent_spec.nameChildren[prim_spec.name]
                            removed_count += 1

        for layer_id, layer in layer_cache.items():
            if layer != source_layer:
                layer.Save()
                self.add_affected_stage(layer_id)

        if removed_count > 0:
            self.log_operation(f"Removed {removed_count} unused material references")
