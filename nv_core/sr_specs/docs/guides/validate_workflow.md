# SimReady Validation Workflow

This guide walks through validating OpenUSD assets against a SimReady profile
using the `simready-validate` CLI. It covers setting up your environment,
running validation against a real asset, saving results to JSON, and stamping
validation metadata into the asset.

All commands run from the **repository root**.

## Prerequisites

| Requirement | Minimum |
|-------------|---------|
| Python | 3.12 |
| Git LFS | Installed and initialised (`git lfs install`) |

## 1. Create a clean virtual environment

`simready-validate` depends on `usd-validation-nvidia` and `usd-core`.
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

The `simready-validate` package is hosted on the internal NVIDIA Artifactory
registry:

```bash
pip install -r requirements.txt
```

This installs:
- **`simready-validate`** — the CLI and `simready.validate` Python API
  (pulls in `usd-validation-nvidia`, `usd-profiles-nvidia`, and `usd-core` as
  transitive dependencies).
- **`physx-usd-schemas`**, **`MaterialX`**, **`pillow`**, and **`numpy`** —
  needed by the tier validators when you run them from this source tree.

Verify the install succeeded:

```bash
simready-validate --help
```

## 3. Run validation on a sample asset

````{note}
**End users** normally install the published [tier](tiers.md) wheel
(`simready-foundation-tier-core`) alongside `simready-validate`. The CLI then
auto-discovers rules, capabilities, features, and profiles from that package,
so you omit `--rules-path`, `--features-path`, and `--profiles-path`:

Base tier core supports Python 3.11–3.13. Install it with
`pip install simready-foundation-tier-core`. For optional Isaac transformation
and schema tooling, use Python 3.12 and install
`pip install "simready-foundation-tier-core[isaac]"`.

```bash
simready-validate --profile Robotics-Prop --version 4.0.0 path/to/asset.usd
```

See [SimReady Foundation PyPI Packages](foundation_pypi.md) for install and
discovery details. The commands below are the **in-repo** alternative: they point
`simready-validate` at the tier source trees in this clone so you can exercise
unpublished local changes without building and installing wheels.
````

Use the `simready-validate` CLI to validate the included apple asset against
the `Robotics-Prop` profile. Spec content for that profile lives in the
core tier under
`nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/`.

```{note}
The commands below pass explicit `--rules-path`, `--features-path`, and `--profiles-path` flags pointing at the core tier. This is sufficient for prop profiles. For profiles owned by another tier, such as `Sensor-IMU` in the sensors tier, also pass that tier's `rules_and_reqs` directory with `--rules-path` and its `features` directory (plus its `capabilities` directory, if it has one) with `--features-path`. Alternatively, install the tiers with `pip install` and omit all three path flags — `simready-validate` will discover the installed tiers automatically via entry points.
```

````{tab-set}
```{tab-item} Windows (PowerShell)
simready-validate --rules-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs --features-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities --features-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features --profiles-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles --profile Robotics-Prop --version 4.0.0 sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd
```

```{tab-item} Linux
simready-validate --rules-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs --features-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities --features-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features --profiles-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles --profile Robotics-Prop --version 4.0.0 sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd
```
````

What each flag does:

| Flag | Value | Purpose |
|------|-------|---------|
| `--rules-path` | `nv_core/tiers/.../tier_core/rules_and_reqs` | Directory containing the rule checkers (`validation.py`) and requirement definitions |
| `--features-path` | `nv_core/tiers/.../tier_core/capabilities` and `nv_core/tiers/.../tier_core/features` | Directories of contract JSON: `CAP`-prefixed capabilities and runtime-tested `FET` features. Repeat the flag for each directory; a profile only resolves if every contract it selects is loaded |
| `--profiles-path` | `nv_core/tiers/.../tier_core/profiles` | Directory of profile TOMLs, each a list of feature and capability selectors |
| `--profile` | `Robotics-Prop` | Name of the profile to validate against |
| `--version` | `4.0.0` | Version of the profile |

You should see output like:

```text
Asset: sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd
  [PASSED] Robotics-Prop v4.0.0
           CAP004_Multibody.MuJoCo.0-1-0: optional feature, unmet requirements: ['com.nvidia.simready.RB.MB.001']
           FET004_Multibody.0-2-0: optional feature, unmet requirements: ['com.nvidia.simready.RB.MB.001']
           FET004_Multibody.PhysX.0-4-0: optional feature, unmet requirements: ['com.nvidia.simready.RB.MB.001']
```

Every required capability and feature passes. The three listed contracts are
multibody checks that `Robotics-Prop` selects as optional; the apple is a
single rigid body, so `RB.MB.001` is unmet, but optional failures are reported
without failing the profile.

## 4. Save results to JSON

For repeatable `RV.010` / `RV.011` report-attribution regression coverage, run
the [Runtime attribution QA plan](runtime_attribution_qa.md). It uses the
published `Robotics-Prop@5.0.0` profile and checks failing requirement IDs in
the CLI's JSON output.

Add `--output` to write a machine-readable report:

```bash
simready-validate --rules-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs --features-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities --features-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features --profiles-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles --profile Robotics-Prop --version 4.0.0 --output results.json sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd
```

Open `results.json` to see the pass/fail outcome of every resolved capability
and feature, keyed by its full dotted ID.

## 5. Stamp validation results into the asset

The `--stamp-asset-validation` flag records the validation outcome in a
`.simready/validation.json` receipt next to the asset and, for writable
`.usd`, `.usda`, and `.usdc` files, in the root layer's `customLayerData`.
A `.usdz` archive is never modified.

```bash
simready-validate --rules-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs --features-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities --features-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features --profiles-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles --profile Robotics-Prop --version 4.0.0 --stamp-asset-validation sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd
```

After stamping, the USD file contains metadata like (one entry per resolved
capability and feature; one shown):

```
customLayerData = {
    "SimReady_Metadata" = {
        "validation" = {
            "profile" = "Robotics-Prop"
            "profile_version" = "4.0.0"
            "validated_features" = {
                "<YYYY-MM-DD>" = {
                    "CAP000_Core.0-2-0" = {
                        "blocking_failure" = false
                        "dependencies" = "[]"
                        "passed" = true
                        "version" = "0-2-0"
                    }
                }
            }
        }
    }
}
```

The `<YYYY-MM-DD>` key (e.g. `2026-05-12`) records when the stamp was written.
Running the command again on a later date appends a new entry, preserving the
full validation history. The stamp records which profile target was checked;
it does not declare the asset's profile. Downstream tools — renderers,
simulation pipelines, asset browsers — can read this metadata without
re-running validation.

## 6. Understanding the validator (sample project)

To understand how rules, capabilities, and profiles fit together, explore the
minimal sample project in `nv_core/validator_sample/`. It contains a single
requirement, capability, and profile you can read end-to-end:

```text
validator_sample/
├── sample_assets/
│   ├── sample1.usda          # passes SAMP.001 (defaultPrim = "Foo")
│   └── sample_fail.usda      # fails  SAMP.001 (defaultPrim = "NotFoo")
├── sample_capabilities/
│   └── CAP900_ProperlyNamed.1-0-0.json
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
| **`sample_requirements/`** | Defines the `SAMP` requirement category, requirement `SAMP.001`, and the rule checker class that inspects the USD stage. |
| **`sample_capabilities/`** | Declares capability `CAP900_ProperlyNamed.1-0-0`, which requires `SAMP.001`. |
| **`sample_profiles/profiles.toml`** | Defines `Sample-Profile` version `1.0.0`, which selects that capability. |
| **`sample_assets/sample1.usda`** | A valid USDA — its default prim is `"Foo"`, satisfying the rule. |
| **`sample_assets/sample_fail.usda`** | An invalid USDA — its default prim is `"NotFoo"`, causing the rule to fail. |

You can run the sample project from `nv_core/validator_sample/` to see a
controlled pass/fail cycle:

```bash
cd nv_core/validator_sample

# Passing — sample1.usda has defaultPrim = "Foo"
simready-validate --rules-path sample_requirements --features-path sample_capabilities --profiles-path sample_profiles/profiles.toml --profile Sample-Profile --version 1.0.0 sample_assets/sample1.usda

# Failing — sample_fail.usda has defaultPrim = "NotFoo"
simready-validate --rules-path sample_requirements --features-path sample_capabilities --profiles-path sample_profiles/profiles.toml --profile Sample-Profile --version 1.0.0 sample_assets/sample_fail.usda
```

The failing run reports
`CAP900_ProperlyNamed.1-0-0: failing requirements: ['com.nvidia.simready.SAMP.001']`
and exits with a non-zero code. Add `-v` to also print each issue's message,
here `Root prim must be named 'Foo'.` See the
[SimReady Learning Workflow](SimReady_learning_workflow.md) for a deeper dive
into writing your own requirements, rules, and capabilities.

## Troubleshooting

### `simready-validate` command not found

The CLI entry point is installed by the `simready-validate` pip package. If the
command is missing:

- Make sure the venv is activated.
- Run `pip install -r requirements.txt` from the repository root again.

### NP.003 reports a storage parent directory

The release 2026.10 directory checker inspects every directory component above
the root USD file, excluding the filesystem root or drive anchor. A storage
parent such as `Parent With Space` or `parent(copy)` therefore fails NP.003,
even when the asset package itself uses compliant directory names. NP.003's
asset-directory contract remains defined by
[Directory structure](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/naming_paths/requirements/directory-structure.md).

For this release, copy the complete asset package, including its dependencies,
to a path whose ancestor directories use compliant names, for example
`C:/simready_qa/asset_name/` or `/tmp/simready_qa/asset_name/`. Quote the USD path
when invoking the CLI and rerun the same profile and version on that copy.
Quoting handles shell parsing; the ancestor directory names still need to pass
the checker. Use the compliant copy for `simready-manage submit` as well.

Keep the source package intact. Correctly accepting arbitrary storage parent
names requires a directory-checker fix; moving the copy is a workaround for
the release validator.

### Git LFS pointer files

If USD files are tiny text files starting with
`version https://git-lfs.github.com/spec/v1`, LFS pointers were not resolved:

```bash
git lfs install
git lfs pull
```
