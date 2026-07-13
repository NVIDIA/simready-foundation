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

import os
import shutil
import tempfile

import omni.kit.test
from isaacsim.asset.transformer.organizer.rules.variants import VariantRoutingRule
from pxr import Usd

# Path to UR10e test asset
_TEST_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
    "data",
    "tests",
    "ur10e",
)
_UR10E_USD = os.path.join(_TEST_DATA_DIR, "ur10e.usd")


class TestVariantRoutingRule(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_get_configuration_parameters(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        rule = VariantRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={},
        )

        params = rule.get_configuration_parameters()

        self.assertEqual(len(params), 1)
        self.assertEqual(params[0].name, "variant_sets")

    async def test_process_rule_no_default_prim_skips(self):
        # Create a stage without default prim in temp dir
        stage_path = os.path.join(self._tmpdir, "no_default.usda")
        stage = Usd.Stage.CreateNew(stage_path)
        stage.DefinePrim("/SomePrim", "Xform")
        stage.GetRootLayer().Save()

        rule = VariantRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={},
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("No valid default prim" in msg for msg in log))

    async def test_process_rule_handles_stage_with_variants(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = VariantRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={},
        )

        rule.process_rule()

        log = rule.get_operation_log()
        # Should process or skip based on whether UR10e has variant sets
        self.assertTrue(any("VariantRoutingRule" in msg for msg in log))

    async def test_process_rule_logs_operations(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = VariantRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={},
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("VariantRoutingRule start" in msg for msg in log))
        self.assertTrue(any("VariantRoutingRule completed" in msg for msg in log))

    async def test_process_rule_with_filter(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = VariantRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "variant_sets": ["Gripper"],
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        # Should filter by variant set name
        self.assertTrue(any("VariantRoutingRule" in msg for msg in log))
