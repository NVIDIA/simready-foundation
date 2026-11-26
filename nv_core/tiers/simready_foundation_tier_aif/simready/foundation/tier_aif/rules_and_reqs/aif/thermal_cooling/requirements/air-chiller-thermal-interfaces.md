# Air-cooled chiller thermal interfaces

| Code | TC.003 |
| --- | --- |
| Validator | {oav-validator-latest-link}`tc-003` |
| Compatibility | {compatibility}`AIF` |
| Tags | {tag}`essential` |

## Summary

`Air-Cooled-Chiller@0.3.0` selects TC.003 through `CAP205_AirCooledChiller.0-3-0`.

AirCooledChiller has positive `aif:spec:referenceNetEvaporatorCapacity_W` and exactly one CP2 thermal FWS supply and return pair. Selection uses typed domain, system and direction properties rather than prim names. CP.010–CP.012 check the connection vocabulary and report completeness; CP.012 retains its INFO/WARNING diagnostics for stub/draft interfaces. The published synthetic example has production-complete ports and is tested to emit neither completeness diagnostic.

Both ports carry the same positive design flow at a common design condition, within the authored equipment limits and cooling-map flow envelope, converted from m³/s to CP2 L/s by multiplying by 1000. CP2 maximum flow covers the design flow and the maximum validated evaporator flow. The supply design temperature lies within the authored leaving-temperature limits and cooling-map envelope, with Kelvin map values converted to Celsius; the return temperature may differ. This FWS pair identifies the single evaporator circuit and cannot be substituted by a TCS/condenser pair.

The CP2 port diameter is internal bore in meters; evaporator pipe outside diameter is a separate equipment quantity in millimeters and is not an alias. Ambient air does not require a fabricated condenser-liquid circuit. Existing TC.001 and TC.002 continue to handle legacy classes unchanged.
