# Air-cooled chiller tabular model

| Code | AM.010 |
| --- | --- |
| Validator | {oav-validator-latest-link}`am-010` |
| Compatibility | {compatibility}`AIF` |
| Tags | {tag}`essential` |

## Summary

`Air-Cooled-Chiller@0.3.0` selects AM.010 through `CAP205_AirCooledChiller.0-3-0`. The Properties-layer default prim and the composed default prim must both declare `aif:core:assetClass` as a USD `string` resolving to `AirCooledChiller`. Matching ignores case and surrounding whitespace.

Set `aif:spec:performanceModelType` to `TABULAR` for every AirCooledChiller. The three performance maps use selected fields from the [ASHRAE Standard 205 RS0001 chiller schema](https://data.ashrae.org/standard205/assets/schema/RS0001.schema.json).

All 18 tabular arrays are nonempty. Cooling axes are evaporator flow, evaporator leaving temperature, condenser entering dry-bulb temperature, relative humidity, ambient pressure, and compressor sequence rank, in that order. The last axis varies fastest. Every grid is finite and strictly increasing; flow, Kelvin and absolute-pressure axes are positive; relative humidity stays within [0, 1] and sequence ranks start at 1; every lookup length equals the product of its grid lengths. Standby and evaporator pressure-drop maps follow their own one- and two-axis products. Operating-state elements are NORMAL or STANDBY. A NORMAL point with positive condenser rejection has positive condenser air flow.

COP, when authored, equals reference evaporator capacity divided by reference input power. AIF adds an optional link from the reference ratings to an exact tabulated point using `aif:spec:referenceCoolingMapPointIndex`, a zero-based integer into the cooling lookup arrays in the axis order above. At that index, input power, net evaporator capacity, and net condenser capacity must match their respective reference ratings within numerical tolerance. Index zero selects the first point. Omit the index when the rating's conditions are unknown or fall between grid points. Ratings without an index are checked independently of the table.

Declared min/max evaporator-flow and leaving-setpoint limits lie within the map envelope, minimum does not exceed maximum, and the pressure-drop map covers the same evaporator envelope. These ordering and envelope rules define this AIF validation contract rather than asserting normative ASHRAE constraints. For NORMAL points with separately rejected oil/auxiliary heat equal to zero, condenser rejection equals evaporator capacity plus input power within numerical tolerance. Other heat-rejection boundaries require separate physical acceptance and are not certified by this simple balance check.
