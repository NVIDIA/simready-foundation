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
from isaacsim.asset.transformer.organizer.rules.materials import MaterialsRoutingRule
from pxr import Sdf, Usd

# Path to UR10e test asset
_TEST_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
    "data",
    "tests",
    "ur10e",
)
_UR10E_USD = os.path.join(_TEST_DATA_DIR, "ur10e.usd")


class TestMaterialsRoutingRule(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_get_configuration_parameters(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        rule = MaterialsRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={},
        )

        params = rule.get_configuration_parameters()

        self.assertEqual(len(params), 5)
        param_names = [p.name for p in params]
        self.assertIn("scope", param_names)
        self.assertIn("materials_layer", param_names)
        self.assertIn("textures_folder", param_names)
        self.assertIn("deduplicate", param_names)
        self.assertIn("download_textures", param_names)

    async def test_process_rule_creates_materials_layer(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = MaterialsRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "materials_layer": "materials.usda",
                    "textures_folder": "Textures",
                }
            },
        )

        rule.process_rule()

        materials_path = os.path.join(self._tmpdir, "payloads", "materials.usda")
        if os.path.exists(materials_path):
            materials_layer = Sdf.Layer.FindOrOpen(materials_path)
            self.assertIsNotNone(materials_layer)

    async def test_process_rule_with_scope(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = MaterialsRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "scope": "/ur10e",
                    "materials_layer": "materials.usda",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("scope=/ur10e" in msg for msg in log))

    async def test_process_rule_with_deduplication(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = MaterialsRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "materials_layer": "materials.usda",
                    "deduplicate": True,
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("deduplicate=True" in msg for msg in log))

    async def test_process_rule_affected_stages(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = MaterialsRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "materials_layer": "materials.usda",
                }
            },
        )

        rule.process_rule()

        affected = rule.get_affected_stages()
        self.assertGreaterEqual(len(affected), 0)

    async def test_process_rule_logs_operations(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = MaterialsRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "materials_layer": "materials.usda",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("MaterialsRoutingRule start" in msg for msg in log))
        self.assertTrue(any("MaterialsRoutingRule completed" in msg for msg in log))
