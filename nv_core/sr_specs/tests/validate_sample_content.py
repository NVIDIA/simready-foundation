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
"""Validate sample_content and fail on regressions vs the compare branch."""
from __future__ import annotations

import csv
import json
import logging
import os
import re
import secrets
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

# Register PhysX schemas before either checkout initializes USD's schema registry.
# The compare checkout may predate the standalone-provider fallback.
try:
    from pxr import PhysxSchema  # noqa: F401
except ImportError:
    from physx_usd_schemas import PhysxSchema  # noqa: F401

# The compare checkout may import robot schemas lazily, after opening a stage.
try:
    from usd.schema.isaac import robot_schema  # noqa: F401
except ImportError:
    pass  # Validators report unavailable Isaac checks in environments without it.

from pxr import Usd

import simready.validate as sv

# Fallback source lists when sample_content/project_config.toml omits the keys
# or leaves them empty for installed-tier discovery. This regression test must
# validate each checkout's tier content, even when no tier wheels are installed.
_DEFAULT_TIER_PACKAGES = [
    "nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core",
    "nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton",
    "nv_core/tiers/simready_foundation_tier_sensors/simready/foundation/sensors",
]
# The compare branch and the branch under test can name the requirement tree
# differently, and both are validated from the same defaults.
_RULES_DIRNAMES = ("rules_and_reqs", "capabilities")
_CONTRACT_DIRNAMES = ("features", "capabilities")
_DEFAULT_PROFILES_PATHS = [
    "nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles",
    "nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/profiles",
    "nv_core/tiers/simready_foundation_tier_sensors/simready/foundation/sensors/profiles",
]


def _default_requirements_paths(checkout: str) -> list[str]:
    """Each default tier's requirement tree, under whichever name this checkout uses."""
    paths = []
    for package in _DEFAULT_TIER_PACKAGES:
        name = next(
            (n for n in _RULES_DIRNAMES if os.path.isdir(os.path.join(checkout, package, n))),
            _RULES_DIRNAMES[0],
        )
        paths.append(f"{package}/{name}")
    return paths


def _default_features_paths(checkout: str) -> list[str]:
    """Each default tier's contract directories that exist in this checkout. A relocated
    tier holds CAP contracts in ``capabilities/`` and may hold no FET contracts, leaving no
    ``features/`` for git to track. Before the rename ``capabilities/`` is the requirement
    tree instead, so it is only a contract directory when the requirements live elsewhere."""
    requirement_paths = set(_default_requirements_paths(checkout))
    return [
        path
        for package in _DEFAULT_TIER_PACKAGES
        for path in (f"{package}/{name}" for name in _CONTRACT_DIRNAMES)
        if path not in requirement_paths and os.path.isdir(os.path.join(checkout, path))
    ]


def _comparison_id(feature_id: str) -> str:
    """Compare neutral aliases using the same spelling as current readers."""
    return re.sub(r"\.OpenUSD(?=\.)", "", feature_id, flags=re.IGNORECASE)


def _legacy_feature_ids(checkout: str) -> dict[str, str]:
    """Foundations 2 contract ID to the Foundations 1 feature ID it was projected from,
    across every tier in this checkout. The map sits in ``foundations2/`` until the
    contracts are relocated and at the tier package root after. Native contracts
    have no Foundations 1 identity and keep their dotted ID in comparisons."""
    legacy: dict[str, str] = {}
    for pattern in ("*/catalog-map.json", "*/foundations2/catalog-map.json"):
        for path in Path(checkout).glob(f"nv_core/tiers/*/simready/foundation/{pattern}"):
            for contract in json.loads(path.read_text(encoding="utf-8"))["contracts"]:
                if not contract.get("native", False):
                    legacy[_comparison_id(contract["id"])] = contract["legacy_id"]
    return legacy


def _as_legacy_features(features_summary: dict, legacy: dict[str, str]) -> dict:
    """A features summary keyed by Foundations 1 feature ID, so a branch validated through
    Foundations 2 contracts compares against one that is not. Several contracts can project
    from one Foundations 1 ID, one per published version; their entries fold into one that
    passes only if each of them passes, as the validator folds versions within one ID."""
    folded: dict[str, dict] = {}
    for feature_id, data in features_summary.items():
        feature_id = _comparison_id(feature_id)
        legacy_id = legacy.get(feature_id, feature_id)
        if legacy_id in folded:
            folded[legacy_id] = {**folded[legacy_id], "passed": folded[legacy_id]["passed"] and data["passed"]}
        else:
            folded[legacy_id] = data
    return folded


def _is_rules_package(module_name: str) -> bool:
    """A path-loaded requirement tree, imported under its directory name."""
    return any(module_name == n or module_name.startswith(f"{n}.") for n in _RULES_DIRNAMES)


class _ErrorLogHandler(logging.Handler):
    """Collect error-level records so logged validation failures affect the exit code."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def resolve_compare_ref() -> str:
    """Prefer the MR target branch, otherwise the repo default branch."""
    return os.environ.get("CI_MERGE_REQUEST_TARGET_BRANCH_NAME") or os.environ.get("CI_DEFAULT_BRANCH", "main")


def load_known_deletions(repo_root: str) -> tuple[dict[str, Path], list[str]]:
    """Load and validate intentional sample asset deletion records."""
    records: dict[str, Path] = {}
    errors: list[str] = []
    records_dir = Path(repo_root) / "sample_content" / "known_deletions"

    if not records_dir.is_dir():
        return records, errors

    for record_path in sorted(records_dir.glob("*.toml")):
        try:
            with record_path.open("rb") as f:
                record_data = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError) as error:
            errors.append(f"Invalid known deletion record ({record_path}): {error}")
            continue

        deletion = record_data.get("deletion")
        if not isinstance(deletion, dict):
            errors.append(f"Known deletion record ({record_path}) must contain a [deletion] table")
            continue

        missing_fields = {"asset_path", "reason"} - deletion.keys()
        if missing_fields:
            errors.append(
                f"Known deletion record ({record_path}) missing required fields: "
                f"{', '.join(sorted(missing_fields))}"
            )
            continue

        asset_path = deletion["asset_path"]
        reason = deletion["reason"]

        if not isinstance(asset_path, str):
            errors.append(f"Known deletion record ({record_path}) asset_path must be a string")
            continue
        path_parts = asset_path.split("/")
        if (
            asset_path != asset_path.strip()
            or "\\" in asset_path
            or any(part in {"", ".", ".."} for part in path_parts)
            or not path_parts
            or path_parts[0] != "sample_content"
        ):
            errors.append(
                f"Known deletion record ({record_path}) asset_path must be a normalized, "
                "repository-relative path under sample_content/"
            )
            continue

        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"Known deletion record ({record_path}) reason must be a non-empty string")
            continue

        if asset_path in records:
            errors.append(
                f"Duplicate known deletion for ({asset_path}) in " f"({records[asset_path]}) and ({record_path})"
            )
            continue
        records[asset_path] = record_path

    return records, errors


def validate_known_deletion_state(
    repo_root: str,
    current_manifest_paths: set[str],
    known_deletions: dict[str, Path],
) -> list[str]:
    """Reject deletion records for assets that remain published or present."""
    errors: list[str] = []
    for asset_rel_path, record_path in known_deletions.items():
        if asset_rel_path in current_manifest_paths:
            errors.append(
                f"Known deletion ({record_path}) asset ({asset_rel_path}) " "is still listed in the current manifest"
            )
        asset_path = Path(repo_root).joinpath(*asset_rel_path.split("/"))
        if asset_path.exists():
            errors.append(f"Known deletion ({record_path}) asset ({asset_rel_path}) still exists on disk")
    return errors


def get_missing_asset_error(
    asset_rel_path: str,
    current_manifest_paths: set[str],
    known_deletions: dict[str, Path],
) -> str | None:
    """Explain an unapproved missing asset, or return None for a known deletion."""
    if asset_rel_path in current_manifest_paths:
        return f"Asset ({asset_rel_path}) missing on current branch"
    if asset_rel_path not in known_deletions:
        return f"Asset ({asset_rel_path}) removed from the current manifest " "without a known deletion record"
    return None


def _profile_target(receipt: dict) -> tuple[str, str]:
    """Require an exact identity; never substitute the latest profile version."""
    if not isinstance(receipt, dict):
        raise ValueError("profile receipt must be a dictionary")
    target = (receipt.get("profile"), receipt.get("profile_version"))
    if any(not isinstance(value, str) or not value.strip() or value != value.strip() for value in target):
        raise ValueError("profile and profile_version must be non-empty strings")
    return target


def _profile_targets(validation: dict) -> set[tuple[str, str]]:
    """Read legacy and multi-profile receipts, deduplicating compatibility fields."""
    if not isinstance(validation, dict):
        raise ValueError("validation metadata must be a dictionary")
    targets = set()
    if "profile" in validation or "profile_version" in validation:
        targets.add(_profile_target(validation))
    profiles = validation.get("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("validation.profiles must be a dictionary")
    for key, receipt in profiles.items():
        target = _profile_target(receipt)
        if key != "@".join(target):
            raise ValueError(f"profile receipt key ({key}) disagrees with its target ({'@'.join(target)})")
        targets.add(target)
    return targets


def read_sample_targets(
    checkout: str, asset_paths: list[str], known_deletions: dict[str, Path],
) -> tuple[dict[str, set[tuple[str, str]]], list[str]]:
    """Read claimed targets without treating absent validation results as absent files."""
    targets = {}
    errors = []
    for asset_path in asset_paths:
        relative = Path(asset_path).relative_to(checkout).as_posix()
        if not Path(asset_path).is_file():
            if relative not in known_deletions:
                errors.append(f"Asset ({relative}) missing on disk in ({checkout})")
            continue
        try:
            stage = Usd.Stage.Open(asset_path, load=Usd.Stage.LoadNone)
            if stage is None:
                raise ValueError("USD stage could not be opened")
            targets[relative] = _profile_targets(sv.get_simready_validation_metadata(stage))
        except Exception as error:
            errors.append(f"Cannot read profile claims for ({relative}) in ({checkout}): {error}")
            continue
        if not targets[relative]:
            print(f"Asset ({relative}) has no profile claim in ({checkout})")
    return targets, errors


def validate_sample_targets(
    checkout: str, targets: dict[str, set[tuple[str, str]]],
) -> tuple[dict[tuple[str, str, str], dict], list[str]]:
    """Validate every asset/profile/version independently with the public batch API."""
    keys = [(asset, profile, version) for asset in sorted(targets) for profile, version in sorted(targets[asset])]
    configs = [
        sv.AssetValidationConfig(
            asset_path=str(Path(checkout) / asset), profile_id=profile, profile_version=version,
        )
        for asset, profile, version in keys
    ]
    results = sv.validate_asset_list(configs)
    summaries = {}
    errors = []
    legacy = _legacy_feature_ids(checkout)
    for key, result in zip(keys, results, strict=True):
        if result is None or not result.features_summary:
            errors.append(f"Validation unavailable or empty for ({key}) in ({checkout})")
            continue
        summaries[key] = _as_legacy_features(result.features_summary, legacy)
    return summaries, errors


def load_known_profile_removals(repo_root: str) -> tuple[dict[tuple[str, str, str], str], list[str]]:
    """Explicit, exact claims intentionally retired from still-published assets."""
    path = Path(repo_root) / "sample_content/known_profile_removals.toml"
    if not path.exists():
        return {}, []
    records = {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        removals = data.get("removal")
        if not isinstance(removals, list):
            raise ValueError("expected [[removal]] records")
        for record in removals:
            target = _profile_target(record)
            asset = record.get("asset_path")
            reason = record.get("reason")
            if (
                not isinstance(asset, str) or asset != asset.strip() or "\\" in asset
                or not asset.startswith("sample_content/")
                or any(part in {"", ".", ".."} for part in asset.split("/"))
            ):
                raise ValueError("asset_path must be a normalized repository-relative sample_content/ path")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("reason must be a non-empty string")
            key = (asset, *target)
            if key in records:
                raise ValueError(f"duplicate profile removal ({key})")
            records[key] = reason
    except (OSError, ValueError) as error:
        return {}, [f"Invalid profile removal record ({path}): {error}"]
    return records, []


def compare_sample_targets(
    compare_targets: dict[str, set[tuple[str, str]]],
    current_targets: dict[str, set[tuple[str, str]]],
    compare_results: dict[tuple[str, str, str], dict],
    current_results: dict[tuple[str, str, str], dict],
    current_manifest: set[str],
    known_deletions: dict[str, Path],
    known_profile_removals: dict[tuple[str, str, str], str],
) -> list[str]:
    """Compare identical targets; require a record for each intentionally retired claim."""
    errors = []
    for (asset, profile, version), reason in known_profile_removals.items():
        if asset not in current_manifest:
            errors.append(f"Profile removal ({asset}, {profile}@{version}) requires a published asset")
        elif (profile, version) in current_targets.get(asset, set()):
            errors.append(f"Profile removal ({asset}, {profile}@{version}) is still claimed")
        else:
            print(f"Retired profile claim ({asset}, {profile}@{version}): {reason}")
    for asset, targets in compare_targets.items():
        if asset not in current_manifest:
            error = get_missing_asset_error(asset, current_manifest, known_deletions)
            if error:
                errors.append(error)
            continue
        if asset not in current_targets:
            # Reading the file/receipt already produced an explicit error.
            continue
        for profile, version in sorted(targets - current_targets[asset]):
            key = (asset, profile, version)
            if key not in known_profile_removals:
                errors.append(f"Asset ({asset}) removed profile claim ({profile}@{version}) without a removal record")
    for key, current_features in current_results.items():
        asset, profile, version = key
        label = f"Asset ({asset}) Profile ({profile}@{version})"
        print(f"Checking {label}")
        if (profile, version) not in compare_targets.get(asset, set()):
            if not sv.features_summary_passed(current_features):
                errors.append(f"{label} newly claimed profile fails")
            continue
        compare_features = compare_results.get(key)
        if compare_features is None:
            # An unavailable baseline result already produced an explicit error.
            continue
        for feature, old in compare_features.items():
            current = current_features.get(feature)
            if old["passed"] and (current is None or not current["passed"]):
                errors.append(f"{label} Feature ({feature}) missing or fails when it used to pass")
    return errors


def _isolate_validation_state(*docs_dirs: str) -> None:
    """Reset simready.validate so the next pass cannot inherit the previous one's state.

    This job validates the sample content twice in a single process -- once against the
    default branch, once against the branch under test -- calling ``sv.initialize()`` for
    each. ``initialize()`` is not re-entrant: it regenerates ``omni.generated_capabilities``
    but evicts only the top-level package, and it appends each branch's docs directory to
    ``sys.path`` without ever removing it. Both must therefore be cleared by the caller:

    1. ``sys.modules`` -- a stale ``omni.generated_capabilities._capabilities`` from the
       previous pass would shadow the regenerated one, so this pass would bind requirement
       enums belonging to the *other* branch. Anything new on this branch then vanishes:
       ``cannot import name '<Cap>Requirements'`` when a capability is added, or
       ``type object '<Cap>Requirements' has no attribute '<CODE>'`` when a requirement is.
    2. ``sys.path`` -- the previous branch's ``docs`` directory still on the path makes this
       pass's import of its requirement tree re-resolve to the other branch's copy. That
       tree is imported under its directory name, which the two branches may spell
       differently, so every name in ``_RULES_DIRNAMES`` is evicted.

    ``docs_dirs`` are the repository roots whose ``nv_core/sr_specs/docs`` entries should be
    dropped; passing them explicitly avoids pattern-matching ``sys.path``, which would also
    strip unrelated paths that merely end in the same components.
    """
    sv.destroy()

    for module_name in list(sys.modules):
        if (
            _is_rules_package(module_name)
            or module_name == "omni.generated_capabilities"
            or module_name.startswith("omni.generated_capabilities.")
        ):
            del sys.modules[module_name]

    stale_docs = {os.path.normpath(os.path.join(d, "nv_core", "sr_specs", "docs")) for d in docs_dirs}
    sys.path[:] = [p for p in sys.path if os.path.normpath(p) not in stale_docs]

    # Fail loudly rather than silently validating against the wrong branch's rules.
    leaked_modules = sorted(
        m
        for m in sys.modules
        if _is_rules_package(m) or m == "omni.generated_capabilities" or m.startswith("omni.generated_capabilities.")
    )
    leaked_paths = sorted(p for p in sys.path if os.path.normpath(p) in stale_docs)
    if leaked_modules or leaked_paths:
        raise RuntimeError(
            "validation state did not isolate between passes; the next pass would read the "
            f"previous branch's rules. modules={leaked_modules} paths={leaked_paths}"
        )


def validate_sample_content() -> bool:
    validation_result = False

    try:
        # Checkout worktree
        repo_root = str(Path(__file__).resolve().parent.parent.parent.parent).replace("\\", "/")
        compare_ref = resolve_compare_ref()
        random_hash = secrets.token_hex(8)
        worktree_dir = os.path.join(
            repo_root,
            f"_build/validation-compare-{compare_ref.replace('/', '_')}-{random_hash}",
        ).replace("\\", "/")
        print(f"Checking out compare branch ({compare_ref}) to: {worktree_dir}")
        os.makedirs(os.path.dirname(worktree_dir), exist_ok=True)
        subprocess.run(["git", "fetch", "origin", compare_ref], cwd=repo_root, check=True)
        subprocess.run(
            ["git", "worktree", "add", "--detach", worktree_dir, f"origin/{compare_ref}"],
            cwd=repo_root,
            check=True,
        )
        subprocess.run(
            ["git", "lfs", "pull"],
            cwd=worktree_dir,
            check=True,
        )

        # Get sample assets on the compare branch
        manifest_rel_path = "sample_content/manifest.csv"

        compare_branch_manifest_path = os.path.join(worktree_dir, manifest_rel_path)
        compare_branch_asset_paths = []
        with open(compare_branch_manifest_path, "r") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                asset_path = os.path.join(worktree_dir, row[0]).replace("\\", "/")
                compare_branch_asset_paths.append(asset_path)

        cur_branch_manifest_path = os.path.join(repo_root, manifest_rel_path)
        cur_branch_asset_paths = []
        cur_branch_manifest_rel_paths = set()
        with open(cur_branch_manifest_path, "r") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                rel_path = row[0].replace("\\", "/")
                cur_branch_manifest_rel_paths.add(rel_path)
                asset_path = os.path.join(repo_root, rel_path).replace("\\", "/")
                cur_branch_asset_paths.append(asset_path)

        known_deletions, errors = load_known_deletions(repo_root)
        known_profile_removals, removal_errors = load_known_profile_removals(repo_root)
        errors.extend(removal_errors)

        # Load compare-branch configs
        compare_config_path = os.path.join(worktree_dir, "sample_content/project_config.toml")
        with open(compare_config_path, "rb") as f:
            compare_config = tomllib.load(f)
        compare_validate = compare_config.get("validate", {})
        compare_requirements_paths = [
            Path(os.path.join(worktree_dir, path))
            for path in (compare_validate.get("requirements_paths") or _default_requirements_paths(worktree_dir))
        ]
        compare_features_paths = [
            Path(os.path.join(worktree_dir, path))
            for path in (compare_validate.get("features_paths") or _default_features_paths(worktree_dir))
        ]
        compare_profile_paths: list[Path] = []
        for profiles_path in compare_validate.get("profiles_paths") or _DEFAULT_PROFILES_PATHS:
            profiles_dir = os.path.join(worktree_dir, profiles_path)
            if os.path.isdir(profiles_dir):
                compare_profile_paths.extend(sorted(Path(profiles_dir).glob("*.toml")))

        _isolate_validation_state(worktree_dir, repo_root)
        sv.initialize(
            rules_and_requirements_paths=compare_requirements_paths,
            features_paths=compare_features_paths,
            profiles_paths=compare_profile_paths,
        )

        compare_targets, target_errors = read_sample_targets(worktree_dir, compare_branch_asset_paths, known_deletions)
        errors.extend(target_errors)
        compare_results, result_errors = validate_sample_targets(worktree_dir, compare_targets)
        errors.extend(result_errors)

        # Load cur branch configs
        cur_config_path = os.path.join(repo_root, "sample_content/project_config.toml")
        with open(cur_config_path, "rb") as f:
            cur_config = tomllib.load(f)
        cur_validate = cur_config.get("validate", {})
        cur_requirements_paths = [
            Path(os.path.join(repo_root, path))
            for path in (cur_validate.get("requirements_paths") or _default_requirements_paths(repo_root))
        ]
        cur_features_paths = [
            Path(os.path.join(repo_root, path))
            for path in (cur_validate.get("features_paths") or _default_features_paths(repo_root))
        ]
        cur_profile_paths: list[Path] = []
        for profiles_path in cur_validate.get("profiles_paths") or _DEFAULT_PROFILES_PATHS:
            profiles_dir = os.path.join(repo_root, profiles_path)
            if os.path.isdir(profiles_dir):
                cur_profile_paths.extend(sorted(Path(profiles_dir).glob("*.toml")))

        _isolate_validation_state(worktree_dir, repo_root)
        sv.initialize(
            rules_and_requirements_paths=cur_requirements_paths,
            features_paths=cur_features_paths,
            profiles_paths=cur_profile_paths,
        )

        current_targets, target_errors = read_sample_targets(repo_root, cur_branch_asset_paths, {})
        errors.extend(target_errors)
        current_results, result_errors = validate_sample_targets(repo_root, current_targets)
        errors.extend(result_errors)
        errors.extend(validate_known_deletion_state(repo_root, cur_branch_manifest_rel_paths, known_deletions))
        errors.extend(compare_sample_targets(
            compare_targets, current_targets, compare_results, current_results,
            cur_branch_manifest_rel_paths, known_deletions, known_profile_removals,
        ))
        for error in errors:
            print(error, file=sys.stderr)
        validation_result = not errors
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", worktree_dir],
            cwd=repo_root,
            check=False,
        )

    return validation_result


def _selftest_isolate_validation_state() -> None:
    """Prove _isolate_validation_state() actually removes what it claims to.

    Runs before the real validation. The bug this guards only reproduces on a branch that
    adds a requirement code absent from main, so this job's own pipeline cannot exercise it
    -- validating main against a branch with an identical spec passes whether or not the
    isolation works. This seeds the exact state the second pass must not inherit and checks
    it is gone, so the fix carries its own proof rather than depending on some other branch
    happening to fail.
    """
    import types

    root = os.path.normpath(os.path.join(tempfile.gettempdir(), "_sv_selftest_root"))
    docs = os.path.normpath(os.path.join(root, "nv_core", "sr_specs", "docs"))
    # Shares the final three components but is a different directory -- a suffix match would
    # wrongly strip this, so it must survive.
    decoy = os.path.normpath(os.path.join(root + "_other", "bad_nv_core", "sr_specs", "docs"))

    seeded_modules = {
        "capabilities": types.ModuleType("capabilities"),
        "capabilities._selftest": types.ModuleType("capabilities._selftest"),
        "rules_and_reqs": types.ModuleType("rules_and_reqs"),
        "rules_and_reqs._selftest": types.ModuleType("rules_and_reqs._selftest"),
        "omni.generated_capabilities": types.ModuleType("omni.generated_capabilities"),
        "omni.generated_capabilities._capabilities": types.ModuleType("omni.generated_capabilities._capabilities"),
    }
    unrelated = "capabilities_unrelated"
    seeded_modules[unrelated] = types.ModuleType(unrelated)

    saved_modules = {k: sys.modules.get(k) for k in seeded_modules}
    saved_path = list(sys.path)
    try:
        sys.modules.update(seeded_modules)
        sys.path[:0] = [docs, decoy]

        _isolate_validation_state(root)

        leaked = sorted(
            m
            for m in (
                "capabilities",
                "capabilities._selftest",
                "rules_and_reqs",
                "rules_and_reqs._selftest",
                "omni.generated_capabilities",
                "omni.generated_capabilities._capabilities",
            )
            if m in sys.modules
        )
        if leaked:
            raise RuntimeError(f"self-test: modules not evicted: {leaked}")
        if docs in [os.path.normpath(x) for x in sys.path]:
            raise RuntimeError("self-test: stale docs dir not removed from sys.path")
        if decoy not in [os.path.normpath(x) for x in sys.path]:
            raise RuntimeError("self-test: unrelated path sharing the docs suffix was wrongly removed")
        if unrelated not in sys.modules:
            raise RuntimeError("self-test: module merely prefixed 'capabilities' was wrongly evicted")
    finally:
        sys.path[:] = saved_path
        for name, mod in saved_modules.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


def main() -> int:
    error_log_handler = _ErrorLogHandler()
    root_logger = logging.getLogger()
    root_logger.addHandler(error_log_handler)
    compare_ref = resolve_compare_ref()
    try:
        _selftest_isolate_validation_state()
        validation_passed = validate_sample_content()
    finally:
        root_logger.removeHandler(error_log_handler)

    if error_log_handler.records:
        print(
            f"Sample content validation logged {len(error_log_handler.records)} error(s).",
            file=sys.stderr,
        )
        validation_passed = False

    if validation_passed:
        print(f"No validation regressions vs {compare_ref}.")
        return 0
    print("Sample content validation failed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
