# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Check Object Forward contracts and profile adoption."""

from pathlib import Path

from simready.foundation.contracts import (
    load_feature_definitions,
)


def test_object_forward_contract():
    root = Path(__file__).parents[1] / "simready/foundation/tier_core"
    features = load_feature_definitions([root / "features"])
    feature_id = "FET008_ObjectForward.0-1-0"
    feature = features[feature_id]
    assert feature.all_requirements == ("AF.001",)
    assert not feature.capabilities
    assert feature.runtime_tests == (
        "simready.foundation.tier_core.runtime_tests:object_forward_contract",
        "simready.foundation.tier_core.runtime_tests:object_forward_camera_response",
    )


def test_object_forward_profile_adoption_preserves_existing_bundles():
    from simready.foundation.contracts import (
        load_capability_definitions,
        load_profile_definitions,
        resolve_profile,
    )
    from simready.foundation.validation import build_validation_plan

    roots = sorted(Path(__file__).parents[2].glob("simready_foundation_tier_*/simready/foundation/tier_*"))
    features = load_feature_definitions([root / "features" for root in roots])
    caps = load_capability_definitions([root / "capabilities" for root in roots])
    profiles = load_profile_definitions([root / "profiles" for root in roots])
    forward = "FET008_ObjectForward.0-1-0"
    for name, old, new, optional in [
        ("Robotics-Prop", "4.0.0", "5.0.0", False),
        ("Robot-Body", "3.0.0", "3.1.0", True),
    ]:
        before = profiles[name, old]
        after = profiles[name, new]
        if name == "Robot-Body":
            assert after.features[1:] == before.features
            assert after.capabilities == before.capabilities
        resolved = resolve_profile(after, features, caps)
        selected = next(item for item in resolved.features if item.id == forward)
        assert selected.optional is optional
        plan = build_validation_plan(resolved, features, caps)
        facing = next(item for item in plan.requirements if item.id == "AF.001")
        assert facing.optional is optional
        assert "UN.006" in plan.required_requirements
        evidence = next(item for item in plan.feature_evidence if item.feature_id == forward)
        assert evidence.optional is optional
        assert len(evidence.runtime_tests) == 2
        assert evidence.adapters == ("skill:simready-foundation-conform-fet-008-object-forward",)
