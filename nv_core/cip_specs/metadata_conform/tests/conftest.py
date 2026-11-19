# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Test path setup for running against the source tree without installing."""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]

for _path in (_PACKAGE_ROOT / "src", _PACKAGE_ROOT / "tests"):
    entry = str(_path)
    if _path.is_dir() and entry not in sys.path:
        sys.path.insert(0, entry)
