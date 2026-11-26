# Air-cooled chiller thermal interfaces

| Code | TC.004 |
| --- | --- |
| Validator | {oav-validator-latest-link}`tc-004` |
| Compatibility | {compatibility}`AIF` |
| Tags | {tag}`essential` |

## Summary

`Liquid-Cooled-Chiller@0.3.0` selects TC.004 through `CAP206_LiquidCooledChiller.0-3-0`.

Both reference thermal capacities must be positive. Author one CP2 supply and one return for each liquid circuit. Use system `FWS` for the evaporator and `equipment_cooling` for the condenser. The evaporator supply carries leaving chilled water. The condenser supply carries entering cooling water.

Both ports in a circuit carry the same design flow in L/s. The equipment flow axes use m³/s. The port maximum flow covers the design flow and the maximum validated equipment flow. Check each supply temperature in °C against the corresponding map axis in K. At positive duty, the return temperature in each circuit exceeds its supply temperature. Port bore and pipe outside diameter are separate measurements.
