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

import math
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Sdf, Usd, UsdPhysics
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    motion_utils,
    velocity_limit,
)


@pytest.fixture
def compatibility_schema(monkeypatch):
    """Expose the existing compatibility accessor without loading a native engine."""
    import pxr

    schema = SimpleNamespace(
        PhysxJointAPI=SimpleNamespace(
            Get=lambda stage, path: SimpleNamespace(
                GetMaxJointVelocityAttr=lambda: stage.GetPrimAtPath(path).GetAttribute("physxJoint:maxJointVelocity")
            )
        )
    )
    monkeypatch.setattr(pxr, "PhysxSchema", schema, raising=False)


@pytest.mark.parametrize(
    "joint_schema,authored,expected",
    [(UsdPhysics.RevoluteJoint, 180.0, math.pi), (UsdPhysics.PrismaticJoint, 1.25, 1.25)],
)
def test_joint_compatibility_cap_uses_qualified_importer_units(compatibility_schema, joint_schema, authored, expected):
    stage = Usd.Stage.CreateInMemory()
    prim = joint_schema.Define(stage, "/Robot/joint").GetPrim()
    prim.CreateAttribute("physxJoint:maxJointVelocity", Sdf.ValueTypeNames.Float).Set(authored)

    assert motion_utils._read_joint_max_velocity(prim) == pytest.approx(expected)


def test_actuator_effort_speed_velocity_limit_is_not_substituted_for_joint_cap(compatibility_schema):
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Robot", "Xform")
    prim = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/joint").GetPrim()
    prim.CreateAttribute("newton:velocityLimit", Sdf.ValueTypeNames.Float).Set(2.0)
    actuator = stage.DefinePrim("/Robot/motor", "NewtonActuator")
    actuator.CreateRelationship("newton:targets").SetTargets([prim.GetPath()])
    actuator.CreateAttribute("newton:velocityLimit", Sdf.ValueTypeNames.Float).Set(8.0)

    assert motion_utils._read_joint_max_velocity(prim) is None
    limits = motion_utils.resolve_usd_max_velocities(stage, "/Robot", ["joint"], root, root)
    assert limits.shape == (1,)
    assert np.isnan(limits[0])


def test_missing_runtime_cap_does_not_reinterpret_actuator_envelope(compatibility_schema):
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Robot", "Xform")
    prim = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/joint").GetPrim()
    prim.CreateAttribute("newton:velocityLimit", Sdf.ValueTypeNames.Float).Set(2.0)
    usd_limits = motion_utils.resolve_usd_max_velocities(stage, "/Robot", ["joint"], root, root)
    robot = SimpleNamespace(
        dof_names=["joint"],
        dof_count=1,
        get_joint_position_limits=lambda: (np.array([-1.0]), np.array([1.0])),
        get_joint_velocity_limits=lambda: np.array([float("nan")]),
    )

    assert velocity_limit.find_joints_with_velocity_limits(robot, usd_limits) == []


def test_provenance_records_actual_versions_without_importing_newton(monkeypatch):
    versions = {"newton": "1.2.1", "newton-usd-schemas": "0.2.0"}
    monkeypatch.setattr(motion_utils.metadata, "version", versions.__getitem__)

    context = motion_utils.velocity_limit_provenance()

    assert context["runtime_newton_version"] == "1.2.1"
    assert context["runtime_newton_usd_schemas_version"] == "0.2.0"
    assert "degrees/s convert to radians/s" in context["joint_limit_basis"]
    assert "not a hard joint-speed cap" in context["actuator_velocity_limit_basis"]
    assert "not established" in context["hard_cap_enforcement"]


def test_unavailable_version_metadata_remains_diagnostic_only(monkeypatch):
    def unavailable(name):
        raise RuntimeError("diagnostic metadata unavailable")

    monkeypatch.setattr(motion_utils.metadata, "version", unavailable)

    context = motion_utils.velocity_limit_provenance()

    assert context["runtime_newton_version"] is None
    assert context["runtime_newton_usd_schemas_version"] is None


def test_skip_and_failure_messages_do_not_prescribe_unverified_asset_repairs():
    messages = [
        velocity_limit._fix_message_no_velocity_limits(),
        velocity_limit._fix_message_violations(1, 1, "joint", "joint: peak=2, ceiling=1"),
    ]

    assert "insufficient evidence" in messages[0]
    assert "cause is not established" in messages[1]
    for message in messages:
        assert "Newton 1.2.1" in message
        assert "not a hard joint-speed cap" in message
        assert "Paste-ready" not in message
        assert "raise the authored limit" not in message
