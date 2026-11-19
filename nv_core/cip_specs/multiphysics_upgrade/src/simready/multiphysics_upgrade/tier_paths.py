# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Locate the Foundation tier-core data used by profile-aware upgrade planning.

Installed runtimes have no repository checkout, so the tier root is resolved in
this order: explicit override, installed ``simready.foundation.tier_core``
distribution, then an in-repo checkout discovered from this file's location.
Callers that need no profile data (the neutral-to-runtimes pipeline) never
touch this module.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

TIER_ROOT_ENV_VAR = "SIMREADY_TIER_CORE_ROOT"

#: The requirement source tree is ``rules_and_reqs/`` in a Foundations 2 tier and
#: ``capabilities/`` in a Foundations 1 one. A Foundations 2 tier reuses
#: ``capabilities/`` for its CAP contracts, so the new name must win.
_RULES_DIRNAMES = ("rules_and_reqs", "capabilities")
_REQUIRED_SUBDIRS = ("features", "profiles")


class TierDataUnavailableError(RuntimeError):
    """Raised when profile/feature data is required but cannot be located."""


def rules_dir(tier_root: Path) -> Path | None:
    """Return the tier's requirement source tree, or ``None`` when it has none."""
    for name in _RULES_DIRNAMES:
        candidate = tier_root / name
        if candidate.is_dir():
            return candidate
    return None


def _is_tier_root(candidate: Path) -> bool:
    return rules_dir(candidate) is not None and all(
        (candidate / name).is_dir() for name in _REQUIRED_SUBDIRS
    )


def _from_environment() -> Path | None:
    raw = os.environ.get(TIER_ROOT_ENV_VAR, "").strip()
    if not raw:
        return None
    candidate = Path(raw).expanduser().resolve()
    return candidate if _is_tier_root(candidate) else None


def _from_installed_distribution() -> Path | None:
    try:
        spec = importlib.util.find_spec("simready.foundation.tier_core")
    except (ImportError, ModuleNotFoundError, ValueError):
        return None
    if spec is None:
        return None
    for location in spec.submodule_search_locations or []:
        candidate = Path(location).resolve()
        if _is_tier_root(candidate):
            return candidate
    return None


def _from_repository_checkout() -> Path | None:
    tier_suffix = Path("nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core")
    for parent in Path(__file__).resolve().parents:
        candidate = parent / tier_suffix
        if _is_tier_root(candidate):
            return candidate
    return None


def find_tier_root() -> Path | None:
    """Return the tier-core data root, or ``None`` when it is unavailable."""
    for resolver in (_from_environment, _from_installed_distribution, _from_repository_checkout):
        found = resolver()
        if found is not None:
            return found
    return None


def require_tier_root() -> Path:
    """Return the tier-core data root or raise with actionable guidance."""
    found = find_tier_root()
    if found is None:
        raise TierDataUnavailableError(
            "SimReady tier-core data was not found. Install "
            "simready-foundation-tier-core, or set "
            f"{TIER_ROOT_ENV_VAR} to a tier_core directory containing "
            f"{' or '.join(_RULES_DIRNAMES)}, {', '.join(_REQUIRED_SUBDIRS)}."
        )
    return found
