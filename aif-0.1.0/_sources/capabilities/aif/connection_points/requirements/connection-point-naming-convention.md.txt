# connection-point-naming-convention

| Code     | CP.004 |
|----------|--------|
| Validator| {oav-validator-latest-link}`cp-004` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

All prims under the `ConnectionPoints` scope must follow the `<vendor>_<type>_<suffix>` naming pattern using a valid type prefix from the AIF connection point type table.

## Description

The naming convention encodes both who authored the connection point (vendor) and what kind of physical interface it represents (type). The suffix disambiguates multiple connection points of the same type.

## Why is it required?

- Encoding vendor and type in the name allows pipelines to identify connection points programmatically without inspecting geometry
- The standardized type prefix table ensures interoperability across equipment from different vendors
- Suffixes allow multiple connection points of the same type (e.g., two liquid supply ports)

## Valid Type Prefixes

| Type Prefix | Interface |
|-------------|-----------|
| `liq_supply` | Generic liquid intake pipe |
| `liq_return` | Generic liquid outflow pipe |
| `fws_supply` | Facility Water Supply pipe |
| `fws_return` | Facility Water Return pipe |
| `tcs_supply` | Technology Cooling Supply pipe |
| `tcs_return` | Technology Cooling Return pipe |
| `electrical_nominal_voltage` | Electrical power socket |
| `airvent_intake` | Airflow intake vent |
| `airvent_outflow` | Airflow outflow vent |

## Examples

```text
vertiv_fws_supply_piping_connection_main   # valid
vertiv_tcs_return_piping_connection_01     # valid
trane_electrical_nominal_voltage_main      # valid
trane_airvent_intake_frontplate            # valid
supply_pipe_01                             # INVALID: no vendor prefix
vertiv_water_in                            # INVALID: 'water_in' is not a valid type prefix
```

## How to comply

Name all prims inside `ConnectionPoints` as `<vendor_name>_<type_prefix>[_<any_suffix>]`. Use your equipment vendor name (lowercase, no spaces) as the vendor prefix.

## Related requirements

- CP.001 `connectionpoints-scope-structure`: prims must be inside the `ConnectionPoints` scope to be checked
- CP.005 `connection-points-composition`: the `*_ConnectionPoints.usd` sublayer must contain these named prims
- TC.002 `thermal-cooling-connection-points`: checks for prims matching specific type prefixes
- EL.004 `electrical-connection-points`: checks for prims matching `electrical_nominal_voltage` prefix

## For More Information

- [USD Prim](https://openusd.org/release/glossary.html#usdglossary-prim)
