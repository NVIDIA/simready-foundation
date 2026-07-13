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
from isaacsim.asset.transformer.organizer.rules.schemas import (
    SchemaRoutingRule,
    ensure_prim_spec_in_layer,
    get_schema_property_namespace,
    move_applied_api_schemas,
    props_from_applied_api_token,
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


class TestGetSchemaPropertyNamespace(omni.kit.test.AsyncTestCase):
    async def test_physx_joint_api_namespace(self):
        result = get_schema_property_namespace("PhysxJointAPI")

        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("physx"))

    async def test_multi_apply_schema_namespace(self):
        result = get_schema_property_namespace("PhysicsDriveAPI:angular")

        self.assertIsNotNone(result)
        self.assertIn("angular", result)

    async def test_physics_rigid_body_namespace(self):
        result = get_schema_property_namespace("PhysicsRigidBodyAPI")

        # Should derive physics: namespace
        self.assertIsNotNone(result)


class TestPropsFromAppliedApiToken(omni.kit.test.AsyncTestCase):
    async def test_known_api_schema_returns_properties(self):
        result = props_from_applied_api_token("MaterialBindingAPI")

        self.assertIsInstance(result, set)

    async def test_unknown_api_schema_returns_empty_set(self):
        result = props_from_applied_api_token("NonExistentAPI")

        self.assertEqual(result, set())


class TestMoveAppliedApiSchemas(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_move_applied_api_schemas_basic(self):
        src_layer_path = os.path.join(self._tmpdir, "source.usda")
        src_layer = Sdf.Layer.CreateNew(src_layer_path)
        src_spec = Sdf.CreatePrimInLayer(src_layer, "/TestPrim")
        src_spec.SetInfo("apiSchemas", Sdf.TokenListOp.CreateExplicit(["SchemaA", "SchemaB"]))

        dst_layer_path = os.path.join(self._tmpdir, "dest.usda")
        dst_layer = Sdf.Layer.CreateNew(dst_layer_path)
        dst_spec = Sdf.CreatePrimInLayer(dst_layer, "/TestPrim")

        move_applied_api_schemas(src_spec, dst_spec, ["SchemaA"])

        dst_schemas = dst_spec.GetInfo("apiSchemas")
        self.assertIsNotNone(dst_schemas)

    async def test_move_applied_api_schemas_empty_list_no_op(self):
        src_layer_path = os.path.join(self._tmpdir, "source.usda")
        src_layer = Sdf.Layer.CreateNew(src_layer_path)
        src_spec = Sdf.CreatePrimInLayer(src_layer, "/TestPrim")
        src_spec.SetInfo("apiSchemas", Sdf.TokenListOp.CreateExplicit(["SchemaA"]))

        dst_layer_path = os.path.join(self._tmpdir, "dest.usda")
        dst_layer = Sdf.Layer.CreateNew(dst_layer_path)
        dst_spec = Sdf.CreatePrimInLayer(dst_layer, "/TestPrim")

        move_applied_api_schemas(src_spec, dst_spec, [])

        dst_schemas = dst_spec.GetInfo("apiSchemas")
        self.assertIsNone(dst_schemas)


class TestSchemaRoutingRule(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_get_configuration_parameters(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        rule = SchemaRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={},
        )

        params = rule.get_configuration_parameters()

        self.assertEqual(len(params), 2)
        param_names = [p.name for p in params]
        self.assertIn("schemas", param_names)
        self.assertIn("stage_name", param_names)

    async def test_process_rule_no_schemas_skips(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        rule = SchemaRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={"params": {"schemas": []}},
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("No schemas" in msg for msg in log))

    async def test_process_rule_no_matches_skips_file_creation(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = SchemaRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "schemas": ["NonExistentSchema*"],
                    "stage_name": "empty.usda",
                }
            },
        )

        rule.process_rule()

        output_path = os.path.join(self._tmpdir, "payloads", "empty.usda")
        self.assertFalse(os.path.exists(output_path))

        log = rule.get_operation_log()
        self.assertTrue(any("No matching" in msg for msg in log))

    async def test_process_rule_routes_physics_schemas(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = SchemaRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "schemas": ["Physics*"],
                    "stage_name": "physics_schemas.usda",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("SchemaRoutingRule" in msg for msg in log))

    async def test_process_rule_logs_completion(self):
        temp_asset = os.path.join(self._tmpdir, "ur10e.usd")
        shutil.copy(_UR10E_USD, temp_asset)
        stage = Usd.Stage.Open(temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = SchemaRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "schemas": ["Physics*"],
                    "stage_name": "physics_schemas.usda",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("SchemaRoutingRule start" in msg for msg in log))
