"""Structured result types returned by the packaging-step API.

:class:`PreValidationResult` and :class:`PostValidationResult` wrap
the :class:`simready.validate.AssetValidationResult` objects produced
by the underlying validation engine, adding orchestration context
(which profiles were run, what metadata files were written, which
features failed) so callers can inspect outcomes without parsing
terminal output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import simready.validate as sv

__all__ = [
    "PostValidationResult",
    "PreValidationResult",
]


@dataclass
class PreValidationResult:
    """Outcome of asset-level pre-validation across one or more profiles.

    ``results`` maps each profile ID to a list of
    ``(rel_path, AssetValidationResult | None)`` pairs — one per
    validated USD file.  The :class:`sv.AssetValidationResult` carries
    ``.features_summary`` with the per-feature pass/fail detail;
    ``None`` means the engine returned no result for that asset.
    """

    source: Path
    profile_version: str
    results: dict[str, list[tuple[str, sv.AssetValidationResult | None]]]
    metadata_written: list[str] = field(default_factory=list)
    failed_features: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failed_features


@dataclass
class PostValidationResult:
    """Outcome of package-level post-validation across one or more profiles.

    ``results`` maps each profile ID to a list of
    ``(rel_path, AssetValidationResult | None)`` pairs (typically one
    entry per profile — the package-definition path).  The
    :class:`sv.AssetValidationResult` carries ``.features_summary``
    with per-feature pass/fail detail.
    """

    package_def: Path
    profile_version: str
    results: dict[str, list[tuple[str, sv.AssetValidationResult | None]]]
    evidence_paths: list[Path] = field(default_factory=list)
    failed_features: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failed_features
