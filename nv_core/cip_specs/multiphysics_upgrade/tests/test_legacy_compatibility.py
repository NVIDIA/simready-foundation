# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""The historical CIP adapter import paths must keep resolving.

CIP configurations, docs, and existing scripts import
``asset_handler_modules.multiphysics_upgrade``. Those imports must reach the
same module objects the packaged distribution exposes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_CIP_SPECS = Path(__file__).resolve().parents[2]
if str(_CIP_SPECS) not in sys.path:
    sys.path.insert(0, str(_CIP_SPECS))

pytest.importorskip("pxr", reason="USD Python bindings are required")


def test_legacy_package_exposes_the_packaged_modules():
    import simready.multiphysics_upgrade as packaged
    from asset_handler_modules import multiphysics_upgrade as legacy

    assert legacy.core is packaged.core
    assert legacy.edges is packaged.edges
    assert legacy.runner is packaged.runner
    assert legacy.types is packaged.types
    assert legacy.neutral_to_runtimes is packaged.neutral_to_runtimes


def test_legacy_submodule_imports_resolve():
    from asset_handler_modules.multiphysics_upgrade.neutral_to_runtimes import upgrade_stage
    from asset_handler_modules.multiphysics_upgrade.runner import build_plan, main
    from simready.multiphysics_upgrade import neutral_to_runtimes, runner

    assert main is runner.main
    assert build_plan is runner.build_plan
    assert upgrade_stage is neutral_to_runtimes.upgrade_stage


def test_feature_adapter_registrations_are_intact():
    from asset_handler_modules import multiphysics_upgrade as legacy

    metadata = getattr(legacy.minimal_standard_0_1_0_to_1_0_1, "_feature_adapter", None)
    assert metadata is not None
    assert metadata["input_feature_id"] == "FET001_MinimalPlaceableVisual.0-1-0"
    assert metadata["output_feature_id"] == "FET001_MinimalPlaceableVisual.1-0-1"
    assert len(legacy.edges.ORDERED_EDGES) == 12
