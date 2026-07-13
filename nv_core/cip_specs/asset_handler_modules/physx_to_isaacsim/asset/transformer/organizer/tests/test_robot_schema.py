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
from isaacsim.asset.transformer.organizer.rules.robot_schema import RobotSchemaRule
from pxr import Usd

# Path to UR10e test asset
_TEST_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
    "data",
    "tests",
    "ur10e",
)
_UR10E_USD = os.path.join(_TEST_DATA_DIR, "ur10e.usd")


class TestRobotSchemaRule(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_get_configuration_parameters(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        rule = RobotSchemaRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={},
        )

        params = rule.get_configuration_parameters()

        self.assertEqual(len(params), 2)
        param_names = [p.name for p in params]
        self.assertIn("prim_path", param_names)
        self.assertIn("stage_name", param_names)

    async def test_process_rule_uses_default_prim(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = RobotSchemaRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "stage_name": "robot_schema.usda",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("RobotSchemaRule start" in msg for msg in log))
        self.assertTrue(any("/ur10e" in msg for msg in log))

    async def test_process_rule_with_explicit_prim_path(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = RobotSchemaRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "prim_path": "/ur10e",
                    "stage_name": "robot_schema.usda",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("prim=/ur10e" in msg for msg in log))

    async def test_process_rule_invalid_prim_path_skips(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = RobotSchemaRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "prim_path": "/NonExistent",
                    "stage_name": "robot_schema.usda",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("skipped" in msg.lower() or "invalid" in msg.lower() for msg in log))

    async def test_process_rule_creates_destination_layer(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = RobotSchemaRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "stage_name": "robot_schema.usda",
                }
            },
        )

        rule.process_rule()

        schema_path = os.path.join(self._tmpdir, "payloads", "robot_schema.usda")
        self.assertTrue(os.path.exists(schema_path))

    async def test_process_rule_applies_robot_api(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = RobotSchemaRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "stage_name": "robot_schema.usda",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("RobotAPI" in msg for msg in log))

    async def test_process_rule_no_default_prim_uses_world(self):
        stage_path = os.path.join(self._tmpdir, "no_default.usda")
        stage = Usd.Stage.CreateNew(stage_path)
        stage.DefinePrim("/World", "Xform")
        stage.GetRootLayer().Save()

        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = RobotSchemaRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "stage_name": "robot_schema.usda",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("/World" in msg for msg in log))

    async def test_process_rule_affected_stages(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = RobotSchemaRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "stage_name": "robot_schema.usda",
                }
            },
        )

        rule.process_rule()

        affected = rule.get_affected_stages()
        self.assertTrue(len(affected) >= 1)

    async def test_process_rule_logs_completion(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = RobotSchemaRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "stage_name": "robot_schema.usda",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("RobotSchemaRule completed" in msg for msg in log))

    async def test_process_rule_adds_sublayer(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = RobotSchemaRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "stage_name": "robot_schema.usda",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("sublayer" in msg.lower() for msg in log))
