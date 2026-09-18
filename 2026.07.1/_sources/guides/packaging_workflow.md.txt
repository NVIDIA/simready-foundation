# SimReady Packaging Workflow

This guide walks through packaging a SimReady USD asset using the
`simready-package` CLI. The steps follow the natural progression of a
packaging run: validate the source folder, produce a package definition,
post-validate the result, and — when WRAPP is available — publish a full
package with a Bill of Materials (BOM) and content hash.

All commands run from the **repository root** unless stated otherwise.

## Prerequisites

| Requirement | Minimum |
|-------------|---------|
| Python | 3.11+ |
| Git LFS | Installed and initialised (`git lfs install`) |
| WRAPP wheel | Required for step 5 (full WRAPP packaging) only |

## 1. Create a clean virtual environment

`simready-package` depends on `simready-validate` and
`usd-validation-nvidia`. Use a dedicated venv to avoid conflicts with
other packages.

````{tab-set}
```{tab-item} Windows (PowerShell)
python -m venv .venv
.venv\Scripts\activate
```

```{tab-item} Linux
python -m venv .venv
source .venv/bin/activate
```
````

## 2. Install dependencies

### 2a. Core packages

```bash
pip install "simready-foundation-tier-core==2026.7.1" "simready-validate>=2026.7.0.dev1" "simready-package[publish]>=2026.6.0a1"
```

This installs `simready-package` and its dependencies (`simready-validate`,
`usd-validation-nvidia`, `usd-core`, `usd-profiles-nvidia`) together with the
Foundation 7.1 tier content. The `publish` extra supplies the WRAPP integration;
omit `[publish]` when only local package creation and validation are needed. See
the [Foundation 7.1 library set](foundation_pypi.md#foundation-71-library-set)
for the complete compatibility matrix.

Verify the install:

```bash
simready-package --help
```

### 2b. WRAPP (required for full BOM packaging only)

`ovpackage` is not on `pypi.nvidia.com`. Install it separately from
the NVIDIA internal index:

```bash
pip install ovpackage
```

Steps 3–4 work without WRAPP.

## 3. Pre-validate a source folder

Pre-validation checks that the USD files in a source folder conform to the
`Package-Candidate` profile **before** any packaging artifacts are created.
Run this step in isolation with `--pre-validate-only`.

The `--project-config` flag is required whenever you run outside a Kit
environment. It points `simready-package` at a `project_config.toml` whose
`[validate]` section lists the rules, features, and profiles paths.

```bash
simready-package sample_content/packaging/simple_packages/apple_a01_nobom --project-config sample_content/project_config.toml --root-usd apple_a01/simready_usd/sm_apple_a01_01.usd --pre-validate-only
```

| Argument | Value | Purpose |
|----------|-------|---------|
| SOURCE (positional) | `sample_content/…/apple_a01_nobom` | Source folder to validate |
| `--project-config` | `sample_content/project_config.toml` | Loads rules, features, and profiles from `[validate]` |
| `--root-usd` | relative path inside SOURCE | Top-level USD entry point. Repeatable for multi-USD packages. |
| `--pre-validate-only` | — | Run pre-validation only; do not build a package |

Expected output:

```text
Pre-validation: [PASSED]
```

Exit code `0` means the folder is ready to package. The
`Package-Candidate` profile checks that all USD references are
self-contained (`FET031`) and that the required packaging metadata
structure is in place (`FET033`).

## 4. Local packaging (no BOM)

Local mode writes a minimal `com.nvidia.simready.packaging.json` directly
into the source folder. No WRAPP installation is required. No BOM or content
hash is produced — use this mode for prototyping or environments where WRAPP
is not available.

```bash
simready-package sample_content/packaging/simple_packages/apple_a01_nobom --name apple_a01 --version 1.0.0 --license Apache-2.0 --project-config sample_content/project_config.toml --root-usd apple_a01/simready_usd/sm_apple_a01_01.usd
```

Local mode automatically uses the `Package-NoBOM` profile for
post-validation. `Package-NoBOM` checks only manifest structure
(`FET_030_STANDARD`: `format_version`, `package_id`, `license`),
without requiring a BOM or content hash. The full `Package` profile
(which adds `FET032` BOM introspection) is only used in WRAPP mode.

Expected output:

```text
Pre-validation: [PASSED]

Post-validation: [PASSED]

Package definition: sample_content/packaging/simple_packages/apple_a01_nobom/com.nvidia.simready.packaging.json
```

The produced `com.nvidia.simready.packaging.json` contains only the three
required fields: `format_version`, `package_id`, and `license`.

```{note}
If `apple_a01_nobom` already contains a `com.nvidia.simready.packaging.json`
from a previous run, the command overwrites it.
```

## 5. Full WRAPP packaging (with BOM)

Full mode publishes the package into a WRAPP repository and produces a
`com.nvidia.simready.packaging.json` with a BOM, content hash, and
conformance metadata. Both pre- and post-validation are **mandatory** —
`--skip-pre-validation` and `--skip-post-validation` are not allowed.

Install `ovpackage` first (see [step 2b](#2b-wrapp-required-for-full-bom-packaging-only)).

Use a local directory as the target repository. The package lands at
`<repo>/.packages/<name>/<version>/`.

```bash
simready-package sample_content/packaging/simple_packages/apple_a01_nobom --name apple_a01 --version 1.0.0 --license Apache-2.0 --project-config sample_content/project_config.toml --root-usd apple_a01/simready_usd/sm_apple_a01_01.usd --repo /path/to/my_repo
```

Expected output:

```text
Pre-validation: [PASSED]

Post-validation: [PASSED]

Package definition: <repo>/.packages/apple_a01/1.0.0/com.nvidia.simready.packaging.json
BOM:                <repo>/.packages/apple_a01/1.0.0/.metadata/com.nvidia.simready.packaging.bom.json
```

The published layout under `.packages/apple_a01/1.0.0/` matches the
pre-built fixture at
`sample_content/packaging/simple_packages/apple_a01_usd_bom/`.

```{note}
**Clean source before re-running.** Delete any `.metadata/` folder left by a
previous pre-validation run inside the source folder before re-running full
WRAPP packaging. A stale `.metadata/` whose `content_hash` was computed from
a different file set causes `content_hash mismatch` during the build step.
```

## 6. Re-validate an existing package definition

Use `--post-validate-only --package-def <path>` to run post-validation
against an existing `com.nvidia.simready.packaging.json` without rebuilding
the package. This is useful when validating a package produced elsewhere or
re-checking a package after modifying profile definitions.

### 6a. No-BOM package (Package-NoBOM profile)

A package definition produced in local mode has no BOM. Validate it against
`Package-NoBOM`, which checks the manifest structure without requiring a BOM
or content hash:

```bash
simready-package --project-config sample_content/project_config.toml --post-validate-only --package-def sample_content/packaging/simple_packages/apple_a01_nobom/com.nvidia.simready.packaging.json --profile Package-NoBOM
```

Expected output:

```text
Post-validation: [PASSED]
```

### 6b. BOM-enabled package (Package profile)

A package produced by WRAPP (step 5) includes a BOM and content hash.
Validate it against the full `Package` profile, which also checks BOM
completeness (`FET032`):

```bash
simready-package --project-config sample_content/project_config.toml --post-validate-only --package-def sample_content/packaging/simple_packages/apple_a01_usd_bom/com.nvidia.simready.packaging.json
```

Expected output:

```text
Post-validation: [PASSED]
```

The default profile for `--post-validate-only` is `Package`. Pass
`--profile <ID>` to override.

## 7. Understanding the sample packages

The pre-built packages under `sample_content/packaging/simple_packages/`
are concrete references for each packaging variant and serve as fixtures for
the integration tests in `nv_core/package_sample/tests/`:

| Folder | BOM? | What it demonstrates |
|--------|------|----------------------|
| `apple_a01_nobom/` | no | Minimal package — `format_version`, `package_id`, `license` only. Output of local (no-WRAPP) mode. |
| `apple_a01_usd_bom/` | yes | Full WRAPP package — BOM + `content_hash` + Package-Candidate conformance metadata. |
| `apple_a01_usd_bom_multi_hash/` | yes | Same as `apple_a01_usd_bom/` with both `sha256` and `blake3` hashes. |
| `apple_a01_materials/` | yes | Materials/textures-only package — no USD content; exercises the BOM-only path. |
| `fruit_f01_multi_usd/` | yes | Multi-root-USD package — `apple_a01` and `orange_a01` entry points. |

## Troubleshooting

### `simready-package` command not found

- Make sure the venv is activated.
- Run `pip install -r nv_core/package_sample/requirements.txt` again.
- On Windows, try `python -m simready.package` as a fallback.

### `Error: no root USD files specified`

Pass `--root-usd <relative-path>` to identify the entry-point USD file(s)
inside the source folder. The path is relative to the source folder root,
e.g. `--root-usd apple_a01/simready_usd/sm_apple_a01_01.usd`.

### `Packaging failed: WRAPP build failed: content_hash mismatch`

A stale `.metadata/` directory inside the source folder contains a
`content_hash` computed from a different file set. Delete `.metadata/` from
the source folder and re-run.

### `Validation failed: <engine-error>`

Profile definitions were not loaded. Pass
`--project-config sample_content/project_config.toml` on every invocation
outside a Kit environment. This flag triggers `simready.validate.initialize()`
before validation runs.

### Git LFS pointer files

If USD files are tiny text files starting with
`version https://git-lfs.github.com/spec/v1`, LFS pointers were not
resolved:

```bash
git lfs install
git lfs pull
```
