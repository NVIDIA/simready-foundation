# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Data structs for multiphysics upgrade adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Blocker:
    """A fail-closed refusal to guess topology or policy."""

    code: str
    requirement: str
    detail: str
    paths: list[str] = field(default_factory=list)


@dataclass
class PreflightResult:
    """Collected stage facts plus blockers."""

    default_prim_path: str = ""
    default_prim_name: str = ""
    colliders: list[str] = field(default_factory=list)
    rigid_bodies: list[str] = field(default_factory=list)
    physics_materials: list[str] = field(default_factory=list)
    joints: list[str] = field(default_factory=list)
    articulation_roots: list[str] = field(default_factory=list)
    base_approximations: dict[str, str] = field(default_factory=dict)
    blockers: list[Blocker] = field(default_factory=list)


@dataclass(frozen=True)
class FeatureRef:
    """Exact dotted contract id, which carries its own version segment."""

    contract_id: str

    def key(self) -> str:
        return self.contract_id


@dataclass(frozen=True)
class AdapterEdge:
    """One exact CIP feature edge."""

    name: str
    input_feature: FeatureRef
    output_feature: FeatureRef
    apply: Callable  # (Usd.Stage) -> None


@dataclass
class MutationReport:
    """Structured report for one edge or runner step."""

    name: str
    status: str
    detail: str = ""
    blockers: list[dict] = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)


@dataclass
class PhysicsTuningChange:
    """One physics value or runtime schema imported from a tuned counterpart."""

    path: str
    property: str
    destination: str
    value_type: str
    old_value: Any
    tuned_value: Any


@dataclass
class PhysicsTuningSkip:
    """One counterpart difference intentionally not imported."""

    path: str
    property: str
    reason: str
    neutral_value: Any = None
    tuned_value: Any = None


@dataclass
class PhysicsTuningRelocation:
    """A counterpart value the neutral stage already carries at another prim.

    The Neutral and PhysX packages sometimes place the same mass block on
    different prims of a rigid-body/collider pair, so an identical value can
    look brand new at the counterpart's path. That is a placement difference,
    not tuning, and is recorded here instead of as an imported change.
    """

    path: str
    property: str
    neutral_path: str
    value_type: str
    tuned_value: Any
    basis: str
