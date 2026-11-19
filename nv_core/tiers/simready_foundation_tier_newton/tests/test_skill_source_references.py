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

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SKILLS = ROOT / "nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/skills"
SOURCES = sorted(SKILLS.glob("*/SKILL.md"))
assert SOURCES, "No shipped Newton skills found"


@pytest.mark.parametrize("skill", SOURCES, ids=lambda path: path.parent.name)
def test_explicit_skill_catalog_reads_resolve(skill):
    # Check actual referenced files, not headings/prose or logical site links.
    references = re.findall(r"`(nv_core/tiers/[^`\n]+\.(?:json|md))`", skill.read_text(encoding="utf-8"))
    assert references, "No explicit source-of-truth reads found"
    for reference in references:
        source = ROOT / reference
        assert source.is_file(), f"{skill.parent.name}: missing authoritative source {reference}"
        if source.suffix == ".json":
            manifest = json.loads(source.read_text(encoding="utf-8"))
            assert isinstance(manifest, dict) and manifest.get("id"), reference
