# AIF Test Fixtures

This directory contains USD assets used to verify the AIF validator suite (AM, CP, TC, EL). Fixtures fall into two categories:

- **Compliant baselines:** full assets authored to satisfy all applicable AIF validators. Used to verify that validators do not produce false-positive failures on well-formed AIF assets.
- **Non-compliant variants:** assets deliberately broken in a specific way so a specific validator should fail on them. Used to verify that validators correctly detect missing or malformed data.

## Directory layout

```
tests/aif/
|-- README.md                                              (this file)
|-- __init__.py
|-- test_aif.py                                            pytest harness
`-- fixtures/
    |-- Generic_CDU/                                       compliant CDU baseline
    |   `-- asset/
    |       |-- Generic_CDU.usda
    |       |-- Generic_CDU.json                           NP.006 sidecar metadata
    |       |-- layers/
    |       |   |-- Generic_CDU_ConnectionPoints.usd
    |       |   `-- Generic_CDU_Properties.usda
    |       |-- payloads/
    |       |   |-- external.usd
    |       |   `-- internal.usd
    |       |-- materials/
    |       |   |-- Aluminum_Cast.mdl
    |       |   `-- Aluminum_Cast/                         MDL texture set
    |       `-- textures/                                  UsdPreviewSurface textures
    |-- gb300/                                             compliant GB300 baseline
    |   `-- asset/
    |       |-- gb300.usda
    |       |-- gb300.json                                 NP.006 sidecar metadata
    |       |-- layers/
    |       |   |-- GB300_ConnectionPoints.usd
    |       |   `-- GB300_Properties.usda
    |       `-- payloads/
    |           |-- external.usd
    |           `-- internal.usd
    `-- variants/                                          non-compliant test variants
        |-- am_fail_no_properties_sublayer.usda            AM.001
        |-- am_fail_no_assetClass.usda                     AM.002
        |-- am_fail_no_assetClass_Properties.usda
        |-- am_fail_no_manufacturer.usda                   AM.003
        |-- am_fail_no_manufacturer_Properties.usda
        |-- am_fail_no_dimensions.usda                     AM.004
        |-- am_fail_no_dimensions_Properties.usda
        |-- am_fail_no_simready_version.usda               AM.005
        |-- am_fail_no_simready_version_Properties.usda
        |-- am_fail_no_description.usda                    AM.006
        |-- am_fail_no_description_Properties.usda
        |-- am_fail_no_cooling_type.usda                   AM.007
        |-- am_fail_no_cooling_type_Properties.usda
        |-- tc_fail_no_cooling_capacity.usda               TC.001
        |-- tc_fail_no_cooling_capacity_Properties.usda
        |-- tc_fail_no_thermal_cps.usda                    TC.002
        |-- tc_fail_no_thermal_cps_Properties.usda
        |-- el_fail_no_voltage.usda                        EL.001
        |-- el_fail_no_voltage_Properties.usda
        |-- el_fail_no_power_rating.usda                   EL.002
        |-- el_fail_no_power_rating_Properties.usda
        |-- el_fail_no_frequency.usda                      EL.003
        |-- el_fail_no_frequency_Properties.usda
        |-- el_fail_no_electrical_cps.usda                 EL.004
        |-- el_fail_no_electrical_cps_Properties.usda
        |-- cp_pass_complete.usda                          CP.001/004/005 positive
        |-- cp_pass_complete_ConnectionPoints.usd
        |-- cp_fail_bad_names.usda                         CP.004 (invalid naming patterns)
        |-- cp_fail_uppercase_names.usda                   CP.004 (uppercase rejected)
        |-- cp_fail_no_scope.usda                          CP.001 (missing scope)
        |-- cp_fail_no_default_prim.usda                   CP.001 (no defaultPrim)
        |-- cp_fail_empty_scope.usda                       CP.001 (empty scope)
        |-- cp_fail_wrong_type_scope.usda                  CP.001 (Xform not Scope)
        `-- cp_fail_no_sublayer.usda                       CP.005
```

## Compliant baselines

| Asset | Equipment class | Profile target | Validators exercised |
|---|---|---|---|
| `Generic_CDU/asset/Generic_CDU.usda` | CDU | AIF-CDU-Neutral | AM (all 7) + CP (3 active) + TC (both) + EL (all 4) = **16 of 16 active** |
| `gb300/asset/gb300.usda` | Compute Rack (GB300, `assetClass = "Compute Rack"`) | AIF-Rack-Neutral | AM (all 7) + CP (3 active) = **10 of 16 active**. TC and EL do not apply to compute racks (DC power, no cooling subsystem of their own) |

## Non-compliant variants

All non-compliant variants live in `variants/`. Each one targets a specific validator by removing a single required attribute, scope, sublayer, or prim. Two shape families coexist in the folder:

- The AM / TC / EL variants are near-copies of `Generic_CDU.usda` with one attribute or structural element removed. Most pair a main `.usda` with a matching `_Properties.usda` sublayer. `am_fail_no_properties_sublayer.usda` is the exception: a single self-contained file with no sublayer.
- The CP variants are minimal synthetic stubs (a `TestAsset` Xform plus a small `ConnectionPoints` scope) rather than CDU-derived. `cp_pass_complete.usda` lives alongside them as a positive companion (documented in the pass/fail expectation matrix below).

| Variant | Targeted validator | What's broken |
|---|---|---|
| `am_fail_no_properties_sublayer.usda` | AM.001 (properties-sublayer-required) | No `*_Properties.usda` sublayer composed in |
| `am_fail_no_assetClass.usda` | AM.002 (asset-class-required) | `aif:core:assetClass` attribute removed |
| `am_fail_no_manufacturer.usda` | AM.003 (asset-identification-metadata) | `aif:core:manufacturer` attribute removed |
| `am_fail_no_dimensions.usda` | AM.004 (physical-dimensions-metadata) | `aif:core:weight` attribute removed (one of the dimension attrs) |
| `am_fail_no_simready_version.usda` | AM.005 (simready-version-tracking) | `aif:core:simreadyVersion` attribute removed |
| `am_fail_no_description.usda` | AM.006 (asset-description-required) | `aif:core:assetDescription` attribute removed |
| `am_fail_no_cooling_type.usda` | AM.007 (equipment-class-template-compliance) | `aif:spec:coolingType` attribute removed (a CDU template attribute not separately checked by TC or EL) |
| `cp_fail_no_scope.usda` | CP.001 (scope structure) | Default prim has no `ConnectionPoints` Scope child |
| `cp_fail_no_default_prim.usda` | CP.001 (scope structure) | Stage has no `defaultPrim` declared |
| `cp_fail_empty_scope.usda` | CP.001 (scope structure) | `ConnectionPoints` Scope exists but has no children |
| `cp_fail_wrong_type_scope.usda` | CP.001 (scope structure) | `ConnectionPoints` exists as an Xform, not a Scope |
| `cp_fail_bad_names.usda` | CP.004 (naming convention) | Connection point names violate the `<vendor>_<type>_<suffix>` pattern |
| `cp_fail_uppercase_names.usda` | CP.004 (naming convention) | All prim names are uppercase; the convention is lowercase only |
| `cp_fail_no_sublayer.usda` | CP.005 (composition) | No `*_ConnectionPoints.usd` sublayer composed in |
| `tc_fail_no_cooling_capacity.usda` | TC.001 (nominal-cooling-capacity) | `aif:spec:nominalCoolingCapacity` attribute removed |
| `tc_fail_no_thermal_cps.usda` | TC.002 (thermal-cooling-connection-points) | ConnectionPoints scope has no FWS/TCS supply/return CPs |
| `el_fail_no_voltage.usda` | EL.001 (nominal-voltage-required) | `aif:spec:nominalVoltage` attribute removed |
| `el_fail_no_power_rating.usda` | EL.002 (power-rating-required) | `aif:spec:powerRating` attribute removed |
| `el_fail_no_frequency.usda` | EL.003 (electrical-frequency-required) | `aif:spec:frequency` attribute removed |
| `el_fail_no_electrical_cps.usda` | EL.004 (electrical-connection-points) | ConnectionPoints scope has no `electrical_nominal_voltage` CP |

## Pass/fail expectation matrix

For each fixture, the expected outcome of running it through its target profile, per validator.

Legend:
- `✓` validator does not report a failure (either runs and passes, or correctly short-circuits because the asset class isn't gated for that check)
- `✗` validator reports a failure
- `—` validator is not registered under the target profile

Target profile per fixture: **AIF-CDU-Neutral** for `Generic_CDU`, the `am_fail_*` / `tc_fail_*` / `el_fail_*` variants, and the synthetic `cp_*` stubs. **AIF-Rack-Neutral** for `GB300`. Deferred validators (CP.002, CP.003, CP.006) are omitted because their implementations are not in v0.1.0.

Cells flagged `✗` in a variant include the *targeted* failure (the one the variant was designed to trigger) and any *collateral* failures that follow from the variant's minimal shape (e.g., the AM variants do not declare a ConnectionPoints scope or sublayer, so CP.001/CP.005 also fire). All `✗` cells are expected outcomes.

| Fixture | AM.001 | AM.002 | AM.003 | AM.004 | AM.005 | AM.006 | AM.007 | CP.001 | CP.004 | CP.005 | TC.001 | TC.002 | EL.001 | EL.002 | EL.003 | EL.004 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `Generic_CDU/asset/Generic_CDU.usda` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `gb300/asset/gb300.usda` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | — | — | — | — |
| `cp_pass_complete.usda` | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `am_fail_no_properties_sublayer.usda` | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `am_fail_no_assetClass.usda` | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `am_fail_no_manufacturer.usda` | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✗ |
| `am_fail_no_dimensions.usda` | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✗ |
| `am_fail_no_simready_version.usda` | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✗ |
| `am_fail_no_description.usda` | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✗ |
| `am_fail_no_cooling_type.usda` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✗ |
| `cp_fail_no_scope.usda` | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `cp_fail_no_default_prim.usda` | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `cp_fail_empty_scope.usda` | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `cp_fail_wrong_type_scope.usda` | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `cp_fail_bad_names.usda` | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `cp_fail_uppercase_names.usda` | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `cp_fail_no_sublayer.usda` | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `tc_fail_no_cooling_capacity.usda` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ | ✗ |
| `tc_fail_no_thermal_cps.usda` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ |
| `el_fail_no_voltage.usda` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | ✗ | ✗ | ✓ | ✓ | ✗ |
| `el_fail_no_power_rating.usda` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ | ✗ |
| `el_fail_no_frequency.usda` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ |
| `el_fail_no_electrical_cps.usda` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✗ |
