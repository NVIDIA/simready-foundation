# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Resolve SR.003 metadata values while preserving per-field provenance."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

# The full SR.003 contract at FET_033_STANDARD@0.3.0.
REQUIRED_FIELDS = (
    "author",
    "asset_name",
    "asset_type",
    "asset_license",
    "category",
    "source_file",
    "usd_date_generated",
    "qcode",
    "rigid_body_count",
    "asset_extents",
    "mass",
)

STRING_FIELDS = frozenset(
    {
        "author",
        "asset_name",
        "asset_type",
        "asset_license",
        "category",
        "source_file",
        "usd_date_generated",
    }
)

QCODE_RE = re.compile(r"^Q[0-9]+$")

PHYSICAL_COMPUTED_FIELDS = frozenset({"rigid_body_count", "asset_extents", "mass"})

# SR.001 places provenance strings at the top level of customLayerData while
# SR.003 requires them nested in SimReady_Metadata. Assets authored against
# SR.001 therefore carry real provenance the nested lookup cannot see, so the
# top level is promoted as a source. Physical fields are deliberately excluded:
# they stay current-stage derivation only so a stale authored mass, extent, or
# body count can never be promoted back in.
LAYER_PROMOTED_FIELDS = STRING_FIELDS | {"qcode"}


@dataclass(frozen=True)
class ResolvedField:
    value: Any
    source: str
    warning: str | None = None


def is_valid_field(field: str, value: Any) -> bool:
    """Report whether ``value`` satisfies the SR.003 contract for ``field``."""
    if value is None or isinstance(value, bool):
        return False
    if field in STRING_FIELDS:
        return isinstance(value, str) and bool(value.strip())
    if field == "qcode":
        return isinstance(value, str) and QCODE_RE.fullmatch(value.strip()) is not None
    if field == "rigid_body_count":
        return isinstance(value, int) and value >= 0
    if field == "mass":
        return isinstance(value, (int, float)) and value > 0
    if field == "asset_extents":
        try:
            components = list(value)
        except TypeError:
            return False
        return len(components) == 3 and all(
            isinstance(item, (int, float)) and not isinstance(item, bool) and item >= 0
            for item in components
        )
    if isinstance(value, str):
        return bool(value.strip())
    return True


def resolve_metadata(
    *,
    request: Mapping[str, Any] | None = None,
    existing: Mapping[str, Any] | None = None,
    layer: Mapping[str, Any] | None = None,
    sidecar: Mapping[str, Any] | None = None,
    derived: Mapping[str, Any] | None = None,
) -> dict[str, ResolvedField]:
    """Pick one value per field and record where it came from.

    Precedence for provenance strings is request, then nested existing
    metadata, then promoted top-level layer keys, then the package sidecar
    file. ``qcode`` prefers an explicit request value, then stage-derived
    semantics. The physical fields accept ``derived`` only.
    """
    request = request or {}
    existing = existing or {}
    sidecar = sidecar or {}
    derived = derived or {}
    layer_values = {
        field: value
        for field, value in (layer or {}).items()
        if field in LAYER_PROMOTED_FIELDS
    }
    fields = (
        set(request)
        | set(existing)
        | set(layer_values)
        | set(sidecar)
        | set(derived)
    )
    computed = {*PHYSICAL_COMPUTED_FIELDS, "qcode"}
    result: dict[str, ResolvedField] = {}
    for field in sorted(fields):
        if field in PHYSICAL_COMPUTED_FIELDS:
            # Physical fields are current-stage derivation only. Existing
            # nested values are never a fallback when derivation is missing.
            sources = (("derived", derived),)
        elif field == "qcode":
            sources = (
                ("request", request),
                ("derived", derived),
                ("existing", existing),
                ("existing_layer", layer_values),
                ("sidecar", sidecar),
            )
        else:
            sources = (
                ("request", request),
                ("existing", existing),
                ("existing_layer", layer_values),
                ("sidecar", sidecar),
            )
        for source_name, source in sources:
            value = source.get(field)
            if not is_valid_field(field, value):
                continue
            warning = None
            if (
                source_name in {"derived", "existing"}
                and field in computed
                and is_valid_field(field, existing.get(field))
                and is_valid_field(field, derived.get(field))
                and existing[field] != derived[field]
            ):
                warning = "Existing value conflicts with current stage evidence"
            result[field] = ResolvedField(value, source_name, warning)
            break
    return result


def unresolved_fields(
    resolved: Mapping[str, ResolvedField],
    required: tuple[str, ...] = REQUIRED_FIELDS,
) -> tuple[str, ...]:
    return tuple(field for field in required if field not in resolved)


def rejected_physical_fields(request: Mapping[str, Any] | None) -> tuple[str, ...]:
    """Report physical fields a caller tried to supply.

    ``rigid_body_count``, ``asset_extents``, and ``mass`` must be evidence from
    the asset being conformed. Accepting caller values would let a request force
    an SR.003 pass with numbers nothing in the package supports, so they are
    reported and never merged.
    """
    return tuple(
        field
        for field in sorted(PHYSICAL_COMPUTED_FIELDS)
        if (request or {}).get(field) is not None
    )


def load_package_sidecar(asset_path: Path) -> dict[str, Any]:
    """Load a package-local metadata sidecar JSON file, if one exists."""
    asset = Path(asset_path).resolve()
    candidates = (
        asset.with_suffix(".metadata.json"),
        asset.parent / "simready_metadata.json",
        asset.parent.parent / "simready_metadata.json",
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            nested = value.get("SimReady_Metadata", value)
            if isinstance(nested, dict):
                return dict(nested)
    return {}
