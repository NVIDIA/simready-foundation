# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Validate sample_content and fail on regressions vs main."""
from __future__ import annotations

import csv
import os
import secrets
import subprocess
import sys
import tomllib
from pathlib import Path

import simready.validate as sv


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
                f"Duplicate known deletion for ({asset_path}) in "
                f"({records[asset_path]}) and ({record_path})"
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
                f"Known deletion ({record_path}) asset ({asset_rel_path}) "
                "is still listed in the current manifest"
            )
        asset_path = Path(repo_root).joinpath(*asset_rel_path.split("/"))
        if asset_path.exists():
            errors.append(
                f"Known deletion ({record_path}) asset ({asset_rel_path}) still exists on disk"
            )
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
        return (
            f"Asset ({asset_rel_path}) removed from the current manifest "
            "without a known deletion record"
        )
    return None


def validate_sample_content() -> bool:
    validation_result = False

    try:
        # Checkout worktree
        repo_root = str(Path(__file__).resolve().parent.parent.parent.parent).replace("\\", "/")
        compare_ref = os.environ.get("CI_DEFAULT_BRANCH", "main")
        random_hash = secrets.token_hex(8)
        worktree_dir = os.path.join(
            repo_root,
            f"_build/validation-compare-{compare_ref.replace('/', '_')}-{random_hash}",
        ).replace("\\", "/")
        print(f"Checking out main branch to: {worktree_dir}")
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

        # Get sample assets in main
        manifest_rel_path = "sample_content/manifest.csv"

        main_branch_manifest_path = os.path.join(worktree_dir, manifest_rel_path)
        main_branch_asset_paths = []
        with open(main_branch_manifest_path, "r") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                asset_path = os.path.join(worktree_dir, row[0]).replace("\\", "/")
                main_branch_asset_paths.append(asset_path)

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

        # Load main configs
        main_config_path = os.path.join(worktree_dir, "sample_content/project_config.toml")
        with open(main_config_path, "rb") as f:
            main_config = tomllib.load(f)
        main_validate = main_config.get("validate", {})
        main_requirements_paths = [
            Path(os.path.join(worktree_dir, path))
            for path in main_validate.get("requirements_paths", ["nv_core/sr_specs/docs/capabilities"])
        ]
        main_features_paths = [
            Path(os.path.join(worktree_dir, path))
            for path in main_validate.get("features_paths", ["nv_core/sr_specs/docs/features"])
        ]
        main_profile_paths: list[Path] = []
        for profiles_path in main_validate.get("profiles_paths", ["nv_core/sr_specs/docs/profiles"]):
            profiles_dir = os.path.join(worktree_dir, profiles_path)
            if os.path.isdir(profiles_dir):
                main_profile_paths.extend(sorted(Path(profiles_dir).glob("*.toml")))

        sv.destroy()
        for module_name in list(sys.modules):
            if module_name == "capabilities" or module_name.startswith("capabilities."):
                del sys.modules[module_name]
        sv.initialize(
            rules_and_requirements_paths=main_requirements_paths,
            features_paths=main_features_paths,
            profiles_paths=main_profile_paths,
        )

        # Run validation on main
        main_results = sv.validate_asset_list([
            sv.AssetValidationConfig(
                asset_path=asset_path,
            )
            for asset_path in main_branch_asset_paths
        ])

        # Load cur branch configs
        cur_config_path = os.path.join(repo_root, "sample_content/project_config.toml")
        with open(cur_config_path, "rb") as f:
            cur_config = tomllib.load(f)
        cur_validate = cur_config.get("validate", {})
        cur_requirements_paths = [
            Path(os.path.join(repo_root, path))
            for path in cur_validate.get("requirements_paths", ["nv_core/sr_specs/docs/capabilities"])
        ]
        cur_features_paths = [
            Path(os.path.join(repo_root, path))
            for path in cur_validate.get("features_paths", ["nv_core/sr_specs/docs/features"])
        ]
        cur_profile_paths: list[str] = []
        for profiles_path in cur_validate.get("profiles_paths", ["nv_core/sr_specs/docs/profiles"]):
            profiles_dir = os.path.join(repo_root, profiles_path)
            if os.path.isdir(profiles_dir):
                cur_profile_paths.extend(sorted(Path(profiles_dir).glob("*.toml")))

        sv.destroy()
        for module_name in list(sys.modules):
            if module_name == "capabilities" or module_name.startswith("capabilities."):
                del sys.modules[module_name]
        sv.initialize(
            rules_and_requirements_paths=cur_requirements_paths,
            features_paths=cur_features_paths,
            profiles_paths=cur_profile_paths,
        )

        # Run validation on cur branch
        cur_results = sv.validate_asset_list([
            sv.AssetValidationConfig(
                asset_path=asset_path,
            )
            for asset_path in cur_branch_asset_paths
        ])

        # Process the data so its easier to compare
        main_results_fixed = {}
        for result in main_results:
            if not result:
                continue
            rel_path = result.asset_path.replace(worktree_dir + "/", "")
            main_results_fixed[rel_path] = result.features_summary
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

        for rel_path in main_results_fixed.keys():
            print(f"Checking asset: {rel_path}")
            main_features = main_results_fixed[rel_path]
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
                    print(
                        f"Asset ({rel_path}) has known deletion record ({known_deletions[rel_path]})"
                    )
                continue
            for feature_name, main_feature_data in main_features.items():
                cur_feature_data = cur_features.get(feature_name)
                if cur_feature_data is None:
                    if main_feature_data["passed"]:
                        validation_passed = False
                        print(
                            f"Asset ({rel_path}) Feature ({feature_name}) missing on current branch",
                            file=sys.stderr,
                        )
                    continue
                if main_feature_data["passed"] and not cur_feature_data["passed"]:
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


def main() -> int:
    if validate_sample_content():
        print("No validation regressions vs main.")
        return 0
    print("Sample content validation failed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
