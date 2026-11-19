# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Standalone multiphysics upgrade package for SimReady props.

Authors PhysX/Newton/MuJoCo runtime payloads on a neutral prop package and
composes the result for Isaac Sim. Depends on ``pxr`` only for the mutation
core; the Isaac composition step is imported lazily so the package remains
usable when the transformer distribution is absent.
"""

from __future__ import annotations

from .api import (
    PROTOCOL_VERSION,
    NeutralToRuntimesRequest,
    NeutralToRuntimesResult,
    ResultError,
    run_neutral_to_runtimes,
)
from .version import __version__

__all__ = [
    "PROTOCOL_VERSION",
    "NeutralToRuntimesRequest",
    "NeutralToRuntimesResult",
    "ResultError",
    "__version__",
    "run_neutral_to_runtimes",
]
