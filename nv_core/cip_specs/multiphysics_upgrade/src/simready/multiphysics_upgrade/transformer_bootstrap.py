# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Resolve ``simready.asset_transformer`` for the Isaac composition step.

The transformer ships in the Foundation core tier. Installed runtimes import it
directly; a repository checkout falls back to the in-repo ``src`` root. Both
distributions publish ``simready`` as a PEP 420 namespace package, so adding the
source root merges into the namespace instead of shadowing it.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path

_IN_REPO_SRC_SUFFIX = Path(
    "nv_core/tiers/simready_foundation_tier_core/tools/isaac_asset_transformer/src"
)


class TransformerUnavailableError(RuntimeError):
    """Raised when the Isaac asset transformer cannot be imported."""


def _find_in_repo_src() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / _IN_REPO_SRC_SUFFIX
        if (candidate / "simready" / "asset_transformer").is_dir():
            return candidate
    return None


def ensure_transformer_importable() -> None:
    """Make ``simready.asset_transformer`` importable, if it is available."""
    try:
        if importlib.util.find_spec("simready.asset_transformer") is not None:
            return
    except (ImportError, ModuleNotFoundError, ValueError):
        pass

    src = _find_in_repo_src()
    if src is None:
        return
    entry = str(src)
    if entry not in sys.path:
        sys.path.insert(0, entry)
        importlib.invalidate_caches()


def load_transform_package() -> Callable[..., object]:
    """Return ``simready.asset_transformer.transform_package``."""
    ensure_transformer_importable()
    try:
        from simready.asset_transformer import transform_package
    except ImportError as exc:
        raise TransformerUnavailableError(
            "simready.asset_transformer is not importable. Install "
            'simready-foundation-tier-core[isaac] in a Python 3.12 interpreter.'
        ) from exc
    return transform_package
