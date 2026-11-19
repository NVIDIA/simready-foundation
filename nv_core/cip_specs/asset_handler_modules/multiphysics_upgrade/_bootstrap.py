# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Make ``simready.multiphysics_upgrade`` importable for the CIP adapter package.

The implementation lives in the standalone ``simready-multiphysics-upgrade``
distribution. Installed runtimes import it directly; a repository checkout
(CIP loading adapters straight from source) falls back to the in-repo ``src``
root. Both use ``simready`` as a PEP 420 namespace package, so adding the
source root merges into the namespace instead of shadowing it.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

_IN_REPO_SRC = Path(__file__).resolve().parents[2] / "multiphysics_upgrade" / "src"


def ensure_importable() -> None:
    """Add the in-repo source root to ``sys.path`` when the package is absent."""
    try:
        if importlib.util.find_spec("simready.multiphysics_upgrade") is not None:
            return
    except (ImportError, ModuleNotFoundError, ValueError):
        pass

    if not (_IN_REPO_SRC / "simready" / "multiphysics_upgrade").is_dir():
        return
    entry = str(_IN_REPO_SRC)
    if entry not in sys.path:
        sys.path.insert(0, entry)
        importlib.invalidate_caches()
