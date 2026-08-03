# SimReady Packaging Workflow

This guide walks you through packaging a real asset — **`apple_a01`** — from a folder of USD files into a distributable SimReady package. You will learn the expected folder layout, pre-validate the asset, produce a package definition (with or without a Bill of Materials), and re-validate an existing package.

We use the same apple asset from start to finish so the file paths line up across every step.

Run all commands from the **repository root** unless stated otherwise.

## Prerequisites

Environment setup (Python 3.12, virtual environment, LFS) is covered in the <a href="../../../../README.md">top-level README</a>. This guide assumes you have already:

- Created and activated a virtual environment.
- Installed the packaging dependencies from `nv_core/package_sample/requirements.txt`.

Verify `simready-package` is on your PATH:

```bash
simready-package --help
```

If the command is not found, re-check the venv activation and reinstall dependencies. See [Troubleshooting](#troubleshooting).

| Requirement | Minimum |
|-------------|---------|
| Python | 3.12 |
| Git LFS | Installed and initialized (`git lfs install`) |
| WRAPP (`omni-wrapp-minimal`) | Only required for step 5 (full WRAPP packaging) |

## 1. Meet the working asset: `apple_a01`

Our running example is the canonical apple asset at <a href="../../../../sample_content/common_assets/props_general/apple_a01/">sample_content/common_assets/props_general/apple_a01/</a>. Its `simready_usd/` subfolder holds everything the packager needs:

```text
apple_a01/
└── simready_usd/                                    ← the SimReady-conformant content
    ├── sm_apple_a01_01.usd                          ← root USD (entry point)
    ├── sm_apple_a01_01.json                         ← optional asset-metadata sidecar
    ├── materials/OmniPBR/*.mdl                      ← MDL material graphs
    ├── textures/image0.png                          ← texture assets
├── web/sm_apple_a01_01.glb                      ← optional web-preview glTF
    └── .thumbs/
        ├── sm_apple_a01_01_thumbnail.png            ← legacy thumbnail
        └── 256x256/sm_apple_a01_01.usd.png          ← SR.002-compliant thumbnail (required for FET033)
```

### What makes a folder a "SimReady asset"

The pre-validation stage checks that your source folder satisfies asset packaging structure constraints and requirements. In practice that means:

| Expectation | Where enforced |
|-------------|----------------|
| Root USD sits under `simready_usd/` (or another sub-tree you point `--root-usd` at) | `--root-usd` argument or the [content-root layout](#file-layout-summary) |
| All USD references resolve to files **inside** the source folder — no absolute paths, no upward `..` escapes | `FET031_PACKAGE_SELF_CONTAINED` |
| Each root USD has a matching thumbnail at `.thumbs/256x256/<root>.usd.png` | `FET033` (SR.002) |
| No stray files outside the packaging convention (materials, textures, thumbs, web, and USDs are recognized) | `Package-Candidate` profile |

> [!NOTE]
> The `apple_a01` folder already meets these expectations. When you start from a raw folder of USDs, you may need to move files into `simready_usd/`, resolve reference paths, and add a thumbnail. The pre-validation step in section 3 tells you exactly what is missing.

### File layout summary

The packager treats the **source folder you pass as the positional `SOURCE` argument** as the package root. All `--root-usd` paths are relative to it, and every file inside becomes a candidate for the Bill of Materials. Nested `simready_usd/` folders are a convention — the packager does not require them, but the SimReady tooling expects them and the sample packages follow this layout.

## 2. Configuring `simready-package`

`simready-package` needs to know where to find validation **rules**, **features**, and **profiles**. There are two ways to tell it — one file-based, one all on the command line.

### 2a. Project config (recommended)

`sample_content/project_config.toml` is a project-level dispatcher. When you pass `--project-config <path>` to `simready-package`, it reads the `[validate]` section and resolves the three paths for you.

```toml
[project_root]
setting = ".."

[validate]
requirements_configs_path = "nv_core/sr_specs/config"
requirements_paths        = ["nv_core/sr_specs/docs/capabilities"]
features_paths            = ["nv_core/sr_specs/docs/features"]
profiles_paths            = ["nv_core/sr_specs/docs/profiles"]
```

| Key | What it points at |
|-----|-------------------|
| `[project_root] setting` | The **project root** — resolved relative to the config file's own directory. All `[validate]` paths below are then resolved relative to this project root. |
| `requirements_paths` | Directories containing capability + requirement definitions (`docs/capabilities/**`) |
| `features_paths` | Directories containing feature manifest files (`FET*.md` + JSON) |
| `profiles_paths` | Directories or files containing profile TOMLs (e.g. the `profiles/` directory of per-profile TOMLs) |
| `requirements_configs_path` | Optional overrides for individual requirements |

Path resolution happens in two steps:

1. **Locate the project root.** `[project_root] setting` is resolved relative to the directory of the config file itself. In `sample_content/project_config.toml`, `setting = ".."` climbs one directory up from `sample_content/`, landing at the repository root.
2. **Resolve `[validate]` paths from that project root.** So `nv_core/sr_specs/docs/capabilities` under `requirements_paths` becomes `<repo_root>/nv_core/sr_specs/docs/capabilities`.

This two-step design lets a config live anywhere in the tree (in a sub-folder, next to sample content, etc.) while still pointing at repo-root-relative paths — just set `setting` to whatever hop is needed to reach the project root from the config file.

Every command in this guide uses `--project-config sample_content/project_config.toml` for consistency. If your project has a similar config elsewhere, point at that one instead.

### 2b. Direct CLI flags (no config file)

If you do not have a project config, pass the three paths directly. Every command that accepts `--project-config` also accepts `--rules-path`, `--features-path`, and `--profiles-path`:

<details open>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
simready-package sample_content\common_assets\props_general\apple_a01 `
    --rules-path    nv_core\sr_specs\docs\capabilities `
    --features-path nv_core\sr_specs\docs\features `
    --profiles-path nv_core\sr_specs\docs\profiles `
    --root-usd simready_usd\sm_apple_a01_01.usd `
    --pre-validate-only
```
</details>

<details>
<summary><strong>Linux</strong></summary>

```bash
simready-package sample_content/common_assets/props_general/apple_a01 \
    --rules-path    nv_core/sr_specs/docs/capabilities \
    --features-path nv_core/sr_specs/docs/features \
    --profiles-path nv_core/sr_specs/docs/profiles \
    --root-usd simready_usd/sm_apple_a01_01.usd \
    --pre-validate-only
```
</details>

Each flag is repeatable — pass `--rules-path` twice, for example, to load rules from two directories. This is useful when you have both foundation rules and a private extension set.

> [!TIP]
> The two modes compose. If you pass `--project-config` **and** `--rules-path`, the CLI flag wins for that path. Use this when you want to override just one path from the config without rewriting the file.

## 3. Pre-validate the asset

Pre-validation is a fast check on your source folder before you commit to a longer build. It runs and exits without writing packaging artifacts.

<details open>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
simready-package sample_content\common_assets\props_general\apple_a01 `
    --project-config sample_content\project_config.toml `
    --root-usd simready_usd\sm_apple_a01_01.usd `
    --pre-validate-only
```
</details>

<details>
<summary><strong>Linux</strong></summary>

```bash
simready-package sample_content/common_assets/props_general/apple_a01 \
    --project-config sample_content/project_config.toml \
    --root-usd simready_usd/sm_apple_a01_01.usd \
    --pre-validate-only
```
</details>

| Argument | Value | Purpose |
|----------|-------|---------|
| `SOURCE` (positional) | `.../apple_a01` | Folder to validate |
| `--project-config` | `sample_content/project_config.toml` | Load rules/features/profiles from `[validate]` |
| `--root-usd` | `simready_usd/sm_apple_a01_01.usd` | Top-level USD entry point (repeatable for multi-USD packages) |
| `--pre-validate-only` | — | Run pre-validation only; do not build |

Expected output:

```text
Pre-validation: [PASSED]
```

When pre-validation passes, `Package-Candidate` has confirmed:

- All USD references resolve to files inside the folder (`FET031`).
- Each root USD meets SimReady packaging prerequisites (`FET033`), such as an SR.002-compliant thumbnail.

If something is missing (typically the `256x256` thumbnail), the failure message names the exact requirement so you know what to fix.

## 4. Local packaging (no BOM)

Choose this path when you want a minimal manifest for prototyping or when WRAPP is unavailable. `simready-package` writes a `com.nvidia.simready.packaging.json` directly into your source folder. No BOM, no content hash — just the three required fields.

<details open>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
simready-package sample_content\common_assets\props_general\apple_a01 `
    --project-config sample_content\project_config.toml `
    --name apple_a01 `
    --version 1.0.0 `
    --license Apache-2.0 `
    --root-usd simready_usd\sm_apple_a01_01.usd
```
</details>

<details>
<summary><strong>Linux</strong></summary>

```bash
simready-package sample_content/common_assets/props_general/apple_a01 \
    --project-config sample_content/project_config.toml \
    --name apple_a01 \
    --version 1.0.0 \
    --license Apache-2.0 \
    --root-usd simready_usd/sm_apple_a01_01.usd
```
</details>

Post-validation uses the `Package-NoBOM` profile automatically, checking manifest structure only (`FET030_PACKAGING_CORE`: `format_version`, `package_id`, `license`). The full `Package` profile — which adds `FET032` BOM introspection — applies only in step 5.

Expected output:

```text
Pre-validation: [PASSED]

Post-validation: [PASSED]

Package definition: sample_content/common_assets/props_general/apple_a01/com.nvidia.simready.packaging.json
```

The generated file contains only the required fields:

```json
{
  "format_version": "1.0",
  "package_id": "com.nvidia.simready.apple_a01.1.0.0",
  "license": "Apache-2.0",
  "metadata": []
}
```

> [!NOTE]
> If your source folder already contains a `com.nvidia.simready.packaging.json`, this command overwrites it. If it also contains a stale `.metadata/` folder from a previous run, delete it first — see the note in section 5.

## 5. Full WRAPP packaging (with BOM)

Use this path when you need a versioned, distributable package with a Bill of Materials, content hash, and conformance metadata. Pre- and post-validation are **mandatory** — `--skip-pre-validation` and `--skip-post-validation` are rejected in this mode.

For a local test run, use a local directory as the target repository:

<details open>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
simready-package sample_content\common_assets\props_general\apple_a01 `
    --project-config sample_content\project_config.toml `
    --name apple_a01 `
    --version 1.0.0 `
    --license Apache-2.0 `
    --root-usd simready_usd\sm_apple_a01_01.usd `
    --repo C:\temp\my_repo
```
</details>

<details>
<summary><strong>Linux</strong></summary>

```bash
simready-package sample_content/common_assets/props_general/apple_a01 \
    --project-config sample_content/project_config.toml \
    --name apple_a01 \
    --version 1.0.0 \
    --license Apache-2.0 \
    --root-usd simready_usd/sm_apple_a01_01.usd \
    --repo /tmp/my_repo
```
</details>

Expected output:

```text
Pre-validation: [PASSED]

Post-validation: [PASSED]

Package definition: <repo>/.packages/apple_a01/1.0.0/com.nvidia.simready.packaging.json
BOM:                <repo>/.packages/apple_a01/1.0.0/.metadata/com.nvidia.simready.packaging.bom.json
```

### The `.packages/` folder

Your target repo — the directory you passed to `--repo` — is treated as a package store. Every published package lands at `<repo>/.packages/<name>/<version>/`. For our apple:

```text
<repo>/.packages/apple_a01/1.0.0/
├── com.nvidia.simready.packaging.json    ← top-level manifest (metadata[] + content_hash + package_hash)
├── .metadata/                             ← sidecar artifacts referenced by the manifest
│   ├── com.nvidia.simready.packaging.bom.json                        ← Bill of Materials: file list + per-file hashes
│   ├── com.nvidia.simready.root_usds.json                            ← recorded root-USD entry points
│   ├── com.nvidia.simready.conformance.Package-Candidate@1.0.0.json  ← pre-validation evidence
│   └── com.nvidia.simready.conformance.Package@1.0.0.json            ← post-validation evidence (Package profile)
└── simready_usd/                          ← the payload — same shape as the source
    ├── sm_apple_a01_01.usd
    ├── materials/…
    ├── textures/…
    └── .thumbs/…
```

| Artifact | Contents |
|----------|----------|
| `com.nvidia.simready.packaging.json` | `format_version`, `package_id`, `license`, `metadata[]` (hash of each sidecar), rolled-up `content_hash`, and `package_hash` |
| `.metadata/…packaging.bom.json` | Every file in the payload with its `sha256` (and optionally `blake3`) hash, size, and relative path |
| `.metadata/…root_usds.json` | The set of `--root-usd` entry points recorded at build time |
| `.metadata/…conformance.Package-Candidate@1.0.0.json` | Structured record of the pre-validation results (evidence for the `Package-Candidate` profile) |
| `.metadata/…conformance.Package@1.0.0.json` | Structured record of the post-validation results (evidence for the full `Package` profile) |

> [!IMPORTANT]
> **Clean your source before re-running.** A stale `.metadata/` folder from a previous pre-validation run can cause `content_hash mismatch` during the build step. Delete `.metadata/` from your source folder before you run full WRAPP packaging again.

### Compare against the reference fixture

Compare the layout under `<repo>/.packages/apple_a01/1.0.0/` against the pre-built reference at <a href="../../../../sample_content/packaging/simple_packages/apple_a01_usd_bom/">sample_content/packaging/simple_packages/apple_a01_usd_bom/</a>. You should see the same set of files (package definition with `metadata` / `content_hash` / `package_hash`, `.metadata/` folder with BOM, root-USDs, and conformance sidecars, plus the payload). Individual hash values will differ if your source content differs.

## 6. Re-validate an existing package

If you already have a `com.nvidia.simready.packaging.json` file — because you built it earlier, received it from someone else, or updated the profile definitions — you can post-validate it in place with `--post-validate-only`. This does not rebuild anything; it just re-checks that the recorded hashes still match the files on disk.

### 6a. No-BOM package

If your package was created in local mode (step 4), it has no BOM. Validate it with the `Package-NoBOM` profile, which checks manifest structure only:

<details open>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
simready-package `
    --project-config sample_content\project_config.toml `
    --post-validate-only `
    --package-def sample_content\packaging\simple_packages\apple_a01_nobom\com.nvidia.simready.packaging.json `
    --profile Package-NoBOM
```
</details>

<details>
<summary><strong>Linux</strong></summary>

```bash
simready-package \
    --project-config sample_content/project_config.toml \
    --post-validate-only \
    --package-def sample_content/packaging/simple_packages/apple_a01_nobom/com.nvidia.simready.packaging.json \
    --profile Package-NoBOM
```
</details>

Expected output:

```text
Post-validation: [PASSED]
```

### 6b. BOM-enabled package

If your package was created with WRAPP (step 5), the manifest declares a BOM and content hash. Validate it with the default `Package` profile, which also checks BOM completeness (`FET032`):

<details open>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
simready-package `
    --project-config sample_content\project_config.toml `
    --post-validate-only `
    --package-def sample_content\packaging\simple_packages\apple_a01_usd_bom\com.nvidia.simready.packaging.json
```
</details>

<details>
<summary><strong>Linux</strong></summary>

```bash
simready-package \
    --project-config sample_content/project_config.toml \
    --post-validate-only \
    --package-def sample_content/packaging/simple_packages/apple_a01_usd_bom/com.nvidia.simready.packaging.json
```
</details>

Expected output:

```text
Post-validation: [PASSED]
```

The default profile for `--post-validate-only` is `Package`. Pass `--profile <ID>` to override it.

## 7. Understanding the sample packages

The repo ships pre-built packages under `sample_content/packaging/simple_packages/` that you can compare against:

| Folder | BOM? | What it demonstrates |
|--------|------|----------------------|
| `apple_a01_nobom/` | No | Minimal package: `format_version`, `package_id`, `license` only. Output of local (no-WRAPP) mode. |
| `apple_a01_usd_bom/` | Yes | Full WRAPP package: BOM + `content_hash` + Package-Candidate conformance metadata. |
| `apple_a01_usd_bom_multi_hash/` | Yes | Same as `apple_a01_usd_bom/` with both `sha256` and `blake3` hashes. |
| `apple_a01_materials/` | Yes | Materials/textures-only package with no USD content; demonstrates the BOM-only path. |
| `fruit_f01_multi_usd/` | Yes | Multi-root-USD package with `apple_a01` and `orange_a01` entry points. |

## Exit codes

Every `simready-package` command in this guide returns an exit code your pipeline can gate on:

| Exit code | Meaning |
|-----------|---------|
| `0` | Success. Every phase that ran completed without error (or was skipped). |
| `1` | Validation failure, build failure, or invalid arguments. Read the console output to tell them apart. |

## Troubleshooting

### `simready-package` command not found

- Make sure the venv is activated.
- Reinstall dependencies: `pip install -r nv_core/package_sample/requirements.txt`.
- On Windows, try `python -m simready.package` as a fallback.

### `Error: no root USD files specified`

Pass `--root-usd <relative-path>` to name the entry-point USD file inside your source folder. The path is relative to `SOURCE`, for example `--root-usd simready_usd/sm_apple_a01_01.usd`.

### `Packaging failed: WRAPP build failed: content_hash mismatch`

A stale `.metadata/` folder inside your source folder contains a `content_hash` computed from a different file set. Delete `.metadata/` and re-run.

### `Validation failed: <engine-error>`

Profile definitions were not loaded. Pass `--project-config sample_content/project_config.toml` on every invocation outside a Kit environment, or the three `--rules-path` / `--features-path` / `--profiles-path` flags. See section 2.

### Git LFS pointer files

If your USD files are tiny text stubs starting with `version https://git-lfs.github.com/spec/v1`, LFS pointers were not resolved:

```bash
git lfs install
git lfs pull
```
