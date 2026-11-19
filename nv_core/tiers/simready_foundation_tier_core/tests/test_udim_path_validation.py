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
"""Regression coverage for shared UDIM path handling."""

import importlib.util
from pathlib import Path

PATH_UTILS_PATH = Path(__file__).parents[1] / "simready/foundation/tier_core/rules_and_reqs/core/path_utils.py"
PATH_UTILS_SPEC = importlib.util.spec_from_file_location("core_path_utils", PATH_UTILS_PATH)
assert PATH_UTILS_SPEC and PATH_UTILS_SPEC.loader
path_utils = importlib.util.module_from_spec(PATH_UTILS_SPEC)
PATH_UTILS_SPEC.loader.exec_module(path_utils)

sidecar_json_identifier = path_utils.sidecar_json_identifier
thumbnail_png_identifier = path_utils.thumbnail_png_identifier
resolve_existing_udim_template_path = path_utils.resolve_existing_udim_template_path
resolve_udim_template_path = path_utils.resolve_udim_template_path
udim_tiles_exist = path_utils.udim_tiles_exist


class _UriLayer:
    identifier = "omniverse://server/library/chair.usd"

    def ComputeAbsolutePath(self, relative_path: str) -> str:
        return "omniverse://server/library/" + relative_path


def test_sidecar_json_identifier_keeps_uri_scheme():
    assert sidecar_json_identifier(_UriLayer()) == "omniverse://server/library/chair.json"


def test_thumbnail_png_identifier_keeps_uri_scheme():
    assert thumbnail_png_identifier(_UriLayer()) == "omniverse://server/library/.thumbs/256x256/chair.usd.png"


def test_resolve_udim_template_path_anchors_authored_path(tmp_path):
    layer_path = tmp_path / "asset" / "root.usda"

    result = resolve_udim_template_path(
        authored_path="./textures/albedo.<UDIM>.png",
        anchor_file_path=str(layer_path),
    )

    assert result == (layer_path.parent / "textures" / "albedo.<UDIM>.png").as_posix()


def test_udim_tiles_exist_requires_matching_four_digit_tile(tmp_path):
    template = tmp_path / "albedo.<UDIM>.png"
    (tmp_path / "albedo.preview.png").touch()
    (tmp_path / "albedo.10001.png").touch()

    assert not udim_tiles_exist(template.as_posix())

    (tmp_path / "albedo.1001.png").touch()

    assert udim_tiles_exist(template.as_posix())


def test_aa001_resolves_existing_udim_tile(tmp_path):
    layer_path = tmp_path / "asset" / "root.usda"
    texture_dir = layer_path.parent / "textures"
    texture_dir.mkdir(parents=True)
    (texture_dir / "albedo.1001.png").touch()

    result = resolve_existing_udim_template_path(
        authored_path="./textures/albedo.<UDIM>.png",
        anchor_file_path=str(layer_path),
    )

    assert Path(result) == texture_dir / "albedo.<UDIM>.png"


def test_aa001_rejects_udim_template_without_tiles(tmp_path):
    layer_path = tmp_path / "asset" / "root.usda"
    layer_path.parent.mkdir()

    result = resolve_existing_udim_template_path(
        authored_path="./textures/albedo.<UDIM>.png",
        anchor_file_path=str(layer_path),
    )

    assert result == ""


is_builtin_mdl_search_path = path_utils.is_builtin_mdl_search_path


def test_builtin_mdl_search_path_accepts_the_forms_the_runtime_resolves():
    for authored in (
        "OmniPBR.mdl",
        "omnipbr.MDL",
        "OmniGlass.mdl",
        "OmniPBRBase.mdl",
        "OmniPBR_Opacity.mdl",
        "OmniGlass_Opacity.mdl",
        "SimPBR.mdl",
        "nvidia/core_definitions.mdl",
        "nvidia\\core_definitions.mdl",
        "OmniSurface/OmniSurfaceBase.mdl",
        "materialx/pbrlib.mdl",
        "gltf/pbr.mdl",
    ):
        assert is_builtin_mdl_search_path(authored), authored


def test_builtin_mdl_search_path_rejects_names_kit_does_not_resolve_as_written():
    # OmniSurfaceBase.mdl and core_definitions.mdl live in subfolders of a search folder,
    # so only their folder-qualified names resolve. omnipbr_base.mdl matches no shipped
    # file. The MDL standard library and the renderer's own modules are not material
    # sources, and their generic names would match an asset's own module.
    for authored in ("OmniSurfaceBase.mdl", "core_definitions.mdl", "omnipbr_base.mdl", "base.mdl", "Default.mdl"):
        assert not is_builtin_mdl_search_path(authored), authored


def test_builtin_mdl_search_path_rejects_paths_that_name_a_location():
    # An anchored, absolute, directory-qualified or URI path states where the file is,
    # so NP.008 still has to find it there.
    for authored in ("./OmniPBR.mdl", "../OmniPBR.mdl", "/kit/mdl/OmniPBR.mdl", "materials/OmniPBR.mdl", "omniverse://srv/OmniPBR.mdl"):
        assert not is_builtin_mdl_search_path(authored), authored


def test_builtin_mdl_search_path_rejects_modules_the_runtime_does_not_ship():
    assert not is_builtin_mdl_search_path("Custom.mdl")


is_builtin_mdl_module = path_utils.is_builtin_mdl_module


def test_builtin_mdl_module_matches_shipped_modules_at_any_path():
    # VM.MDL.001 matches by name wherever the file sits, so a packaged copy counts too.
    for authored in ("OmniPBR_Opacity.mdl", "./materials/OmniPBRBase.mdl", "OmniSurface/OmniSurfaceBase.mdl", "./mdl/nvidia/core_definitions.mdl"):
        assert is_builtin_mdl_module(authored), authored


def test_builtin_mdl_module_does_not_claim_an_assets_own_generically_named_module():
    for authored in ("./materials/default.mdl", "./materials/base.mdl", "./materials/Custom.mdl"):
        assert not is_builtin_mdl_module(authored), authored
