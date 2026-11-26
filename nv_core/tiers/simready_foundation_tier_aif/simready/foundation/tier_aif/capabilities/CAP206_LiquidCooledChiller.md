# Liquid-Cooled Chiller

| Property | Value |
|---|---|
| Contract | `CAP206_LiquidCooledChiller.0-3-0` |
| Tier | AIF |
| Runtime | OpenUSD |
| Profile | [Liquid-Cooled-Chiller@0.3.0](../profiles/liquid-cooled-chiller.md) |
| Dependencies | `CAP200_AifMetadata.0-3-0`, `CAP201_ConnectionPoints.0-3-0`, `CAP202_ThermalCooling.0-3-0`, `CAP203_Electrical.0-3-0` |

This capability checks the relationships between a chiller's equipment ratings, performance tables and physical interfaces.

| Requirement | What the asset must provide |
|---|---|
| [AM.011](../rules_and_reqs/aif/metadata/requirements/liquid-chiller-tabular-model.md) | Chiller class on the Properties and composed default prims, and consistent cooling, standby and evaporator and condenser pressure-drop tables. |
| [TC.004](../rules_and_reqs/aif/thermal_cooling/requirements/liquid-chiller-thermal-interfaces.md) | Separate evaporator and condenser supply/return pairs with flows and temperatures within their operating limits. |
| [EL.006](../rules_and_reqs/aif/electrical/requirements/liquid-chiller-electrical-interface.md) | AC inlets with the declared voltage and frequency, and sufficient total inlet capacity for the reference input power. |
