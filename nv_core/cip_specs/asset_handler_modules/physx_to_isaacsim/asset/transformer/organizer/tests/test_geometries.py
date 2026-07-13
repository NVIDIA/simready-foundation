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
from isaacsim.asset.transformer.organizer.rules.geometries import GeometriesRoutingRule
from pxr import Gf, Sdf, Usd, UsdGeom

from .common import _UR10E_SHOULDER_USD, _UR10E_USD


class TestGeometriesRoutingRule(omni.kit.test.AsyncTestCase):
    async def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._temp_asset = os.path.join(self._tmpdir, "payloads/base.usd")
        stage = Usd.Stage.Open(_UR10E_SHOULDER_USD)
        stage.Export(self._temp_asset)
        self._success = False

    async def tearDown(self):
        if self._success:
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_get_configuration_parameters(self):
        stage = Usd.Stage.Open(_UR10E_SHOULDER_USD)
        rule = GeometriesRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={},
        )

        params = rule.get_configuration_parameters()

        self.assertEqual(len(params), 6)
        param_names = [p.name for p in params]
        self.assertIn("scope", param_names)
        self.assertIn("geometries_layer", param_names)
        self.assertIn("instance_layer", param_names)
        self.assertIn("deduplicate", param_names)
        self.assertIn("verbose", param_names)
        self.assertIn("save_base_as_usda", param_names)
        self._success = True

    async def test_process_rule_creates_geometries_layer(self):
        base_stage = Usd.Stage.Open(self._temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = GeometriesRoutingRule(
            source_stage=base_stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "geometries_layer": "geometries.usd",
                    "instance_layer": "instances.usda",
                }
            },
        )

        updated_stage_path = rule.process_rule()
        base_stage = Usd.Stage.Open(updated_stage_path)
        log = rule.get_operation_log()
        for msg in log:
            print(f"msg: {msg}")

        geometries_path = os.path.join(self._tmpdir, "payloads", "geometries.usd")
        if os.path.exists(geometries_path):
            geometries_layer = Sdf.Layer.FindOrOpen(geometries_path)
            self.assertIsNotNone(geometries_layer)
        # Open the geometries layer and check if it contains the correct number of geometries
        geometries_stage = Usd.Stage.Open(geometries_path)

        # Assert that the geometries layer contains the correct number of geometries
        self.assertEqual(len([prim for prim in geometries_stage.Traverse() if UsdGeom.Gprim(prim)]), 2)
        # Assert that the instances layer contains the correct number of instances
        instances_stage = Usd.Stage.Open(os.path.join(self._tmpdir, "payloads", "instances.usda"))
        self.assertEqual(len([prim for prim in instances_stage.GetPrimAtPath("/Instances").GetChildren()]), 6)
        # Assert that the base stage has the correct architecture for meshes
        mesh_prim_paths_expected = {
            "/ur10e/torso_link/visuals/head_link/Cube_01",
            "/ur10e/shoulder_link/duplicated_instanceable_01/shoulder/Cube_01",
            "/ur10e/shoulder_link/duplicated_direct_mesh/direct_mesh_material",
            "/ur10e/shoulder_link/duplicated_instanceable_04/shoulder/Cube_01",
            "/ur10e/shoulder_link/direct_mesh_material/direct_mesh_material",
            "/ur10e/shoulder_link/duplicated_instanceable/shoulder/Cube_01",
            "/ur10e/torso_link/visuals_01/head_link/Cube_01",
            "/ur10e/shoulder_link/convex_hull_instanceable/Cube_01",
            "/ur10e/shoulder_link/duplicated_non_instanceable/shoulder/Cube_01",
            "/ur10e/torso_link/visuals/logo_link/Cube_01",
            "/ur10e/shoulder_link/duplicated_instanceable_03/shoulder/Cube_01",
            "/ur10e/shoulder_link/instanceable_collider_no_material_03/shoulder/Cube_01",
            "/ur10e/torso_link/visuals_01/torso_link_rev_1_0/Cube_01",
            "/ur10e/shoulder_link/duplicated_instanceable_02/shoulder/Cube_01",
            "/ur10e/shoulder_link/instanceable_collider_no_material/shoulder/Cube_01",
            "/ur10e/shoulder_link/instanceable_visuals_materials/shoulder/Cube_01",
            "/ur10e/torso_link/visuals_01/logo_link/Cube_01",
            "/ur10e/torso_link/visuals/torso_link_rev_1_0/Cube_01",
            "/ur10e/shoulder_link/instanceable_collider_no_material_2/shoulder/Cube_01",
        }
        mesh_global_transforms_expected = {
            "/ur10e/shoulder_link/instanceable_visuals_materials/shoulder/Cube_01": Gf.Matrix4d(
                0.04999999999999935,
                8.742277645101089e-09,
                0.0,
                0.0,
                -8.742277645101089e-09,
                0.04999999999999935,
                0.0,
                0.0,
                0.0,
                0.0,
                0.05,
                0.0,
                0.0,
                0.0,
                0.18070000410079956,
                1.0,
            ),
            "/ur10e/shoulder_link/direct_mesh_material/direct_mesh_material": Gf.Matrix4d(
                -0.04999999999999985,
                -4.371138822550555e-09,
                0.0,
                0.0,
                4.371138822550555e-09,
                -0.04999999999999985,
                0.0,
                0.0,
                0.0,
                0.0,
                0.05,
                0.0,
                0.0,
                0.0,
                0.35153456480788414,
                1.0,
            ),
            "/ur10e/shoulder_link/convex_hull_instanceable/Cube_01": Gf.Matrix4d(
                1.1102230357117887e-17,
                -1.268162312721288e-18,
                -0.05,
                0.0,
                -4.371138815159158e-09,
                0.04999999999999985,
                -1.268163283309083e-18,
                0.0,
                0.04999999999999985,
                4.371138815159158e-09,
                1.1102230246251566e-17,
                0.0,
                0.0,
                0.0,
                0.0,
                1.0,
            ),
            "/ur10e/shoulder_link/instanceable_collider_no_material/shoulder/Cube_01": Gf.Matrix4d(
                0.04999999999999935,
                8.742277645101089e-09,
                0.0,
                0.0,
                -8.742277645101089e-09,
                0.04999999999999935,
                0.0,
                0.0,
                0.0,
                0.0,
                0.05,
                0.0,
                -0.2030558236568815,
                -2.812414082680294e-22,
                0.18070000410079218,
                1.0,
            ),
            "/ur10e/shoulder_link/instanceable_collider_no_material_2/shoulder/Cube_01": Gf.Matrix4d(
                0.04999999999999935,
                8.742277645101089e-09,
                0.0,
                0.0,
                -8.742277645101089e-09,
                0.04999999999999935,
                0.0,
                0.0,
                0.0,
                0.0,
                0.05,
                0.0,
                -0.2030558236568815,
                -2.812414082680294e-22,
                0.18070000410079218,
                1.0,
            ),
            "/ur10e/shoulder_link/instanceable_collider_no_material_03/shoulder/Cube_01": Gf.Matrix4d(
                0.04999999999999935,
                8.742277645101089e-09,
                0.0,
                0.0,
                -8.742277645101089e-09,
                0.04999999999999935,
                0.0,
                0.0,
                0.0,
                0.0,
                0.05,
                0.0,
                -0.4400958513209592,
                -7.874759431504823e-22,
                0.18070000410078613,
                1.0,
            ),
            "/ur10e/shoulder_link/duplicated_direct_mesh/direct_mesh_material": Gf.Matrix4d(
                -0.035355339059327265,
                -3.090861902933278e-09,
                -0.03535533905932738,
                0.0,
                4.371138822550555e-09,
                -0.04999999999999985,
                0.0,
                0.0,
                -0.03535533905932727,
                -3.0908619029332784e-09,
                0.035355339059327376,
                0.0,
                0.15872725025768017,
                3.1763735522036263e-22,
                0.35153456480788403,
                1.0,
            ),
            "/ur10e/shoulder_link/duplicated_instanceable/shoulder/Cube_01": Gf.Matrix4d(
                2.220446106736341e-17,
                -6.5756339423677346e-18,
                -0.05000000000000002,
                0.0,
                -8.742277638525446e-09,
                0.04999999999999932,
                -6.575637207032326e-18,
                0.0,
                0.04999999999999932,
                8.742277638525446e-09,
                1.1102230246251574e-17,
                0.0,
                0.2339776999529507,
                3.308722450212111e-24,
                0.18070000410079662,
                1.0,
            ),
            "/ur10e/shoulder_link/duplicated_non_instanceable/shoulder/Cube_01": Gf.Matrix4d(
                2.220446106736341e-17,
                -6.5756339423677346e-18,
                -0.05000000000000002,
                0.0,
                -8.742277638525446e-09,
                0.04999999999999932,
                -6.575637207032326e-18,
                0.0,
                0.04999999999999932,
                8.742277638525446e-09,
                1.1102230246251574e-17,
                0.0,
                0.4500473744420806,
                1.8889410850703915e-08,
                0.18070000410078624,
                1.0,
            ),
            "/ur10e/shoulder_link/duplicated_instanceable_01/shoulder/Cube_01": Gf.Matrix4d(
                2.220446106736341e-17,
                -6.5756339423677346e-18,
                -0.05000000000000002,
                0.0,
                -8.742277638525446e-09,
                0.04999999999999932,
                -6.575637207032326e-18,
                0.0,
                0.04999999999999932,
                8.742277638525446e-09,
                1.1102230246251574e-17,
                0.0,
                0.23397769995295267,
                1.5881867761018131e-22,
                -0.06804603563804534,
                1.0,
            ),
            "/ur10e/shoulder_link/duplicated_instanceable_02/shoulder/Cube_01": Gf.Matrix4d(
                1.1102228984499468e-17,
                1.4432762274116413e-17,
                0.05,
                0.0,
                -4.371138830860082e-09,
                0.04999999999999985,
                -1.4432761303528665e-17,
                0.0,
                -0.04999999999999985,
                -4.371138830860082e-09,
                1.1102230246251566e-17,
                0.0,
                0.2339776999529581,
                6.518183226917858e-22,
                -0.5031511428954939,
                1.0,
            ),
            "/ur10e/shoulder_link/duplicated_instanceable_03/shoulder/Cube_01": Gf.Matrix4d(
                0.04999999999999983,
                4.371138815974918e-09,
                1.7114271111395855e-09,
                0.0,
                -4.371138666357197e-09,
                0.049999999999999704,
                -4.371138815974914e-09,
                0.0,
                -1.711427482174436e-09,
                4.371138666357196e-09,
                0.04999999999999982,
                0.0,
                0.23397769995295478,
                3.341809674714232e-22,
                -0.2692127111122363,
                1.0,
            ),
            "/ur10e/shoulder_link/duplicated_instanceable_04/shoulder/Cube_01": Gf.Matrix4d(
                2.220446106736341e-17,
                -6.5756339423677346e-18,
                -0.05000000000000002,
                0.0,
                -8.742277638525446e-09,
                0.04999999999999932,
                -6.575637207032326e-18,
                0.0,
                0.04999999999999932,
                8.742277638525446e-09,
                1.1102230246251574e-17,
                0.0,
                0.2339776999529561,
                0.2799383068893438,
                -0.06804603563804745,
                1.0,
            ),
            "/ur10e/torso_link/visuals/torso_link_rev_1_0/Cube_01": Gf.Matrix4d(
                2.2204460492503132e-17,
                0.0,
                -0.1,
                0.0,
                0.0,
                0.1,
                0.0,
                0.0,
                0.1,
                0.0,
                2.2204460492503132e-17,
                0.0,
                -0.003963499795645475,
                -0.5374244968549189,
                0.04399999976158142,
                1.0,
            ),
            "/ur10e/torso_link/visuals/head_link/Cube_01": Gf.Matrix4d(
                5.551115123125783e-18,
                0.05,
                -8.326672684688675e-18,
                0.0,
                0.0,
                5.551115123125783e-18,
                0.05,
                0.0,
                0.05,
                -8.326672684688675e-18,
                0.0,
                0.0,
                0.0,
                -0.5374244968549189,
                0.2,
                1.0,
            ),
            "/ur10e/torso_link/visuals/logo_link/Cube_01": Gf.Matrix4d(
                4.440892098500626e-18,
                0.0,
                -0.02,
                0.0,
                0.0,
                0.1,
                0.0,
                0.0,
                0.05,
                0.0,
                1.1102230246251566e-17,
                0.0,
                0.052638901207180566,
                -0.5374244968549189,
                0.0,
                1.0,
            ),
            "/ur10e/torso_link/visuals_01/torso_link_rev_1_0/Cube_01": Gf.Matrix4d(
                2.2204460492503132e-17,
                0.0,
                -0.1,
                0.0,
                0.0,
                0.1,
                0.0,
                0.0,
                0.1,
                0.0,
                2.2204460492503132e-17,
                0.0,
                -0.003963499795645475,
                -0.33804472772541205,
                0.04399999976158142,
                1.0,
            ),
            "/ur10e/torso_link/visuals_01/head_link/Cube_01": Gf.Matrix4d(
                5.551115123125783e-18,
                0.05,
                -8.326672684688675e-18,
                0.0,
                0.0,
                5.551115123125783e-18,
                0.05,
                0.0,
                0.05,
                -8.326672684688675e-18,
                0.0,
                0.0,
                0.0,
                -0.33804472772541205,
                0.2,
                1.0,
            ),
            "/ur10e/torso_link/visuals_01/logo_link/Cube_01": Gf.Matrix4d(
                4.440892098500626e-18,
                0.0,
                -0.02,
                0.0,
                0.0,
                0.1,
                0.0,
                0.0,
                0.05,
                0.0,
                1.1102230246251566e-17,
                0.0,
                0.052638901207180566,
                -0.33804472772541205,
                0.0,
                1.0,
            ),
        }
        # Open the base stage and get the paths of the mesh prims
        mesh_prims = set(
            [
                p.GetPath().pathString
                for p in Usd.PrimRange(base_stage.GetPrimAtPath("/"), Usd.TraverseInstanceProxies())
                if UsdGeom.Gprim(p)
            ]
        )
        self.assertEqual(mesh_prim_paths_expected, mesh_prims)
        xform_cache = UsdGeom.XformCache()
        mesh_global_transforms = {
            p.GetPath().pathString: xform_cache.GetLocalToWorldTransform(p)
            for p in Usd.PrimRange(base_stage.GetPrimAtPath("/"), Usd.TraverseInstanceProxies())
            if UsdGeom.Gprim(p)
        }
        self.assertEqual(mesh_global_transforms_expected, mesh_global_transforms)
        self._success = True

    async def test_process_rule_with_scope(self):
        stage = Usd.Stage.Open(self._temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = GeometriesRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "scope": "/ur10e/base_link",
                    "geometries_layer": "geometries.usd",
                }
            },
        )

        updated_stage_path = rule.process_rule()
        updated_stage = Usd.Stage.Open(updated_stage_path)
        log = rule.get_operation_log()
        self.assertTrue(any("scope=/ur10e/base_link" in msg for msg in log))
        self._success = True

    async def test_process_rule_without_deduplication(self):
        stage = Usd.Stage.Open(self._temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = GeometriesRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "geometries_layer": "geometries.usd",
                    "deduplicate": False,
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("deduplicate=False" in msg for msg in log))
        self._success = True

    async def test_process_rule_affected_stages(self):
        stage = Usd.Stage.Open(self._temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = GeometriesRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "geometries_layer": "geometries.usd",
                }
            },
        )

        rule.process_rule()

        affected = rule.get_affected_stages()
        self.assertGreaterEqual(len(affected), 0)
        self._success = True

    async def test_process_rule_logs_operations(self):
        stage = Usd.Stage.Open(self._temp_asset)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = GeometriesRoutingRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "params": {
                    "geometries_layer": "geometries.usd",
                }
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("GeometriesRoutingRule start" in msg for msg in log))
        self.assertTrue(any("GeometriesRoutingRule completed" in msg for msg in log))
        self._success = True
