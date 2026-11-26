# Air-cooled chiller tabular model

| Code | AM.011 |
| --- | --- |
| Validator | {oav-validator-latest-link}`am-011` |
| Compatibility | {compatibility}`AIF` |
| Tags | {tag}`essential` |

## Summary

`Liquid-Cooled-Chiller@0.3.0` selects AM.011 through `CAP206_LiquidCooledChiller.0-3-0`. The Properties-layer default prim and the composed default prim must both declare `aif:core:assetClass` as a USD `string` resolving to `LiquidCooledChiller`. Matching ignores case and surrounding whitespace.

Set `aif:spec:performanceModelType` to `TABULAR`. In the cooling map, use evaporator liquid flow, evaporator leaving temperature, condenser liquid flow, condenser entering temperature and compressor sequence rank, in that order. The last axis varies fastest. Each finite axis increases strictly. Every table has one entry per combination of grid points.

Provide a standby power map and a pressure-drop map for each water circuit. The pressure-drop maps cover the corresponding cooling-map envelopes. Every condenser pressure-drop value is positive. Declared flow limits and evaporator leaving-temperature limits lie within their cooling-map axes.

The optional zero-based `referenceCoolingMapPointIndex` links the three equipment ratings to the corresponding cooling lookup values. At a normal point with zero separately rejected oil and auxiliary heat, condenser heat rejection equals net evaporator capacity plus electrical input. When supplied, reference COP equals reference evaporator capacity divided by reference input power.
