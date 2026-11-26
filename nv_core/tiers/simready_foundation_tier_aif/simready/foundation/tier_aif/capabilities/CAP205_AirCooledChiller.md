# Air-Cooled Chiller

| Property | Value |
|---|---|
| Contract | `CAP205_AirCooledChiller.0-3-0` |
| Tier | AIF |
| Runtime | OpenUSD |
| Profile | [Air-Cooled-Chiller@0.3.0](../profiles/air-cooled-chiller.md) |
| Dependencies | `CAP200_AifMetadata.0-3-0`, `CAP201_ConnectionPoints.0-3-0`, `CAP202_ThermalCooling.0-3-0`, `CAP203_Electrical.0-3-0` |

This capability checks the relationships between a chiller's equipment ratings, performance tables and physical interfaces.

| Requirement | What the asset must provide |
|---|---|
| [AM.010](../rules_and_reqs/aif/metadata/requirements/air-chiller-tabular-model.md) | Chiller class on the Properties and composed default prims, and consistent cooling, standby and evaporator pressure-drop tables. |
| [TC.003](../rules_and_reqs/aif/thermal_cooling/requirements/air-chiller-thermal-interfaces.md) | An evaporator supply and return with flow and temperature consistent with the equipment limits. |
| [EL.005](../rules_and_reqs/aif/electrical/requirements/air-chiller-electrical-interface.md) | AC inlets with the declared voltage and frequency, and sufficient total inlet capacity for the reference input power. |
