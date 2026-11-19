# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Typed adapter around the bundled FET_033 derivation snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pxr import Usd, UsdGeom

from ..resources.extract_simready_metadata import (
    build_mass_report,
    compute_extents_meters,
    count_rigid_bodies,
    derive_qcode,
    sum_authored_mass,
)

# SR.003 fields that may only come from the current stage. Nothing else is
# allowed to supply them, so a stale authored mass or extent can never be
# promoted back onto an asset whose geometry has changed.
PHYSICAL_FIELDS = ("rigid_body_count", "asset_extents", "mass")


@dataclass(frozen=True)
class DerivationResult:
    values: dict[str, Any]
    warnings: tuple[str, ...]
    unresolved: tuple[str, ...]
    meters_per_unit: float
    mass_body_count: int
    mass_check: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "values": dict(self.values),
            "warnings": list(self.warnings),
            "unresolved": list(self.unresolved),
            "meters_per_unit": self.meters_per_unit,
            "mass_body_count": self.mass_body_count,
            "mass_check": self.mass_check,
        }


def derive_metadata(
    asset_path: Path,
    *,
    expected_mass_min: float | None = None,
    expected_mass_max: float | None = None,
    mass_rationale: str | None = None,
) -> DerivationResult:
    """Derive the physical SR.003 fields and the authored qcode from a stage."""
    asset = Path(asset_path).resolve()
    stage = Usd.Stage.Open(str(asset))
    if stage is None:
        raise ValueError(f"Failed to open USD stage: {asset}")
    default = stage.GetDefaultPrim()
    root = default if default and default.IsValid() else stage.GetPseudoRoot()
    warnings = []
    if not default or not default.IsValid():
        warnings.append("Stage has no valid default prim; using the pseudo-root")
    extents, note = compute_extents_meters(stage, root)
    if note:
        warnings.append(note)
    mass, mass_body_count = sum_authored_mass(stage)
    qcode, _source = derive_qcode(root)
    values = {
        "rigid_body_count": count_rigid_bodies(stage),
        "asset_extents": extents,
        "mass": mass,
        "qcode": qcode,
    }
    unresolved = tuple(
        field for field in ("asset_extents", "mass", "qcode") if values[field] is None
    )
    meters_per_unit = float(UsdGeom.GetStageMetersPerUnit(stage) or 1.0)
    mass_check = build_mass_report(
        stage,
        meters_per_unit,
        mass,
        expected_mass_min,
        expected_mass_max,
        mass_rationale,
    )
    warnings.extend(mass_check["warnings"])
    return DerivationResult(
        values=values,
        warnings=tuple(warnings),
        unresolved=unresolved,
        meters_per_unit=meters_per_unit,
        mass_body_count=mass_body_count,
        mass_check=mass_check,
    )
