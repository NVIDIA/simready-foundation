# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Optional profile validation gate.

Importing this module requires the ``validate`` extra
(``simready-validate`` plus an installed Foundation tier). It is deliberately
not imported by ``api`` or ``sidecar`` so a host application can conform an
asset without installing the validator.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_PROFILE = "Package-Candidate"
DEFAULT_VERSION = "1.2.0"
#: Each metadata contract by its Foundations 2 name, which matches every version,
#: and its Foundations 1 id, so a report from either tier layout is recognized.
METADATA_FEATURES = (
    ("CAP031_SelfContainedPackage", "FET_031_STANDARD"),
    ("CAP033_SimReadyPackage", "FET_033_STANDARD"),
)


class ValidatorUnavailableError(RuntimeError):
    """Raised when the validator or Foundation tier data is not installed."""


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    profile: str
    version: str
    failing_features: tuple[str, ...]
    failing_requirements: tuple[str, ...]
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "profile": self.profile,
            "version": self.version,
            "failing_features": list(self.failing_features),
            "failing_requirements": list(self.failing_requirements),
        }


def _tier_root() -> Path:
    try:
        from simready.foundation import tier_core
    except ImportError as exc:
        raise ValidatorUnavailableError(
            "simready-foundation-tier-core is not installed; "
            'install this package with the "validate" extra'
        ) from exc
    return Path(tier_core.__file__).resolve().parent


#: The requirement source tree is ``rules_and_reqs/`` in a Foundations 2 tier and
#: ``capabilities/`` in a Foundations 1 one. A Foundations 2 tier reuses
#: ``capabilities/`` for its CAP contracts, so the new name must win.
_RULES_DIRNAMES = ("rules_and_reqs", "capabilities")


def _rules_dir(tier_root: Path) -> Path:
    for name in _RULES_DIRNAMES:
        candidate = tier_root / name
        if candidate.is_dir():
            return candidate
    raise ValidatorUnavailableError(
        f"{tier_root} has no requirement tree ({' or '.join(_RULES_DIRNAMES)})"
    )


def _names_contract(summary_key: str, names: tuple[str, ...]) -> bool:
    """Whether a ``features_summary`` key is one of ``names``, in any version."""
    return summary_key in names or summary_key.rsplit(".", 1)[0] in names


def _failed_requirements(raw: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for asset_report in raw.values():
        if not isinstance(asset_report, dict):
            continue
        for feature in asset_report.get("features_summary", {}).values():
            if not isinstance(feature, dict):
                continue
            for key in ("failing_requirements", "failed_requirements"):
                found.update(str(item) for item in feature.get(key, []))
    return found


def validate_asset(
    asset_path: Path,
    profile: str = DEFAULT_PROFILE,
    version: str = DEFAULT_VERSION,
    features: tuple[tuple[str, ...], ...] = METADATA_FEATURES,
) -> ValidationResult:
    """Validate one asset against a profile and report the metadata features."""
    asset = Path(asset_path).resolve()
    tier_root = _tier_root()
    with tempfile.TemporaryDirectory(prefix="simready-metadata-validation-") as temp:
        report = Path(temp) / "report.json"
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "from simready.validate._cli import main; raise SystemExit(main())",
                "--profile",
                profile,
                "--version",
                version,
                "--rules-path",
                str(_rules_dir(tier_root)),
                "--features-path",
                str(tier_root / "features"),
                "--profiles-path",
                str(tier_root / "profiles"),
                "--output",
                str(report),
                "-v",
                str(asset),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        raw = (
            json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
        )

    asset_report = next(iter(raw.values()), {}) if raw else {}
    summary = asset_report.get("features_summary", {})
    relevant = {
        feature_id: result
        for feature_id, result in summary.items()
        if any(_names_contract(feature_id, names) for names in features)
    }
    failing = tuple(
        sorted(feature_id for feature_id, result in relevant.items() if not result.get("passed", False))
    )
    matches = (
        asset_report.get("profile_id") == profile
        and asset_report.get("profile_version") == version
        and all(any(_names_contract(key, names) for key in relevant) for names in features)
    )
    passed = completed.returncode == 0 and matches and not failing
    if not passed and not failing:
        failing = ("VALIDATOR_ERROR",)
    return ValidationResult(
        passed=passed,
        profile=profile,
        version=version,
        failing_features=failing,
        failing_requirements=tuple(sorted(_failed_requirements(raw))),
        raw=raw,
    )
