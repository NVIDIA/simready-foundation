# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""The 2026.10.0 asset-profile versions differ from their predecessors only where intended.

Each new version swaps in the FET006 versions that leave VM.MAT.001 out and requires
FET009_MaterialCoverage after them, which holds VM.MAT.001. Robot-Body 4.0.0 also leaves out the deprecated
CAP023_RobotMaterials.Isaac. The robot profiles require neutral Core and align their
runtime Core capabilities with it. Robot 4.0.0 requires Newton; Prop 5.0.0
adds Object Forward, material coverage, and runtime Core alignment to 4.0.0.
"""

from pathlib import Path

import pytest
from simready.foundation.contracts import (
    load_capability_definitions,
    load_feature_definitions,
    load_profile_definitions,
    resolve_profile,
)
from simready.foundation.validation import build_validation_plan

_ROBOT_MATERIALS = "CAP023_RobotMaterials.Isaac.0-1-0"
_CORE = "CAP000_Core.0-2-0"
_CORE_SWAPS = {
    f"CAP000_Core.{runtime}.0-1-0": f"CAP000_Core.{runtime}.0-2-0"
    for runtime in ("PhysX", "Newton", "MuJoCo", "Isaac")
}
_MATERIAL_COVERAGE = ("FET009_MaterialCoverage.0-1-0", False)
_FET006_SWAPS = {
    "FET006_Materials.0-2-0": "FET006_Materials.0-3-0",
    "FET006_Materials.Openpbr.0-1-0": "FET006_Materials.Openpbr.0-2-0",
    "FET006_Materials.MDL.0-2-0": "FET006_Materials.MDL.0-3-0",
}
_VERSIONS = [
    ("Robotics-Prop", "4.0.0", "5.0.0", ()),
    ("Robot-Body", "3.1.0", "4.0.0", (_ROBOT_MATERIALS,)),
    ("Robot-Gripper", "3.0.0", "4.0.0", ()),
]


def _catalog():
    roots = sorted(Path(__file__).parents[2].glob("simready_foundation_tier_*/simready/foundation/tier_*"))
    features = load_feature_definitions([root / "features" for root in roots])
    capabilities = load_capability_definitions([root / "capabilities" for root in roots])
    profiles = load_profile_definitions([root / "profiles" for root in roots])
    return features, capabilities, profiles


def _selectors(items):
    return [(str(item.selector), item.optional) for item in items]


def _with_material_coverage(selectors):
    """Insert the required FET009 selector after the last FET006 selector."""
    last = max(i for i, (selector, _) in enumerate(selectors) if selector.startswith("FET006_"))
    return selectors[: last + 1] + [_MATERIAL_COVERAGE] + selectors[last + 1 :]


@pytest.mark.parametrize(("name", "old", "new", "dropped"), _VERSIONS)
def test_new_version_swaps_fet006_and_adds_material_coverage(name, old, new, dropped):
    _, _, profiles = _catalog()
    before, after = profiles[name, old], profiles[name, new]

    expected_features = _with_material_coverage(
        [(_FET006_SWAPS.get(selector, selector),
          False if name != "Robotics-Prop" and ".Newton." in selector else optional)
         for selector, optional in _selectors(before.features)]
    )
    if name == "Robotics-Prop":
        expected_features.insert(0, ("FET008_ObjectForward.0-1-0", False))
    assert _selectors(after.features) == expected_features
    expected_capabilities = [
        (_CORE_SWAPS.get(selector, selector),
         False if name != "Robotics-Prop" and ".Newton." in selector else optional)
        for selector, optional in _selectors(before.capabilities)
        if selector not in dropped
    ]
    if (_CORE, False) not in expected_capabilities:
        expected_capabilities.insert(0, (_CORE, False))
    assert _selectors(after.capabilities) == expected_capabilities


@pytest.mark.parametrize(("name", "old", "new", "dropped"), _VERSIONS)
def test_new_version_requires_material_binding_and_neutral_core(name, old, new, dropped):
    features, capabilities, profiles = _catalog()
    plans = {
        version: build_validation_plan(
            resolve_profile(profiles[name, version], features, capabilities), features, capabilities
        )
        for version in (old, new)
    }

    core_requirements = set(capabilities[_CORE].requirements)
    added_requirements = {"AF.001"} if name == "Robotics-Prop" else {
        requirement
        for contract in (*plans[new].features, *plans[new].capabilities)
        if ".Newton." in contract.id
        for requirement in contract.requirements
    }
    if name != "Robotics-Prop":
        added_requirements.update(capabilities["CAP024_BaseArticulation.0-1-0"].requirements)
    assert set(plans[new].required_requirements) == (
        set(plans[old].required_requirements) | core_requirements | added_requirements
    )
    assert "VM.MAT.001" in plans[new].required_requirements
    resolved = {item.id: item.optional for item in plans[new].capabilities}
    assert resolved[_CORE] is False
    assert not set(_CORE_SWAPS) & resolved.keys()
    for capability in dropped:
        assert capability not in resolved


def test_prop_version_catalog_is_consolidated():
    _, _, profiles = _catalog()
    assert {version for name, version in profiles if name == "Robotics-Prop"} == {
        "3.0.0", "3.1.0", "3.2.0", "3.3.0", "4.0.0", "5.0.0",
    }


@pytest.mark.parametrize("name", ["Robot-Body", "Robot-Gripper"])
def test_newton_is_required_in_robot_4_only(name):
    features, capabilities, profiles = _catalog()
    profile = profiles[name, "4.0.0"]
    selected = [item for item in (*profile.features, *profile.capabilities) if ".Newton." in str(item.selector)]
    assert len(selected) == 5
    assert all(not item.optional for item in selected)
    plan = build_validation_plan(resolve_profile(profile, features, capabilities), features, capabilities)
    assert {"NEWTON.COL.001", "NEWTON.DJ.001", "NEWTON.BA.001", "RV.004"} <= set(plan.required_requirements)
    assert all(not item.optional for item in plan.feature_evidence if ".Newton." in item.feature_id)
    for (profile_name, version), previous in profiles.items():
        if profile_name == name and version != "4.0.0":
            assert all(item.optional for item in (*previous.features, *previous.capabilities)
                       if ".Newton." in str(item.selector))
