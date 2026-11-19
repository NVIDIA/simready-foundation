# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""CAP039 allocation, dependency resolution and deferred profile adoption."""

import json
from pathlib import Path

from simready.foundation.contracts import (
    CapabilitySelector,
    ProfileDefinition,
    ProfileSelector,
    load_capability_definitions,
    load_feature_definitions,
    load_profile_definitions,
    resolve_profile,
)
from simready.foundation.validation import build_validation_plan

ROOT = Path(__file__).parents[1] / "simready/foundation/tier_core"
CAP = "CAP039_ObjectAffordances.0-1-0"


def test_standalone_capability_resolves_generic_semantic_labels():
    capabilities = load_capability_definitions([ROOT / "capabilities"])
    features = load_feature_definitions([ROOT / "features"])
    definition = capabilities[CAP]
    assert definition.requirements == ("AFF.001", "AFF.002")
    assert tuple(map(str, definition.features)) == ("FET011_SemanticLabels.0-2-0",)
    profile = ProfileDefinition(
        "Affordances-Acceptance", "1.0.0", capabilities=(ProfileSelector(CapabilitySelector.parse(CAP)),)
    )
    resolved = resolve_profile(profile, features, capabilities)
    plan = build_validation_plan(resolved, features, capabilities)
    assert {"AFF.001", "AFF.002", "SL.001", "SL.002", "SL.003"} <= set(plan.required_requirements)
    assert not any(e.feature_id.startswith("FET039") for e in plan.feature_evidence)


def test_profile_adoption_is_deferred_and_family_029_is_preserved():
    profiles = load_profile_definitions([ROOT / "profiles"])
    assert all(not any("CAP039" in str(s.selector) for s in p.capabilities) for p in profiles.values())
    connection = json.loads((ROOT / "capabilities/CAP029_ConnectionJoint.0-1-0.json").read_text())
    assert connection["requirements"] == ["CN.005", "CN.009"]
    assert not (ROOT / "features/FET_029_STANDARD-0.1.0.json").exists()
    catalog = json.loads((ROOT / "catalog-map.json").read_text())["contracts"]
    assert next(x for x in catalog if x["id"] == CAP)["kind"] == "capability"
