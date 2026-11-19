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

"""RB.007 (OMPE-119299): the rule must require an *authored* ``physics:mass``.

``UsdPhysics.MassAPI`` predeclares ``physics:mass`` with a 0.0 fallback, so a body
that merely applies ``MassAPI`` without authoring a value reports a non-None
``Get()``. The requirement page requires the ``physics:mass`` attribute to be
present, so such a body must still fail RB.007. These three stages mirror the
ticket's assets a/b/c.

Requires an installed ``simready-foundation-tier-core`` wheel (with generated
requirements) plus ``usd-validation-nvidia`` and ``pxr``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("usd_validation_nvidia")
pytest.importorskip("pxr")
pytest.importorskip("simready.foundation.tier_core.requirements")

from pxr import Usd, UsdGeom, UsdPhysics  # noqa: E402
from simready.foundation.tier_core.rules_and_reqs.physics_bodies.physics_rigid_bodies import (  # noqa: E402
    validation as rb,
)

BODY_PATH = "/World/Body"
COLLIDER_PATH = "/World/Body/Collider"


def _stage(*, apply_mass_api: bool, author_mass: bool) -> Usd.Stage:
    """One rigid body with a single child collider that carries no mass."""
    stage = Usd.Stage.CreateInMemory()
    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())

    body = UsdGeom.Xform.Define(stage, BODY_PATH).GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    if apply_mass_api:
        mass_api = UsdPhysics.MassAPI.Apply(body)
        if author_mass:
            mass_api.CreateMassAttr(1.0)

    collider = UsdGeom.Cube.Define(stage, COLLIDER_PATH).GetPrim()
    UsdPhysics.CollisionAPI.Apply(collider)
    return stage


def _rb007_issues(stage: Usd.Stage):
    import simready.foundation.tier_core.requirements as cap

    checker = rb.RigidBodyMassChecker()
    checker.CheckStage(stage)
    code = cap.PhysicsRigidBodiesRequirements.RB_007
    return [i for i in checker.GetIssues() if i.requirement == code]


def test_mass_api_without_authored_mass_fails():
    """Asset a: MassAPI applied but no authored ``physics:mass`` -> fail."""
    assert _rb007_issues(_stage(apply_mass_api=True, author_mass=False))


def test_no_mass_api_fails():
    """Asset b: no MassAPI and the collider has no mass -> fail."""
    assert _rb007_issues(_stage(apply_mass_api=False, author_mass=False))


def test_authored_mass_passes():
    """Asset c: MassAPI with authored ``physics:mass`` -> pass."""
    assert not _rb007_issues(_stage(apply_mass_api=True, author_mass=True))
