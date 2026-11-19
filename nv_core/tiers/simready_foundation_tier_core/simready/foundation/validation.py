# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Validator-facing execution plans for Foundations 2 contracts.

This module is deliberately independent of one USD validation engine.  The
Foundation resolves catalogs and optionality once, then passes an immutable
plan to the installed validator, Kit runner, or benchmark backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence, TypeVar

from .contracts import (
    CapabilityDefinition,
    ContractError,
    FeatureDefinition,
    ProfileDefinition,
    ProfileTarget,
    ResolvedProfile,
    resolve_profiles,
)


@dataclass(frozen=True)
class PlannedContract:
    """One resolved feature or capability in a validation plan."""

    id: str
    optional: bool
    requirements: tuple[str, ...]


@dataclass(frozen=True)
class PlannedRequirement:
    """A deduplicated requirement with its effective optional state."""

    id: str
    optional: bool
    sources: tuple[str, ...]


@dataclass(frozen=True)
class FeatureEvidence:
    """Runtime evidence and mutation paths declared by a feature."""

    feature_id: str
    optional: bool
    runtime_tests: tuple[str, ...]
    adapters: tuple[str, ...]


# Foundations 2 previously exposed this name while non-runnable FETs existed.
RunnableEvidence = FeatureEvidence


@dataclass(frozen=True)
class ValidationPlan:
    """Fully resolved validator input for one profile target."""

    profile: ResolvedProfile
    features: tuple[PlannedContract, ...]
    capabilities: tuple[PlannedContract, ...]
    requirements: tuple[PlannedRequirement, ...]
    feature_evidence: tuple[FeatureEvidence, ...]

    @property
    def required_requirements(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.requirements if not item.optional)

    @property
    def optional_requirements(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.requirements if item.optional)

    @property
    def runnable_evidence(self) -> tuple[FeatureEvidence, ...]:
        """Compatibility alias for pre-realignment validator consumers."""

        return self.feature_evidence


ResultT = TypeVar("ResultT")


def build_validation_plan(
    profile: ResolvedProfile,
    features: Mapping[str, FeatureDefinition],
    capabilities: Mapping[str, CapabilityDefinition],
) -> ValidationPlan:
    """Translate one resolved profile into a validator execution plan."""

    planned_features: list[PlannedContract] = []
    planned_capabilities: list[PlannedContract] = []
    evidence: list[FeatureEvidence] = []
    requirement_states: dict[str, tuple[bool, list[str]]] = {}

    for item in profile.features:
        try:
            definition = features[item.id]
        except KeyError as exc:
            raise ContractError(
                f"Resolved feature '{item.id}' is missing from the feature catalog."
            ) from exc
        contract = PlannedContract(
            id=item.id,
            optional=item.optional,
            requirements=definition.all_requirements,
        )
        planned_features.append(contract)
        _merge_requirements(requirement_states, contract)
        if definition.runtime_tests:
            evidence.append(
                FeatureEvidence(
                    feature_id=item.id,
                    optional=item.optional,
                    runtime_tests=definition.runtime_tests,
                    adapters=definition.adapters,
                )
            )

    for item in profile.capabilities:
        try:
            definition = capabilities[item.id]
        except KeyError as exc:
            raise ContractError(
                f"Resolved capability '{item.id}' is missing from the capability catalog."
            ) from exc
        contract = PlannedContract(
            id=item.id,
            optional=item.optional,
            requirements=definition.requirements,
        )
        planned_capabilities.append(contract)
        _merge_requirements(requirement_states, contract)

    requirements = tuple(
        PlannedRequirement(id=key, optional=optional, sources=tuple(sources))
        for key, (optional, sources) in sorted(requirement_states.items())
    )
    return ValidationPlan(
        profile=profile,
        features=tuple(planned_features),
        capabilities=tuple(planned_capabilities),
        requirements=requirements,
        feature_evidence=tuple(evidence),
    )


def validate_profiles(
    asset: str | Path,
    targets: Sequence[ProfileTarget],
    profiles: Mapping[tuple[str, str], ProfileDefinition],
    features: Mapping[str, FeatureDefinition],
    capabilities: Mapping[str, CapabilityDefinition],
    validate_one: Callable[[str | Path, ValidationPlan], ResultT],
) -> dict[tuple[str, str], ResultT]:
    """Resolve and validate one asset against every caller-supplied target."""

    resolved = resolve_profiles(
        targets,
        profiles=profiles,
        features=features,
        capabilities=capabilities,
    )
    return {
        (profile.name, profile.version): validate_one(
            asset,
            build_validation_plan(profile, features, capabilities),
        )
        for profile in resolved
    }


def _merge_requirements(
    states: dict[str, tuple[bool, list[str]]],
    contract: PlannedContract,
) -> None:
    for requirement in contract.requirements:
        if requirement not in states:
            states[requirement] = (contract.optional, [contract.id])
            continue
        optional, sources = states[requirement]
        states[requirement] = (
            optional and contract.optional,
            [*sources, contract.id] if contract.id not in sources else sources,
        )


__all__ = [
    "CapabilityDefinition",
    "PlannedContract",
    "PlannedRequirement",
    "FeatureEvidence",
    "RunnableEvidence",
    "ValidationPlan",
    "build_validation_plan",
    "validate_profiles",
]
