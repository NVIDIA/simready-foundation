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
"""Tests for the Isaac prop adapter's shared output-package promotion logic.

The adapter package
(``nv_core/cip_specs/asset_handler_modules/physx_to_isaacsim/__init__.py``)
imports the Kit-extension (``isaacsim.asset.transformer``) and CIP
(``omni.cip.configurable.feature_adapter``) modules at import scope, so it cannot
be imported in a USD-only environment. The reusable promotion/copy-back logic
lives in a sibling ``promotion.py`` that depends only on ``pxr`` and the standard
library; these tests load that module directly by path and exercise it.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest

pytest.importorskip("pxr")
from pxr import Sdf, Usd  # noqa: E402

_PROMOTION_PATH = Path(__file__).resolve().parents[2] / "asset_handler_modules" / "physx_to_isaacsim" / "promotion.py"


def _load_promotion():
    spec = importlib.util.spec_from_file_location("physx_to_isaacsim_promotion", _PROMOTION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


promotion = _load_promotion()


def _fake_report(results):
    return types.SimpleNamespace(results=results)


def _fake_result(*, name, success, error=None, log=None):
    return types.SimpleNamespace(
        rule=types.SimpleNamespace(name=name),
        success=success,
        error=error,
        log=log or [],
    )


def test_promotion_module_path_exists():
    assert _PROMOTION_PATH.is_file()


def test_raise_on_rule_failure_passes_when_all_success():
    report = _fake_report(
        [
            _fake_result(name="A", success=True, log=[{"message": "ok"}]),
            _fake_result(name="B", success=True),
        ]
    )
    promotion.raise_on_rule_failure(report)


def test_raise_on_rule_failure_raises_on_first_failure():
    report = _fake_report(
        [
            _fake_result(name="A", success=True),
            _fake_result(name="B", success=False, error="boom"),
        ]
    )
    with pytest.raises(RuntimeError, match="boom"):
        promotion.raise_on_rule_failure(report)


def _build_transformed_package(root: Path, interface_filename: str) -> Path:
    """Create a minimal transformed package with a root layer and sibling dirs."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "payloads").mkdir()
    (root / "payloads" / "base.usda").write_text("#usda 1.0\n", encoding="utf-8")
    (root / "Textures").mkdir()
    (root / "Textures" / "tex.png").write_bytes(b"\x89PNG\r\n")

    layer = Sdf.Layer.CreateNew(str(root / interface_filename))
    Sdf.PrimSpec(layer.pseudoRoot, "RootNode", Sdf.SpecifierDef)
    layer.defaultPrim = "RootNode"
    layer.subLayerPaths.append("./payloads/base.usda")
    layer.customLayerData = {"SimReady_Metadata": {"kind": "component"}}
    layer.documentation = "transformed"
    layer.Save()
    del layer
    return root


def test_promote_transformed_package_copies_root_and_moves_siblings(tmp_path):
    interface_filename = "asset.usd"

    package_dir = tmp_path / "package"
    package_dir.mkdir()
    # Junk dir that should be cleared before promotion (not .thumbs).
    (package_dir / "stale").mkdir()
    (package_dir / "stale" / "junk.txt").write_text("old", encoding="utf-8")
    thumbs = package_dir / ".thumbs"
    thumbs.mkdir()
    (thumbs / "thumb.png").write_bytes(b"keep")

    output_stage = Usd.Stage.CreateNew(str(package_dir / interface_filename))
    output_stage.GetRootLayer().Save()

    transformed_root = tmp_path / "temp_transformed_asset"
    _build_transformed_package(transformed_root, interface_filename)

    promotion.promote_transformed_package(output_stage, transformed_root, interface_filename)

    out_layer = output_stage.GetRootLayer()
    assert out_layer.defaultPrim == "RootNode"
    assert list(out_layer.subLayerPaths) == ["./payloads/base.usda"]
    assert dict(out_layer.customLayerData).get("SimReady_Metadata") == {"kind": "component"}
    assert out_layer.GetPrimAtPath("/RootNode") is not None

    # Sibling outputs promoted alongside the output root layer.
    assert (package_dir / "payloads" / "base.usda").is_file()
    assert (package_dir / "Textures" / "tex.png").is_file()
    # .thumbs preserved, stale dir cleared.
    assert (package_dir / ".thumbs" / "thumb.png").is_file()
    assert not (package_dir / "stale").exists()
    # Temporary package consumed; the reserved root-layer slot was not moved.
    assert not transformed_root.exists()


def test_promote_transformed_package_missing_dir_raises(tmp_path):
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    output_stage = Usd.Stage.CreateNew(str(package_dir / "asset.usd"))
    output_stage.GetRootLayer().Save()

    with pytest.raises(RuntimeError, match="Expected transformed asset directory not found"):
        promotion.promote_transformed_package(output_stage, tmp_path / "does_not_exist", "asset.usd")


def test_promote_transformed_package_missing_root_layer_raises(tmp_path):
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    output_stage = Usd.Stage.CreateNew(str(package_dir / "asset.usd"))
    output_stage.GetRootLayer().Save()

    empty_transformed = tmp_path / "temp_transformed_asset"
    empty_transformed.mkdir()

    with pytest.raises(RuntimeError, match="Transformed root layer not found"):
        promotion.promote_transformed_package(output_stage, empty_transformed, "asset.usd")
