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
"""Kit-free feature-adapter provider contract tests."""

from __future__ import annotations

import importlib
import importlib.machinery
import sys
import types
from pathlib import Path

import pytest


def _set_transformer_installed(monkeypatch: pytest.MonkeyPatch, installed: bool) -> None:
    name = "isaacsim.asset.transformer"
    module = None
    if installed:
        module = types.ModuleType(name)
        module.__spec__ = importlib.machinery.ModuleSpec(name, None)
    monkeypatch.setitem(sys.modules, name, module)


def _load_provider():
    tools_root = Path(__file__).resolve().parents[1] / "tools"
    sys.path.insert(0, str(tools_root))
    try:
        return importlib.import_module("asset_handler_modules")
    finally:
        sys.path.remove(str(tools_root))


def test_provider_loads_without_kit_or_cip() -> None:
    provider = _load_provider()
    definitions = provider.get_feature_adapters()

    assert definitions
    assert "omni.cip.configurable.feature_adapter" not in sys.modules
    assert "isaacsim.asset.transformer" not in sys.modules
    assert all(callable(definition.callback) for definition in definitions)
    assert len({definition.name for definition in definitions}) == len(definitions)


def test_provider_contains_current_isaac_composition_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _load_provider()
    _set_transformer_installed(monkeypatch, True)
    by_name = {definition.name: definition for definition in provider.get_feature_adapters()}

    prop = by_name["minimal_to_isaac_prop_standalone"]
    assert (prop.input_feature, prop.input_feature_version) == (
        "FET001_MinimalPlaceableVisual.1-0-1",
        "0.0.0",
    )
    assert (prop.output_feature, prop.output_feature_version) == (
        "CAP100_IsaacComposition.Isaac.0-4-0",
        "0.0.0",
    )

    robot = by_name["minimal_to_isaac_robot_standalone"]
    assert (robot.input_feature, robot.input_feature_version) == (
        "FET001_MinimalPlaceableVisual.1-0-1",
        "0.0.0",
    )
    assert (robot.output_feature, robot.output_feature_version) == (
        "CAP101_RobotComposition.Isaac.0-1-0",
        "0.0.0",
    )


def test_provider_omits_isaac_adapters_without_isaac_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _load_provider()
    # Register the Isaac adapters first so the provider must filter, not just skip the import.
    _set_transformer_installed(monkeypatch, True)
    provider.get_feature_adapters()
    _set_transformer_installed(monkeypatch, False)
    names = {definition.name for definition in provider.get_feature_adapters()}

    assert "minimal_to_isaac_prop_standalone" not in names
    assert "minimal_to_isaac_robot_standalone" not in names
    assert names
