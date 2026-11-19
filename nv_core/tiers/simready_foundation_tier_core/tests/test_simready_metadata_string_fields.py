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

"""SR.003/SR.004 (OMPE-113066): required string fields must reject non-string values.

``author``, ``asset_name``, ``asset_type``, ``asset_license``, ``category``,
``source_file`` and ``usd_date_generated`` are documented as ``string``. The
presence/non-empty checks alone accepted an integer for any of them, so
schema-invalid provenance passed mandatory package metadata validation. Each must
now fail with a diagnostic naming the field.
"""

import pytest
import simready.foundation.tier_core.requirements as cap
from pxr import Usd
from simready.foundation.tier_core.rules_and_reqs.core.sim_ready.validation import (
    MetadataUnion,
    NestedSimReadyMetadata,
)

_CHECKERS = [
    (MetadataUnion, cap.SimReadyRequirements.SR_004),
    (NestedSimReadyMetadata, cap.SimReadyRequirements.SR_003),
]

_STRING_FIELDS = (
    "author",
    "asset_name",
    "asset_type",
    "asset_license",
    "category",
    "source_file",
    "usd_date_generated",
)


def _metadata(**overrides):
    metadata = {
        "author": "nvidia",
        "asset_name": "Copper_Brushed",
        "asset_type": "material",
        "asset_license": "CC-BY-4.0",
        "category": "metal",
        "source_file": "Copper_Brushed.mtlx",
        "usd_date_generated": "2026-10-22",
        "qcode": "Q753",
        "rigid_body_count": 1,
        "asset_extents": [0.1, 0.2, 0.3],
        "mass": 1.0,
    }
    metadata.update(overrides)
    return metadata


def _stage(tmp_path, **overrides):
    stage = Usd.Stage.CreateNew(str(tmp_path / "asset.usda"))
    stage.SetDefaultPrim(stage.DefinePrim("/Asset", "Xform"))
    stage.GetRootLayer().customLayerData = {"SimReady_Metadata": _metadata(**overrides)}
    return stage


def _messages(checker_type, requirement, stage):
    checker = checker_type()
    checker.CheckStage(stage)
    issues = list(checker.GetIssues())
    assert all(issue.requirement == requirement for issue in issues)
    return [issue.message for issue in issues]


@pytest.mark.parametrize(("checker_type", "requirement"), _CHECKERS)
def test_valid_string_metadata_passes(tmp_path, checker_type, requirement):
    assert _messages(checker_type, requirement, _stage(tmp_path)) == []


@pytest.mark.parametrize(("checker_type", "requirement"), _CHECKERS)
@pytest.mark.parametrize("field", _STRING_FIELDS)
def test_integer_value_for_a_string_field_fails(tmp_path, checker_type, requirement, field):
    messages = _messages(checker_type, requirement, _stage(tmp_path, **{field: 17}))
    type_errors = [m for m in messages if "must be string values" in m]
    assert type_errors, f"{field} with an integer value must fail {requirement}"
    assert field in type_errors[0]


@pytest.mark.parametrize(("checker_type", "requirement"), _CHECKERS)
def test_a_nonempty_license_string_is_preserved(tmp_path, checker_type, requirement):
    """No closed license whitelist: any non-empty string license passes."""
    stage = _stage(tmp_path, asset_license="My-Custom-License-1.0")
    assert _messages(checker_type, requirement, stage) == []
