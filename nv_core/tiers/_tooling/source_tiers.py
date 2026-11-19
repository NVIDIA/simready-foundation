# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Explicit source selection for tier tests; installed-wheel tests leave it unset."""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys


def select_source_tiers() -> None:
    # A comma also permits portable multi-root declarations in repo.toml.
    selected_roots = os.environ.get("SIMREADY_FOUNDATION_SOURCE_ROOTS", "").replace(",", os.pathsep)
    if selected_roots and os.environ.get("SIMREADY_REQUIRE_BUILT_TIER_WHEEL") == "1":
        raise RuntimeError(
            "SIMREADY_FOUNDATION_SOURCE_ROOTS cannot be combined with "
            "SIMREADY_REQUIRE_BUILT_TIER_WHEEL=1; select source tests or built-wheel qualification."
        )
    roots = [Path(value).resolve() for value in selected_roots.split(os.pathsep) if value]
    for root in reversed(roots):
        sys.path.insert(0, str(root))
    importlib.invalidate_caches()
    # Preserve shared namespace module identities while selecting their source portions.
    for name, suffix in (("simready", "simready"), ("simready.foundation", "simready/foundation")):
        if not roots:
            break
        namespace = importlib.import_module(name)
        selected = [str(root / suffix) for root in roots if (root / suffix).is_dir()]
        namespace.__path__ = selected + [path for path in namespace.__path__ if path not in selected]
    for root in roots:
        for package in (root / "simready/foundation").iterdir():
            if not (package / "__init__.py").is_file():
                continue
            name = "simready.foundation." + package.name
            module = sys.modules.get(name)
            if module is not None and Path(module.__file__).resolve() != (package / "__init__.py").resolve():
                raise RuntimeError(f"Selected source tier {name} was already imported from {module.__file__}")
