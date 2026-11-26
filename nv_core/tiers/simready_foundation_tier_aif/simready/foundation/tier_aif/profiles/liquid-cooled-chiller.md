# Liquid-Cooled Chiller

Use `Liquid-Cooled-Chiller@0.3.0` to validate a complete liquid-cooled chiller. Author
`aif:core:assetClass = "LiquidCooledChiller"` on the Properties sublayer's
default prim and preserve it on the composed default prim.

The profile checks the shared AIF equipment template, CP2 vocabulary, visual
and packaging contracts. It also selects the [Liquid-Cooled Chiller capability](../capabilities/CAP206_LiquidCooledChiller.md)
for tabular performance, separate evaporator and condenser water circuits, and AC power.

| Kind | Required selector |
|---|---|
| Feature | `FET001_MinimalPlaceableVisual.1-0-0` |
| Capability | `CAP000_Core.0-2-0` |
| Capability | `CAP200_AifMetadata.0-3-0` |
| Capability | `CAP201_ConnectionPoints.0-3-0` |
| Capability | `CAP202_ThermalCooling.0-3-0` |
| Capability | `CAP203_Electrical.0-3-0` |
| Capability | `CAP206_LiquidCooledChiller.0-3-0` |
| Capability | `CAP031_SelfContainedPackage.0-1-0` |
| Capability | `CAP033_SimReadyPackage.0-4-0` |

```sh
simready-validate --profile Liquid-Cooled-Chiller --version 0.3.0 \
  sample_content/aif/Synthetic_LiquidCooledChiller/asset/Synthetic_LiquidCooledChiller.usda
```
