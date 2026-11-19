# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Deterministic FET_031 and FET_033 metadata conformance for SimReady packages.

Repairs authored asset paths (AA.001), derives and stamps nested provenance
metadata (SR.003), and normalizes the package thumbnail (SR.002). Physical
values are always derived from the asset and never fabricated.
"""

from __future__ import annotations

from .api import (
    MetadataConformRequest,
    MetadataConformResult,
    ResultError,
    run_metadata_conform,
)
from .conform import Blocker, ConformOutcome, conform_package
from .core import REQUIRED_FIELDS
from .protocol import PROTOCOL_VERSION
from .version import __version__

__all__ = [
    "PROTOCOL_VERSION",
    "REQUIRED_FIELDS",
    "Blocker",
    "ConformOutcome",
    "MetadataConformRequest",
    "MetadataConformResult",
    "ResultError",
    "__version__",
    "conform_package",
    "run_metadata_conform",
]
