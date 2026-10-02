# equipment-class-template-compliance

| Code     | AM.007 |
|----------|--------|
| Validator| {oav-validator-latest-link}`am-007` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

The default prim must carry every `aif:spec:*` attribute that its declared equipment class defines.

## Description

The validator reads `aif:core:assetClass`, selects that class's attribute set, and checks each attribute in the set is present on the default prim. It fails in two cases: `aif:core:assetClass` is missing or empty, and `aif:core:assetClass` names a class this specification does not define.

A missing attribute is reported as a warning, not a failure. Of the source templates only `CDU.csv` marks its rows `Required`; `CRAH.csv`, `UPS.csv` and `GB300_Rack.csv` leave that column blank, so the source does not state that those attributes are mandatory. The attributes a downstream requirement consumes are enforced by that requirement instead: EL.001, EL.002 and EL.003 each fail when the attribute their equipment class names for nominal voltage, power rating or frequency is absent, and TC.001 and TC.002 fail on missing thermal connection points.

The attributes themselves are named in the per-class reference tables on the
[Core Metadata capability](../capability-metadata.md) page, which is where to look up what a
given class must carry. Those tables were derived from the equipment CSVs published in
[aif-pipeline-samples](https://github.com/NVIDIA-Omniverse/aif-pipeline-samples/tree/main/metadata/templates/source), and the sets the validator reads from `config/aif-equipment-<class>.json` match them exactly.

The check is presence only. The type an attribute is declared with and the unit its value is in are not validated.

An equipment class to which neither electrical nor thermal cooling applies has no requirement that fails on a missing `aif:spec:*` attribute. Compute Rack is the only such class.

Recognised classes and their attribute counts:

| `aif:core:assetClass` | Attributes |
| :---- | :---- |
| `CDU` | 61 |
| `CRAH` | 31 |
| `UPS` | 31 |
| `compute rack` | 18 |

An asset whose `assetClass` is none of these fails this requirement: the validator cannot
select a set for it.

The table above is the state of `config/`, not a closed list. Each class is defined by a
`config/aif-equipment-<class>.json` file naming the `aif:core:assetClass` tokens it answers
to and the attributes it requires. Adding an equipment class is adding one of those files;
it needs no validator change, no new requirement code and no feature JSON edit.

## Why is it required?

- Ensures simulation runtimes have all data needed to model equipment behavior
- Equipment-specific attributes (cooling curves, pump specs, battery specs, power profiles) are critical for thermal/electrical simulation
- Single check covers all equipment-specific metadata without a separate requirement per attribute


## Examples

```usda
# CDU asset with aif:spec:* attributes present
def Xform "Generic_CDU" {
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
