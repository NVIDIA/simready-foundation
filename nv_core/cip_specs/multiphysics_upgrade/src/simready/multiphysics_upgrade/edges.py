# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Ordered exact feature edges for Prop-Robotics-Physx -> Robotics-Prop multiphysics."""

from __future__ import annotations

from . import core
from .types import AdapterEdge, FeatureRef

ORDERED_EDGES: list[AdapterEdge] = [
    AdapterEdge(
        name="minimal_standard_0_1_0_to_1_0_1",
        input_feature=FeatureRef("FET001_MinimalPlaceableVisual.0-1-0"),
        output_feature=FeatureRef("FET001_MinimalPlaceableVisual.1-0-1"),
        apply=core.apply_minimal_upgrade,
    ),
    AdapterEdge(
        name="rigid_body_physx_0_1_0_to_standard_0_2_0",
        input_feature=FeatureRef("FET003_RigidBody.PhysX.0-1-0"),
        output_feature=FeatureRef("FET003_RigidBody.0-2-0"),
        apply=core.apply_physx_to_standard_rigid_body,
    ),
    AdapterEdge(
        name="multibody_physx_0_1_0_to_standard_0_2_0",
        input_feature=FeatureRef("FET004_Multibody.PhysX.0-1-0"),
        output_feature=FeatureRef("FET004_Multibody.0-2-0"),
        apply=core.apply_physx_to_standard_multibody,
    ),
    AdapterEdge(
        name="core_standard_to_physx_0_1_0",
        input_feature=FeatureRef("CAP000_Core.0-1-0"),
        output_feature=FeatureRef("CAP000_Core.PhysX.0-1-0"),
        apply=lambda stage: core.apply_runtime_scaffold(stage, "PhysX"),
    ),
    AdapterEdge(
        name="core_standard_to_newton_0_1_0",
        input_feature=FeatureRef("CAP000_Core.0-1-0"),
        output_feature=FeatureRef("CAP000_Core.Newton.0-1-0"),
        apply=lambda stage: core.apply_runtime_scaffold(stage, "Newton"),
    ),
    AdapterEdge(
        name="core_standard_to_mujoco_0_1_0",
        input_feature=FeatureRef("CAP000_Core.0-1-0"),
        output_feature=FeatureRef("CAP000_Core.MuJoCo.0-1-0"),
        apply=lambda stage: core.apply_runtime_scaffold(stage, "MuJoCo"),
    ),
    AdapterEdge(
        name="rigid_body_standard_0_2_0_to_physx_0_4_0",
        input_feature=FeatureRef("FET003_RigidBody.0-2-0"),
        output_feature=FeatureRef("FET003_RigidBody.PhysX.0-4-0"),
        apply=core.apply_standard_to_physx_rigid_body,
    ),
    AdapterEdge(
        name="rigid_body_standard_0_2_0_to_newton_0_1_0",
        input_feature=FeatureRef("FET003_RigidBody.0-2-0"),
        output_feature=FeatureRef("FET003_RigidBody.Newton.0-1-0"),
        apply=core.apply_standard_to_newton_rigid_body,
    ),
    AdapterEdge(
        name="rigid_body_standard_0_2_0_to_mujoco_0_1_0",
        input_feature=FeatureRef("FET003_RigidBody.0-2-0"),
        output_feature=FeatureRef("CAP003_RigidBody.MuJoCo.0-1-0"),
        apply=core.apply_standard_to_mujoco_rigid_body,
    ),
    AdapterEdge(
        name="multibody_standard_0_2_0_to_physx_0_4_0",
        input_feature=FeatureRef("FET004_Multibody.0-2-0"),
        output_feature=FeatureRef("FET004_Multibody.PhysX.0-4-0"),
        apply=core.apply_standard_to_physx_multibody,
    ),
    AdapterEdge(
        name="multibody_standard_0_2_0_to_newton_0_1_0",
        input_feature=FeatureRef("FET004_Multibody.0-2-0"),
        output_feature=FeatureRef("FET004_Multibody.Newton.0-1-0"),
        apply=core.apply_standard_to_newton_multibody,
    ),
    AdapterEdge(
        name="multibody_standard_0_2_0_to_mujoco_0_1_0",
        input_feature=FeatureRef("FET004_Multibody.0-2-0"),
        output_feature=FeatureRef("CAP004_Multibody.MuJoCo.0-1-0"),
        apply=core.apply_standard_to_mujoco_multibody,
    ),
]

# Retained optional features that need no mutation for the default migration.
PASSTHROUGH_FEATURES = (
    FeatureRef("CAP000_Core.0-1-0"),
    FeatureRef("FET005_Grasp.0-1-0"),
    FeatureRef("FET006_Materials.MDL.0-1-0"),
)

DEFAULT_SELECTED_OPTIONALS = [
    "CAP000_Core.PhysX.0-1-0",
    "CAP000_Core.Newton.0-1-0",
    "CAP000_Core.MuJoCo.0-1-0",
    "FET003_RigidBody.PhysX.0-4-0",
    "FET003_RigidBody.Newton.0-1-0",
    "CAP003_RigidBody.MuJoCo.0-1-0",
    "FET004_Multibody.0-2-0",
    "FET004_Multibody.PhysX.0-4-0",
    "FET004_Multibody.Newton.0-1-0",
    "CAP004_Multibody.MuJoCo.0-1-0",
    "FET005_Grasp.0-1-0",
    "FET006_Materials.MDL.0-1-0",
]


def plan_edges() -> list[AdapterEdge]:
    """Return the fixed upgrade edge order.

    Unibody assets still include FET_004 edges here; the runner skips them at
    runtime when preflight raises ``NOT_MULTIBODY``.
    """
    return list(ORDERED_EDGES)
