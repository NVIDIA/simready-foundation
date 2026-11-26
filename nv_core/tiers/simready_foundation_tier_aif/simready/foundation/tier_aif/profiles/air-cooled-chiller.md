# Air-Cooled Chiller

Use `Air-Cooled-Chiller@0.3.0` to validate a complete air-cooled chiller. Author
`aif:core:assetClass = "AirCooledChiller"` on the Properties sublayer's
default prim and preserve it on the composed default prim.

The profile checks the shared AIF equipment template, CP2 vocabulary, visual
and packaging contracts. It also selects the [Air-Cooled Chiller capability](../capabilities/CAP205_AirCooledChiller.md)
for tabular performance, evaporator supply and return, and AC power. The
[general AIF profile](aif-entity.md#equipment-class-differentiation) describes
the thermal checks for CDU and CRAH assets.

| Kind | Required selector |
|---|---|
| Feature | `FET001_MinimalPlaceableVisual.1-0-0` |
| Capability | `CAP000_Core.0-2-0` |
| Capability | `CAP200_AifMetadata.0-3-0` |
| Capability | `CAP201_ConnectionPoints.0-3-0` |
| Capability | `CAP202_ThermalCooling.0-3-0` |
| Capability | `CAP203_Electrical.0-3-0` |
| Capability | `CAP205_AirCooledChiller.0-3-0` |
| Capability | `CAP031_SelfContainedPackage.0-1-0` |
| Capability | `CAP033_SimReadyPackage.0-4-0` |

```sh
simready-validate --profile Air-Cooled-Chiller --version 0.3.0 \
  sample_content/aif/Synthetic_AirCooledChiller/asset/Synthetic_AirCooledChiller.usda
```

## Air-cooled chiller metadata

Set `aif:core:assetClass` to `AirCooledChiller` on the Properties default prim. Matching ignores case and surrounding whitespace. The packaged schema is generated from `standards/equipment-classes/aif-v0.3/air-cooled-chiller.csv`. For full chiller conformance, the dedicated Air-Cooled-Chiller profile checks the tabular model under [AM.010](../rules_and_reqs/aif/metadata/requirements/air-chiller-tabular-model.md).

The 17 Required rows must have authored values on the properties default prim. Optional and Conditional rows are checked when authored; unspecified non-tabular applicability does not require their presence. Every authored chiller field must use its declared USD type, finite numeric values, permitted Options, and `customData = { string units = "<SI Unit Values>" }`. Units are exact schema strings and do not derive from stage `metersPerUnit`. Array spellings map to native `float[]`, `int[]`, and `token[]`.

Mass fraction, relative humidity, and cycling degradation remain within [0, 1]. Kelvin values are positive; nonnegative physical magnitudes cannot be negative. Compressor sequence numbers are capacity ranks starting at 1, independently of installed compressor count. Required string/token values are nonempty. Refrigerant uses an R- designation.

## Mapping manufacturer data

Use the source units, rating conditions, and equipment or port identified in the manual to select the destination. The equipment field names below have the prefix `aif:spec:`. Port field names have the prefix `simready:connectionPoint:`.

| Manufacturer data | AIF representation and conditions |
| --- | --- |
| Cooling capacity curve, nominal capacity, maximum capacity | Use net evaporator cooling duty in W. Put the duty at the declared rating in `referenceNetEvaporatorCapacity_W` and performance data in `performanceMapCoolingLookupNetEvaporatorCapacity_W`. A flow-versus-capacity curve supplies one slice when the other five axis conditions are known. A complete cooling map requires all six axes and matching lookup tables. Treat the largest tabulated value as the OEM maximum only when the OEM identifies that rating and the map covers its stated conditions. |
| Total heat dissipated | Use `referenceNetCondenserCapacity_W` or `performanceMapCoolingLookupNetCondenserCapacity_W` when the source measures net condenser heat rejection. Establish the treatment of casing losses, oil-cooler heat, and auxiliary heat before mapping a heat rating. Convert kW to W by multiplying by 1000. |
| Nominal flow, maximum flow, maximum operating pressure | On the applicable evaporator water port, use `thermal:designFlowRate` and `thermal:maxFlowRate` in L/s and `thermal:maxPressure` in Pa gauge. Multiply m³/s by 1000 for the port. Use a refrigerant-side pressure rating only in a model of that circuit. |
| Primary or secondary supply and return piping | Identify the evaporator circuit and equipment-relative direction. Author the FWS supply and return frames on the corresponding physical ports. Use the port’s bore, flange size and flange rating for mating. A label such as “secondary” alone does not identify an evaporator port. |
| Voltage, frequency, phases, power factor, breaker | Use `nominalVoltage_V` and `nominalFrequency_Hz` for equipment ratings. On each matching AC feed, use `electrical:nominalVoltage`, `electrical:frequency`, `electrical:phases`, and `electrical:powerFactor`. Map the upstream breaker rating in A to `electrical:breakerRating`. Keep motor and skid ratings scoped to the component they describe. |
| Rated power or rated maximum power | Use `referenceInputPower_W` for whole-equipment electrical demand at the reference condition. Use `electrical:ratedPower` for a feed's rated capacity in W. A generic nameplate kW value needs an identified measurement boundary and duty before assignment. |

The optional `referenceCoolingMapPointIndex` identifies the rating conditions directly in the published [cooling map](../rules_and_reqs/aif/metadata/requirements/air-chiller-tabular-model.md). Detailed fan and refrigerant models can also use the following optional equipment fields. Omit a field when its rating or scope is unknown.

| Manufacturer data | AIF field and meaning |
| --- | --- |
| Installed condenser fan type and EC fan count | `fanType` describes the common installed condenser fan type. `numberOfFans` reuses the existing EC fan count field for the installed condenser bank. |
| Maximum condenser fan speed | `maximumCondenserFanRotationalSpeed_Hz` records positive rated shaft speed in revolutions per second. Divide maximum shaft RPM by 60. The drive’s electrical frequency is a separate quantity. |
| Condenser fan motor efficiency | `efficiencyRotatingEquipment` records rated motor efficiency as a fraction greater than zero and at most one. Divide percent by 100. Use one value when the installed condenser fan motors share the rating. A whole-chiller input map already includes the loads within its declared measurement boundary. |
| Refrigerant charge per circuit | `refrigerantChargePerCircuit_kg` records one positive factory charge mass per circuit in a nonempty array. Document the manufacturer's circuit order with the source data. Each element describes one circuit. |
