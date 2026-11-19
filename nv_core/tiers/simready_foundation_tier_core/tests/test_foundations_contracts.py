# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import tomllib
from pathlib import Path
import sys

import pytest


PACKAGE_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from simready.foundation.contracts import (  # noqa: E402
    CapabilityDefinition,
    CapabilityId,
    CapabilitySelector,
    ContractError,
    FeatureDefinition,
    FeatureId,
    FeatureSelector,
    ProfileDefinition,
    ProfileSelector,
    ProfileTarget,
    load_capability_definitions,
    load_feature_definitions,
    load_profile_definitions,
    resolve_profile,
    resolve_profiles,
    validate_asset_against_profiles,
)
from simready.foundation.validation import build_validation_plan, validate_profiles  # noqa: E402


def _feature(
    feature_id: str,
    *,
    capabilities: tuple[str, ...] = (),
) -> FeatureDefinition:
    return FeatureDefinition.from_mapping(
        {
            "id": feature_id,
            "requirements": ["REQ.001"],
            "capabilities": list(capabilities),
            "additional_requirements": ["RUN.001"],
            "adapters": ["module:adapter"],
            "runtime_tests": ["suite:test"],
        }
    )


def test_feature_id_carries_name_runtime_and_version() -> None:
    feature_id = FeatureId.parse("FET004_Multibody.PhysX.2-0-2")

    assert feature_id.name == "FET004_Multibody"
    assert feature_id.family == "FET004"
    assert feature_id.runtime == "PhysX"
    assert feature_id.version == "2-0-2"
    assert str(feature_id) == "FET004_Multibody.PhysX.2-0-2"


@pytest.mark.parametrize(("id_type", "selector_type", "name"), [
    (FeatureId, FeatureSelector, "FET004_Multibody"),
    (CapabilityId, CapabilitySelector, "CAP024_BaseArticulation"),
])
def test_neutral_ids_and_selectors_preserve_versions_and_runtime_globs(id_type, selector_type, name):
    neutral = id_type.parse(f"{name}.00-release")
    physx = id_type.parse(f"{name}.PhysX.00-release")
    assert neutral.runtime == "OpenUSD"
    assert neutral.version == "00-release"
    assert str(neutral) == f"{name}.00-release"
    assert str(id_type.parse(f"{name}.OpenUSD.00-release")) == str(neutral)
    for selector, neutral_matches, runtime_matches in [
        (name, True, True),
        (f"{name}.*", True, True),
        (f"{name}.*.*", True, True),
        (f"{name}.00-release", True, False),
        (f"{name}.00-*", True, False),
        (f"{name}.PhysX", False, True),
        (f"{name}.Phys*.*", False, True),
        (f"{name}.OpenUSD.*", True, False),
        (f"{name}.*.00-*", True, True),
        (f"{name}.99-*", False, False),
    ]:
        parsed = selector_type.parse(selector)
        assert parsed.matches(neutral) is neutral_matches
        assert parsed.matches(physx) is runtime_matches
        assert selector_type.parse(str(parsed)).matches(neutral) is neutral_matches
        assert selector_type.parse(str(parsed)).matches(physx) is runtime_matches


@pytest.mark.parametrize(
    ("selector", "matches"),
    [
        ("FET004.*", True),
        ("FET004.PhysX.*", True),
        ("FET004.Newton.*", False),
        ("FET004_Multibody.PhysX.2-0-2", True),
    ],
)
def test_feature_selectors_support_family_runtime_and_version_wildcards(selector: str, matches: bool) -> None:
    feature_id = FeatureId.parse("FET004_Multibody.PhysX.2-0-2")

    assert FeatureSelector.parse(selector).matches(feature_id) is matches


def test_feature_identity_is_not_duplicated_in_legacy_fields() -> None:
    with pytest.raises(ContractError, match="only in 'id'"):
        FeatureDefinition.from_mapping(
            {
                "id": "FET004_Multibody.PhysX.2-0-2",
                "runtime": "PhysX",
                "version": "2-0-2",
                "additional_requirements": ["RUN.001"],
                "adapters": ["module:adapter"],
                "runtime_tests": ["suite:test"],
            }
        )


def test_features_require_runtime_tests_unless_they_are_sources() -> None:
    with pytest.raises(ContractError, match="source FET.*CAP-prefixed capability"):
        FeatureDefinition.from_mapping(
            {
                "id": "FET004_Multibody.2-0-2",
                "requirements": ["JT.001"],
            }
        )

    with pytest.raises(ContractError, match="additional_requirements and adapters"):
        FeatureDefinition.from_mapping(
            {
                "id": "FET004_Multibody.PhysX.2-0-4",
                "requirements": ["JT.001"],
                "runtime_tests": ["FET004:joint-movement"],
            }
        )

    feature = _feature("FET004_Multibody.PhysX.2-0-4")
    assert feature.all_requirements == ("REQ.001", "RUN.001")
    assert feature.runnable is True


def test_testless_fet_is_rejected_without_source_role() -> None:
    with pytest.raises(ContractError, match="source FET.*CAP-prefixed capability"):
        FeatureDefinition.from_mapping(
            {
                "id": "FET004_Multibody.2-0-2",
                "requirements": ["JT.001"],
                "runnable": False,
            }
        )


@pytest.mark.parametrize(
    ("selector", "matches"),
    [
        ("CAP024.*", True),
        ("CAP024.PhysX.*", True),
        ("CAP024.Newton.*", False),
        ("CAP024.Phys*.*", True),
        ("CAP024.*.0-1-0", True),
        ("CAP024.*.9-*", False),
        ("CAP024_BaseArticulation.PhysX", True),
        ("CAP024_BaseArticulation", True),
        ("*articulation*.*.*", True),
        ("*grasp*.*.*", False),
    ],
)
def test_capability_selectors_match_exactly_like_feature_selectors(selector: str, matches: bool) -> None:
    capability_id = CapabilityId.parse("CAP024_BaseArticulation.PhysX.0-1-0")

    assert CapabilitySelector.parse(selector).matches(capability_id) is matches


def test_capability_ids_and_selectors_require_cap_prefix() -> None:
    capability = CapabilityDefinition.from_mapping(
        {"id": "CAP006_Materials.0-1-0", "requirements": ["MAT.001"]}
    )

    assert capability.id == CapabilityId.parse("CAP006_Materials.0-1-0")
    with pytest.raises(ContractError, match="CAP.*prefix"):
        CapabilityDefinition.from_mapping(
            {"id": "physics.joints.0-1-0", "requirements": ["JT.001"]}
        )
    with pytest.raises(ContractError, match="FET.*prefix"):
        FeatureId.parse("physics.joints.0-1-0")
    # Selectors carry no prefix requirement: it is the ids that guarantee a
    # well-formed catalog, and demanding a prefix of a selector would forbid a
    # leading wildcard.
    assert CapabilitySelector.parse("*joints*").name == "*joints*"
    assert FeatureSelector.parse("*joints*").name == "*joints*"


def test_profile_expands_wildcards_and_preserves_optional_fets_and_caps() -> None:
    profile = ProfileDefinition(
        name="Robot",
        version="2.0.0",
        features=(
            ProfileSelector(FeatureSelector.parse("FET004.*"), optional=True),
            ProfileSelector(FeatureSelector.parse("FET004.PhysX.2-0-4")),
        ),
        capabilities=(
            ProfileSelector(CapabilitySelector.parse("CAP006*")),
            ProfileSelector(CapabilitySelector.parse("CAP007*"), optional=True),
        ),
    )
    features = {
        str(item.id): item
        for item in (
            _feature("FET004_Multibody.PhysX.2-0-2"),
            _feature("FET004_Multibody.PhysX.2-0-4"),
            _feature("FET004_Multibody.Newton.0-0-2"),
        )
    }
    capabilities = {
        "CAP006_Materials.0-1-0": CapabilityDefinition.from_mapping(
            {"id": "CAP006_Materials.0-1-0", "requirements": ["MAT.001"]}
        ),
        "CAP006_MDL.0-1-0": CapabilityDefinition.from_mapping(
            {"id": "CAP006_MDL.0-1-0", "requirements": ["MAT.MDL.001"]}
        ),
    }

    resolved = resolve_profile(profile, features, capabilities)

    assert [item.id for item in resolved.features] == [
        "FET004_Multibody.Newton.0-0-2",
        "FET004_Multibody.PhysX.2-0-2",
        "FET004_Multibody.PhysX.2-0-4",
    ]
    assert {item.id: item.optional for item in resolved.features} == {
        "FET004_Multibody.Newton.0-0-2": True,
        "FET004_Multibody.PhysX.2-0-2": True,
        "FET004_Multibody.PhysX.2-0-4": False,
    }
    assert [item.id for item in resolved.capabilities] == [
        "CAP006_MDL.0-1-0",
        "CAP006_Materials.0-1-0",
    ]


def test_required_unmatched_selector_fails_but_optional_unmatched_selector_does_not() -> None:
    required = ProfileDefinition(
        name="Required",
        version="1.0.0",
        features=(ProfileSelector(FeatureSelector.parse("FET999.*")),),
    )
    optional = ProfileDefinition(
        name="Optional",
        version="1.0.0",
        features=(ProfileSelector(FeatureSelector.parse("FET999.*"), optional=True),),
    )

    with pytest.raises(ContractError, match="matched no catalog entries"):
        resolve_profile(required, {})
    assert resolve_profile(optional, {}).features == ()


def test_profile_toml_accepts_keyed_and_explicit_selector_forms(tmp_path: Path) -> None:
    profile_path = tmp_path / "profiles.toml"
    profile_path.write_text(
        """
[Robot]
"2.0.0" = {features = [
    {"FET004.*" = {}, optional = true},
    {selector = "FET022.PhysX.*"},
], capabilities = [
    {selector = "CAP006*", optional = true},
]}
""".strip(),
        encoding="utf-8",
    )

    definitions = load_profile_definitions([profile_path])

    profile = definitions[("Robot", "2.0.0")]
    assert str(profile.features[0].selector) == "FET004.*.*"
    assert profile.features[0].optional is True
    assert profile.capabilities[0].optional is True


def test_packaged_foundations2_examples_load_and_resolve() -> None:
    fixtures = Path(__file__).parent / "fixtures" / "foundations2"
    features = load_feature_definitions([fixtures / "features"])
    capabilities = load_capability_definitions([fixtures / "capabilities"])
    profiles = load_profile_definitions([fixtures / "profiles"])

    resolved = resolve_profile(
        profiles[("Robot", "2.0.0")],
        features,
        capabilities,
    )

    assert [item.id for item in resolved.features] == [
        "FET004_Multibody.2-0-2",
        "FET004_Multibody.Newton.0-0-2",
        "FET004_Multibody.PhysX.2-0-4",
    ]
    assert {item.id: item.optional for item in resolved.features} == {
        "FET004_Multibody.Newton.0-0-2": True,
        "FET004_Multibody.2-0-2": True,
        "FET004_Multibody.PhysX.2-0-4": False,
    }
    assert resolved.capabilities[0].id == "CAP007_NonVisualMaterials.0-1-0"
    assert resolved.capabilities[0].optional is True


def test_source_feature_classifies_family_without_implicit_inheritance() -> None:
    source = FeatureDefinition.from_mapping(
        {
            "id": "FET004_Multibody.2-0-2",
            "source": True,
            "requirements": ["SOURCE.001"],
        }
    )
    derived = FeatureDefinition.from_mapping(
        {
            "id": "FET004_Multibody.PhysX.2-0-4",
            "source_feature": "FET004_Multibody.2-0-2",
            "additional_requirements": ["PHYSX.001"],
            "adapters": ["module:adapter"],
            "runtime_tests": ["suite:test"],
        }
    )
    features = {str(item.id): item for item in (source, derived)}
    profile = ProfileDefinition(
        name="Robot",
        version="2.0.0",
        features=(
            ProfileSelector(
                FeatureSelector.parse("FET004_Multibody.PhysX.2-0-4")
            ),
        ),
    )

    resolved = resolve_profile(profile, features)
    plan = build_validation_plan(resolved, features, {})

    assert [item.id for item in resolved.features] == [
        "FET004_Multibody.PhysX.2-0-4"
    ]
    assert plan.required_requirements == ("PHYSX.001",)


def test_feature_dependencies_are_resolved_with_required_winning() -> None:
    base = _feature("FET003_RigidBody.PhysX.0-0-1")
    feature = FeatureDefinition.from_mapping(
        {
            "id": "FET004_Multibody.PhysX.2-0-4",
            "requirements": ["REQ.001"],
            "dependencies": ["FET003_RigidBody.PhysX.0-0-1"],
            "additional_requirements": ["RUN.001"],
            "adapters": ["module:adapter"],
            "runtime_tests": ["suite:test"],
        }
    )
    profile = ProfileDefinition(
        name="Robot",
        version="2.0.0",
        features=(
            ProfileSelector(FeatureSelector.parse("FET003.*"), optional=True),
            ProfileSelector(FeatureSelector.parse("FET004.PhysX.*")),
        ),
    )

    resolved = resolve_profile(profile, {str(item.id): item for item in (base, feature)})

    assert {item.id: item.optional for item in resolved.features} == {
        "FET003_RigidBody.PhysX.0-0-1": False,
        "FET004_Multibody.PhysX.2-0-4": False,
    }


def test_feature_capabilities_and_capability_dependencies_are_resolved() -> None:
    feature = _feature(
        "FET004_Multibody.PhysX.2-0-4",
        capabilities=("CAP006_Materials.0-1-0",),
    )
    capabilities = {
        "CAP006_Shading.0-1-0": CapabilityDefinition.from_mapping(
            {"id": "CAP006_Shading.0-1-0", "requirements": ["MAT.001"]}
        ),
        "CAP006_Materials.0-1-0": CapabilityDefinition.from_mapping(
            {
                "id": "CAP006_Materials.0-1-0",
                "requirements": ["MAT.002"],
                "dependencies": ["CAP006_Shading.0-1-0"],
            }
        ),
    }
    profile = ProfileDefinition(
        name="Robot",
        version="2.0.0",
        features=(ProfileSelector(FeatureSelector.parse("FET004.PhysX.*")),),
    )

    resolved = resolve_profile(profile, {str(feature.id): feature}, capabilities)

    assert {item.id: item.optional for item in resolved.capabilities} == {
        "CAP006_Materials.0-1-0": False,
        "CAP006_Shading.0-1-0": False,
    }


def test_optional_feature_makes_its_capability_dependencies_optional() -> None:
    feature = _feature(
        "FET004_Multibody.Newton.0-0-2",
        capabilities=("CAP006_Materials.0-1-0",),
    )
    capabilities = {
        "CAP006_Materials.0-1-0": CapabilityDefinition.from_mapping(
            {"id": "CAP006_Materials.0-1-0", "requirements": ["MAT.001"]}
        )
    }
    profile = ProfileDefinition(
        name="Robot",
        version="2.0.0",
        features=(
            ProfileSelector(
                FeatureSelector.parse("FET004.Newton.*"),
                optional=True,
            ),
        ),
    )

    resolved = resolve_profile(profile, {str(feature.id): feature}, capabilities)

    assert resolved.capabilities[0].optional is True


def test_one_asset_can_be_validated_against_multiple_profiles() -> None:
    features = {"FET004_Multibody.PhysX.2-0-2": _feature("FET004_Multibody.PhysX.2-0-2")}
    profiles = {
        (name, "1.0.0"): ProfileDefinition(
            name=name,
            version="1.0.0",
            features=(ProfileSelector(FeatureSelector.parse("FET004.*")),),
        )
        for name in ("Profile-A", "Profile-B")
    }
    resolved = resolve_profiles(
        [ProfileTarget("Profile-A", "1.0.0"), ProfileTarget("Profile-B", "1.0.0")],
        profiles,
        features,
    )

    results = validate_asset_against_profiles(
        "asset.usd",
        resolved,
        lambda asset, profile: f"{asset}:{profile.name}@{profile.version}",
    )

    assert results == {
        ("Profile-A", "1.0.0"): "asset.usd:Profile-A@1.0.0",
        ("Profile-B", "1.0.0"): "asset.usd:Profile-B@1.0.0",
    }


def test_validator_plan_preserves_optional_contracts_and_required_wins() -> None:
    features = {
        "FET004_Multibody.PhysX.2-0-4": FeatureDefinition.from_mapping(
            {
                "id": "FET004_Multibody.PhysX.2-0-4",
                "requirements": ["SHARED.001"],
                "capabilities": ["CAP006_Materials.0-1-0"],
                "additional_requirements": ["RUN.001"],
                "runtime_tests": ["FET004:joint-movement"],
                "adapters": ["neutral_to_physx:collider_neutral_to_prop_physx"],
            }
        )
    }
    capabilities = {
        "CAP006_Materials.0-1-0": CapabilityDefinition.from_mapping(
            {
                "id": "CAP006_Materials.0-1-0",
                "requirements": ["SHARED.001", "CAP.001"],
            }
        )
    }
    profile = ProfileDefinition(
        name="Robot",
        version="2.0.0",
        features=(
            ProfileSelector(FeatureSelector.parse("FET004.PhysX.*")),
        ),
        capabilities=(
            ProfileSelector(CapabilitySelector.parse("CAP006*"), optional=True),
        ),
    )
    resolved = resolve_profile(profile, features, capabilities)

    plan = build_validation_plan(resolved, features, capabilities)

    assert plan.required_requirements == ("CAP.001", "RUN.001", "SHARED.001")
    assert plan.optional_requirements == ()
    assert plan.feature_evidence[0].runtime_tests == ("FET004:joint-movement",)
    assert plan.runnable_evidence == plan.feature_evidence


def test_validator_orchestration_returns_one_result_per_profile_target() -> None:
    features = {"FET004_Multibody.PhysX.2-0-4": _feature("FET004_Multibody.PhysX.2-0-4")}
    capabilities: dict[str, CapabilityDefinition] = {}
    profiles = {
        (name, "1.0.0"): ProfileDefinition(
            name=name,
            version="1.0.0",
            features=(ProfileSelector(FeatureSelector.parse("FET004.*")),),
        )
        for name in ("Profile-A", "Profile-B")
    }

    results = validate_profiles(
        "asset.usd",
        [ProfileTarget("Profile-A", "1.0.0"), ProfileTarget("Profile-B", "1.0.0")],
        profiles,
        features,
        capabilities,
        lambda asset, plan: f"{asset}:{plan.profile.name}",
    )

    assert results == {
        ("Profile-A", "1.0.0"): "asset.usd:Profile-A",
        ("Profile-B", "1.0.0"): "asset.usd:Profile-B",
    }


def test_missing_contract_directory_is_treated_as_empty() -> None:
    """A tier publishing no contracts of one kind has no directory to ship.

    It leaves the directory empty, git cannot track an empty directory, so the
    path is absent in a fresh checkout and present wherever the catalog has been
    generated. Loading must not depend on which of those a checkout is.
    """
    fixtures = Path(__file__).parent / "fixtures" / "foundations2"
    absent = fixtures / "no-such-section"

    present_only = load_feature_definitions([fixtures / "features"])
    with_absent = load_feature_definitions([fixtures / "features", absent])

    assert present_only, "fixture should publish at least one feature"
    assert with_absent.keys() == present_only.keys()
    assert load_feature_definitions([absent]) == {}
    assert load_capability_definitions([absent]) == {}
    assert load_profile_definitions([absent]) == {}


def test_all_tier_foundations2_catalogs_load_and_profiles_resolve() -> None:
    repo_root = Path(__file__).parents[4]
    # Package directory names are not uniform (the sensors tier is plain
    # ``sensors``), so tiers are discovered by their descriptor, not by name.
    catalog_roots = sorted(
        descriptor.parent
        for descriptor in repo_root.glob(
            "nv_core/tiers/simready_foundation_tier_*/simready/foundation/*/_tier.py"
        )
    )
    assert catalog_roots, "no tier descriptors found"
    # A tier publishing no contracts of one kind leaves that directory empty,
    # and git cannot track an empty directory, so some of these paths are absent
    # in a fresh checkout. The loaders treat missing and empty alike.
    feature_paths = [root / "features" for root in catalog_roots]
    capability_paths = [root / "capabilities" for root in catalog_roots]
    profile_paths = [root / "profiles" for root in catalog_roots]

    features = load_feature_definitions(feature_paths)
    capabilities = load_capability_definitions(capability_paths)
    profiles = load_profile_definitions(profile_paths)
    resolved = [
        resolve_profile(profile, features, capabilities)
        for profile in profiles.values()
    ]

    # Expectations come from the contract manifests, so publishing a
    # new contract or profile version does not also require editing this test.
    declared_ids = [
        json.loads(path.read_text(encoding="utf-8"))["id"]
        for root in catalog_roots
        for section in ("features", "capabilities")
        for path in sorted((root / section).glob("*.json"))
    ]
    assert declared_ids, "no contract manifests declared in any tier"
    assert set(features) == {item for item in declared_ids if item.startswith("FET")}
    assert set(capabilities) == {item for item in declared_ids if item.startswith("CAP")}

    expected_profile_versions = sum(
        len(versions)
        for path in sorted(p for directory in profile_paths for p in directory.glob("*.toml"))
        for versions in tomllib.loads(path.read_text(encoding="utf-8")).values()
    )
    assert expected_profile_versions, "no profile versions found in the tier catalogs"
    assert len(profiles) == expected_profile_versions
    assert len(resolved) == len(profiles)


def test_prop_and_robot_body_keep_independent_validation_evidence() -> None:
    roots = sorted(Path(__file__).parents[2].glob("*/simready/foundation/*/_tier.py"))
    features = load_feature_definitions([path.parent / "features" for path in roots])
    capabilities = load_capability_definitions([path.parent / "capabilities" for path in roots])
    profiles = load_profile_definitions([path.parent / "profiles" for path in roots])

    def validate_one(asset, plan):
        # A Newton failure blocks the robot target but is optional for the prop.
        return {
            "asset": str(asset),
            "profile": plan.profile.name,
            "version": plan.profile.version,
            "features": {item.id: item.optional for item in plan.features},
            "capabilities": {item.id: item.optional for item in plan.capabilities},
            "passed": "NEWTON.COL.001" not in plan.required_requirements,
        }

    results = validate_profiles(
        "asset.usd",
        [ProfileTarget("Robotics-Prop", "5.0.0"), ProfileTarget("Robot-Body", "4.0.0")],
        profiles, features, capabilities, validate_one,
    )
    prop = results["Robotics-Prop", "5.0.0"]
    robot = results["Robot-Body", "4.0.0"]
    assert prop["passed"] is True
    assert robot["passed"] is False
    assert prop["asset"] == robot["asset"]
    assert prop["features"]["FET003_RigidBody.Newton.0-1-0"] is True
    assert robot["features"]["FET003_RigidBody.Newton.0-1-0"] is False
    assert prop["features"]["FET008_ObjectForward.0-1-0"] is False
    assert robot["features"]["FET008_ObjectForward.0-1-0"] is True
    assert prop["capabilities"]["CAP000_Core.Newton.0-2-0"] is True
    assert robot["capabilities"]["CAP000_Core.Newton.0-2-0"] is False
