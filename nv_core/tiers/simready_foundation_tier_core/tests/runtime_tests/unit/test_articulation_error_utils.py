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
"""Tests for articulation_phases.error_utils."""
from simready_benchmark_kit_suite.articulation_phases.error_utils import (
    asset_fix,
    engine_note,
)


def test_asset_fix_prefixes_message():
    assert asset_fix("Tune drive stiffness") == "Asset fix: Tune drive stiffness"


def test_engine_note_prefixes_message():
    assert engine_note("May reflect engine behavior") == ("Engine note: May reflect engine behavior")


def test_asset_fix_preserves_empty_string():
    assert asset_fix("") == "Asset fix: "


def test_engine_note_preserves_empty_string():
    assert engine_note("") == "Engine note: "
