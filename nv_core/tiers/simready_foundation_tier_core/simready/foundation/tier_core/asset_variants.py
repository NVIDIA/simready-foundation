# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Read, enumerate, and recompose SimReady asset-variation variant sets.

Asset variations are mutually exclusive, composed alternatives of one asset that
preserve the asset's **visual envelope** and **collision envelope** and are
discoverable through ``customLayerData.SimReady_Metadata.Variants.<Category>``.
This module is the shared read/compute layer for the ``asset_variants``
validators (``AV.*``) and the ``fet013``-``fet016`` runtime tests, mirroring the
role ``asset_frame.py`` plays for Object Forward.

The physics-runtime ``Variants.Physics`` category is owned by the
``runtime_variants`` capability (``RV.*``) and is **reserved**: an asset
variation must not author or reuse it here.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from pxr import Gf, Usd, UsdGeom, UsdPhysics

# --------------------------------------------------------------------------- #
# Metadata location and vocabulary
# --------------------------------------------------------------------------- #
SIMREADY_METADATA_KEY = "SimReady_Metadata"
VARIANTS_KEY = "Variants"

# Category owned by runtime_variants (RV.*); never authored as an asset variation.
RESERVED_CATEGORY = "Physics"

# Category tokens shipped by the 0.1.0 asset-variation feature family.
CATEGORY_REPRESENTATION = "Representation"
CATEGORY_MESH_VARIANT = "MeshVariant"
CATEGORY_COLLISION = "Collision"
CATEGORY_APPEARANCE = "Appearance"

KNOWN_CATEGORIES = (
    CATEGORY_REPRESENTATION,
    CATEGORY_MESH_VARIANT,
    CATEGORY_COLLISION,
    CATEGORY_APPEARANCE,
)

# Impact classes. A visual-only variation disturbs no simulation-relevant data;
# a simulation-affecting variation declares the domain it changes.
IMPACT_VISUAL_ONLY = "visual-only"
IMPACT_SIMULATION_AFFECTING = "simulation-affecting"
IMPACT_CLASSES = (IMPACT_VISUAL_ONLY, IMPACT_SIMULATION_AFFECTING)

# Required keys on every discovery-metadata entry. ``prim``, ``variantSetName``
# and ``activateOption`` match the runtime_variants entry shape; ``category``
# and ``impactClass`` carry the asset-variation contract.
REQUIRED_ENTRY_KEYS = ("prim", "variantSetName", "category", "default", "impactClass")

# Default envelope tolerance (meters), applied after unit scaling. Kept loose
# enough to absorb representation re-meshing noise but tight enough to reject a
# genuine resize.
ENVELOPE_TOLERANCE_M = 1e-3


def _simready_metadata(stage: Usd.Stage) -> dict:
    custom_layer_data = stage.GetRootLayer().customLayerData or {}
    return custom_layer_data.get(SIMREADY_METADATA_KEY, {}) or {}


def variation_metadata(stage: Usd.Stage) -> Dict[str, dict]:
    """Return ``SimReady_Metadata.Variants`` minus the reserved ``Physics`` bucket.

    The result maps a category token to its per-variant-set entry dict, for
    every category except ``Physics`` (which belongs to ``runtime_variants``).
    """
    variants = _simready_metadata(stage).get(VARIANTS_KEY, {}) or {}
    return {
        category: entries
        for category, entries in variants.items()
        if category != RESERVED_CATEGORY and isinstance(entries, dict)
    }


def iter_variation_entries(stage: Usd.Stage) -> Iterable[Tuple[str, str, dict]]:
    """Yield ``(category, variant_set_name, entry)`` for every declared variation set."""
    for category, entries in variation_metadata(stage).items():
        for variant_set_name, entry in entries.items():
            if isinstance(entry, dict):
                yield category, variant_set_name, entry


def master_set_name(category: str) -> str:
    """The master (whole-asset) variant-set name for a category."""
    return category


def is_per_part_set(category: str, variant_set_name: str) -> bool:
    """True when ``variant_set_name`` is a per-part set of ``category`` (``Category_part``).

    USD variant-set names must be valid identifiers, so the per-part delimiter is
    ``_`` (not ``:``). No category token contains an underscore, so the category
    prefix stays unambiguous.
    """
    return variant_set_name.startswith(f"{category}_")


def variation_variant_sets(prim: Usd.Prim, category: str) -> List[str]:
    """Names of the master and per-part variant sets of ``category`` authored on ``prim``."""
    names = set(prim.GetVariantSets().GetNames())
    return sorted(
        name for name in names if name == master_set_name(category) or is_per_part_set(category, name)
    )


def option_names(prim: Usd.Prim, variant_set_name: str) -> List[str]:
    return list(prim.GetVariantSet(variant_set_name).GetVariantNames())


def authored_default_selection(stage: Usd.Stage, prim: Usd.Prim, variant_set_name: str) -> Optional[str]:
    """The root-layer authored default selection for ``variant_set_name``, or ``None``."""
    prim_spec = stage.GetRootLayer().GetPrimAtPath(prim.GetPath())
    if prim_spec is None:
        return None
    return dict(prim_spec.variantSelections).get(variant_set_name)


def compose_with_selection(
    root_layer, selections: Dict[str, str]
) -> Usd.Stage:
    """Open a fresh stage and apply ``{variant_set_name: option}`` on the default prim.

    Selections are written on the **session** layer (never the root layer), so
    the authored defaults are untouched, mirroring the ``runtime_variants``
    per-selection isolation pattern.
    """
    composed = Usd.Stage.Open(root_layer)
    default_prim = composed.GetDefaultPrim()
    present = set(default_prim.GetVariantSets().GetNames())
    with Usd.EditContext(composed, composed.GetSessionLayer()):
        for variant_set_name, option in selections.items():
            if variant_set_name in present:
                default_prim.GetVariantSet(variant_set_name).SetVariantSelection(option)
    return composed


def _bbox_cache(purpose_tokens) -> UsdGeom.BBoxCache:
    return UsdGeom.BBoxCache(Usd.TimeCode.Default(), purpose_tokens, useExtentsHint=True)


def _range_for(stage: Usd.Stage, purpose_tokens) -> Optional[Gf.Range3d]:
    root = stage.GetDefaultPrim()
    if not root or not root.IsValid():
        return None
    bound = _bbox_cache(purpose_tokens).ComputeWorldBound(root)
    rng = bound.ComputeAlignedRange()
    if rng.IsEmpty():
        return None
    return rng


def visual_envelope(stage: Usd.Stage) -> Optional[Gf.Range3d]:
    """World-aligned bounds over default + render purposes (the visible envelope)."""
    return _range_for(stage, [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])


def collision_envelope(stage: Usd.Stage) -> Optional[Gf.Range3d]:
    """World-aligned bounds over the guide/proxy collision purposes."""
    rng = _range_for(stage, [UsdGeom.Tokens.proxy, UsdGeom.Tokens.guide])
    if rng is not None:
        return rng
    # Fall back to colliders carried on default-purpose geometry.
    return _range_for(stage, [UsdGeom.Tokens.default_])


def envelope_size(rng: Optional[Gf.Range3d]) -> Optional[Gf.Vec3d]:
    return rng.GetSize() if rng is not None else None


def sizes_match(a: Optional[Gf.Vec3d], b: Optional[Gf.Vec3d], tolerance: float = ENVELOPE_TOLERANCE_M) -> bool:
    """True when two envelope sizes agree on every axis within ``tolerance`` meters."""
    if a is None or b is None:
        return a is None and b is None
    return all(abs(a[i] - b[i]) <= tolerance for i in range(3))


def authored_mass_properties(prim: Usd.Prim) -> dict:
    """Explicitly authored ``UsdPhysics.MassAPI`` values on ``prim``.

    Returns only values with an authored opinion; derived/fallback values are
    omitted so a caller can tell authored-not-derived (``AV.009``) apart from a
    runtime-computed default.
    """
    out: dict = {}
    if not prim or not prim.HasAPI(UsdPhysics.MassAPI):
        return out
    mass_api = UsdPhysics.MassAPI(prim)
    mass_attr = mass_api.GetMassAttr()
    if mass_attr and mass_attr.HasAuthoredValue():
        out["mass"] = mass_attr.Get()
    com_attr = mass_api.GetCenterOfMassAttr()
    if com_attr and com_attr.HasAuthoredValue():
        out["centerOfMass"] = com_attr.Get()
    inertia_attr = mass_api.GetDiagonalInertiaAttr()
    if inertia_attr and inertia_attr.HasAuthoredValue():
        out["diagonalInertia"] = inertia_attr.Get()
    return out


def iter_mass_bearing_prims(stage: Usd.Stage) -> Iterable[Usd.Prim]:
    """Prims under the default prim that carry ``UsdPhysics.MassAPI``."""
    root = stage.GetDefaultPrim()
    if not root or not root.IsValid():
        return
    for prim in Usd.PrimRange(root):
        if prim.HasAPI(UsdPhysics.MassAPI):
            yield prim
