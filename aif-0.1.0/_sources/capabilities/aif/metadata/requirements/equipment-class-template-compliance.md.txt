# equipment-class-template-compliance

| Code     | AM.007 |
|----------|--------|
| Validator| {oav-validator-latest-link}`am-007` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

All `aif:spec:*` attributes defined in the equipment-class schema (determined by `aif:core:assetClass`) must be present on the default prim.

## Description

Each equipment class has a JSON schema in `config/aif-equipment-<class>.json` defining all required `aif:spec:*` attributes. The validator reads `aif:core:assetClass` to select the appropriate schema and checks that every property key in that schema is present on the default prim.

Supported classes and their schemas:
- `CDU` → `aif-equipment-cdu.json` (~65 attributes)
- `CRAH` → `aif-equipment-crah.json` (~31 attributes)
- `UPS` → `aif-equipment-ups.json` (~32 attributes)
- `compute rack` / `gb300` → `aif-equipment-gb300-rack.json` (~18 attributes)

## Why is it required?

- Ensures simulation runtimes have all data needed to model equipment behavior
- Equipment-specific attributes (cooling curves, pump specs, battery specs, power profiles) are critical for thermal/electrical simulation
- Single check covers all equipment-specific metadata without a separate requirement per attribute

## Examples

```usda
# CDU asset with aif:spec:* attributes present
def Xform "CW375" {
    string aif:core:assetClass = "CDU"
    float aif:spec:nominalCoolingCapacity = 375.0
    float aif:spec:maximumCoolingCapacity = 400.0
    float aif:spec:nominalFlow = 60.0
    int aif:spec:numberOfPumps = 2
    float aif:spec:nominalVoltage = 400.0
    float aif:spec:powerRating = 15.0
    float aif:spec:frequency = 50.0
    # ... all remaining CDU aif:spec:* attributes
}
```

## How to comply

Use the [AIF pipeline metadata tools](https://nvidia-omniverse.github.io/aif-pipeline-samples/workflows/metadata.html) to generate a template for your equipment class:

```bash
aif-pipeline metadata create --type cdu --output my_cdu_metadata.json
```

Then apply it to your asset:

```bash
aif-pipeline metadata apply my_cdu_metadata.json --output AssetName_Properties.usda --prim RootPrimName
```

## Related requirements

- AM.001 `properties-sublayer-required`: the properties sublayer must exist before `aif:spec:*` attributes can be set
- AM.002 `asset-class-required`: `aif:core:assetClass` must be present for the template selector to function
- TC.001 `nominal-cooling-capacity`: overlaps with CDU/CRAH `aif:spec:nominalCoolingCapacity`
- EL.001 `nominal-voltage-required`: overlaps with CDU/CRAH/UPS electrical voltage attributes

## For More Information

- [USD Custom Attributes](https://openusd.org/release/glossary.html#usdglossary-attribute)
- [AIF Pipeline Samples: Metadata workflow](https://nvidia-omniverse.github.io/aif-pipeline-samples/workflows/metadata.html)
