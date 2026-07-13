---
name: simready-foundation-create-package
description: "Use for creating SimReady packages with package sample scripts, WRAPP setup, root USD inputs, validation phases, and fallback modes."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - packaging
    - validation
---

# SimReady Create Package

## Purpose

Use this skill when a user wants to turn a folder of USD assets into a SimReady package with the bundled package sample workflow.

The skill guides `assets/scripts/create_simready_package.py`, which runs pre-validation, package creation, and post-validation. The helper package under `assets/scripts/sr_pkg_sample/` is bundled with the skill so the workflow can run without reaching back into `nv_core/package_sample/`.

## Prerequisites

Before running packaging commands, confirm:

- the repository root is `simready_foundations`
- Python 3.10 or newer is available in the shell that will run the sample
- `assets/scripts/setup_venv.sh` can be run from Git Bash, WSL, or another bash-compatible shell
- the user has the WRAPP wheel `omni_wrapp_minimal-2.2.0-py3-none-any.whl`, or has access to an internal index that provides it
- the source folder contains every USD file and referenced asset that should go into the package
- the user provides the license that applies to the asset; do not choose a license for them

No OpenAI API key is required.

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `name` | Package name, lowercase and without spaces, such as `apple_a01`. |
| `version` | Package version, such as `1.0.0`. |
| `license` | SPDX identifier or `LicenseRef-*` expression chosen by the user. |
| `source` | Folder that contains the root USDs and all referenced files. |
| `repo` | WRAPP repository path or `file://` URL for the full WRAPP flow. |
| `root_usd` | Relative path inside `source` for each root USD, repeated with `--root-usd`. |
| `mode` | Full flow, pre-validation only, post-validation only, skip phase, or no-WRAPP fallback. |

## Instructions

Use this checklist from the repository root:

1. Use the bundled scripts in `skills/simready-foundation-create-package/assets/scripts/`.
2. Change into `skills/simready-foundation-create-package/assets/scripts/` before running setup or package commands.
3. If `.venv/` already exists, activate it and verify `import simready.validate` and `import wrapp` before rebuilding it.
4. If a virtual environment is needed, run `./setup_venv.sh --wrapp-wheel <path-to-wheel>`. Add `--extra-index <url>` only when the user has a package index that provides missing dependencies.
5. Activate the virtual environment for every packaging command. If running from outside the repository root, set `SIMREADY_FOUNDATIONS_ROOT` to the repository root so the bundled helper can find `nv_core/sr_specs/docs`.
6. Prefer the default flow for publication:
   ```bash
   python create_simready_package.py <name> <version> <license> <source> <repo> \
       --root-usd <relative/root.usd>
   ```
7. Use `--only-pre-validation --source <folder> --root-usd <path>` when the user is iterating on source-folder conformance before building.
8. Use `--only-post-validation --package-def <path-to-com.nvidia.simready.packaging.json>` to validate an already-created package.
9. Suggest `--skip-pre-validation` only after a successful pre-validation against the same unchanged source folder.
10. Suggest `--skip-post-validation` only when the user intentionally wants to validate the created package later.
11. Use `--no-wrapp` only for a minimal package skeleton or when WRAPP cannot be installed. Tell the user it is not suitable for publication and may fail BOM or introspection checks.
12. Inspect the command return code. Treat stdout as evidence, not proof of success.

## Examples

Full package creation:

```bash
cd skills/simready-foundation-create-package/assets/scripts
source .venv/bin/activate
python create_simready_package.py apple_a01 1.0.0 Apache-2.0 \
    ~/my_asset/simready_usd ~/my_repo \
    --root-usd sm_apple_a01_01.usd
```

Pre-validation only while repairing source-folder paths:

```bash
python create_simready_package.py --only-pre-validation \
    --source ~/my_asset/simready_usd \
    --root-usd sm_apple_a01_01.usd
```

No-WRAPP fallback for a local experiment:

```bash
python create_simready_package.py apple_a01 1.0.0 MIT \
    ~/my_asset/simready_usd \
    --no-wrapp --skip-post-validation
```

## Failure Handling

- Pre-validation `FET031_PACKAGE_SELF_CONTAINED` or `AA.001`: report the offending anchored-path failure and ask before editing USD references.
- Pre-validation usage error: collect the missing `--root-usd`, missing `--source`, or invalid folder path.
- Create error about an existing root `.wrapp` marker: ask whether to reuse that package name or remove the marker.
- Create error about nested packages: ask the user to remove nested `.wrapp` files before retrying.
- Post-validation `FET030_PACKAGING_CORE`: cite the failing package-core requirement and keep the generated package for inspection.
- Post-validation `FET032_PACKAGING_INTROSPECTION`: check whether BOM metadata was written and rerun the full flow if the source did not change.

## Policies

- Do not rewrite the user's USD files automatically while packaging.
- Do not pick the asset license for the user.
- Treat `assets/scripts/` as the skill-owned copy of the package workflow.
- Preserve generated reports and metadata unless the user asks for cleanup.
- Stop after two setup retries and summarize the blocker with the exact command that failed.

## Limitations

- This skill does not replace profile-specific conformance skills for repairing USD content.
- The WRAPP setup depends on user-provided packages, credentials, or indexes that may not be available in the current shell.
- The no-WRAPP fallback creates a lightweight package definition and is expected to miss full publication evidence.

## Troubleshooting

- Error: `Could not find a version that satisfies the requirement`. Solution: verify access to `https://pypi.nvidia.com/`, then add the user's private index or local wheels.
- Error: `no root USD files specified`. Solution: add one or more `--root-usd` paths relative to the source folder, or use `--no-usd-files` only for intentional non-USD packages.
- Error: package source changed after pre-validation. Solution: rerun the default flow so conformance metadata hashes match the current source.
- Error: WRAPP local backend is disabled. Solution: reinstall the WRAPP wheel with the `[local]` extra through `setup_venv.sh`.

## Resources

- `assets/scripts/create_simready_package.py` is the command-line entrypoint.
- `assets/scripts/setup_venv.sh` creates the sample virtual environment.
- `assets/scripts/requirements-package-sample.txt` lists the package workflow dependencies.
- `assets/scripts/sr_pkg_sample/` contains the Python API for custom tooling integrations.

## Summary Format

Report:

| Field | Meaning |
|---|---|
| `mode` | Full flow, pre-validation only, post-validation only, skip phase, or no-WRAPP fallback. |
| `source` | Source folder that was packaged or checked. |
| `package_name` | Package name and version. |
| `root_usds` | Root USD paths supplied to the script. |
| `repo` | Target WRAPP repository, when used. |
| `first_failing_phase` | First failed phase, or `none`. |
| `reports` | Validation report paths, metadata paths, or package definition path. |
| `next_step` | Repair source, rerun packaging, publish, or inspect generated evidence. |
