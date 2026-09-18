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
import logging
import os
import secrets
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import simready.validate as sv

# Fallback source lists when sample_content/project_config.toml omits the keys.
# Validation content is owned by the tiers.
_DEFAULT_REQUIREMENTS_PATHS = [
    "nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities",
]
_DEFAULT_FEATURES_PATHS = [
    "nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features",
]
_DEFAULT_PROFILES_PATHS = [
    "nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles",
]


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
       pass's ``import capabilities`` re-resolve to the other branch's copy.

    ``docs_dirs`` are the repository roots whose ``nv_core/sr_specs/docs`` entries should be
    dropped; passing them explicitly avoids pattern-matching ``sys.path``, which would also
    strip unrelated paths that merely end in the same components.
    """
    sv.destroy()

    for module_name in list(sys.modules):
        if (
            module_name == "capabilities"
            or module_name.startswith("capabilities.")
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
        if m == "capabilities"
        or m.startswith("capabilities.")
        or m == "omni.generated_capabilities"
        or m.startswith("omni.generated_capabilities.")
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

        known_deletions, known_deletion_errors = load_known_deletions(repo_root)

        # Load compare-branch configs
        compare_config_path = os.path.join(worktree_dir, "sample_content/project_config.toml")
        with open(compare_config_path, "rb") as f:
            compare_config = tomllib.load(f)
        compare_validate = compare_config.get("validate", {})
        compare_requirements_paths = [
            Path(os.path.join(worktree_dir, path))
            for path in compare_validate.get("requirements_paths", _DEFAULT_REQUIREMENTS_PATHS)
        ]
        compare_features_paths = [
            Path(os.path.join(worktree_dir, path))
            for path in compare_validate.get("features_paths", _DEFAULT_FEATURES_PATHS)
        ]
        compare_profile_paths: list[Path] = []
        for profiles_path in compare_validate.get("profiles_paths", _DEFAULT_PROFILES_PATHS):
            profiles_dir = os.path.join(worktree_dir, profiles_path)
            if os.path.isdir(profiles_dir):
                compare_profile_paths.extend(sorted(Path(profiles_dir).glob("*.toml")))

        _isolate_validation_state(worktree_dir, repo_root)
        sv.initialize(
            rules_and_requirements_paths=compare_requirements_paths,
            features_paths=compare_features_paths,
            profiles_paths=compare_profile_paths,
        )

        # Run validation on the compare branch
        compare_results = sv.validate_asset_list(
            [
                sv.AssetValidationConfig(
                    asset_path=asset_path,
                )
                for asset_path in compare_branch_asset_paths
            ]
        )

        # Load cur branch configs
        cur_config_path = os.path.join(repo_root, "sample_content/project_config.toml")
        with open(cur_config_path, "rb") as f:
            cur_config = tomllib.load(f)
        cur_validate = cur_config.get("validate", {})
        cur_requirements_paths = [
            Path(os.path.join(repo_root, path))
            for path in cur_validate.get("requirements_paths", _DEFAULT_REQUIREMENTS_PATHS)
        ]
        cur_features_paths = [
            Path(os.path.join(repo_root, path)) for path in cur_validate.get("features_paths", _DEFAULT_FEATURES_PATHS)
        ]
        cur_profile_paths: list[str] = []
        for profiles_path in cur_validate.get("profiles_paths", _DEFAULT_PROFILES_PATHS):
            profiles_dir = os.path.join(repo_root, profiles_path)
            if os.path.isdir(profiles_dir):
                cur_profile_paths.extend(sorted(Path(profiles_dir).glob("*.toml")))

        _isolate_validation_state(worktree_dir, repo_root)
        sv.initialize(
            rules_and_requirements_paths=cur_requirements_paths,
            features_paths=cur_features_paths,
            profiles_paths=cur_profile_paths,
        )

        # Run validation on cur branch
        cur_results = sv.validate_asset_list(
            [
                sv.AssetValidationConfig(
                    asset_path=asset_path,
                )
                for asset_path in cur_branch_asset_paths
            ]
        )

        # Process the data so its easier to compare
        compare_results_fixed = {}
        for result in compare_results:
            if not result:
                continue
            rel_path = result.asset_path.replace(worktree_dir + "/", "")
            compare_results_fixed[rel_path] = result.features_summary
        cur_results_fixed = {}
        for result in cur_results:
            if not result:
                continue
            rel_path = result.asset_path.replace(repo_root + "/", "")
            cur_results_fixed[rel_path] = result.features_summary

        known_deletion_errors.extend(
            validate_known_deletion_state(
                repo_root,
                cur_branch_manifest_rel_paths,
                known_deletions,
            )
        )
        validation_passed = not known_deletion_errors
        for error in known_deletion_errors:
            print(error, file=sys.stderr)

        for rel_path in compare_results_fixed.keys():
            print(f"Checking asset: {rel_path}")
            compare_features = compare_results_fixed[rel_path]
            cur_features = cur_results_fixed.get(rel_path)
            if cur_features is None:
                error = get_missing_asset_error(
                    rel_path,
                    cur_branch_manifest_rel_paths,
                    known_deletions,
                )
                if error:
                    validation_passed = False
                    print(error, file=sys.stderr)
                else:
                    print(f"Asset ({rel_path}) has known deletion record ({known_deletions[rel_path]})")
                continue
            for feature_name, compare_feature_data in compare_features.items():
                cur_feature_data = cur_features.get(feature_name)
                if cur_feature_data is None:
                    if compare_feature_data["passed"]:
                        validation_passed = False
                        print(
                            f"Asset ({rel_path}) Feature ({feature_name}) missing on current branch",
                            file=sys.stderr,
                        )
                    continue
                if compare_feature_data["passed"] and not cur_feature_data["passed"]:
                    validation_passed = False
                    print(
                        f"Asset ({rel_path}) Feature ({feature_name}) fails when it used to pass",
                        file=sys.stderr,
                    )
        validation_result = validation_passed
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
