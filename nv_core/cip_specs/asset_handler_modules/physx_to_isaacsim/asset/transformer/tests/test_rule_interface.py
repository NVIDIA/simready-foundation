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

import types
from unittest.mock import patch

import omni.kit.test
from isaacsim.asset.transformer.rule_interface import RuleInterface


class _NoOpRule(RuleInterface):
    def process_rule(self):
        self.log_operation("noop")
        self.add_affected_stage("stage://mem")
        return None

    def get_configuration_parameters(self):
        return []


class TestRuleInterface(omni.kit.test.AsyncTestCase):
    async def test_rule_interface_logging_and_affected_list(self):
        fake_stage_mod = types.SimpleNamespace()
        fake_usd_mod = types.SimpleNamespace(Stage=fake_stage_mod)
        with patch("isaacsim.asset.transformer.rule_interface.Usd", fake_usd_mod, create=True):
            rule = _NoOpRule(source_stage=object(), package_root="/pkg", destination_path="", args={"destination": "x"})
            rule.process_rule()
            self.assertEqual(rule.get_operation_log()[-1], "noop")
            self.assertIn("stage://mem", rule.get_affected_stages())
            rule.add_affected_stage("stage://mem")
            self.assertEqual(rule.get_affected_stages().count("stage://mem"), 1)
