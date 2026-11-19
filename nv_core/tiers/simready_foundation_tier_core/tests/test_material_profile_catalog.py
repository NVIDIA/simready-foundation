# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Check that Material 1.0.0 validates a material as a self-contained SimReady package."""

from pathlib import Path

from simready.foundation.contracts import (
    load_capability_definitions,
    load_feature_definitions,
    load_profile_definitions,
    resolve_profile,
)
from simready.foundation.validation import build_validation_plan

_PACKAGE_CAPABILITIES = {
    "CAP000_Core.0-2-0",
    "CAP031_SelfContainedPackage.0-1-0",
    "CAP033_SimReadyPackage.0-4-0",
}


def _plan():
    roots = sorted(Path(__file__).parents[2].glob("simready_foundation_tier_*/simready/foundation/tier_*"))
    features = load_feature_definitions([root / "features" for root in roots])
    capabilities = load_capability_definitions([root / "capabilities" for root in roots])
    profiles = load_profile_definitions([root / "profiles" for root in roots])
    resolved = resolve_profile(profiles["Material", "1.0.0"], features, capabilities)
    return resolved, build_validation_plan(resolved, features, capabilities)


def test_material_selects_the_package_capabilities_as_required():
    resolved, plan = _plan()

    selected = {item.id: item.optional for item in resolved.capabilities}
    assert {cap: selected.get(cap) for cap in _PACKAGE_CAPABILITIES} == dict.fromkeys(_PACKAGE_CAPABILITIES, False)
    required = set(plan.required_requirements)
    assert {"NP.005", "com.nvidia.usd.AA.001", "SR.002", "SR.004"} <= required


def test_material_leaves_out_binding_and_non_visual_materials():
    resolved, plan = _plan()

    selected = {item.id.split(".")[0] for item in resolved.capabilities}
    assert not selected & {"CAP007_NonVisualMaterials", "CAP009_MaterialBinding"}
    planned = set(plan.required_requirements) | set(plan.optional_requirements)
    assert not planned & {"VM.MAT.001", "com.nvidia.simready.NVM.004", "NVM.004"}
