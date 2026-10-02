# connection-point-base-namespace

| Code     | CP.011 |
|----------|--------|
| Validator| {oav-validator-latest-link}`cp-011` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`normative` |

## Summary

Every connection point must carry all five base namespace properties, which together state the semantic identity of the connection.

## Description

The base `simready:connectionPoint:` namespace answers "what is this connection?" without describing its physical characteristics or operating parameters. These five properties apply to every connection point in every domain.

| Property | Type | Example values | Description |
|----------|------|---------------|-------------|
| `simready:connectionPoint:domain` | token | `thermal`, `electrical`, `network`, `airflow` | The physical domain of this connection |
| `simready:connectionPoint:direction` | token | `supply`, `return`, `input`, `output`, `bidirectional` | Flow or signal direction |
| `simready:connectionPoint:system` | token | `FWS`, `TCS`, `power`, `BMS`, `high_speed_data`, `mgmt`, `equipment_cooling` | System classification within the facility |
| `simready:connectionPoint:disconnectType` | token | `flanged`, `quick_disconnect`, `hardwired`, `RJ45`, `OSFP`, `blind_mate`, `open_vent` | Physical disconnect mechanism |
| `simready:connectionPoint:serviceClearance` | float (meters) | `0.3`, `0.0` | Shortest distance from the connection interface to any obstruction that would prevent service access. Zero means an obstruction sits against the interface and there is no service access |

The value is zero or greater. `serviceClearance` is the one base property that could be argued as domain-specific. It stays in the base namespace because every connection needs a maintenance access envelope and the concept does not change shape across domains.

### Token values are open

The example values above are drawn from current equipment classes and are not closed enumerations. New equipment classes and OEM partners will surface values not listed here.

A value outside the example set is never a validation error. Validators emit an informational or warning diagnostic to aid authoring review and accept the asset. Closed value sets, if they are ever needed, come with schema promotion.

### `type` is a deprecated alias for `domain`

Earlier drafts and some pre-release exemplars used `simready:connectionPoint:type` for the domain identifier. It was renamed to `simready:connectionPoint:domain` to match the terminology used elsewhere in the vocabulary.

Validators treat `simready:connectionPoint:type` as a deprecated alias: warn, and where tooling supports it, map it to `domain`. The old name will not survive schema promotion, so assets carrying it should be updated.

## Why is it required?

- A consuming tool can classify every interface on an asset from these five properties alone, with no geometry loaded and no prim names parsed
- Keeping the base namespace free of physical dimensions means every property in it applies to every connection, so a consumer never has to know which base properties apply to which domain
- `serviceClearance` gives robotic and maintenance planning an access envelope without a separate annotation pass
- Open tokens let new equipment classes enter the ecosystem without a vocabulary revision blocking them

## Examples

A connection point carrying only the base namespace. This is a valid authoring stub, complete under this requirement and incomplete under CP.012:

```usda
def Xform "fws_supply_main"
{
    uniform token purpose = "guide"

    token simready:connectionPoint:domain = "thermal"
    token simready:connectionPoint:direction = "supply"
    token simready:connectionPoint:system = "FWS"
    token simready:connectionPoint:disconnectType = "flanged"
    float simready:connectionPoint:serviceClearance = 0.3
}
```

## How to comply

1. Author all five base properties on every connection point Xform
2. Use SI units: `serviceClearance` in meters
3. Prefer a value from the example set where one fits; author a new token where none does
4. Replace any `simready:connectionPoint:type` property with `simready:connectionPoint:domain`

## Related requirements

- CP.010 `connection-point-prim-structure`: requires `domain` and `direction` as the minimum subset of this set
- CP.012 `connection-point-domain-namespace`: the domain properties selected by the `domain` value authored here

## For More Information

- [USD Properties](https://openusd.org/release/glossary.html#usdglossary-property)
