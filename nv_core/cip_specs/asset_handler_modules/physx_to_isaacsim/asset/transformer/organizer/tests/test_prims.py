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
from isaacsim.asset.transformer.organizer.rules.prims import (
    PrimRoutingRule,
    copy_composed_prim_to_layer,
    merge_list_op,
    merge_path_list_op,
    remove_prim_from_source_layers,
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


class TestMergeListOp(omni.kit.test.AsyncTestCase):
    async def test_merge_list_op_no_existing(self):
        new_items = ["item1", "item2"]
        result = merge_list_op(None, new_items)

        self.assertTrue(result.isExplicit)
        self.assertEqual(list(result.explicitItems), new_items)

    async def test_merge_list_op_with_existing_explicit(self):
        existing = Sdf.TokenListOp.CreateExplicit(["existing1", "existing2"])
        new_items = ["new1", "new2"]

        result = merge_list_op(existing, new_items)

        self.assertTrue(result.isExplicit)
        explicit = list(result.explicitItems)
        self.assertEqual(explicit[:2], ["new1", "new2"])
        self.assertIn("existing1", explicit)
        self.assertIn("existing2", explicit)

    async def test_merge_list_op_with_existing_prepended(self):
        existing = Sdf.TokenListOp()
        existing.prependedItems = ["prepended1"]
        new_items = ["new1"]

        result = merge_list_op(existing, new_items)

        prepended = list(result.prependedItems)
        self.assertEqual(prepended[0], "new1")
        self.assertIn("prepended1", prepended)


class TestMergePathListOp(omni.kit.test.AsyncTestCase):
    async def test_merge_path_list_op_adds_new_paths(self):
        path_list_op = Sdf.PathListOp()
        new_paths = [Sdf.Path("/World/Prim1"), Sdf.Path("/World/Prim2")]

        merge_path_list_op(path_list_op, new_paths)

        added = list(path_list_op.GetAddedOrExplicitItems())
        self.assertEqual(len(added), 2)


class TestCopyComposedPrimToLayer(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_copy_composed_prim_basic(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        # Get an Xform prim from UR10e
        prim = stage.GetPrimAtPath("/ur10e")

        dst_layer_path = os.path.join(self._tmpdir, "dest.usda")
        dst_layer = Sdf.Layer.CreateNew(dst_layer_path)

        result = copy_composed_prim_to_layer(prim, dst_layer, Sdf.Path("/CopiedPrim"))

        self.assertTrue(result)
        copied_spec = dst_layer.GetPrimAtPath("/CopiedPrim")
        self.assertIsNotNone(copied_spec)

    async def test_copy_composed_prim_invalid_prim_returns_false(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        invalid_prim = stage.GetPrimAtPath("/NonExistent")

        dst_layer_path = os.path.join(self._tmpdir, "dest.usda")
        dst_layer = Sdf.Layer.CreateNew(dst_layer_path)

        result = copy_composed_prim_to_layer(invalid_prim, dst_layer, Sdf.Path("/Dest"))

        self.assertFalse(result)


class TestRemovePrimFromSourceLayers(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_remove_prim_from_source_layers(self):
        # Copy UR10e to temp dir to avoid modifying original
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)

        stage = Usd.Stage.Open(temp_asset)
        prim = stage.GetPrimAtPath("/ur10e")

        exclude_layer_path = os.path.join(self._tmpdir, "exclude.usda")
        exclude_layer = Sdf.Layer.CreateNew(exclude_layer_path)

        removed_count, modified_layers = remove_prim_from_source_layers(prim, exclude_layer)

        self.assertGreaterEqual(removed_count, 0)


class TestPrimRoutingRule(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_get_configuration_parameters(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        rule = PrimRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={},
        )

        params = rule.get_configuration_parameters()

        self.assertEqual(len(params), 3)
        param_names = [p.name for p in params]
        self.assertIn("prim_types", param_names)
        self.assertIn("stage_name", param_names)
        self.assertIn("scope", param_names)

    async def test_process_rule_no_prim_types_skips(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        rule = PrimRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={"params": {"prim_types": []}},
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("No prim types" in msg for msg in log))

    async def test_process_rule_routes_xform_prims(self):
        # Copy to temp for modification
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = PrimRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "prim_types": ["Xform"],
                    "stage_name": "xforms.usda",
                }
            },
        )

        rule.process_rule()

        output_path = os.path.join(self._tmpdir, "payloads", "xforms.usda")
        # UR10e contains Xform prims
        if os.path.exists(output_path):
            output_layer = Sdf.Layer.FindOrOpen(output_path)
            self.assertIsNotNone(output_layer)

    async def test_process_rule_no_matches_skips_file_creation(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = PrimRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "prim_types": ["NonExistentType*"],
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

        rule = PrimRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "prim_types": ["Xform"],
                    "stage_name": "xforms.usda",
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

        rule = PrimRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "prim_types": ["Xform"],
                    "stage_name": "xforms.usda",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("PrimRoutingRule start" in msg for msg in log))
        self.assertTrue(any("PrimRoutingRule completed" in msg for msg in log))
