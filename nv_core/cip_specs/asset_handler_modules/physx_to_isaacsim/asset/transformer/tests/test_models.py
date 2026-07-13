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
import unittest

import omni.kit.test
from isaacsim.asset.transformer.models import (
    ExecutionReport,
    RuleExecutionResult,
    RuleProfile,
    RuleSpec,
)


class TestModels(omni.kit.test.AsyncTestCase):
    async def test_rule_spec_to_from_dict_roundtrip(self):
        spec = RuleSpec(
            name="TestRule",
            type="module.Rule",
            destination="/tmp/out",
            params={"a": 1, "b": "x"},
            enabled=False,
        )
        data = spec.to_dict()
        restored = RuleSpec.from_dict(data)
        self.assertEqual(restored, spec)

    async def test_rule_spec_from_dict_missing_fields_raises(self):
        with self.assertRaises(ValueError):
            RuleSpec.from_dict({"type": "T"})
        with self.assertRaises(ValueError):
            RuleSpec.from_dict({"name": "N"})

    async def test_rule_profile_json_roundtrip_is_deterministic(self):
        spec1 = RuleSpec(name="A", type="m.A", params={"k": 2})
        spec2 = RuleSpec(name="B", type="m.B", enabled=False)
        profile = RuleProfile(
            profile_name="p",
            version="1.0",
            rules=[spec1, spec2],
            interface_asset_name="iface",
            output_package_root="/tmp/out",
        )
        s1 = profile.to_json()
        profile2 = RuleProfile.from_json(s1)
        s2 = profile2.to_json()
        self.assertEqual(s1, s2)
        parsed = json.loads(s1)
        self.assertSetEqual(
            set(parsed.keys()),
            {"interface_asset_name", "output_package_root", "profile_name", "rules", "version"},
        )
        self.assertEqual(parsed["rules"][0]["name"], "A")
        self.assertIs(parsed["rules"][1]["enabled"], False)

    async def test_rule_profile_from_dict_validation(self):
        with self.assertRaises(ValueError):
            RuleProfile.from_dict({})
        data = {"profile_name": "p", "rules": [{"name": "R", "type": "T"}]}
        prof = RuleProfile.from_dict(data)
        self.assertEqual(prof.profile_name, "p")
        self.assertEqual(len(prof.rules), 1)
        self.assertEqual(prof.rules[0].name, "R")

    async def test_rule_execution_result_close_sets_timestamp(self):
        spec = RuleSpec(name="R", type="T")
        res = RuleExecutionResult(rule=spec, success=False)
        self.assertIsNone(res.finished_at)
        res.close()
        self.assertIsInstance(res.finished_at, str)
        self.assertTrue(res.finished_at.endswith("Z"))

    async def test_execution_report_serialization_and_close(self):
        prof = RuleProfile(profile_name="p")
        report = ExecutionReport(profile=prof, input_stage_path="in.usda", package_root="/out")
        d1 = report.to_dict()
        self.assertIsNone(d1["finished_at"])
        self.assertIsInstance(d1["started_at"], str)
        s = report.to_json()
        self.assertIsInstance(s, str)
        report.close()
        d2 = report.to_dict()
        self.assertIsInstance(d2["finished_at"], str)
        self.assertTrue(d2["finished_at"].endswith("Z"))
        s2 = report.to_json()
        self.assertEqual(s2, json.dumps(d2, sort_keys=True, separators=(",", ":")))
