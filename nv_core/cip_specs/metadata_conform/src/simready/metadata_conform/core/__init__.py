# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Deterministic, pxr-only FET_031 and FET_033 conformance primitives.

Nothing here promotes, validates against a profile, or talks to a network. Each
module is one stage of the per-asset chain so the pieces stay independently
testable:

``audit`` digest -> ``paths`` repair -> ``derivation`` -> ``sources`` resolution
-> ``paths`` stamp -> ``thumbnails`` -> ``audit`` verify
"""

from __future__ import annotations

from .audit import audit_mutation, protected_stage_digest
from .derivation import PHYSICAL_FIELDS, DerivationResult, derive_metadata
from .paths import (
    SR_001_IDENTITY_FIELDS,
    PathRepair,
    read_existing_metadata,
    read_top_level_metadata,
    repair_simple_asset_paths,
    stamp_metadata,
)
from .sources import (
    REQUIRED_FIELDS,
    STRING_FIELDS,
    ResolvedField,
    load_package_sidecar,
    rejected_physical_fields,
    resolve_metadata,
    unresolved_fields,
)
from .thumbnails import (
    ExistingThumbnailProvider,
    ExplicitThumbnailProvider,
    ThumbnailCandidate,
    ThumbnailProvider,
    ThumbnailResult,
    discover_candidates,
    is_valid_png,
    normalize_thumbnail,
    target_path,
)

__all__ = [
    "PHYSICAL_FIELDS",
    "REQUIRED_FIELDS",
    "SR_001_IDENTITY_FIELDS",
    "STRING_FIELDS",
    "DerivationResult",
    "ExistingThumbnailProvider",
    "ExplicitThumbnailProvider",
    "PathRepair",
    "ResolvedField",
    "ThumbnailCandidate",
    "ThumbnailProvider",
    "ThumbnailResult",
    "audit_mutation",
    "derive_metadata",
    "discover_candidates",
    "is_valid_png",
    "load_package_sidecar",
    "normalize_thumbnail",
    "protected_stage_digest",
    "read_existing_metadata",
    "read_top_level_metadata",
    "rejected_physical_fields",
    "repair_simple_asset_paths",
    "resolve_metadata",
    "stamp_metadata",
    "target_path",
    "unresolved_fields",
]
