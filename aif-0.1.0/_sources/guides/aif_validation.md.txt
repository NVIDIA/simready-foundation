# Validating an AIF Asset

This guide shows how to validate an NVIDIA AI Factory (AIF) data center asset (CDU, CRAH, UPS, or Compute Rack) against the `AIF-Entity` profile.

> If you only want to confirm your setup works, the minimal `Foo` sample in the top-level README is the quickest check. **This page is the AIF path**: use it once you have a real data center asset to validate.

## Prerequisites

- Python 3.10 to 3.12 (3.12 recommended).
- The `simready-validate` toolchain installed in an active virtual environment. **If you already completed Environment setup in the top-level README, you have this; just activate that virtual environment and continue.** If not, create and activate a virtual environment (see the README) and, from the repository root, run:

  ```bash
  pip install -r nv_core/validator_sample/requirements.txt
  ```

  This pulls `simready-validate`, `omniverse-usd-profiles` (which ships the `omni.capabilities` module the AIF validators import), and `omniverse-asset-validator`. No local build/codegen step is required to run validation.

- An AIF asset to validate. See the [AIF-Entity authoring guide](../profiles/aif-entity.md) for the required stage composition and the per-equipment-class attribute sets.

## The asset class drives validation

A single `AIF-Entity` profile covers all four equipment classes. The `aif:core:assetClass` property on the asset selects which expectations apply:

| `aif:core:assetClass` | Thermal | Electrical |
|---|---|---|
| `CDU` | Yes | Yes |
| `CRAH` | Yes | Yes |
| `UPS` | No | Yes |
| `Rack` | No | No |

You do not pick a different profile per class; you set `aif:core:assetClass` on the asset and validate against `AIF-Entity`.

## Running validation

From the repository root:

```bash
simready-validate \
  --rules-path    nv_core/sr_specs/docs/capabilities \
  --features-path nv_core/sr_specs/docs/features \
  --profiles-path nv_core/sr_specs/docs/profiles/profiles.toml \
  --profile AIF-Entity --version 0.1.0 \
  -v path/to/your_asset.usd
```

The `aif:core:assetClass` property on the asset selects which expectations apply (`CDU`, `CRAH`, `UPS`, or `Rack`), so the same `AIF-Entity` invocation works for every class. Write results to a file for programmatic inspection with `--output results.json`.

> **The asset path can point anywhere on disk.** It does not need to live inside this repository. Pass an absolute or relative path to any `.usd`/`.usda` and the validator will resolve and check it. Note that the asset must be self-contained: any references it makes to external files (textures, sublayers, payloads) must resolve, or those references will be reported as failures.

### Stamping the result into the asset

Add `--stamp-asset-validation` to record the outcome in the asset's `customLayerData` under `SimReady_Metadata` (see the README for the stamp schema). This gives downstream tools a portable record of what passed, against which profile, and when.

## Expected results per class

> All four pass the `AIF-Entity` checks with zero failing requirements.

| `assetClass` | Expected | Notes |
|---|---|---|
| `CDU`  | Pass | `Generic_CDU` fixture |
| `CRAH` | Pass | `CW375` fixture |
| `UPS`  | Pass | `EXLS1` fixture |
| `Rack` | Pass | `gb300` fixture. Large geometry; full validation run takes ~20 min |

## Where this fits

This repository is the **spec and validation rules**. To author an AIF asset from CAD (ingestion, optimization, metadata), use the [AIF Pipeline Samples](https://nvidia-omniverse.github.io/aif-pipeline-samples/), then validate the output here against `AIF-Entity`.
