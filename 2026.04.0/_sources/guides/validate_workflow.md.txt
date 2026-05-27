# SimReady Validation Workflow

This guide walks through validating OpenUSD assets against a SimReady profile
using the `simready-validate` CLI. It covers setting up your environment,
running validation against a real asset, saving results to JSON, and stamping
validation metadata into the asset.

All commands run from the **repository root**.

## Prerequisites

| Requirement | Minimum |
|-------------|---------|
| Python | 3.12+ |
| Git LFS | Installed and initialised (`git lfs install`) |

## 1. Create a clean virtual environment

`simready-validate` depends on `omniverse-asset-validator` and `usd-core`.
These packages can conflict with other USD or Omniverse installations, so
always work inside a dedicated venv.

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

```bash
pip install -r nv_core/validator_sample/requirements.txt
```

This installs:
- **`simready-validate`** — the CLI and `simready.validate` Python API
  (pulls in `omniverse-asset-validator` and `usd-core` as transitive
  dependencies).
- **`omniverse-usd-profiles`** — profile definitions the validator uses to
  resolve feature and requirement references.

Verify the install succeeded:

```bash
simready-validate --help
```

## 3. Run validation on a sample asset

Use the `simready-validate` CLI to validate the included apple asset against
the `Prop-Robotics-Neutral` profile:

````{tab-set}
```{tab-item} Windows (PowerShell)
simready-validate --rules-path nv_core/sr_specs/docs/capabilities --features-path nv_core/sr_specs/docs/features --profiles-path nv_core/sr_specs/docs/profiles/profiles.toml --profile Prop-Robotics-Neutral --version 1.0.0 sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd
```

```{tab-item} Linux
simready-validate --rules-path nv_core/sr_specs/docs/capabilities --features-path nv_core/sr_specs/docs/features --profiles-path nv_core/sr_specs/docs/profiles/profiles.toml --profile Prop-Robotics-Neutral --version 1.0.0 sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd
```
````

What each flag does:

| Flag | Value | Purpose |
|------|-------|---------|
| `--rules-path` | `nv_core/sr_specs/docs/capabilities` | Directory containing the rule checkers (validation.py) and requirement definitions |
| `--features-path` | `nv_core/sr_specs/docs/features` | Directory containing feature definitions (JSON) that group requirements into named features |
| `--profiles-path` | `nv_core/sr_specs/docs/profiles/profiles.toml` | TOML file that assembles features into named profiles |
| `--profile` | `Prop-Robotics-Neutral` | Name of the profile to validate against |
| `--version` | `1.0.0` | Version of the profile |

You should see output like:

```text
Asset: sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd
  [FAILED] Prop-Robotics-Neutral v1.0.0
           FET006_BASE_MDL: failing requirements: ['VM.TEX.002']
           FET004_BASE_NEUTRAL: failing requirements: ['RB.MB.001']
```

The core features — hierarchy, units, rigid-body physics, and grasp physics —
all pass. The two failures (`VM.TEX.002` material texture colorspace and
`RB.MB.001` multi-body) are known gaps in the sample asset and do not affect
the primary validation workflow.

```{note}
The production validators in `nv_core/sr_specs` require additional dependencies
beyond what `requirements.txt` provides. If you hit import errors, see
[Troubleshooting](#troubleshooting) below.
```

## 4. Save results to JSON

Add `--output` to write a machine-readable report:

```bash
simready-validate --rules-path nv_core/sr_specs/docs/capabilities --features-path nv_core/sr_specs/docs/features --profiles-path nv_core/sr_specs/docs/profiles/profiles.toml --profile Prop-Robotics-Neutral --version 1.0.0 --output results.json sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd
```

Open `results.json` to see per-requirement pass/fail details, messages, and
the prim paths that triggered each finding.

## 5. Stamp validation results into the asset

The `--stamp-asset-validation` flag writes the validation outcome directly into
the USD file's `customLayerData`:

```bash
simready-validate --rules-path nv_core/sr_specs/docs/capabilities --features-path nv_core/sr_specs/docs/features --profiles-path nv_core/sr_specs/docs/profiles/profiles.toml --profile Prop-Robotics-Neutral --version 1.0.0 --stamp-asset-validation sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd
```

After stamping, the USD file contains metadata like:

```
customLayerData = {
    "SimReady_Metadata" = {
        "validation" = {
            "profile" = "Prop-Robotics-Neutral"
            "validated_features" = {
                "<YYYY-MM-DD>" = {
                    "FET001_BASE_NEUTRAL" = {
                        "version" = "0.1.0"
                        "dependencies" = "[]"
                        "passed" = true
                    }
                }
            }
        }
    }
}
```

The `<YYYY-MM-DD>` key (e.g. `2026-05-12`) records when the stamp was written.
Running the command again on a later date appends a new entry, preserving the
full validation history. Downstream tools — renderers, simulation pipelines,
asset browsers — can read this metadata without re-running validation.

## 6. Understanding the validator (sample project)

To understand how rules, features, and profiles fit together, explore the
minimal sample project in `nv_core/validator_sample/`. It contains a single
requirement, feature, and profile you can read end-to-end:

```text
validator_sample/
├── requirements.txt
├── sample_assets/
│   ├── sample1.usda          # passes SAMP.001 (defaultPrim = "Foo")
│   └── sample_fail.usda      # fails  SAMP.001 (defaultPrim = "NotFoo")
├── sample_features/
│   └── feat_1_properly_named.json
├── sample_profiles/
│   └── profiles.toml
└── sample_requirements/
    ├── __init__.py
    ├── capability-sample.md
    ├── requirement-name.md
    └── rule_name_checker.py
```

| Component | Role |
|-----------|------|
| **`sample_requirements/`** | Defines capability `SAMP`, requirement `SAMP.001`, and the rule checker class that inspects the USD stage. |
| **`sample_features/`** | Declares feature `Feat_1` ("ProperlyNamed"), which requires `SAMP.001`. |
| **`sample_profiles/profiles.toml`** | Defines `Sample-Profile` version `1.0.0`, which requires `Feat_1`. |
| **`sample_assets/sample1.usda`** | A valid USDA — its default prim is `"Foo"`, satisfying the rule. |
| **`sample_assets/sample_fail.usda`** | An invalid USDA — its default prim is `"NotFoo"`, causing the rule to fail. |

You can run the sample project from `nv_core/validator_sample/` to see a
controlled pass/fail cycle:

```bash
cd nv_core/validator_sample

# Passing — sample1.usda has defaultPrim = "Foo"
simready-validate --rules-path sample_requirements --features-path sample_features --profiles-path sample_profiles/profiles.toml --profile Sample-Profile --version 1.0.0 sample_assets/sample1.usda

# Failing — sample_fail.usda has defaultPrim = "NotFoo"
simready-validate --rules-path sample_requirements --features-path sample_features --profiles-path sample_profiles/profiles.toml --profile Sample-Profile --version 1.0.0 sample_assets/sample_fail.usda
```

The failing run reports `Root prim must be named 'Foo'.` and exits with a
non-zero code. See the
[SimReady Learning Workflow](SimReady_learning_workflow.md) for a deeper dive
into writing your own requirements, rules, and features.

## Troubleshooting

### `simready-validate` command not found

The CLI entry point is installed by the `simready-validate` pip package. If the
command is missing:

- Make sure the venv is activated.
- Run `pip install -r nv_core/validator_sample/requirements.txt` again.
- On Windows, try `python -m simready.validate` as a fallback.

### Git LFS pointer files

If USD files are tiny text files starting with
`version https://git-lfs.github.com/spec/v1`, LFS pointers were not resolved:

```bash
git lfs install
git lfs pull
```
