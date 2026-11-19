# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Sidecar protocol version, kept importable without USD.

Packaging tools read this file directly so they can stamp the protocol version
into a wheelhouse manifest on hosts that have no USD build available.
"""

from __future__ import annotations

PROTOCOL_VERSION = 1
