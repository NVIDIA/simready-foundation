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
from isaacsim.asset.transformer.organizer.rules.interface import (
    CONNECTION_PAYLOAD,
    CONNECTION_REFERENCE,
    CONNECTION_SUBLAYER,
    InterfaceConnectionRule,
)
from pxr import Sdf, Usd

# Path to UR10e test asset
_TEST_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
    "data",
    "tests",
    "ur10e",
)
_UR10E_USD = os.path.join(_TEST_DATA_DIR, "ur10e.usd")


class TestInterfaceConnectionRule(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()
        # Create payloads directory with base layer from UR10e
        self._setup_test_structure()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _setup_test_structure(self):
        # Create payloads directory with a flattened base layer
        payloads_dir = os.path.join(self._tmpdir, "payloads")
        os.makedirs(payloads_dir, exist_ok=True)

        # Create a simple base layer
        base_layer = Sdf.Layer.CreateNew(os.path.join(payloads_dir, "base.usda"))
        prim_spec = Sdf.CreatePrimInLayer(base_layer, "/ur10e")
        prim_spec.specifier = Sdf.SpecifierDef
        prim_spec.typeName = "Xform"
        base_layer.defaultPrim = "ur10e"
        base_layer.Save()

    async def test_get_configuration_parameters(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        rule = InterfaceConnectionRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="",
            args={},
        )

        params = rule.get_configuration_parameters()

        self.assertEqual(len(params), 6)
        param_names = [p.name for p in params]
        self.assertIn("base_layer", param_names)
        self.assertIn("base_connection_type", param_names)
        self.assertIn("generate_folder_variants", param_names)
        self.assertIn("payloads_folder", param_names)
        self.assertIn("connections", param_names)
        self.assertIn("default_variant_selections", param_names)

    async def test_process_rule_creates_interface_layer(self):
        stage = Usd.Stage.Open(_UR10E_USD)

        rule = InterfaceConnectionRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="",
            args={
                "input_stage_path": _UR10E_USD,
                "interface_asset_name": "robot.usda",
                "params": {
                    "base_layer": "payloads/base.usda",
                    "base_connection_type": CONNECTION_REFERENCE,
                },
            },
        )

        rule.process_rule()

        interface_path = os.path.join(self._tmpdir, "robot.usda")
        self.assertTrue(os.path.exists(interface_path))

        interface_layer = Sdf.Layer.FindOrOpen(interface_path)
        self.assertIsNotNone(interface_layer)
        self.assertEqual(interface_layer.defaultPrim, "ur10e")

    async def test_process_rule_no_base_layer_skips(self):
        stage = Usd.Stage.Open(_UR10E_USD)

        rule = InterfaceConnectionRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="",
            args={
                "input_stage_path": _UR10E_USD,
                "interface_asset_name": "robot.usda",
                "params": {
                    "base_layer": "payloads/nonexistent.usda",
                },
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("No referenced files exist" in msg for msg in log))

    async def test_process_rule_reference_connection(self):
        stage = Usd.Stage.Open(_UR10E_USD)

        rule = InterfaceConnectionRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="",
            args={
                "input_stage_path": _UR10E_USD,
                "interface_asset_name": "robot.usda",
                "params": {
                    "base_layer": "payloads/base.usda",
                    "base_connection_type": CONNECTION_REFERENCE,
                },
            },
        )

        rule.process_rule()

        interface_path = os.path.join(self._tmpdir, "robot.usda")
        interface_layer = Sdf.Layer.FindOrOpen(interface_path)
        prim_spec = interface_layer.GetPrimAtPath("/ur10e")
        self.assertIsNotNone(prim_spec)
        self.assertTrue(prim_spec.hasReferences)

    async def test_process_rule_payload_connection(self):
        stage = Usd.Stage.Open(_UR10E_USD)

        rule = InterfaceConnectionRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="",
            args={
                "input_stage_path": _UR10E_USD,
                "interface_asset_name": "robot.usda",
                "params": {
                    "base_layer": "payloads/base.usda",
                    "base_connection_type": CONNECTION_PAYLOAD,
                },
            },
        )

        rule.process_rule()

        interface_path = os.path.join(self._tmpdir, "robot.usda")
        interface_layer = Sdf.Layer.FindOrOpen(interface_path)
        prim_spec = interface_layer.GetPrimAtPath("/ur10e")
        self.assertIsNotNone(prim_spec)
        self.assertTrue(prim_spec.hasPayloads)

    async def test_process_rule_sublayer_connection(self):
        stage = Usd.Stage.Open(_UR10E_USD)

        rule = InterfaceConnectionRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="",
            args={
                "input_stage_path": _UR10E_USD,
                "interface_asset_name": "robot.usda",
                "params": {
                    "base_layer": "payloads/base.usda",
                    "base_connection_type": CONNECTION_SUBLAYER,
                },
            },
        )

        rule.process_rule()

        interface_path = os.path.join(self._tmpdir, "robot.usda")
        interface_layer = Sdf.Layer.FindOrOpen(interface_path)
        self.assertTrue(len(interface_layer.subLayerPaths) > 0)

    async def test_process_rule_derives_interface_name_from_input(self):
        stage = Usd.Stage.Open(_UR10E_USD)

        rule = InterfaceConnectionRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="",
            args={
                "input_stage_path": _UR10E_USD,
                # No interface_asset_name provided
                "params": {
                    "base_layer": "payloads/base.usda",
                },
            },
        )

        rule.process_rule()

        # Should create interface named after source file
        interface_path = os.path.join(self._tmpdir, "ur10e.usd")
        self.assertTrue(os.path.exists(interface_path))

    async def test_process_rule_invalid_connection_type_fallback(self):
        stage = Usd.Stage.Open(_UR10E_USD)

        rule = InterfaceConnectionRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="",
            args={
                "input_stage_path": _UR10E_USD,
                "interface_asset_name": "robot.usda",
                "params": {
                    "base_layer": "payloads/base.usda",
                    "base_connection_type": "InvalidType",
                },
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("Invalid connection type" in msg for msg in log))

        # Should fall back to Reference
        interface_path = os.path.join(self._tmpdir, "robot.usda")
        interface_layer = Sdf.Layer.FindOrOpen(interface_path)
        prim_spec = interface_layer.GetPrimAtPath("/ur10e")
        self.assertTrue(prim_spec.hasReferences)

    async def test_process_rule_generate_folder_variants(self):
        stage = Usd.Stage.Open(_UR10E_USD)

        # Create variant folders with USD files
        gripper_dir = os.path.join(self._tmpdir, "payloads", "Gripper")
        os.makedirs(gripper_dir, exist_ok=True)
        gripper_140 = Sdf.Layer.CreateNew(os.path.join(gripper_dir, "2F_140.usda"))
        gripper_140.Save()
        gripper_85 = Sdf.Layer.CreateNew(os.path.join(gripper_dir, "2F_85.usda"))
        gripper_85.Save()

        rule = InterfaceConnectionRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="",
            args={
                "input_stage_path": _UR10E_USD,
                "interface_asset_name": "robot.usda",
                "params": {
                    "base_layer": "payloads/base.usda",
                    "generate_folder_variants": True,
                    "payloads_folder": "payloads",
                },
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("variant set" in msg.lower() for msg in log))

    async def test_process_rule_affected_stages(self):
        stage = Usd.Stage.Open(_UR10E_USD)

        rule = InterfaceConnectionRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="",
            args={
                "input_stage_path": _UR10E_USD,
                "interface_asset_name": "robot.usda",
                "params": {
                    "base_layer": "payloads/base.usda",
                },
            },
        )

        rule.process_rule()

        affected = rule.get_affected_stages()
        self.assertTrue(len(affected) >= 1)

    async def test_process_rule_logs_completion(self):
        stage = Usd.Stage.Open(_UR10E_USD)

        rule = InterfaceConnectionRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="",
            args={
                "input_stage_path": _UR10E_USD,
                "interface_asset_name": "robot.usda",
                "params": {
                    "base_layer": "payloads/base.usda",
                },
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("InterfaceConnectionRule start" in msg for msg in log))
        self.assertTrue(any("InterfaceConnectionRule completed" in msg for msg in log))
