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
"""Hold released feature versions still, and hold feature manifests to rules that exist.

A contract version is a contract. "This asset conforms to FET006_Materials.MDL.0-1-0"
only means something if 0-1-0 means the same thing today as it did when it shipped.
Editing the requirement list of a version that is already on the default branch breaks
that, and the break is silent: nothing about the asset changed and nothing about the
version changed, only the answer.

Two checks:

1. A contract manifest that exists on the default branch must not have its requirement
   list changed. New versions are the way to change what a contract asks for. An edit that
   is genuinely necessary is recorded under ``features/known_edits`` and accepted::

       [edit]
       feature = "FET006_Materials.MDL.0-1-0"
       requirements = ["VM.BIND.002", "VM.MAT.001", "VM.MDL.001"]
       reason = "why this released version had to move"

   A record accepts the one requirement list it names, and is checked against the
   manifest rather than against a diff. It therefore reads the same before and after the
   edit merges, and a later edit to that same version needs its own record instead of
   inheriting this one. A record stays in the tree after its edit merges, where it goes
   inert: the manifest agrees with the default branch, so there is nothing to accept.

   Manifests are matched to the default branch by their dotted contract ID, which carries
   the version, not by path. A released version that no manifest in the tree publishes
   any longer is reported as well.

2. Every requirement named by a contract manifest this branch adds or changes must
   resolve to a registered rule. A requirement that no rule implements makes its contract
   unregistered, which makes the loader drop every profile version listing that contract --
   silently, apart from one line on stderr. This catches it at build time instead.

   Scoped to what the branch touches on purpose. The repository already carries manifests
   naming requirements no rule implements, inherited rather than introduced, and failing
   on those would make the check unrunnable rather than useful.

Usage:
    python tests/validate_feature_versions.py
"""

from __future__ import annotations

import functools
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TIER = REPO / "nv_core" / "tiers" / "simready_foundation_tier_core" / "simready" / "foundation" / "tier_core"
FEATURES = TIER / "features"
CAPABILITIES = TIER / "capabilities"
RULES = TIER / "rules_and_reqs"
KNOWN_EDITS = FEATURES / "known_edits"
DEFAULT_BRANCH = "main"
REVERSE_DOMAIN = "com.nvidia.simready"


def _contract_dirs() -> list[Path]:
    """The directories holding contract manifests."""
    return [FEATURES, CAPABILITIES]


def _manifests() -> list[Path]:
    return sorted(path for directory in _contract_dirs() for path in directory.glob("*.json"))


def _git(*args: str) -> str | None:
    """Run a git command in the repo, returning stdout or None if it failed."""
    result = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=False)
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


@dataclass
class KnownEdit:
    """One ``known_edits`` record: the edit it accepts, and where it is written."""

    feature: str
    requirements: list[str]
    reason: str
    path: Path


def load_known_edits() -> tuple[dict[str, KnownEdit], list[str]]:
    """Accepted edits to released contract versions, keyed by dotted contract ID.

    A malformed record is reported and dropped rather than raised. One unparseable file
    should cost its own line in the report, not the result of every other check.
    """
    records: dict[str, KnownEdit] = {}
    errors: list[str] = []
    if not KNOWN_EDITS.is_dir():
        return records, errors

    for path in sorted(KNOWN_EDITS.glob("*.toml")):
        try:
            with open(path, "rb") as handle:
                document = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as error:
            errors.append(f"{path.name}: not readable as a known_edits record: {error}")
            continue

        edit = document.get("edit")
        if not isinstance(edit, dict):
            errors.append(f"{path.name}: no [edit] table")
            continue

        malformed = False
        feature, reason = edit.get("feature"), edit.get("reason")
        for field, value in (("feature", feature), ("reason", reason)):
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{path.name}: [edit] {field} is missing or empty")
                malformed = True
        if "version" in edit:
            errors.append(
                f"{path.name}: [edit] version is not a field; name the dotted contract ID, "
                f"which carries the version, in feature"
            )
            malformed = True

        requirements = edit.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            errors.append(
                f"{path.name}: [edit] requirements is missing or empty. A record accepts one "
                f"requirement list, so it has to say which one"
            )
            malformed = True
        elif any(not isinstance(code, str) or not code.strip() for code in requirements):
            errors.append(f"{path.name}: [edit] requirements must be a list of requirement codes")
            malformed = True

        if malformed:
            continue

        if feature in records:
            errors.append(f"{path.name}: {feature} is already recorded in {records[feature].path.name}")
            continue
        records[feature] = KnownEdit(
            feature=feature,
            requirements=list(requirements),
            reason=reason,
            path=path,
        )
    return records, errors


def _requirements(text: str) -> list[str] | None:
    """A manifest's own requirement list. A feature contract names it
    ``additional_requirements``; a capability contract names it ``requirements``."""
    try:
        document = json.loads(text)
        key = "requirements" if "requirements" in document else "additional_requirements"
        return list(document.get(key, []))
    except (json.JSONDecodeError, AttributeError, TypeError):
        return None


def _contract_id(document: dict) -> str:
    """Canonical identity, shared by renamed neutral manifests and baseline IDs."""
    return re.sub(r"\.OpenUSD(?=\.)", "", str(document.get("id")), flags=re.IGNORECASE)


def _manifest_index() -> dict[str, Path]:
    """Every contract manifest in the tree, keyed by contract ID."""
    index: dict[str, Path] = {}
    for path in _manifests():
        try:
            document = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(document, dict):
            index[_contract_id(document)] = path
    return index


@functools.cache
def _released(baseline: str) -> dict[str, list[str]]:
    """The requirement list of every manifest on the baseline, keyed by contract ID, so a
    contract file that moved is compared with the version it replaced rather than read as
    new. The directories are this checkout's."""
    released: dict[str, list[str]] = {}
    for directory in _contract_dirs():
        listing = _git("ls-tree", "--name-only", baseline, f"{directory.relative_to(REPO).as_posix()}/")
        for relative in (listing or "").splitlines():
            if not relative.endswith(".json"):
                continue
            text = _git("show", f"{baseline}:{relative}")
            try:
                document = json.loads(text or "")
            except json.JSONDecodeError:
                continue
            requirements = _requirements(text)
            if isinstance(document, dict) and "id" in document and requirements is not None:
                released[_contract_id(document)] = requirements
    return released


def validate_known_edit_state(problems: list[str], accepted: dict[str, KnownEdit]) -> None:
    """Reject records that no longer describe the manifest they name.

    A record is held to the tree rather than to a diff. Before the edit merges the
    manifest differs from the default branch and the record accepts it; after it merges
    the manifest still lists what the record names, so the record stays valid instead of
    reading as stale the moment it lands. A record that no longer matches is either an
    edit nobody accepted or a record nobody updated, and both want a human.
    """
    index = _manifest_index()
    for feature, record in sorted(accepted.items()):
        path = index.get(feature)
        if path is None:
            problems.append(f"{record.path.name}: names {feature}, which is not a contract manifest in the tree")
            continue

        current = _requirements(path.read_text())
        if current is None:
            problems.append(f"{record.path.name}: {path.name} is not readable as a contract manifest")
            continue
        if current != record.requirements:
            problems.append(
                f"{record.path.name}: accepts {feature} as "
                f"{', '.join(record.requirements)}, but the manifest lists "
                f"{', '.join(current) or 'nothing'}. Update the record to the list it accepts, "
                f"or ship the change as a new version"
            )


def check_released_versions_unchanged(problems: list[str], accepted: dict[str, KnownEdit]) -> None:
    """A version released on the default branch must stay published, with its requirement list."""
    baseline = _baseline_ref()
    if baseline is None:
        problems.append(f"cannot compare against '{DEFAULT_BRANCH}': no such ref in this checkout")
        return

    released = _released(baseline)
    published: set[str] = set()
    for path in _manifests():
        text = path.read_text()
        new = _requirements(text)
        if new is None:
            problems.append(f"{path.name}: not readable as a contract manifest")
            continue
        key = _contract_id(json.loads(text))
        published.add(key)
        old = released.get(key)
        if old is None:
            continue  # a version the baseline does not have, which is how a new version arrives
        if old == new:
            continue

        if key in accepted:
            # Whether the record still describes this manifest is validate_known_edit_state's
            # question, so it is asked in one place and answered against the tree.
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
            f"{KNOWN_EDITS.relative_to(REPO).as_posix()} with the requirement list it produces"
        )

    for feature in sorted(set(released) - published):
        problems.append(
            f"{feature} is released on {baseline}, and no manifest in the tree publishes "
            f"it any longer. A released version stays available to the assets that conform to it"
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
            capabilities_root=str(RULES),
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
        rules_and_requirements_paths=[RULES],
        features_paths=_contract_dirs(),
        # This gate checks requirement bindings. Profiles may require contracts
        # from other tiers, which are qualified by the catalog/profile checks.
        profiles_paths=[],
    )
    registry = RequirementsRegistry()

    released = _released(baseline) if baseline is not None else {}
    for path in _manifests():
        text = path.read_text()
        requirements = _requirements(text) or []
        if released.get(_contract_id(json.loads(text))) == requirements:
            continue  # untouched by this branch
        for code in requirements:
            # A manifest may name a code verbatim, as it does for the upstream
            # com.nvidia.usd.* rules, or unprefixed, in which case the loader tries
            # the reverse domain. Resolve it the same way.
            requirement = registry.find_requirement(code) or registry.find_requirement(f"{REVERSE_DOMAIN}.{code}")
            if requirement is None or not registry.is_implemented(requirement):
                problems.append(
                    f"{path.name} names {code}, which no rule implements. Every profile "
                    f"version listing this feature would be dropped at validation time"
                )


RUNTIME_PACKAGES = ("simready-validate", "usd-validation-nvidia", "usd-profiles-nvidia")


def runtime_versions() -> str:
    """The installed versions of the packages whose behavior influences these checks.

    None of these dependencies are pinned so we'll print their versions at job startup so they appear in the log.
    """
    reported = []
    for name in RUNTIME_PACKAGES:
        try:
            reported.append(f"{name} {metadata.version(name)}")
        except metadata.PackageNotFoundError:
            reported.append(f"{name} not installed")
    return ", ".join(reported)


def main() -> int:
    print(f"checked with {runtime_versions()}")
    problems: list[str] = []
    accepted, record_errors = load_known_edits()
    problems.extend(record_errors)

    validate_known_edit_state(problems, accepted)
    check_released_versions_unchanged(problems, accepted)
    check_requirements_resolve(problems)

    print(f"{len(_manifests())} contract manifests, {len(accepted)} accepted edits")
    if problems:
        for problem in problems:
            print(f"  {problem}")
        print(f"\n{len(problems)} problems")
        return 1
    print("  released versions are unchanged, and every requirement resolves to a rule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
