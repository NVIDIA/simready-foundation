# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for articulation_phases.overlay (pure-Python helpers only)."""
from simready_benchmark_kit_suite.articulation_phases.overlay import (
    OVERLAY_ALLOWED,
    overlay_safe_text,
)


def test_overlay_safe_text_uppercases():
    assert overlay_safe_text("hello") == "HELLO"


def test_overlay_safe_text_strips_disallowed():
    assert overlay_safe_text("Hello, world!") == "HELLO  WORLD "


def test_overlay_safe_text_preserves_allowed_specials():
    assert overlay_safe_text("a.b:c+d-e_f") == "A.B:C+D-E_F"


def test_overlay_safe_text_preserves_newlines():
    assert overlay_safe_text("line1\nline2") == "LINE1\nLINE2"


def test_overlay_allowed_covers_ascii_upper_digits():
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        assert ch in OVERLAY_ALLOWED
