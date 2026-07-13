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
from isaacsim.asset.transformer.manager import AssetStructureManager, RuleRegistry
from isaacsim.asset.transformer.models import RuleProfile, RuleSpec
from isaacsim.asset.transformer.rule_interface import RuleInterface


class _DummyRule(RuleInterface):
    def process_rule(self):
        self.log_operation("dummy-run")
        self.add_affected_stage(self.args.get("destination") or "memory")
        return None

    def get_configuration_parameters(self):
        return []


def _fake_usd(open_returns):
    fake_stage_mod = types.SimpleNamespace()
    fake_stage_mod.Open = lambda path: open_returns
    fake_stage_mod.CreateInMemory = lambda: object()
    return types.SimpleNamespace(Stage=fake_stage_mod)


class TestManager(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        RuleRegistry().clear()

    async def asyncTearDown(self):
        RuleRegistry().clear()

    async def test_rule_registry_register_get_clear(self):
        reg = RuleRegistry()
        reg.register(_DummyRule)
        fqcn = f"{_DummyRule.__module__}.{_DummyRule.__qualname__}"
        cls = reg.get(fqcn)
        self.assertIs(cls, _DummyRule)
        reg.clear()
        self.assertIsNone(reg.get(fqcn))

        class NotARule:  # noqa: D401
            """Not a RuleInterface subclass."""

            pass

        with self.assertRaises(TypeError):
            reg.register(NotARule)  # type: ignore[arg-type]

    async def test_manager_run_happy_path(self):
        fake_usd = _fake_usd(open_returns=object())
        with (
            patch("isaacsim.asset.transformer.manager.Usd", fake_usd, create=True),
            patch("isaacsim.asset.transformer.rule_interface.Usd", fake_usd, create=True),
        ):
            reg = RuleRegistry()
            reg.clear()
            reg.register(_DummyRule)
            fqcn = f"{_DummyRule.__module__}.{_DummyRule.__qualname__}"
            profile = RuleProfile(
                profile_name="p",
                rules=[
                    RuleSpec(name="r1", type=fqcn, destination="out.usda"),
                    RuleSpec(name="disabled", type=fqcn, enabled=False),
                ],
                interface_asset_name="iface",
                output_package_root="/pkg",
            )
            mgr = AssetStructureManager()
            report = mgr.run(input_stage_path="in.usda", profile=profile, package_root=None)
            self.assertEqual(len(report.results), 1)
            result = report.results[0]
            self.assertTrue(result.success)
            self.assertIsNone(result.error)
            self.assertTrue(result.log and result.log[-1]["message"] == "dummy-run")
            self.assertIn("out.usda", result.affected_stages)
            self.assertIsInstance(result.finished_at, str)
            self.assertIsInstance(report.finished_at, str)

    async def test_manager_run_missing_implementation_sets_error(self):
        fake_usd = _fake_usd(open_returns=object())
        with (
            patch("isaacsim.asset.transformer.manager.Usd", fake_usd, create=True),
            patch("isaacsim.asset.transformer.rule_interface.Usd", fake_usd, create=True),
        ):
            RuleRegistry().clear()
            unknown_type = "non.existent.Rule"
            profile = RuleProfile(profile_name="p", rules=[RuleSpec(name="r", type=unknown_type)])
            mgr = AssetStructureManager()
            report = mgr.run(input_stage_path="in.usda", profile=profile)
            self.assertEqual(len(report.results), 1)
            res = report.results[0]
            self.assertFalse(res.success)
            self.assertIsInstance(res.error, str)
            self.assertIn("No rule implementation registered", res.error)
            self.assertIsInstance(res.finished_at, str)

    async def test_manager_run_source_open_failure_raises(self):
        fake_usd = _fake_usd(open_returns=None)
        with patch("isaacsim.asset.transformer.manager.Usd", fake_usd, create=True):
            mgr = AssetStructureManager()
            profile = RuleProfile(profile_name="p", rules=[])
            with self.assertRaises(RuntimeError) as excinfo:
                mgr.run(input_stage_path="missing.usda", profile=profile)
            self.assertIn("Failed to open source stage", str(excinfo.exception))
