# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""The per-asset FET_031 / FET_033 conformance chain.

This module mutates a package in place and reports what it did. It performs no
staging, no promotion, and no profile validation, so it can be driven directly
by a caller that already owns a writable copy. ``api.run_metadata_conform``
wraps it with staging and transactional promotion.
"""

from __future__ import annotations

import gc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pxr import Usd

from . import core
from .core.paths import ExternalLayerError
from .core.thumbnails import STATUS_AMBIGUOUS, STATUS_INVALID, STATUS_MISSING

CODE_METADATA_INCOMPLETE = "METADATA_INCOMPLETE"
CODE_PHYSICAL_EVIDENCE_MISSING = "PHYSICAL_EVIDENCE_MISSING"
CODE_PHYSICAL_VALUE_REJECTED = "PHYSICAL_VALUE_REJECTED"
CODE_THUMBNAIL_MISSING = "THUMBNAIL_MISSING"
CODE_THUMBNAIL_AMBIGUOUS = "THUMBNAIL_AMBIGUOUS"
CODE_THUMBNAIL_INVALID = "THUMBNAIL_INVALID"
CODE_MUTATION_AUDIT_FAILED = "MUTATION_AUDIT_FAILED"
CODE_STAGE_OPEN_FAILED = "STAGE_OPEN_FAILED"


@dataclass(frozen=True)
class Blocker:
    """One reason the package does not satisfy the metadata contract."""

    code: str
    requirement: str
    detail: str
    paths: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "requirement": self.requirement,
            "detail": self.detail,
            "paths": list(self.paths),
        }


@dataclass
class ConformOutcome:
    """Everything one conformance pass learned or changed."""

    asset_usd: str
    resolved_metadata: dict[str, Any] = field(default_factory=dict)
    field_sources: dict[str, str] = field(default_factory=dict)
    field_warnings: dict[str, str] = field(default_factory=dict)
    path_repairs: list[dict[str, str]] = field(default_factory=list)
    thumbnail: dict[str, Any] = field(default_factory=dict)
    derivation: dict[str, Any] = field(default_factory=dict)
    mutation_audit: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    blockers: list[Blocker] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_usd": self.asset_usd,
            "resolved_metadata": dict(self.resolved_metadata),
            "field_sources": dict(self.field_sources),
            "field_warnings": dict(self.field_warnings),
            "path_repairs": list(self.path_repairs),
            "thumbnail": dict(self.thumbnail),
            "derivation": dict(self.derivation),
            "mutation_audit": dict(self.mutation_audit),
            "warnings": list(self.warnings),
            "blockers": [item.to_dict() for item in self.blockers],
        }


def _release_usd_handles() -> None:
    gc.collect()
    Usd.StageCache().Clear()


_THUMBNAIL_BLOCKER_CODES = {
    STATUS_MISSING: CODE_THUMBNAIL_MISSING,
    STATUS_AMBIGUOUS: CODE_THUMBNAIL_AMBIGUOUS,
    STATUS_INVALID: CODE_THUMBNAIL_INVALID,
}


def conform_package(
    asset_usd: Path | str,
    *,
    metadata: dict[str, Any] | None = None,
    thumbnail_source: Path | str | None = None,
    package_root: Path | str | None = None,
    expected_mass_min: float | None = None,
    expected_mass_max: float | None = None,
    mass_rationale: str | None = None,
) -> ConformOutcome:
    """Conform one writable package to FET_031 (AA.001) and FET_033 (SR.002, SR.003).

    Args:
        asset_usd: Root USD of the package to mutate in place.
        metadata: Caller-supplied provenance strings and an optional ``qcode``.
        thumbnail_source: PNG to install as the SR.002 thumbnail. When omitted,
            a unique package-local thumbnail is discovered instead.
        package_root: Search root for package-local files. Defaults to the
            NP.005 layout, one directory above the root USD.

    Returns:
        An outcome whose ``blockers`` list is empty only when the package now
        satisfies both features.
    """
    asset = Path(asset_usd).resolve()
    package = Path(package_root).resolve() if package_root else asset.parent.parent
    outcome = ConformOutcome(asset_usd=str(asset))

    stage = Usd.Stage.Open(str(asset))
    if stage is None:
        outcome.blockers.append(
            Blocker(
                code=CODE_STAGE_OPEN_FAILED,
                requirement="AA.001",
                detail=f"could not open USD stage: {asset}",
                paths=(str(asset),),
            )
        )
        return outcome
    del stage
    _release_usd_handles()

    # Caller-supplied physical values are rejected before anything is written,
    # so a request can never force an SR.003 pass with unsupported numbers.
    rejected = core.rejected_physical_fields(metadata)
    if rejected:
        outcome.blockers.append(
            Blocker(
                code=CODE_PHYSICAL_VALUE_REJECTED,
                requirement="SR.003",
                detail=(
                    "physical fields must be derived from the asset and cannot be "
                    f"supplied by the caller: {', '.join(rejected)}"
                ),
                paths=rejected,
            )
        )
        return outcome

    before_digest = core.protected_stage_digest(asset, package)

    try:
        repairs = core.repair_simple_asset_paths(asset, package)
    except ExternalLayerError as exc:
        outcome.blockers.append(Blocker(
            code="EXTERNAL_LAYER", requirement="AA.001",
            detail=str(exc), paths=exc.paths,
        ))
        return outcome
    outcome.path_repairs = [item.to_dict() for item in repairs]
    _release_usd_handles()

    derivation = core.derive_metadata(
        asset,
        expected_mass_min=expected_mass_min,
        expected_mass_max=expected_mass_max,
        mass_rationale=mass_rationale,
    )
    outcome.derivation = derivation.to_dict()
    outcome.warnings.extend(derivation.warnings)

    resolved = core.resolve_metadata(
        request=metadata or {},
        existing=core.read_existing_metadata(asset),
        layer=core.read_top_level_metadata(asset),
        sidecar=core.load_package_sidecar(asset),
        derived=derivation.values,
    )
    outcome.resolved_metadata = {
        name: entry.value for name, entry in resolved.items()
    }
    outcome.field_sources = {name: entry.source for name, entry in resolved.items()}
    outcome.field_warnings = {
        name: entry.warning for name, entry in resolved.items() if entry.warning
    }

    missing = core.unresolved_fields(resolved)
    missing_physical = tuple(
        name for name in missing if name in core.PHYSICAL_FIELDS
    )
    missing_supplied = tuple(name for name in missing if name not in missing_physical)
    if missing_physical:
        outcome.blockers.append(
            Blocker(
                code=CODE_PHYSICAL_EVIDENCE_MISSING,
                requirement="SR.003",
                detail=(
                    "the asset carries no evidence for: "
                    f"{', '.join(missing_physical)}"
                ),
                paths=missing_physical,
            )
        )
    if missing_supplied:
        outcome.blockers.append(
            Blocker(
                code=CODE_METADATA_INCOMPLETE,
                requirement="SR.003",
                detail=f"no value supplied for: {', '.join(missing_supplied)}",
                paths=missing_supplied,
            )
        )

    core.stamp_metadata(asset, outcome.resolved_metadata)
    _release_usd_handles()

    thumbnail = core.normalize_thumbnail(
        asset,
        thumbnail_source=Path(thumbnail_source) if thumbnail_source else None,
        package_root=package,
    )
    outcome.thumbnail = thumbnail.to_dict()
    if not thumbnail.ok:
        outcome.blockers.append(
            Blocker(
                code=_THUMBNAIL_BLOCKER_CODES.get(
                    thumbnail.status, CODE_THUMBNAIL_MISSING
                ),
                requirement="SR.002",
                detail=thumbnail.reason or f"thumbnail {thumbnail.status}",
                paths=(str(thumbnail.target),),
            )
        )

    outcome.mutation_audit = core.audit_mutation(before_digest, asset, package)
    if not outcome.mutation_audit["passed"]:
        outcome.blockers.append(
            Blocker(
                code=CODE_MUTATION_AUDIT_FAILED,
                requirement="AA.001",
                detail=(
                    "metadata conformance changed authored geometry or physics; "
                    "the staged package must not be promoted"
                ),
                paths=(str(asset),),
            )
        )
    _release_usd_handles()
    return outcome
