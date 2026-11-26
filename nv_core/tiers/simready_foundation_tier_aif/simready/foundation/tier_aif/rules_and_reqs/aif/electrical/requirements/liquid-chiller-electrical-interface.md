# Air-cooled chiller electrical interface

| Code | EL.006 |
| --- | --- |
| Validator | {oav-validator-latest-link}`el-006` |
| Compatibility | {compatibility}`AIF` |
| Tags | {tag}`essential` |

## Summary

`Liquid-Cooled-Chiller@0.3.0` selects EL.006 through `CAP206_LiquidCooledChiller.0-3-0`.

Declare positive nominal voltage, nominal frequency and reference input power. Each CP2 electrical connection with system `power` and direction `input` must match the equipment's nominal voltage and frequency. At least one such inlet is required. The sum of inlet power ratings must cover the reference electrical input. CP.010–CP.012 validate the individual connection points.
