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

PATH_UTILS_PATH = Path(__file__).parents[1] / "simready/foundation/tier_core/capabilities/core/path_utils.py"
PATH_UTILS_SPEC = importlib.util.spec_from_file_location("core_path_utils", PATH_UTILS_PATH)
assert PATH_UTILS_SPEC and PATH_UTILS_SPEC.loader
path_utils = importlib.util.module_from_spec(PATH_UTILS_SPEC)
PATH_UTILS_SPEC.loader.exec_module(path_utils)

resolve_existing_udim_template_path = path_utils.resolve_existing_udim_template_path
resolve_udim_template_path = path_utils.resolve_udim_template_path
udim_tiles_exist = path_utils.udim_tiles_exist


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
