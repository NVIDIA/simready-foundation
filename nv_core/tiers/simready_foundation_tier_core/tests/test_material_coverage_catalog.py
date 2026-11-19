# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Check the Material Coverage contract and its adoption in the 2026.10.0 profile versions."""

from pathlib import Path

import pytest
from simready.foundation.contracts import (
    load_capability_definitions,
    load_feature_definitions,
    load_profile_definitions,
    resolve_profile,
)
from simready.foundation.validation import build_validation_plan

_COVERAGE = "FET009_MaterialCoverage.0-1-0"
# The FET006 render tests, which FET009 shares.
_RUNTIME_TESTS = (
    "simready.foundation.tier_core.runtime_tests:preview_surface_renders",
    "simready.foundation.tier_core.runtime_tests:openpbr_renders",
    "simready.foundation.tier_core.runtime_tests:mdl_renders",
)
_ADAPTERS = ("skill:simready-foundation-conform-fet-009-standard",)


def _catalog():
    roots = sorted(Path(__file__).parents[2].glob("simready_foundation_tier_*/simready/foundation/tier_*"))
    features = load_feature_definitions([root / "features" for root in roots])
    capabilities = load_capability_definitions([root / "capabilities" for root in roots])
    profiles = load_profile_definitions([root / "profiles" for root in roots])
    return features, capabilities, profiles


def test_material_coverage_contract():
    features, _, _ = _catalog()
    feature = features[_COVERAGE]

    assert feature.all_requirements == ("VM.MAT.001",)
    assert [str(item) for item in feature.dependencies] == ["FET006_Materials.0-3-0"]
    assert feature.capabilities == ()
    assert feature.runtime_tests == _RUNTIME_TESTS
    assert feature.adapters == _ADAPTERS


@pytest.mark.parametrize(
    ("name", "version"),
    [("Robotics-Prop", "5.0.0"), ("Robot-Body", "4.0.0"), ("Robot-Gripper", "4.0.0")],
)
def test_material_coverage_and_binding_are_required(name, version):
    features, capabilities, profiles = _catalog()
    resolved = resolve_profile(profiles[name, version], features, capabilities)

    assert next(item for item in resolved.features if item.id == _COVERAGE).optional is False
    plan = build_validation_plan(resolved, features, capabilities)
    assert "VM.MAT.001" in plan.required_requirements
    assert not [item for item in plan.capabilities if str(item.id).startswith("CAP009_")]
    evidence = next(item for item in plan.feature_evidence if item.feature_id == _COVERAGE)
    assert evidence.optional is False
    assert evidence.runtime_tests == _RUNTIME_TESTS
    assert evidence.adapters == _ADAPTERS
