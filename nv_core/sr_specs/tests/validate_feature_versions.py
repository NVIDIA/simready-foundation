#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Hold released feature versions still, and hold feature manifests to rules that exist.

A feature version is a contract. "This asset conforms to FET_006_MDL 0.1.0" only means
something if 0.1.0 means the same thing today as it did when it shipped. Editing the
requirement list of a version that is already on the default branch breaks that, and the
break is silent: nothing about the asset changed and nothing about the version number
changed, only the answer.

Two checks:

1. A feature manifest that exists on the default branch must not have its requirement
   list changed. New versions are the way to change what a feature asks for. An edit that
   is genuinely necessary is recorded under ``features/known_edits`` and accepted.

2. Every requirement named by a feature manifest this branch adds or changes must
   resolve to a registered rule. A requirement that no rule implements makes its feature
   unregistered, which makes the loader drop every profile version listing that feature --
   silently, apart from one line on stderr. This catches it at build time instead.

   Scoped to what the branch touches on purpose. The repository already carries manifests
   naming requirements no rule implements, inherited rather than introduced, and failing
   on those would make the check unrunnable rather than useful.

Usage:
    python tests/validate_feature_versions.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TIER = REPO / "nv_core" / "tiers" / "simready_foundation_tier_core" / "simready" / "foundation" / "tier_core"
FEATURES = TIER / "features"
KNOWN_EDITS = FEATURES / "known_edits"
DEFAULT_BRANCH = "main"
REVERSE_DOMAIN = "com.nvidia.simready"


def _git(*args: str) -> str | None:
    """Run a git command in the repo, returning stdout or None if it failed."""
    result = subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=False
    )
    return result.stdout if result.returncode == 0 else None


def _baseline_ref() -> str | None:
    """The ref to compare against: the default branch as this checkout last saw it.

    CI clones a single branch at a shallow depth, so the default branch is usually not in
    the checkout at all. Fetch it when it is missing -- without this the check cannot tell a
    new feature version from an edit to a released one, which is the whole point of it.
    """
    candidates = (f"origin/{DEFAULT_BRANCH}", DEFAULT_BRANCH)
    for ref in candidates:
        if _git("rev-parse", "--verify", "--quiet", ref):
            return ref

    _git("fetch", "--quiet", "--depth", "200", "origin", DEFAULT_BRANCH)
    for ref in (f"FETCH_HEAD", *candidates):
        if _git("rev-parse", "--verify", "--quiet", ref):
            return ref
    return None


def load_known_edits() -> tuple[dict[tuple[str, str], str], list[str]]:
    """Accepted edits to released feature versions, keyed by (feature id, version)."""
    records: dict[tuple[str, str], str] = {}
    errors: list[str] = []
    if not KNOWN_EDITS.is_dir():
        return records, errors

    for path in sorted(KNOWN_EDITS.glob("*.toml")):
        with open(path, "rb") as handle:
            document = tomllib.load(handle)
        edit = document.get("edit")
        if not isinstance(edit, dict):
            errors.append(f"{path.name}: no [edit] table")
            continue
        feature, version, reason = edit.get("feature"), edit.get("version"), edit.get("reason")
        for field, value in (("feature", feature), ("version", version), ("reason", reason)):
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{path.name}: [edit] {field} is missing or empty")
        if isinstance(feature, str) and isinstance(version, str) and isinstance(reason, str):
            records[(feature, version)] = reason
    return records, errors


def _requirements(text: str) -> list[str] | None:
    try:
        return list(json.loads(text).get("requirements", []))
    except (json.JSONDecodeError, AttributeError):
        return None


def check_released_versions_unchanged(problems: list[str], accepted: dict[tuple[str, str], str]) -> None:
    """A manifest that exists on the default branch must keep its requirement list."""
    baseline = _baseline_ref()
    if baseline is None:
        problems.append(
            f"cannot compare against '{DEFAULT_BRANCH}': no such ref in this checkout"
        )
        return

    used: set[tuple[str, str]] = set()
    for path in sorted(FEATURES.glob("*.json")):
        relative = path.relative_to(REPO).as_posix()
        before = _git("show", f"{baseline}:{relative}")
        if before is None:
            continue  # new file, which is how a new version arrives

        old, new = _requirements(before), _requirements(path.read_text())
        if old is None or new is None:
            problems.append(f"{path.name}: not readable as a feature manifest")
            continue
        if old == new:
            continue

        document = json.loads(path.read_text())
        key = (str(document.get("id")), str(document.get("version")))
        if key in accepted:
            used.add(key)
            continue

        added = [r for r in new if r not in old]
        removed = [r for r in old if r not in new]
        detail = []
        if added:
            detail.append(f"adds {', '.join(added)}")
        if removed:
            detail.append(f"drops {', '.join(removed)}")
        if not detail:
            detail.append("reorders its requirements")
        problems.append(
            f"{path.name} is released on {baseline} and {'; '.join(detail)}. "
            f"Ship the change as a new version, or record it under "
            f"{KNOWN_EDITS.relative_to(REPO).as_posix()}"
        )

    for key in sorted(set(accepted) - used):
        problems.append(
            f"known_edits records an edit to {key[0]} {key[1]} that is not present; "
            f"remove the record"
        )


def check_requirements_resolve(problems: list[str]) -> None:
    """Every requirement named by a manifest this branch touches must be bound to a rule."""
    baseline = _baseline_ref()
    try:
        # The requirements enums are generated at build time and are not in the tree, so a
        # bare checkout cannot import a single capability. Generate them the same way the
        # tier's hatchling hook does, into a directory this run owns.
        from usd_profiles_nvidia.codegen import PythonGenerator

        generated = Path(tempfile.mkdtemp(prefix="requirement-enums-"))
        PythonGenerator(
            capabilities_root=str(TIER / "capabilities"),
            destination_dir=str(generated),
            package_name="simready.foundation.tier_core.requirements",
            reverse_domain=REVERSE_DOMAIN,
        ).generate()
        sys.path.insert(0, str(generated))

        import simready.validate as sv
        from usd_validation_nvidia import RequirementsRegistry
    except ImportError as error:
        problems.append(f"cannot import the validation runtime, so rules were not checked: {error}")
        return

    sv.initialize(
        rules_and_requirements_paths=[TIER / "capabilities"],
        features_paths=[FEATURES],
        profiles_paths=[TIER / "profiles"],
    )
    registry = RequirementsRegistry()

    for path in sorted(FEATURES.glob("*.json")):
        if baseline is not None:
            before = _git("show", f"{baseline}:{path.relative_to(REPO).as_posix()}")
            if before is not None and _requirements(before) == _requirements(path.read_text()):
                continue  # untouched by this branch
        document = json.loads(path.read_text())
        for code in document.get("requirements", []):
            # A manifest may name a code verbatim, as it does for the upstream
            # com.nvidia.usd.* rules, or unprefixed, in which case the loader tries
            # the reverse domain. Resolve it the same way.
            requirement = registry.find_requirement(code) or registry.find_requirement(
                f"{REVERSE_DOMAIN}.{code}"
            )
            if requirement is None or not registry.is_implemented(requirement):
                problems.append(
                    f"{path.name} names {code}, which no rule implements. Every profile "
                    f"version listing this feature would be dropped at validation time"
                )


def main() -> int:
    problems: list[str] = []
    accepted, record_errors = load_known_edits()
    problems.extend(record_errors)

    check_released_versions_unchanged(problems, accepted)
    check_requirements_resolve(problems)

    manifests = len(list(FEATURES.glob("*.json")))
    print(f"{manifests} feature manifests, {len(accepted)} accepted edits")
    if problems:
        for problem in problems:
            print(f"  {problem}")
        print(f"\n{len(problems)} problems")
        return 1
    print("  released versions are unchanged, and every requirement resolves to a rule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
