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
from isaacsim.asset.transformer.organizer.rules import utils
from pxr import Sdf, Usd

# Path to UR10e test asset
_TEST_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
    "data",
    "tests",
    "ur10e",
)
_UR10E_USD = os.path.join(_TEST_DATA_DIR, "ur10e.usd")


class TestSanitizePrimName(omni.kit.test.AsyncTestCase):
    async def test_sanitize_prim_name_basic(self):
        result = utils.sanitize_prim_name("valid_name")
        self.assertEqual(result, "valid_name")

    async def test_sanitize_prim_name_with_special_chars(self):
        result = utils.sanitize_prim_name("name-with.special!chars")
        self.assertEqual(result, "name_with_special_chars")

    async def test_sanitize_prim_name_starting_with_digit(self):
        result = utils.sanitize_prim_name("123name")
        self.assertEqual(result, "prim_123name")

    async def test_sanitize_prim_name_custom_prefix(self):
        result = utils.sanitize_prim_name("456test", prefix="custom_")
        self.assertEqual(result, "custom_456test")

    async def test_sanitize_prim_name_empty_string(self):
        result = utils.sanitize_prim_name("")
        self.assertEqual(result, "prim_")

    async def test_sanitize_prim_name_unicode(self):
        result = utils.sanitize_prim_name("tëst_nàmé")
        # Should replace non-alphanumeric chars
        self.assertFalse("ë" in result)
        self.assertFalse("à" in result)


class TestCreatePrimSpec(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_create_prim_spec_basic(self):
        layer_path = os.path.join(self._tmpdir, "test.usda")
        layer = Sdf.Layer.CreateNew(layer_path)

        prim_spec = utils.create_prim_spec(layer, "/TestPrim")

        self.assertIsNotNone(prim_spec)
        self.assertEqual(prim_spec.specifier, Sdf.SpecifierDef)
        self.assertEqual(prim_spec.path.pathString, "/TestPrim")

    async def test_create_prim_spec_with_type(self):
        layer_path = os.path.join(self._tmpdir, "test.usda")
        layer = Sdf.Layer.CreateNew(layer_path)

        prim_spec = utils.create_prim_spec(layer, "/TestXform", type_name="Xform")

        self.assertIsNotNone(prim_spec)
        self.assertEqual(prim_spec.typeName, "Xform")

    async def test_create_prim_spec_instanceable(self):
        layer_path = os.path.join(self._tmpdir, "test.usda")
        layer = Sdf.Layer.CreateNew(layer_path)

        prim_spec = utils.create_prim_spec(layer, "/TestPrim", instanceable=True)

        self.assertIsNotNone(prim_spec)
        self.assertTrue(prim_spec.instanceable)

    async def test_create_prim_spec_over_specifier(self):
        layer_path = os.path.join(self._tmpdir, "test.usda")
        layer = Sdf.Layer.CreateNew(layer_path)

        prim_spec = utils.create_prim_spec(layer, "/TestPrim", specifier=Sdf.SpecifierOver)

        self.assertIsNotNone(prim_spec)
        self.assertEqual(prim_spec.specifier, Sdf.SpecifierOver)


class TestGetRelativeLayerPath(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_get_relative_layer_path_same_dir(self):
        layer_path = os.path.join(self._tmpdir, "base.usda")
        layer = Sdf.Layer.CreateNew(layer_path)
        target_path = os.path.join(self._tmpdir, "target.usda")

        rel_path = utils.get_relative_layer_path(layer, target_path)

        self.assertEqual(rel_path, "target.usda")

    async def test_get_relative_layer_path_subdir(self):
        layer_path = os.path.join(self._tmpdir, "base.usda")
        layer = Sdf.Layer.CreateNew(layer_path)
        target_path = os.path.join(self._tmpdir, "subdir", "target.usda")

        rel_path = utils.get_relative_layer_path(layer, target_path)

        self.assertEqual(rel_path, "subdir/target.usda")

    async def test_get_relative_layer_path_parent_dir(self):
        subdir = os.path.join(self._tmpdir, "subdir")
        os.makedirs(subdir, exist_ok=True)
        layer_path = os.path.join(subdir, "base.usda")
        layer = Sdf.Layer.CreateNew(layer_path)
        target_path = os.path.join(self._tmpdir, "target.usda")

        rel_path = utils.get_relative_layer_path(layer, target_path)

        self.assertEqual(rel_path, "../target.usda")


class TestClearCompositionArcs(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_clear_composition_arcs_references(self):
        layer_path = os.path.join(self._tmpdir, "test.usda")
        layer = Sdf.Layer.CreateNew(layer_path)

        prim_spec = utils.create_prim_spec(layer, "/TestPrim")
        prim_spec.referenceList.Append(Sdf.Reference("other.usda"))
        self.assertTrue(prim_spec.hasReferences)

        utils.clear_composition_arcs(prim_spec)

        self.assertFalse(prim_spec.hasReferences)

    async def test_clear_composition_arcs_payloads(self):
        layer_path = os.path.join(self._tmpdir, "test.usda")
        layer = Sdf.Layer.CreateNew(layer_path)

        prim_spec = utils.create_prim_spec(layer, "/TestPrim")
        prim_spec.payloadList.Append(Sdf.Payload("other.usda"))
        self.assertTrue(prim_spec.hasPayloads)

        utils.clear_composition_arcs(prim_spec)

        self.assertFalse(prim_spec.hasPayloads)


class TestEnsurePrimHierarchy(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_ensure_prim_hierarchy_creates_parents(self):
        layer_path = os.path.join(self._tmpdir, "test.usda")
        layer = Sdf.Layer.CreateNew(layer_path)

        utils.ensure_prim_hierarchy(layer, "/Root/Child/GrandChild")

        root_spec = layer.GetPrimAtPath("/Root")
        child_spec = layer.GetPrimAtPath("/Root/Child")
        self.assertIsNotNone(root_spec)
        self.assertIsNotNone(child_spec)

    async def test_ensure_prim_hierarchy_deep_nesting(self):
        layer_path = os.path.join(self._tmpdir, "test.usda")
        layer = Sdf.Layer.CreateNew(layer_path)

        utils.ensure_prim_hierarchy(layer, "/A/B/C/D/E")

        for path in ["/A", "/A/B", "/A/B/C", "/A/B/C/D"]:
            self.assertIsNotNone(layer.GetPrimAtPath(path))


class TestCopyStageMetadata(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_copy_stage_metadata_from_ur10e(self):
        src_stage = Usd.Stage.Open(_UR10E_USD)

        dst_path = os.path.join(self._tmpdir, "dest.usda")
        dst_layer = Sdf.Layer.CreateNew(dst_path)

        utils.copy_stage_metadata(src_stage, dst_layer)

        # UR10e should have metersPerUnit and upAxis set
        meters_per_unit = dst_layer.pseudoRoot.GetInfo("metersPerUnit")
        up_axis = dst_layer.pseudoRoot.GetInfo("upAxis")
        # These should be copied from the source stage
        self.assertIsNotNone(meters_per_unit)
        self.assertIsNotNone(up_axis)


class TestFilesAreIdentical(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_files_are_identical_true(self):
        file1 = os.path.join(self._tmpdir, "file1.txt")
        file2 = os.path.join(self._tmpdir, "file2.txt")
        content = b"identical content for testing purposes"

        with open(file1, "wb") as f:
            f.write(content)
        with open(file2, "wb") as f:
            f.write(content)

        self.assertTrue(utils.files_are_identical(file1, file2))

    async def test_files_are_identical_false_different_content(self):
        file1 = os.path.join(self._tmpdir, "file1.txt")
        file2 = os.path.join(self._tmpdir, "file2.txt")

        with open(file1, "wb") as f:
            f.write(b"content one")
        with open(file2, "wb") as f:
            f.write(b"content two")

        self.assertFalse(utils.files_are_identical(file1, file2))

    async def test_files_are_identical_false_different_size(self):
        file1 = os.path.join(self._tmpdir, "file1.txt")
        file2 = os.path.join(self._tmpdir, "file2.txt")

        with open(file1, "wb") as f:
            f.write(b"short")
        with open(file2, "wb") as f:
            f.write(b"much longer content")

        self.assertFalse(utils.files_are_identical(file1, file2))


class TestClearInstanceableRecursive(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_clear_instanceable_recursive_single(self):
        layer_path = os.path.join(self._tmpdir, "test.usda")
        layer = Sdf.Layer.CreateNew(layer_path)

        prim_spec = utils.create_prim_spec(layer, "/Parent", instanceable=True)

        utils.clear_instanceable_recursive(prim_spec)

        self.assertFalse(prim_spec.instanceable)

    async def test_clear_instanceable_recursive_with_children(self):
        layer_path = os.path.join(self._tmpdir, "test.usda")
        layer = Sdf.Layer.CreateNew(layer_path)

        parent_spec = utils.create_prim_spec(layer, "/Parent", instanceable=True)
        child_spec = utils.create_prim_spec(layer, "/Parent/Child", instanceable=True)
        grandchild_spec = utils.create_prim_spec(layer, "/Parent/Child/GrandChild", instanceable=True)

        utils.clear_instanceable_recursive(parent_spec)

        self.assertFalse(parent_spec.instanceable)
        self.assertFalse(child_spec.instanceable)
        self.assertFalse(grandchild_spec.instanceable)


class TestFindAncestorMatching(omni.kit.test.AsyncTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_find_ancestor_matching_in_ur10e(self):
        stage = Usd.Stage.Open(_UR10E_USD)

        # Find the default prim
        default_prim = stage.GetDefaultPrim()
        if default_prim:
            # Try to find an ancestor of a child prim
            for child in default_prim.GetChildren():
                result = utils.find_ancestor_matching(child, lambda p: p.GetTypeName() == "Xform")
                # The default prim or its ancestors should match
                break

    async def test_find_ancestor_matching_not_found(self):
        stage = Usd.Stage.Open(_UR10E_USD)

        default_prim = stage.GetDefaultPrim()
        if default_prim:
            result = utils.find_ancestor_matching(default_prim, lambda p: p.GetTypeName() == "Camera")
            self.assertIsNone(result)
