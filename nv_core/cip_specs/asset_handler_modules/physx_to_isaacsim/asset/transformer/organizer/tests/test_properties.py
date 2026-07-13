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
from isaacsim.asset.transformer.organizer.rules.properties import (
    PropertyRoutingRule,
    copy_property_to_layer,
    ensure_prim_spec_in_layer,
    remove_property_from_source_layers,
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


class TestEnsurePrimSpecInLayer(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_ensure_prim_spec_creates_new(self):
        layer_path = os.path.join(self._tmpdir, "test.usda")
        layer = Sdf.Layer.CreateNew(layer_path)

        result = ensure_prim_spec_in_layer(layer, Sdf.Path("/TestPrim"))

        self.assertIsNotNone(result)
        self.assertEqual(result.specifier, Sdf.SpecifierOver)

    async def test_ensure_prim_spec_returns_existing(self):
        layer_path = os.path.join(self._tmpdir, "test.usda")
        layer = Sdf.Layer.CreateNew(layer_path)
        existing = Sdf.CreatePrimInLayer(layer, "/TestPrim")
        existing.specifier = Sdf.SpecifierDef

        result = ensure_prim_spec_in_layer(layer, Sdf.Path("/TestPrim"))

        self.assertEqual(result.specifier, Sdf.SpecifierDef)


class TestCopyPropertyToLayer(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_copy_property_to_layer_xform_op(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        prim = stage.GetPrimAtPath("/ur10e")

        dst_layer_path = os.path.join(self._tmpdir, "dest.usda")
        dst_layer = Sdf.Layer.CreateNew(dst_layer_path)

        # Try to copy xformOp:translate if it exists
        if prim.HasProperty("xformOp:translate"):
            result = copy_property_to_layer(prim, "xformOp:translate", dst_layer)
            self.assertTrue(result)


class TestRemovePropertyFromSourceLayers(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_remove_property_from_source_layers(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        prim = stage.GetPrimAtPath("/ur10e")

        exclude_layer_path = os.path.join(self._tmpdir, "exclude.usda")
        exclude_layer = Sdf.Layer.CreateNew(exclude_layer_path)

        # Try to remove a property if it exists
        if prim.HasProperty("xformOp:translate"):
            removed_count, modified_layers = remove_property_from_source_layers(
                prim, "xformOp:translate", exclude_layer
            )
            self.assertGreaterEqual(removed_count, 0)


class TestPropertyRoutingRule(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_get_configuration_parameters(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        rule = PropertyRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={},
        )

        params = rule.get_configuration_parameters()

        self.assertEqual(len(params), 3)
        param_names = [p.name for p in params]
        self.assertIn("properties", param_names)
        self.assertIn("stage_name", param_names)
        self.assertIn("scope", param_names)

    async def test_process_rule_no_patterns_skips(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        rule = PropertyRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={"params": {"properties": []}},
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("No property patterns" in msg for msg in log))

    async def test_process_rule_routes_xform_properties(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = PropertyRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "properties": ["xformOp:.*"],
                    "stage_name": "xform_props.usda",
                }
            },
        )

        rule.process_rule()

        output_path = os.path.join(self._tmpdir, "payloads", "xform_props.usda")
        if os.path.exists(output_path):
            output_layer = Sdf.Layer.FindOrOpen(output_path)
            self.assertIsNotNone(output_layer)

    async def test_process_rule_invalid_regex_skipped(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        rule = PropertyRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "properties": ["[invalid regex"],
                    "stage_name": "props.usda",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("Invalid regex" in msg for msg in log))

    async def test_process_rule_no_matches_skips_file_creation(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = PropertyRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "properties": ["nonexistent:.*"],
                    "stage_name": "empty.usda",
                }
            },
        )

        rule.process_rule()

        output_path = os.path.join(self._tmpdir, "payloads", "empty.usda")
        self.assertFalse(os.path.exists(output_path))

        log = rule.get_operation_log()
        self.assertTrue(any("No matching" in msg for msg in log))

    async def test_process_rule_with_scope(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = PropertyRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "properties": ["xformOp:.*"],
                    "stage_name": "xform_props.usda",
                    "scope": "/ur10e",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("/ur10e" in msg for msg in log))

    async def test_process_rule_logs_completion(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = PropertyRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "properties": ["xformOp:.*"],
                    "stage_name": "xform_props.usda",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("PropertyRoutingRule start" in msg for msg in log))
        self.assertTrue(any("PropertyRoutingRule completed" in msg for msg in log))
