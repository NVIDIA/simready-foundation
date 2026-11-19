# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Sidecar protocol version, importable without USD.

Kept free of USD and of the rest of the package so wheelhouse tooling and host
applications can read the protocol version by loading this file directly.
"""

from __future__ import annotations

PROTOCOL_VERSION = 1
