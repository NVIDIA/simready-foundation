# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""CAP039 membership checks on real OpenUSD stages and composed properties."""

from pathlib import Path

import pytest
from pxr import Sdf, Usd, UsdGeom

from simready.foundation.tier_core.rules_and_reqs.physics_bodies.object_affordances.validation import (
    ObjectAffordancesCapabilityChecker,
)

AFFORDANCES = (
    "pressable",
    "touch_operable",
    "rotatable",
    "slideable",
    "openable",
    "lockable",
    "accepts_insertion",
    "toggleable",
    "adjustable",
)
STATES = (
    "open",
    "closed",
    "toggled_on",
    "toggled_off",
    "locked",
    "unlocked",
    "empty",
    "occupied",
    "pressed",
    "unpressed",
    "touched",
    "untouched",
)


def asset():
    stage = Usd.Stage.CreateInMemory()
    prim = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(prim)
    return stage, prim


def labels(prim, taxonomy, values=None, *, samples=None):
    prim.AddAppliedSchema(f"SemanticsLabelsAPI:{taxonomy}")
    attr = prim.CreateAttribute(f"semantics:labels:{taxonomy}", Sdf.ValueTypeNames.TokenArray)
    if values is not None:
        attr.Set(values)
    for time, value in (samples or {}).items():
        attr.Set(value, time)
    return attr


def issues(stage):
    checker = ObjectAffordancesCapabilityChecker()
    checker.CheckStage(stage)
    for prim in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        checker.CheckPrim(prim)
    return checker.GetIssues()


@pytest.mark.parametrize("token", AFFORDANCES)
def test_every_approved_affordance(token):
    stage, prim = asset()
    labels(prim, "affordance", [token])
    assert not issues(stage)


@pytest.mark.parametrize("token", STATES)
def test_every_approved_state_without_coauthored_affordance(token):
    stage, prim = asset()
    labels(prim, "affordance_state", [token])
    assert not issues(stage)


@pytest.mark.parametrize("taxonomy,code", [("affordance", "AFF.001"), ("affordance_state", "AFF.002")])
@pytest.mark.parametrize("invalid", ["bogus", "Openable", "graspable", "", "half_open"])
def test_invalid_token_reports_prim_property_and_value(taxonomy, code, invalid):
    stage, prim = asset()
    labels(prim, taxonomy, [invalid])
    found = issues(stage)
    assert len(found) == 1
    assert found[0].requirement.code.endswith(code)
    assert "/Asset" in found[0].message
    assert f"semantics:labels:{taxonomy}" in found[0].message
    assert repr(invalid) in found[0].message


@pytest.mark.parametrize(
    "taxonomy,valid,code", [("affordance", "openable", "AFF.001"), ("affordance_state", "closed", "AFF.002")]
)
@pytest.mark.parametrize("with_default", [False, True])
def test_invalid_time_sample_is_not_hidden_by_default(taxonomy, valid, code, with_default):
    stage, prim = asset()
    labels(prim, taxonomy, [valid] if with_default else None, samples={1: [valid], 2: ["bogus"]})
    found = issues(stage)
    assert len(found) == 1
    assert found[0].requirement.code.endswith(code)
    assert "time 2.0" in found[0].message


def test_all_invalid_values_and_samples_are_reported():
    stage, prim = asset()
    labels(prim, "affordance", ["bad_b", "bad_a"], samples={1: ["bad_c"], 2: ["bad_d"]})
    found = issues(stage)
    assert len(found) == 4
    assert "bad_a" in found[0].message
    assert "bad_b" in found[1].message


def test_unlabeled_assets_and_other_taxonomies_are_outside_membership_gate():
    stage, prim = asset()
    assert not issues(stage)
    labels(prim, "wikidata_qcode", ["Q40607"])
    labels(prim, "affordance_company_a", ["quarter_turn"])
    labels(prim, "affordance_state_company_a", ["half_open"])
    assert not issues(stage)


@pytest.mark.parametrize("kind", ["missing", "empty", "blocked", "wrong_type"])
def test_generic_structure_is_left_to_semantic_labels(kind):
    stage, prim = asset()
    prim.AddAppliedSchema("SemanticsLabelsAPI:affordance")
    if kind != "missing":
        attr = prim.CreateAttribute("semantics:labels:affordance", Sdf.ValueTypeNames.TokenArray)
        if kind == "blocked":
            attr.Block()
        elif kind == "wrong_type":
            layer = stage.GetRootLayer()
            prim.RemoveProperty("semantics:labels:affordance")
            spec = Sdf.AttributeSpec(
                layer.GetPrimAtPath("/Asset"), "semantics:labels:affordance", Sdf.ValueTypeNames.String
            )
            spec.default = "bogus"
        else:
            attr.Set([])
    assert not issues(stage)


def test_reference_instance_and_stronger_override():
    source, prim = asset()
    child = UsdGeom.Xform.Define(source, "/Asset/Control").GetPrim()
    labels(child, "affordance", ["bogus"])
    stage, target = asset()
    target.GetReferences().AddReference(source.GetRootLayer().identifier)
    target.SetInstanceable(True)
    assert stage.GetPrimAtPath("/Asset/Control").IsInstanceProxy()
    found = issues(stage)
    assert len(found) == 1 and "/Asset/Control" in found[0].message
    labels(child, "affordance", ["pressable"])
    assert not issues(stage)
    target.SetInstanceable(False)
    labels(stage.GetPrimAtPath("/Asset/Control"), "affordance", ["toggleable"])
    assert not issues(stage)


def test_affordance_labels_coexist_with_semantic_label_dependency():
    from simready.foundation.tier_core.rules_and_reqs.semantic_labels.validation import SemanticLabelsCapabilityChecker

    stage, prim = asset()
    labels(prim, "affordance", ["openable", "rotatable"])
    labels(prim, "affordance_state", ["closed"])
    labels(prim, "wikidata_qcode", ["Q127956"])
    UsdGeom.Cube.Define(stage, "/Asset/Door")
    checker = SemanticLabelsCapabilityChecker(False, False, True)
    checker.CheckStage(stage)
    for p in stage.Traverse():
        checker.CheckPrim(p)
    assert not checker.GetIssues()
    assert not issues(stage)


@pytest.mark.parametrize("path", sorted((Path(__file__).parent / "fixtures/object_affordances").glob("*.usda")))
def test_card_semantic_fixtures(path):
    stage = Usd.Stage.Open(str(path))
    assert stage and stage.GetDefaultPrim()
    assert not issues(stage)
