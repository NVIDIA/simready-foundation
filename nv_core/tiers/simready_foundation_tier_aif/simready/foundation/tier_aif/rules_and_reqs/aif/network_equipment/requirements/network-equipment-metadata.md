# network-equipment-metadata

| Code | NET.001 |
|---|---|
| Validator | {oav-validator-latest-link}`net-001` |
| Compatibility | {compatibility}`AIF` |
| Tags | {tag}`essential` |

## Summary

For network equipment, the default prim must declare `aif:core:assetClass = "network-equipment"` as a
string in the Properties sublayer. `manufacturer`, `modelNumber`, and
`assetVersion` in `aif:core` must be non-empty strings. The same prim must author
`height`, `width`, `depth`, and `weight` as finite, strictly positive floats;
`installationClearance` and `accessibilityRequirement` must be finite,
nonnegative floats. Linear values use mm and weight uses kg. All these values must be authored in the Properties
sublayer and resolve to valid values on the composed default prim.

These are data-integrity bounds. OEM-specific engineering plausibility requires
SME review. AM.001–AM.003, AM.005–AM.006, AM.008 and AM.009 apply through the
AIF 0.3 metadata dependency. AM.009 owns scalar presence and retired dimension
rejection; AM.008 owns the common USD type contract.

## How to comply

Author the values described above and validate with `AIF-Entity@0.3.0`.
