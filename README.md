# SimReady Foundation

**This repository is the SimReady specification and validation layer**: the capabilities, features, profiles, and validators that define what a conformant OpenUSD asset must contain and how to verify it, across one or more domains (props, robots, AI Factory data center equipment, and more). Asset *authoring*; turning CAD or other source data into SimReady USD, happens in domain-specific **companion pipeline repositories**. See [Authoring pipelines](#authoring-pipelines-companion-repositories) for how the two relate.

## Getting the repository

This repository uses **Git LFS** to track binary and USD asset files (`.usda`, `.usdc`, `.usd`, `.usdz`, images, and others). You must have Git LFS installed before cloning, otherwise those files will check out as tiny pointer files instead of the real content.

### 1. Install Git LFS (once per machine)

```bash
# macOS (Homebrew)
brew install git-lfs

# Ubuntu / Debian
sudo apt-get install git-lfs

# Windows (winget)
winget install GitHub.GitLFS
```

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

The product requires **Python >=3.10,<3.13** (Python 3.12 recommended).

- **Windows:** Download from [Python Release Python 3.12.0](https://www.python.org/downloads/release/python-3120/) and run the installer. Check **"Add Python to PATH"** during installation. If you already have multiple Python versions, you can use the `py -3.12` launcher.
- **Ubuntu / Debian:** `sudo apt-get install python3.12`

Verify the installation:

```bash
python --version
```

### 5. Create a virtual environment

> [!IMPORTANT]
> Use a **dedicated virtual environment** for SimReady validation. The `simready-validate` tool and its dependencies (`omniverse-asset-validator`, `usd-core`) can conflict with other packages. A clean venv avoids hard-to-debug import errors.

Run this from the repository root, the `simready-foundation` directory you cloned into in step 2. The `.venv` is created there, and the install command in the next step uses paths relative to that same location.

- **Windows (PowerShell):**

  ```powershell
  python -m venv .venv
  .venv\Scripts\activate
  ```

- **Linux:**

  ```bash
  python -m venv .venv
  source .venv/bin/activate
  ```

### 6. Install dependencies

From the repository root, install the SimReady validation library:

```bash
pip install -r nv_core/validator_sample/requirements.txt
pip install "numpy>=1.24,<3"
```

This installs `simready-validate` (which pulls in `omniverse-asset-validator` and `usd-core`) and `omniverse-usd-profiles`. The second line installs `numpy`, which `simready-validate` requires at runtime but does not install automatically; without it, validation fails.

### 7. Running validation on the sample asset

With the dependencies installed, use the `simready-validate` CLI to validate the included sample asset against the sample profile.

From the `nv_core/validator_sample/` directory:

```bash
simready-validate \
  --rules-path sample_requirements \
  --features-path sample_features \
  --profiles-path sample_profiles/profiles.toml \
  --profile Sample-Profile --version 1.0.0 \
  sample_assets/sample1.usda
```

What each flag does:


| Flag              | Value                           | Purpose                                                                                     |
| ----------------- | ------------------------------- | ------------------------------------------------------------------------------------------- |
| `--rules-path`    | `sample_requirements/`          | Directory containing the rule checker (`rule_name_checker.py`) and requirement definitions  |
| `--features-path` | `sample_features/`              | Directory containing feature definitions (JSON) that group requirements into named features |
| `--profiles-path` | `sample_profiles/profiles.toml` | TOML file that assembles features into a named profile                                      |
| `--profile`       | `Sample-Profile`                | Name of the profile to validate against                                                     |
| `--version`       | `1.0.0`                         | Version of the profile                                                                      |


`sample1.usda` has `defaultPrim = "Foo"` and satisfies the single requirement in `Sample-Profile` (the root prim must be named `"Foo"`), so validation should **pass**.

To see it fail, try validating a non-existent or non-conforming asset:

```bash
# Pass a path with a different default prim name to force a failure
simready-validate \
  --rules-path sample_requirements \
  --features-path sample_features \
  --profiles-path sample_profiles/profiles.toml \
  --profile Sample-Profile --version 1.0.0 \
  --output results.json \
  sample_assets/sample1.usda
```

The `--output` flag writes results to a JSON file for programmatic inspection.

### 8. Stamping validation results into the asset

Passing `--stamp-asset-validation` writes the validation outcome directly into the USD asset's metadata:

```bash
simready-validate \
  --rules-path sample_requirements \
  --features-path sample_features \
  --profiles-path sample_profiles/profiles.toml \
  --profile Sample-Profile --version 1.0.0 \
  --stamp-asset-validation \
  sample_assets/sample1.usda
```

On success this modifies `sample1.usda` in-place, adding an entry to its `customLayerData` under the key `SimReady_Metadata`:

```
customLayerData = {
    "SimReady_Metadata": {
        "validation": {
            "profile": "Sample-Profile",
            "validated_features": {
                "2026-04-29": {
                    "Feat_1": {
                        "version": "1.0.0",
                        "dependencies": "[]",
                        "passed": true
                    }
                }
            }
        }
    }
}
```

This stamp acts as a portable, self-describing record of when the asset was last validated, against which profile, and which features passed. Downstream tools (renderers, simulation pipelines, asset browsers) can read it without re-running validation. The date key under `validated_features` is the date the stamp was written; multiple runs accumulate entries so the history is preserved.

The sample above is a minimal demo. For data center asset validation (e.g. CDUs, CRAHs, UPS, etc.) using the `AIF-Entity` profile, see [Validating an AIF Asset](nv_core/sr_specs/docs/guides/aif_validation.md) for how this asset-class-driven validation path functions.

## About SimReady Foundation

SimReady Foundation defines guidelines and requirements for **OpenUSD content** so that assets work reliably across rendering, simulation, robotics, AI training, and data center digital twin workflows within NVIDIA Omniverse.

The framework is built around a layered hierarchy:


| Layer           | Purpose                                                                           | Example                                                                        |
| --------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| **Requirement** | A single, testable rule an asset must satisfy                                     | *"The stage must define a default prim"* (SAMP.001)                            |
| **Capability**  | A category that groups related requirements                                       | *Sample* (`SAMP`), *Visualization/Geometry* (`VG`), *Units* (`UN`)             |
| **Feature**     | A set of requirements that together describe a queryable property of an asset     | *Minimal Placeable Visual*, *RBD Physics*, *AIF Metadata*, *Connection Points* |
| **Profile**     | A bundle of features that defines what an asset must satisfy for a given use case | *Prop-Robotics-Neutral*, *Robot-Body-Isaac*, *AIF-Entity*                      |


> [!IMPORTANT]
> The current validators provided in `nv_core/sr_specs` will not function as they require many more dependencies than this repo provides by itself. Those dependencies will be made available / removed in future releases.

### Authoring pipelines (companion repositories)

SimReady Foundation defines and validates conformance; it does not author assets. Each domain has (or will have) a **companion pipeline repository** that produces SimReady USD from source data, which you then validate here against the matching profile. The relationship is the same for every domain:

```
Author in a companion pipeline  -->  Validate here against a profile  -->  (optional) reference docs
```

| Domain | Author with | Validate against (this repo) |
|--------|-------------|------------------------------|
| Robotics (robots, props) | URDF/MJCF importers and DCC exporters (see [Getting Started](nv_core/sr_specs/docs/guides/getting_started.md)) | `Prop-Robotics-*`, `Robot-Body-*` profiles |
| AI Factory data center (CDU, CRAH, UPS, Rack) | [aif-pipeline-samples](https://nvidia-omniverse.github.io/aif-pipeline-samples/): CAD-to-USD ingestion, optimization, metadata | `AIF-Entity` profile (see [Validating an AIF Asset](nv_core/sr_specs/docs/guides/aif_validation.md)) |

A companion pipeline and its target profile are paired: the pipeline produces assets, this repo defines and verifies what makes them conformant, and the pipeline should pin the profile version it targets so the two stay in sync. You generally need both: authoring without validation yields an asset that may not conform; validation without authoring yields rules with nothing to run against. This table is the template for onboarding any new domain: add a row pointing at its pipeline and its profile.

### Profiles

Profiles are the top-level contracts between asset creators and consumers. Each profile targets a specific simulation scenario and lists the features (and their versions) that an asset must pass. Production profiles in `nv_core/sr_specs/` include:


| Profile                   | Description                                                                                                                                                                                                                                                                                    |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Prop-Robotics-Neutral** | Neutral-format props suitable for robotics pipelines                                                                                                                                                                                                                                           |
| **Prop-Robotics-Physx**   | Props with PhysX rigid-body physics                                                                                                                                                                                                                                                            |
| **Robot-Body-Neutral**    | Neutral robot body with physics                                                                                                                                                                                                                                                                |
| **Robot-Body-Runnable**   | PhysX robot body, runnable in simulation                                                                                                                                                                                                                                                       |
| **AIF-Entity**            | All AI Factory data center equipment (CDU, CRAH, UPS, Compute Rack). A single profile; equipment-class differentiation is driven by the `aif:core:assetClass` property and data-driven validation. See the [AIF-Entity profile authoring guide](nv_core/sr_specs/docs/profiles/aif-entity.md). |


> **Getting started with AIF assets?** See the [AIF Pipeline Samples documentation](https://nvidia-omniverse.github.io/aif-pipeline-samples/) for a guided walkthrough from CAD ingestion to validated SimReady USD. Source code and sample assets are in the [aif-pipeline-samples](https://github.com/NVIDIA-Omniverse/aif-pipeline-samples) repository.

### Use cases

- **Static validation**: check USD assets against a profile's requirements using the `simready-validate` CLI or the `simready.validate` Python API.
- **Asset transformation**: convert assets between profiles (e.g. Neutral to PhysX to Isaac).
- **CI / CD**: automate validation in Jenkins or local runners.

### Where the specs live

The full SimReady specifications (capabilities, features, profiles, and guides) are in `nv_core/sr_specs/docs/`.
