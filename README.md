# SimReady Foundation

## Getting the repository

This repository uses **Git LFS** to track binary and USD asset files (`.usda`, `.usdc`, `.usd`, `.usdz`, images, and others). You must have Git LFS installed before cloning, otherwise those files will check out as tiny pointer files instead of the real content.

### 1. Install Git LFS (once per machine)

<details open>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
winget install GitHub.GitLFS
```

If `winget` is not recognized, run these first:

```powershell
Add-AppxPackage -RegisterByFamilyName -MainPackage "Microsoft.DesktopAppInstaller_8wekyb3d8bbwe"
Install-Module -Name Microsoft.WinGet.Client -Force -Repository PSGallery
Repair-WinGetPackageManager
```
</details>

<details>
<summary><strong>Linux (Ubuntu / Debian)</strong></summary>

```bash
sudo apt-get install git-lfs
```
</details>

After installing, run the one-time setup:

```bash
git lfs install
```

### 2. Clone the repository

```bash
git clone https://github.com/NVIDIA/simready-foundation.git
cd simready-foundation
```

Git LFS files are fetched automatically during clone when `git lfs install` has been run. If you already cloned without LFS, pull the real file contents with:

```bash
git lfs pull
```

### 3. Verify LFS files

You can confirm that LFS-tracked files were downloaded correctly:

```bash
git lfs ls-files
```

If any files still show as pointer files, re-run `git lfs pull`.

## Environment setup

### 4. Install Python

The product requires **Python >=3.12,<3.13**.

<details open>
<summary><strong>Windows</strong></summary>

Download from [python.org/downloads](https://www.python.org/downloads/release/python-3120/) and run the installer. Check **"Add Python to PATH"** during installation. If you already have multiple Python versions, you can use the `py -3.12` launcher.
</details>

<details>
<summary><strong>Linux (Ubuntu / Debian)</strong></summary>

```bash
sudo apt-get install python3.12
```
</details>

Verify the installation:

```bash
python --version
```

### 5. Create a virtual environment

> [!IMPORTANT]
> Use a **dedicated virtual environment** for SimReady validation. The `simready-validate` tool and its dependencies (`omniverse-asset-validator`, `usd-core`) can conflict with other packages. A clean venv avoids hard-to-debug import errors.

<details open>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
python -m venv .venv
.venv\Scripts\activate
```
</details>

<details>
<summary><strong>Linux</strong></summary>

```bash
python -m venv .venv
source .venv/bin/activate
```
</details>

### 6. Install dependencies

Choose the requirements file that matches your workflow:

| Workflow | Requirements file | What gets installed |
|----------|-------------------|---------------------|
| **Validation only** | `requirements.txt` | `simready-validate`, `omniverse-asset-validator`, `usd-core`, `omniverse-usd-profiles` |
| **Packaging** | `nv_core/package_sample/requirements.txt` | Everything above, plus `simready-package`. `omni-wrapp-minimal` must be installed separately — see the [Packaging Workflow guide](nv_core/sr_specs/docs/guides/packaging_workflow.md). |

```bash
# Validation only
pip install -r requirements.txt

# Packaging (includes validation)
pip install -r nv_core/package_sample/requirements.txt
```

> [!NOTE]
> Both CLIs need profile definitions at runtime. Pass
> `--project-config sample_content/project_config.toml` on every invocation
> outside a Kit environment. See the guides below for the exact commands.

You're now ready to go. See [Next steps](#next-steps) for guides on validation, packaging, profiles, and more.

## About SimReady Foundation

SimReady Foundation defines guidelines and requirements for **OpenUSD content** so that assets work reliably across rendering, simulation, robotics, and AI training workflows within NVIDIA Omniverse.

The framework is built around a layered hierarchy:

| Layer | Purpose | Example |
|-------|---------|---------|
| **Requirement** | A single, testable rule an asset must satisfy | *"The stage must define a default prim"* (SAMP.001) |
| **Capability** | A category that groups related requirements | *Sample* (`SAMP`), *Visualization/Geometry* (`VG`), *Units* (`UN`) |
| **Feature** | A set of requirements that together describe a queryable property of an asset | *Minimal Placeable Visual*, *RBD Physics*, *Driven Joints* |
| **Profile** | A bundle of features that defines what an asset must satisfy for a given use case | *Prop-Robotics-Neutral*, *Robot-Body-Isaac* |

### Profiles

Profiles are the top-level contracts between asset creators and consumers. Each profile targets a specific simulation scenario and lists the features (and their versions) that an asset must pass. Production profiles in `nv_core/sr_specs/` include:

| Profile | Description |
|---------|-------------|
| **Prop-Robotics-Neutral** | Neutral-format props suitable for robotics pipelines |
| **Prop-Robotics-Physx** | Props with PhysX rigid-body physics |
| **Robot-Body-Neutral** | Neutral robot body with physics |
| **Robot-Body-Runnable** | PhysX robot body, runnable in simulation |

### Use cases

- **Static validation** — check USD assets against a profile's requirements using the `simready-validate` CLI or the `simready.validate` Python API.
- **Asset transformation** — convert assets between profiles (e.g. Neutral to PhysX to Isaac).
- **CI / CD** — automate validation in Jenkins or local runners.

### Where the specs live

The full SimReady specifications—capabilities, features, profiles, and guides—are in `nv_core/sr_specs/docs/`.

## Next steps

Once you have the environment set up, explore the guides in [`nv_core/sr_specs/docs/guides/`](nv_core/sr_specs/docs/guides/guides.md):

| Guide | Description |
|-------|-------------|
| [SimReady Validation Workflow](nv_core/sr_specs/docs/guides/validate_workflow.md) | Run your first validation — commands, expected output, stamping, and troubleshooting |
| [SimReady Packaging Workflow](nv_core/sr_specs/docs/guides/packaging_workflow.md) | Package a SimReady asset — pre-validate, local mode, full WRAPP build, and troubleshooting |
| [SimReady Benchmark](nv_core/sr_specs/docs/guides/benchmark/benchmark.md) | Run benchmarks with `simready-benchmark`, covering install, the pipeline stages, and reading reports |
| [Getting Started](nv_core/sr_specs/docs/guides/getting_started.md) | Orientation — who SimReady is for, choosing a profile, and where to go next |
| [SimReady Acceptance Workflow](nv_core/sr_specs/docs/guides/acceptance_workflow.md) | How new requirements, features, and profiles move through review |
| [Features Expansion Workflow](nv_core/sr_specs/docs/guides/features_expansion_workflow.md) | Create technology-specific feature variants (e.g. neutral to PhysX) |
| [Profiles Validation Workflow](nv_core/sr_specs/docs/guides/profiles_validation_workflow.md) | Create, version, and validate assets against profiles |
| [Naming Conventions](nv_core/sr_specs/docs/guides/naming_conventions.md) | Asset and prim naming standards |

### Agent skills

Repo-local agent skills live under `skills/<skill-name>/SKILL.md` at the
repository root. The `.agents/skills`, `.codex/skills`, and `.claude/skills`
compatibility links point back to `../skills`, so update the `skills/` source of
truth first.

Use the skills as the first stop when an agent is asked to add, update,
validate, package, or conform SimReady content. The guides in
`nv_core/sr_specs/docs/guides/` remain the source of conceptual workflow detail;
the skills turn that guidance into repeatable agent procedures.

Skill categories:

- `simready-foundation-add-*`: Add new Foundation surfaces such as capabilities, requirements, validators, features, profiles, feature adapters, and runtime tests.
- `simready-foundation-update-*`: Update existing Foundation surfaces while preserving versioning, profile compatibility, and published behavior.
- `simready-foundation-conform-fet-*`: Repair or assess USD assets for a specific feature gate, such as FET000 core, FET003 rigid-body physics, FET004 multibody physics, or FET006 materials.
- `simready-foundation-create-package`: Create SimReady packages with the bundled package-sample workflow, including WRAPP setup, root USD inputs, validation phases, and no-WRAPP fallback modes.
- `simready-foundation-validate-foundation-change`: Audit a Foundation change for consistency across requirement docs, validators, feature manifests, profile TOML, profile markdown, indexes, and related skills.

How skills relate to the spec:

- Capabilities and requirements live under `nv_core/sr_specs/docs/capabilities/`.
- Features live under `nv_core/sr_specs/docs/features/` and bundle exact requirement IDs and dependencies.
- Profiles live under `nv_core/sr_specs/docs/profiles/` and pin exact feature versions.
- Add/update skills help maintain those spec files.
- Conform skills help staged USD assets pass, skip, or block on feature-specific validation gates.

When adding or changing a feature, also update the matching conform skill when
the feature can produce asset-level validation failures. If a feature cannot be
safely repaired by an agent, document that limitation in the feature workflow
and validation summary.

Bundled helper resources live under each skill's `assets/` directory. Current
skills use `assets/openai.yaml` for optional UI metadata and `assets/scripts/`
for deterministic helper scripts. The package workflow skill bundles
`assets/scripts/create_simready_package.py`, `setup_venv.sh`, dependency
requirements, and the `sr_pkg_sample/` helper package.

Usage notes:

- Read `AGENTS.md` and the relevant guide files before making SimReady spec changes.
- Keep conform skills general. They should describe feature requirements and repair policy, not one-off behavior for a specific asset.
- For optional or conditional profile features, conform skills should read the profile documentation before attempting repairs and should report `skipped/not applicable` when the profile allows it.
- If full Omniverse/OAV validation is unavailable, run the narrower checks that are available and state the remaining validation gap.
