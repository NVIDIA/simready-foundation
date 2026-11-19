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
"""SimReady fixes for the public ``isaacsim-asset-isolated==6.2.0.1`` transformer.

Each fix is small and version-guarded by :mod:`.apply`. Remove a fix once a
published isolated wheel contains it; see ``UPSTREAM.md``.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile

from isaacsim.asset.transformer import manager as _manager
from isaacsim.asset.transformer.rules import utils as _rule_utils
from isaacsim.asset.transformer.rules.perf.geometries import GeometriesRoutingRule
from isaacsim.asset.transformer.utils import make_explicit_relative
from pxr import Sdf, Usd, UsdUtils

# Names the copied publish function resolves from the upstream manager module.
_LOGGER = _manager._LOGGER
_collect_composition_errors = _manager._collect_composition_errors
_find_cached_layers = _manager._find_cached_layers
_relocate_path = _manager._relocate_path

_UPSTREAM_MAKE_REFERENCES_NON_INSTANCEABLE = GeometriesRoutingRule._make_references_non_instanceable
_UPSTREAM_COPY_FILE_TO_DIRECTORY = _rule_utils.copy_file_to_directory


def ensure_owner_writable(path: str | os.PathLike[str]) -> None:
    """Add the owner write bit to *path* when it is missing.

    ``shutil.copy2`` preserves the source mode, so copies of a read-only source
    package stay read-only and the rules that re-save them fail.
    """
    mode = os.stat(path).st_mode
    if not mode & stat.S_IWUSR:
        os.chmod(path, mode | stat.S_IWUSR)


def _is_search_path(asset_path: str) -> bool:
    """Return whether *asset_path* is a USD search-path identifier."""
    path, _ = Sdf.Layer.SplitIdentifier(asset_path)
    normalized = path.replace("\\", "/")
    return bool(normalized) and not os.path.isabs(path) and not normalized.startswith(("./", "../"))


def relativize_package_paths(layer: Sdf.Layer, package_root: str) -> bool:
    """Rewrite absolute in-package asset paths in *layer* as explicit relative paths.

    ``Usd.Stage.Flatten`` anchors every relative asset path and stamps the layer
    documentation with the absolute source path. Returns whether the layer changed.
    """
    layer_dir = os.path.dirname(os.path.abspath(layer.realPath))
    root = os.path.normcase(os.path.abspath(package_root))
    changed = False

    def remap(asset_path: str) -> str:
        nonlocal changed
        if not asset_path or "://" in asset_path or not os.path.isabs(asset_path):
            return asset_path
        absolute = os.path.abspath(asset_path)
        try:
            inside = os.path.commonpath([os.path.normcase(absolute), root]) == root
        except ValueError:
            inside = False
        if not inside:
            return asset_path
        changed = True
        return make_explicit_relative(os.path.relpath(absolute, layer_dir).replace(os.sep, "/"))

    UsdUtils.ModifyAssetPaths(layer, remap)
    if layer.documentation.startswith("Generated from Composed Stage"):
        layer.documentation = ""
        changed = True
    return changed


def _make_references_non_instanceable(self) -> None:
    """Run the upstream pre-pass, then undo the paths its re-flatten anchored.

    The upstream pre-pass re-flattens the working layer, which turns the
    package-relative default-prim ``assetInfo:identifier`` absolute (AA.001).
    """
    _UPSTREAM_MAKE_REFERENCES_NON_INSTANCEABLE(self)
    layer = self.source_stage.GetRootLayer()
    if layer.realPath and relativize_package_paths(layer, self.package_root):
        layer.Save()


def copy_file_to_directory(
    src_path: str,
    dest_dir: str,
    existing_collected: dict[str, str] | None = None,
) -> str | None:
    """Delegate to the public helper, then make the copied file owner-writable."""
    dest_path = _UPSTREAM_COPY_FILE_TO_DIRECTORY(src_path, dest_dir, existing_collected)
    if dest_path and os.path.isfile(dest_path):
        ensure_owner_writable(dest_path)
    return dest_path


# Copied verbatim from isaacsim-asset-isolated 6.2.0.1 manager.py except for the
# marked ``_is_search_path`` guard in ``relocate_asset``.
def _publish_staged_package(staging_root: str, output_root: str, output_stage_path: str | None) -> bool:
    """Prepare relocated files, then publish with rollback on failure.

    Args:
        staging_root: Directory containing this conversion's outputs.
        output_root: Destination package directory.
        output_stage_path: Final working stage in the staging directory.

    Returns:
        Whether the final composition diagnostic was incomplete.

    Raises:
        RuntimeError: If a generated layer cannot be prepared or refreshed.
        OSError: If publication or rollback fails.
    """
    transaction_root = tempfile.mkdtemp(prefix=".asset-publication-", dir=output_root)
    preserve_backup = False
    try:
        pending = []
        cached_layers = []
        for directory, _, filenames in os.walk(staging_root):
            for filename in filenames:
                source = os.path.join(directory, filename)
                relative = os.path.relpath(source, staging_root)
                destination = os.path.join(output_root, relative)
                prepared = os.path.join(transaction_root, "prepared", relative)
                backup = os.path.join(transaction_root, "backup", relative)
                os.makedirs(os.path.dirname(prepared), exist_ok=True)
                if os.path.splitext(filename)[1].lower() in (".usd", ".usda", ".usdc"):
                    source_layer = Sdf.Layer.FindOrOpen(source)
                    if source_layer is None:
                        raise RuntimeError(f"Cannot publish generated USD layer: {source}")
                    layer = Sdf.Layer.CreateAnonymous()
                    layer.TransferContent(source_layer)
                    source_layer = None

                    def relocate_asset(asset_path: str) -> str:
                        """Re-anchor a path from the generated layer to its final location.

                        Args:
                            asset_path: Authored asset path or layer identifier.

                        Returns:
                            Identifier resolving to the same asset after publication.
                        """
                        if not asset_path or "://" in asset_path or asset_path.startswith("anon:"):
                            return asset_path
                        # SimReady fix: keep search-path identifiers (for example the
                        # built-in ``OmniPBR.mdl``) bare when no package file backs
                        # them. Anchoring them as ``./name`` points at a missing file.
                        if _is_search_path(asset_path) and not os.path.exists(
                            os.path.join(directory, Sdf.Layer.SplitIdentifier(asset_path)[0])
                        ):
                            return asset_path
                        path, arguments = Sdf.Layer.SplitIdentifier(asset_path)
                        absolute = os.path.normpath(os.path.join(directory, path))
                        relocated = _relocate_path(absolute, staging_root, output_root)
                        if not os.path.isabs(path):
                            relocated = make_explicit_relative(os.path.relpath(relocated, os.path.dirname(destination)))
                        return Sdf.Layer.CreateIdentifier(relocated.replace(os.sep, "/"), arguments)

                    UsdUtils.ModifyAssetPaths(layer, relocate_asset)
                    if not layer.Export(prepared):
                        raise RuntimeError(f"Failed to prepare generated USD layer: {destination}")
                    layer = None
                    for existing in _find_cached_layers(destination):
                        snapshot = Sdf.Layer.CreateAnonymous()
                        snapshot.TransferContent(existing)
                        cached_layers.append((existing, snapshot))
                else:
                    shutil.copy2(source, prepared)
                if os.path.lexists(destination):
                    os.makedirs(os.path.dirname(backup), exist_ok=True)
                    shutil.copy2(destination, backup, follow_symlinks=False)
                else:
                    backup = None
                pending.append((prepared, destination, backup))

        published = []
        diagnostics_truncated = False
        try:
            for prepared, destination, backup in pending:
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                try:
                    os.replace(prepared, destination)
                except PermissionError as error:
                    raise PermissionError(
                        error.errno,
                        "Cannot publish the generated file. Close stages or applications holding the destination "
                        "file, check write permissions, and retry, or choose a different package_root.",
                        destination,
                    ) from error
                published.append((destination, backup))
            for existing, _ in cached_layers:
                if not existing.Reload(force=True):
                    raise RuntimeError(f"Failed to refresh published USD layer: {existing.identifier}")
            if output_stage_path:
                final_path = _relocate_path(output_stage_path, staging_root, output_root)
                published_stage = Usd.Stage.Open(final_path)
                try:
                    errors, diagnostics_truncated = _collect_composition_errors(published_stage)
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Composition error collection failed for %s", final_path)
                    errors = []
                    diagnostics_truncated = True
                finally:
                    published_stage = None
                if errors:
                    raise RuntimeError(
                        f"Replacement would produce invalid USD composition at {final_path}: {errors[0]}. "
                        "When exporting into the source package, flatten its composition first or use a new destination."
                    )
        except Exception:  # noqa: BLE001
            # Restore filesystem contents before cached layers so composition
            # resolves against the previous complete package during rollback.
            preserve_backup = True
            rollback_errors = []
            for destination, backup in reversed(published):
                try:
                    if backup is None:
                        os.remove(destination)
                    else:
                        os.replace(backup, destination)
                except OSError as error:
                    rollback_errors.append(str(error))
            for existing, snapshot in cached_layers:
                try:
                    existing.TransferContent(snapshot)
                except Exception as error:  # noqa: BLE001
                    rollback_errors.append(f"{existing.identifier}: {error}")
            if rollback_errors:
                raise RuntimeError(
                    f"Package publication and rollback failed. Recovery files are preserved at {transaction_root}: "
                    + "; ".join(rollback_errors)
                ) from None
            preserve_backup = False
            raise
        return diagnostics_truncated
    finally:
        if not preserve_backup:
            shutil.rmtree(transaction_root)
