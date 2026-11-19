#!/usr/bin/env python3
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
"""Hold the profile comparison table in ``profiles.md`` to what the profile TOMLs say.

The table claims to be read out of the profile TOMLs. This checks that it is: every
profile a TOML declares has a row, every row names a profile a TOML declares, the Versions
cell lists exactly the versions declared, and the Contracts cell lists exactly the union of
the contracts those versions select. It also checks that every profile has an authoring
guide and every guide has a profile.

The Contracts cell names each feature and capability by name and runtime, without the
version segment, because the versions selected differ between profile versions.

Usage:
    python tests/validate_profile_table.py
"""

from __future__ import annotations

import functools
import json
import re
import sys
import tomllib
from fnmatch import fnmatchcase
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _first(*candidates: Path) -> Path:
    """The first path that exists. The spec tree has two layouts: requirements,
    features and profiles under ``nv_core/sr_specs/docs``, or under a tier package
    with the cross-tier prose in ``docs/shared``. Both are looked for so this runs
    either side of that move."""
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


DOCS = REPO / "nv_core" / "sr_specs" / "docs"
TIER = REPO / "nv_core" / "tiers" / "simready_foundation_tier_core" / "simready" / "foundation" / "tier_core"


def _profile_dirs() -> list[Path]:
    """Every tier's profiles directory. The table lists the profiles from all tiers
    together, so a checker reading only the core tier calls the others undeclared."""
    found = sorted(REPO.glob("nv_core/tiers/*/simready/foundation/*/profiles"))
    return found or [_first(TIER / "profiles", DOCS / "profiles")]


PROFILE_DIRS = _profile_dirs()
PROFILES = PROFILE_DIRS[0]
TABLE = _first(DOCS / "shared" / "profiles" / "profiles.md", PROFILES / "profiles.md")


def _glob(pattern: str) -> list[Path]:
    return sorted(p for directory in PROFILE_DIRS for p in directory.glob(pattern))


SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
TABLE_ROW = re.compile(r"^\|\s*([A-Za-z][\w-]*)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$")
NOT_A_PROFILE = {"Profile"}


@functools.cache
def _contract_ids() -> list[str]:
    """Every feature and capability ID declared across the tiers."""
    ids = []
    for path in sorted(REPO.glob("nv_core/tiers/*/simready/foundation/*/*/*.json")):
        if path.parent.name not in ("capabilities", "features"):
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(document, dict) and isinstance(document.get("id"), str):
            ids.append(document["id"])
    return ids


def _selected(selector: str) -> list[str]:
    """The contracts a selector picks, as ``name.runtime``. Matched as the contract
    loader matches: each segment is a case-insensitive glob, two-segment selectors
    match runtimes or neutral versions, and a bare family token such as ``FET004``
    matches every name in that family."""
    wanted = selector.casefold().split(".")
    short = len(wanted) == 2 and wanted[1] != "*"
    wanted += ["*"] * (3 - len(wanted))
    picked = []
    for contract_id in _contract_ids():
        name, *rest = contract_id.casefold().split(".")
        if len(rest) == 1:
            rest.insert(0, "openusd")
        if not (fnmatchcase(name, wanted[0]) or name.split("_", 1)[0] == wanted[0]):
            continue
        if (
            all(fnmatchcase(have, want) for have, want in zip(rest, wanted[1:]))
            or (short and rest[0] == "openusd" and fnmatchcase(rest[1], wanted[1]))
        ):
            picked.append(contract_id.rsplit(".", 1)[0])
    return picked


def declared() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Versions and the union of selected contracts, per profile, from the TOMLs."""
    versions: dict[str, list[str]] = {}
    contracts: dict[str, list[str]] = {}
    for path in _glob("*.toml"):
        with open(path, "rb") as handle:
            document = tomllib.load(handle)
        for profile, entries in document.items():
            if not isinstance(entries, dict):
                continue
            for version, entry in entries.items():
                if not SEMVER.match(str(version)) or not isinstance(entry, dict):
                    continue
                versions.setdefault(profile, []).append(str(version))
                bucket = contracts.setdefault(profile, [])
                for item in entry.get("features", []) + entry.get("capabilities", []):
                    if not isinstance(item, dict) or "selector" not in item:
                        continue
                    for contract in _selected(item["selector"]):
                        if contract not in bucket:
                            bucket.append(contract)
    for profile in versions:
        versions[profile].sort()
    return versions, contracts


def rows() -> dict[str, tuple[list[str], list[str]]]:
    """Versions and contracts, per profile, as the markdown table states them."""
    out: dict[str, tuple[list[str], list[str]]] = {}
    for line in TABLE.read_text().splitlines():
        match = TABLE_ROW.match(line)
        if not match:
            continue
        profile = match.group(1).strip()
        if profile in NOT_A_PROFILE:
            continue
        version_cell = [v.strip() for v in match.group(2).split(",") if v.strip()]
        if not all(SEMVER.match(v) for v in version_cell):
            continue
        contract_cell = [c.strip() for c in match.group(4).split(",") if c.strip()]
        out[profile] = (sorted(version_cell), contract_cell)
    return out


def main() -> int:
    toml_versions, toml_contracts = declared()
    table = rows()
    problems: list[str] = []

    for profile in sorted(set(toml_versions) | set(table)):
        if profile not in table:
            problems.append(f"{profile}: declared in a TOML, absent from the table")
            continue
        if profile not in toml_versions:
            problems.append(f"{profile}: a table row, but no TOML declares it")
            continue
        listed_versions, listed_contracts = table[profile]
        if listed_versions != toml_versions[profile]:
            problems.append(
                f"{profile}: table lists versions {', '.join(listed_versions)}; "
                f"the TOML declares {', '.join(toml_versions[profile])}"
            )
        # Order is the table author's to choose; which contracts are named is not.
        expected = toml_contracts.get(profile, [])
        missing = [c for c in expected if c not in listed_contracts]
        extra = [c for c in listed_contracts if c not in expected]
        if missing or extra:
            detail = []
            if missing:
                detail.append(f"missing {', '.join(missing)}")
            if extra:
                detail.append(f"lists {', '.join(extra)} which no version selects")
            problems.append(f"{profile}: contracts {'; '.join(detail)}")

    # A guide filename is the profile name lowercased, but the separators are not
    # written consistently: Open-Taxonomy-ImageNet1K's guide is
    # open-taxonomy-imagenet_1k.md. Both sides drop everything but letters and
    # digits so a hyphen and an underscore compare equal.
    def slug(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.lower())

    guides = {p.stem for p in _glob("*.md")} - {"profiles", "package-profiles"}
    by_slug = {slug(g): g for g in guides}
    declared_slugs = {slug(p) for p in toml_versions}

    # A guide that documents no profile is a stale file and fails. A profile with no
    # guide is missing content, which the tier that owns the profile writes; it is
    # reported without failing so one tier's backlog does not block another's merge.
    unguided = [
        profile
        for profile in sorted(toml_versions)
        if slug(profile) not in by_slug and not profile.startswith("Package")
    ]
    for guide in sorted(guides):
        if slug(guide) not in declared_slugs:
            problems.append(f"{guide}.md: an authoring guide for a profile no TOML declares")

    print(f"{len(toml_versions)} profiles across {len(_glob('*.toml'))} TOMLs in {len(PROFILE_DIRS)} tiers")
    if unguided:
        print("  no authoring guide yet: " + ", ".join(unguided))
    if problems:
        for problem in problems:
            print(f"  {problem}")
        print(f"\n{len(problems)} problems")
        return 1
    print("  the table matches the TOMLs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
