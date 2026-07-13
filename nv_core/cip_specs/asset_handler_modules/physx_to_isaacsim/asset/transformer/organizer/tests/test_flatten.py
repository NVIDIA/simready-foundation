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
from isaacsim.asset.transformer.organizer.rules.flatten import FlattenRule
from pxr import Sdf, Usd, UsdPhysics

from .common import _UR10E_USD


class TestFlattenRule(omni.kit.test.AsyncTestCase):

    async def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._success = False

    async def tearDown(self):
        if self._success:
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_get_configuration_parameters(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        rule = FlattenRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="",
            args={"input_stage_path": _UR10E_USD},
        )

        params = rule.get_configuration_parameters()

        self.assertEqual(len(params), 3)
        param_names = [p.name for p in params]
        self.assertIn("output_path", param_names)
        self.assertIn("clear_variants", param_names)
        self.assertIn("selected_variants", param_names)
        self._success = True

    async def test_flatten_basic_stage(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        output_subdir = "payloads"
        output_path = "base.usda"
        os.makedirs(os.path.join(self._tmpdir, output_subdir), exist_ok=True)

        rule = FlattenRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path=output_subdir,
            args={
                "input_stage_path": _UR10E_USD,
                "params": {
                    "output_path": output_path,
                    "clear_variants": False,
                },
            },
        )

        rule.process_rule()

        expected_output = os.path.join(self._tmpdir, output_subdir, output_path)
        self.assertTrue(os.path.exists(expected_output))

        flattened_layer = Usd.Stage.Open(expected_output)
        self.assertIsNotNone(flattened_layer)
        # UR10e has ur10e as default prim
        self.assertTrue(flattened_layer.GetPrimAtPath("/ur10e").IsValid())

        self.assertTrue(flattened_layer.GetPrimAtPath("/ur10e/base_link").IsValid())
        self._success = True

    async def test_flatten_without_input_stage_path_skips(self):
        stage = Usd.Stage.Open(_UR10E_USD)

        rule = FlattenRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="",
            args={},
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("No input_stage_path" in msg for msg in log))
        self._success = True

    async def test_flatten_with_variants_cleared(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        os.makedirs(os.path.join(self._tmpdir, "output"), exist_ok=True)

        rule = FlattenRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="output",
            args={
                "input_stage_path": _UR10E_USD,
                "params": {
                    "output_path": "flattened.usda",
                    "clear_variants": True,
                },
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        # Verify rule processed and cleared variants
        self.assertTrue(any("Cleared" in msg for msg in log) or any("variant" in msg.lower() for msg in log))

        # Verify output exists
        output_path = os.path.join(self._tmpdir, "output", "flattened.usda")
        self.assertTrue(os.path.exists(output_path))

        flattened_layer = Usd.Stage.Open(output_path)
        self.assertTrue(flattened_layer.GetPrimAtPath("/ur10e").IsValid())
        self.assertFalse(flattened_layer.GetPrimAtPath("/ur10e/base_link").IsValid())
        self._success = True

    async def test_flatten_with_selected_variants(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        os.makedirs(os.path.join(self._tmpdir, "output"), exist_ok=True)

        rule = FlattenRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="output",
            args={
                "input_stage_path": _UR10E_USD,
                "params": {
                    "output_path": "flattened.usda",
                    "clear_variants": True,
                    "selected_variants": {"Physics": "PhysX", "Gripper": "Robotiq_2f_85"},
                },
            },
        )

        rule.process_rule()
        output_path = os.path.join(self._tmpdir, "output", "flattened.usda")

        flattened_layer = Usd.Stage.Open(output_path)
        self.assertTrue(flattened_layer.GetPrimAtPath("/ur10e").IsValid())
        self.assertTrue(flattened_layer.GetPrimAtPath("/ur10e/ee_link/Robotiq_2F_85/base_link").IsValid())
        self.assertTrue(
            UsdPhysics.RigidBodyAPI(flattened_layer.GetPrimAtPath("/ur10e/ee_link/Robotiq_2F_85/base_link"))
            .GetPrim()
            .IsValid()
        )
        self._success = True

    async def test_flatten_affected_stages(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = FlattenRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "input_stage_path": _UR10E_USD,
                "params": {"output_path": "base.usda"},
            },
        )

        rule.process_rule()

        affected = rule.get_affected_stages()
        self.assertTrue(len(affected) >= 1)
        self.assertTrue(any("base.usda" in s for s in affected))
        self._success = True

    async def test_flatten_logs_completion(self):
        stage = Usd.Stage.Open(_UR10E_USD)
        os.makedirs(os.path.join(self._tmpdir, "payloads"), exist_ok=True)

        rule = FlattenRule(
            source_stage=stage,
            package_root=self._tmpdir,
            destination_path="payloads",
            args={
                "input_stage_path": _UR10E_USD,
                "params": {"output_path": "base.usda"},
            },
        )

        rule.process_rule()

        log = rule.get_operation_log()
        self.assertTrue(any("FlattenRule start" in msg for msg in log))
        self.assertTrue(any("FlattenRule completed" in msg for msg in log))
        self._success = True
