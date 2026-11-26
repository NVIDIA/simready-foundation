# Air-cooled chiller electrical interface

| Code | EL.005 |
| --- | --- |
| Validator | {oav-validator-latest-link}`el-005` |
| Compatibility | {compatibility}`AIF` |
| Tags | {tag}`essential` |

## Summary

`Air-Cooled-Chiller@0.3.0` selects EL.005 through `CAP205_AirCooledChiller.0-3-0`.

AirCooledChiller has positive unit-explicit nominal voltage, nominal frequency, and reference input power. It has at least one CP2 electrical connection with system power and direction input. CP.010–CP.012 check the electrical vocabulary and report completeness; CP.012 retains its INFO/WARNING diagnostics for stub/draft interfaces. The published synthetic example has a production-complete inlet and is tested to emit neither completeness diagnostic.

Every power inlet's nominal voltage and frequency match the equipment values. The sum of positive inlet rated powers is at least the declared reference input power. Reference input power describes an operating point, not a maximum or nameplate rating; the inlet rating is authored separately. Existing EL.001–EL.004 remain unchanged for legacy classes.
