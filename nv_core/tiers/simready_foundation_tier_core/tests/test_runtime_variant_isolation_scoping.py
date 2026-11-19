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

"""RV.010 / RV.011 per-runtime scoping (OMPE-119276).

``RV.010`` (section purity) and ``RV.011`` (physics isolation) are shared by the
three ``CAP000_Core.<runtime>`` contracts. A cross-runtime leak belongs to the
one runtime whose selection exposes it, not to every runtime that lists the
requirement. When a validation driver composes a single runtime variant
``Enabled`` (as ``simready-validate`` does per runtime bucket), the checkers must
report only that runtime's result so the failure attributes to that runtime's
contract alone. With no single runtime selected (a direct run against the
authored neutral default) the checkers keep auditing every declared runtime so a
standalone run still catches the leak.

Requires an installed ``simready-foundation-tier-core`` wheel (with generated
requirements) plus ``usd-validation-nvidia`` and ``pxr``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("usd_validation_nvidia")
pytest.importorskip("pxr")
pytest.importorskip("simready.foundation.tier_core.requirements")

from pxr import Sdf, Usd, UsdGeom  # noqa: E402
from usd_validation_nvidia import IssueSeverity  # noqa: E402

import simready.foundation.tier_core.requirements as cap  # noqa: E402
from simready.foundation.tier_core.rules_and_reqs.core.runtime_variants import (  # noqa: E402
    validation as rv,
)

RV_010 = cap.RuntimeVariantsRequirements.RV_010
RV_011 = cap.RuntimeVariantsRequirements.RV_011

_SETS = ("PhysX", "Newton")


def _add_variant_sets(default_prim) -> None:
    for name in _SETS:
        vset = default_prim.GetVariantSets().AddVariantSet(name)
        vset.AddVariant("Disabled")
        vset.AddVariant("Enabled")
        vset.SetVariantSelection("Disabled")


def _select(stage, selection: str | None) -> None:
    """Compose a single runtime selection in the session layer (as a driver does)."""
    if selection is None:
        return
    default_prim = stage.GetDefaultPrim()
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        for name in _SETS:
            default_prim.GetVariantSet(name).SetVariantSelection(
                "Enabled" if name == selection else "Disabled"
            )


def _failures(checker_cls, stage, code):
    checker = checker_cls()
    checker.CheckStage(stage)
    return [i for i in checker.GetIssues() if i.requirement == code and i.severity == IssueSeverity.FAILURE]


def _isolation_stage(selection: str | None) -> Usd.Stage:
    """A child collider carries a foreign ``NewtonCollisionAPI`` on the base."""
    stage = Usd.Stage.CreateInMemory()
    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())
    _add_variant_sets(world.GetPrim())

    mesh = UsdGeom.Mesh.Define(stage, "/World/Collider").GetPrim()
    mesh.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["NewtonCollisionAPI"]))

    _select(stage, selection)
    return stage


def _purity_stage(selection: str | None) -> Usd.Stage:
    """The PhysX ``Enabled`` section authors an inline property (impure)."""
    stage = Usd.Stage.CreateInMemory()
    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())
    default_prim = world.GetPrim()

    for name in _SETS:
        vset = default_prim.GetVariantSets().AddVariantSet(name)
        vset.AddVariant("Disabled")
        vset.AddVariant("Enabled")
        if name == "PhysX":
            vset.SetVariantSelection("Enabled")
            with vset.GetVariantEditContext():
                default_prim.CreateAttribute("custom:leak", Sdf.ValueTypeNames.Float).Set(1.0)
        vset.SetVariantSelection("Disabled")

    _select(stage, selection)
    return stage


# --------------------------------------------------------------------------- #
# RV.011 physics isolation
# --------------------------------------------------------------------------- #
def test_isolation_fails_only_under_the_offending_runtime():
    """A Newton schema leaked onto the base fails the PhysX selection only."""
    assert _failures(rv.RuntimePhysicsIsolationChecker, _isolation_stage("PhysX"), RV_011)


def test_isolation_passes_under_the_matching_runtime():
    """Under the Newton selection the Newton schema is native, so RV.011 passes."""
    assert not _failures(rv.RuntimePhysicsIsolationChecker, _isolation_stage("Newton"), RV_011)


def test_isolation_audits_all_runtimes_without_a_selection():
    """A direct run against the authored default still catches the leak."""
    assert _failures(rv.RuntimePhysicsIsolationChecker, _isolation_stage(None), RV_011)


# --------------------------------------------------------------------------- #
# RV.010 section purity
# --------------------------------------------------------------------------- #
def test_purity_fails_only_under_the_offending_runtime():
    """An impure PhysX section fails the PhysX selection only."""
    assert _failures(rv.RuntimeVariantSectionPurityChecker, _purity_stage("PhysX"), RV_010)


def test_purity_passes_under_an_unrelated_runtime():
    """Under the Newton selection only the (clean) Newton section is checked."""
    assert not _failures(rv.RuntimeVariantSectionPurityChecker, _purity_stage("Newton"), RV_010)


def test_purity_audits_all_sections_without_a_selection():
    """A direct run against the authored default still catches the impure section."""
    assert _failures(rv.RuntimeVariantSectionPurityChecker, _purity_stage(None), RV_010)
