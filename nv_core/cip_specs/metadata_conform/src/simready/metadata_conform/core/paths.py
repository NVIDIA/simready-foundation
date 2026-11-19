# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Deterministic FET_031 authored-path repair and FET_033 metadata stamping."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from pxr import Gf, Sdf, Usd

# The identity subset SR.001 requires directly in root-layer customLayerData.
# It is narrower than the SR.003 field set: author, category, licensing, and
# the derived physical values are nested-only provenance.
SR_001_IDENTITY_FIELDS = (
    "asset_name",
    "asset_type",
    "source_file",
    "usd_date_generated",
)


class ExternalLayerError(ValueError):
    """A composed layer is outside the caller-owned package."""

    def __init__(self, paths: tuple[str, ...]):
        self.paths = paths
        super().__init__(
            "Copy and remap external layers into the staged package before repair: "
            + ", ".join(paths)
        )


@dataclass(frozen=True)
class PathRepair:
    """One rewritten authored asset path, kept as AA.001 evidence."""

    layer: str
    original: str
    replacement: str

    def to_dict(self) -> dict[str, str]:
        return {
            "layer": self.layer,
            "original": self.original,
            "replacement": self.replacement,
        }


def _replacement(layer_path: Path, package_root: Path, raw: str) -> str | None:
    if not raw or raw.startswith(("anon:", "http:", "https:", "omniverse:")):
        return None
    normalized = raw.replace("\\", "/")
    is_absolute = Path(normalized).is_absolute() or (
        len(normalized) > 2 and normalized[1] == ":"
    )
    is_unanchored = not is_absolute and not normalized.startswith(("./", "../"))
    if not (is_absolute or is_unanchored):
        return None
    candidate = PurePosixPath(normalized)
    matches = tuple(
        path for path in package_root.rglob(candidate.name) if path.is_file()
    )
    if len(matches) != 1:
        return None
    relative = os.path.relpath(matches[0], layer_path.parent)
    return PurePosixPath(relative.replace("\\", "/")).as_posix()


def _walk_prim_specs(prim_spec: Sdf.PrimSpec):
    yield prim_spec
    for child in prim_spec.nameChildren:
        yield from _walk_prim_specs(child)
    for variant_set in prim_spec.variantSets.values():
        for variant in variant_set.variants.values():
            yield from _walk_prim_specs(variant.primSpec)


def _replace_reference(item: Sdf.Reference, asset_path: str) -> Sdf.Reference:
    return Sdf.Reference(
        assetPath=asset_path,
        primPath=item.primPath,
        layerOffset=item.layerOffset,
        customData=item.customData,
    )


def _replace_payload(item: Sdf.Payload, asset_path: str) -> Sdf.Payload:
    return Sdf.Payload(
        assetPath=asset_path,
        primPath=item.primPath,
        layerOffset=item.layerOffset,
    )


def _rewrite_composition_list(
    list_proxy: Any,
    layer_path: Path,
    package: Path,
    layer_evidence: str,
) -> list[PathRepair]:
    repairs = []
    for field in (
        "explicitItems",
        "prependedItems",
        "appendedItems",
        "addedItems",
        "deletedItems",
        "orderedItems",
    ):
        items = list(getattr(list_proxy, field))
        if not items:
            continue
        rewritten = []
        changed = False
        for item in items:
            raw = getattr(item, "assetPath", "")
            replacement = _replacement(layer_path, package, raw) if raw else None
            if replacement and replacement != raw:
                changed = True
                repairs.append(PathRepair(layer_evidence, raw, replacement))
                if isinstance(item, Sdf.Reference):
                    item = _replace_reference(item, replacement)
                else:
                    item = _replace_payload(item, replacement)
            rewritten.append(item)
        if changed:
            setattr(list_proxy, field, rewritten)
    return repairs


def _rewrite_attribute_paths(
    prim_spec: Sdf.PrimSpec,
    layer_path: Path,
    package: Path,
    layer_evidence: str,
) -> list[PathRepair]:
    """Repair ordinary asset-valued attributes such as texture inputs.

    Composition arcs are handled separately. Asset attributes are the other
    place an authored package-local path can break. MDL module references are
    excluded because file existence does not prove their import closure.
    """
    repairs = []
    for attr_spec in prim_spec.attributes:
        # MDL source assets are module references, not ordinary file links.
        # A package-local file with the same basename may have unresolved
        # imports (for example OmniPBR.mdl imports OmniPBR_ClearCoat.mdl).
        # Path existence alone cannot prove that rewriting the module is safe.
        if attr_spec.name == "info:mdl:sourceAsset":
            continue
        if attr_spec.typeName == Sdf.ValueTypeNames.Asset:
            raw = getattr(attr_spec.default, "path", "")
            replacement = _replacement(layer_path, package, raw) if raw else None
            if replacement and replacement != raw:
                attr_spec.default = Sdf.AssetPath(replacement)
                repairs.append(PathRepair(layer_evidence, raw, replacement))
        elif attr_spec.typeName == Sdf.ValueTypeNames.AssetArray:
            rewritten = []
            changed = False
            for item in list(attr_spec.default or ()):
                raw = getattr(item, "path", "")
                replacement = _replacement(layer_path, package, raw) if raw else None
                if replacement and replacement != raw:
                    changed = True
                    repairs.append(PathRepair(layer_evidence, raw, replacement))
                    item = Sdf.AssetPath(replacement)
                rewritten.append(item)
            if changed:
                attr_spec.default = rewritten
    return repairs


def _repair_layer_paths(layer: Sdf.Layer, package: Path) -> list[PathRepair]:
    raw_layer_path = layer.realPath or layer.identifier
    if not raw_layer_path or raw_layer_path.startswith("anon:"):
        return []
    layer_path = Path(raw_layer_path).resolve()
    if not layer_path.is_relative_to(package.resolve()):
        raise ExternalLayerError((str(layer_path),))
    if not layer_path.is_file():
        return []
    layer_evidence = str(layer_path)
    repairs = []
    for index, raw in enumerate(tuple(layer.subLayerPaths)):
        replacement = _replacement(layer_path, package, raw)
        if replacement and replacement != raw:
            layer.subLayerPaths[index] = replacement
            repairs.append(PathRepair(layer_evidence, raw, replacement))
    for root_prim in layer.rootPrims:
        for prim_spec in _walk_prim_specs(root_prim):
            repairs.extend(
                _rewrite_composition_list(
                    prim_spec.referenceList, layer_path, package, layer_evidence
                )
            )
            repairs.extend(
                _rewrite_composition_list(
                    prim_spec.payloadList, layer_path, package, layer_evidence
                )
            )
            repairs.extend(
                _rewrite_attribute_paths(prim_spec, layer_path, package, layer_evidence)
            )
    if repairs:
        layer.Save()
    return repairs


def repair_simple_asset_paths(
    asset_path: Path, package_root: Path | None = None
) -> tuple[PathRepair, ...]:
    """Rewrite unanchored or absolute authored paths that resolve inside the package.

    Args:
        asset_path: Root USD of the package.
        package_root: Search root for package-local matches. Defaults to the
            NP.005 layout, where the root USD lives one directory below the
            package root.
    """
    asset = Path(asset_path).resolve()
    package = Path(package_root).resolve() if package_root else asset.parent.parent
    stage = Usd.Stage.Open(str(asset))
    if stage is None:
        return ()
    layers = stage.GetUsedLayers()
    # Preflight the entire set before mutating even a package-local layer.
    # Resolve symlinks/junctions as well as absolute and ../ composition arcs.
    external = tuple(sorted({
        str(Path(layer.realPath or layer.identifier).resolve())
        for layer in layers
        if not layer.anonymous
        and not Path(layer.realPath or layer.identifier).resolve().is_relative_to(package)
    }))
    if external:
        raise ExternalLayerError(external)
    repairs = []
    for layer in layers:
        repairs.extend(_repair_layer_paths(layer, package))
    return tuple(repairs)


def read_existing_metadata(asset_path: Path) -> dict[str, Any]:
    """Read the nested SR.003 ``SimReady_Metadata`` dictionary."""
    stage = Usd.Stage.Open(str(Path(asset_path).resolve()))
    if stage is None:
        return {}
    value = stage.GetRootLayer().customLayerData.get("SimReady_Metadata", {})
    return dict(value) if isinstance(value, dict) else {}


def read_top_level_metadata(asset_path: Path) -> dict[str, Any]:
    """Read root-layer customLayerData keys authored outside SimReady_Metadata."""
    stage = Usd.Stage.Open(str(Path(asset_path).resolve()))
    if stage is None:
        return {}
    custom = dict(stage.GetRootLayer().customLayerData)
    custom.pop("SimReady_Metadata", None)
    return custom


def stamp_metadata(asset_path: Path, values: dict[str, Any]) -> None:
    """Merge ``values`` into the root layer's nested ``SimReady_Metadata``.

    The four SR.001 identity keys are additionally written at the top level of
    ``customLayerData``. SR.001 states that it deliberately does not flatten
    nested metadata, so an asset conformed for SR.003 alone still reads as
    missing its identity under any profile that pins
    ``FET_000_STANDARD@0.1.0``. Only these four are lifted: SR.001 asks for no
    others, and SR.004 forbids duplication between the USD and a sidecar
    rather than within the layer, so both contracts hold at once.
    """
    stage = Usd.Stage.Open(str(Path(asset_path).resolve()))
    if stage is None:
        raise ValueError(f"Failed to open USD stage: {asset_path}")
    root = stage.GetRootLayer()
    custom = dict(root.customLayerData)
    current = dict(custom.get("SimReady_Metadata", {}))
    for field, value in values.items():
        if value is None:
            continue
        if field == "asset_extents":
            value = Gf.Vec3f(*(float(item) for item in value))
        elif field == "rigid_body_count":
            value = int(value)
        elif field == "mass":
            value = float(value)
        current[field] = value
    custom["SimReady_Metadata"] = current
    for field in SR_001_IDENTITY_FIELDS:
        value = current.get(field)
        if value is not None:
            custom[field] = value
    root.customLayerData = custom
    if not root.Save():
        raise OSError(f"Failed to save metadata to: {asset_path}")
