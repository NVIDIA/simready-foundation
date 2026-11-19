# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Prefixes for Newton runtime diagnostics."""


def engine_note(message):
    """Identify an engine diagnostic without changing the asset verdict."""
    return "Engine note: " + message
