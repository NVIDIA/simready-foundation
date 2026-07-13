# AIF Core Metadata

**Capability:** AIF Core Metadata (AM)

## Overview

Validates AIF equipment metadata attributes on assets. AIF equipment assets carry structured metadata describing physical and operational characteristics of data center equipment (CDUs, CRAHs, UPS units, compute racks).

Metadata is split into two namespaces:
- `aif:core:*`: common attributes required on all equipment types (dimensions, identity, version)
- `aif:spec:*`: equipment-class-specific attributes defined per equipment type in the equipment schema JSONs

## Reference Tables

The following tables enumerate the AIF metadata attributes that AIF assets carry. They are the source of truth for which `aif:core:*` and `aif:spec:*` attributes must be present on a given equipment class, derived from the CSV templates used by the AIF metadata tooling.

### Common Attributes (`aif:core:*`)

Shared by all AIF equipment types regardless of class. Validated by AM.001–AM.006.

| Attribute | Type | Description |
|---|---|---|
| `aif:core:manufacturer` | string | Equipment manufacturer name |
| `aif:core:modelNumber` | string | Equipment model number |
| `aif:core:overallGeometryDimensions` | float3 | Overall geometry (WxDxH) in mm |
| `aif:core:weight` | float | Equipment weight in kilograms |
| `aif:core:height` | float | Equipment height in mm |
| `aif:core:width` | float | Equipment width in mm |
| `aif:core:depth` | float | Equipment depth in mm |
| `aif:core:installationClearance` | float | Installation clearance in mm |
| `aif:core:accessibilityRequirement` | float | Service clearance in mm |
| `aif:core:assetVersion` | string | Design revision of digital twin asset |
| `aif:core:assetClass` | string | Class of AI Factory equipment |
| `aif:core:simreadyVersion` | string | SimReady version |
| `aif:core:sceneOptimizerVersion` | string | Scene Optimizer version |
| `aif:core:assetValidatorVersion` | string | Asset Validator version |
| `aif:core:assetDescription` | string | Human-readable description of asset |
| `aif:core:connectsToModelDocumentation` | string | URL to online documentation |
| `aif:core:assetCreationDate` | string | Creation date of revision in ISO 8601 format (YYYY-MM-DD) |

### Equipment-Class-Specific Attributes (`aif:spec:*`)

Each equipment class has its own set of `aif:spec:*` attributes. Validated as a complete set by AM.007 against the equipment-class schema selected via `aif:core:assetClass`.

::::{dropdown} CDU (Coolant Distribution Unit) — 61 attributes
:icon: list-unordered

| Attribute | Type | Description |
|---|---|---|
| `aif:spec:coolingType` | string | Primary cooling type (Water/Glycol) |
| `aif:spec:mountStyle` | string | Mount style (In Row / In Rack) |
| `aif:spec:coolingCapacityCurve` | float2_array | Cooling capacity curve (flow rate vs cooling capacity, 5 points required) |
| `aif:spec:referenceFacilityCoolantTemperature` | float | Reference facility coolant temperature in Kelvin |
| `aif:spec:referenceTechnologyCoolantFlowRate` | float | Reference technology coolant flow rate in LPM |
| `aif:spec:referenceSecondaryCoolantTemperature` | float | Reference secondary coolant temperature in Kelvin |
| `aif:spec:totalHeatDissipated` | float | Total heat dissipated (kW) |
| `aif:spec:filterSizeCoolingCapacity` | float | Filter size (μ) for cooling capacity |
| `aif:spec:pumpRedundancyStrategyCoolingCapacity` | float | Pump redundancy strategy for cooling capacity |
| `aif:spec:workingFluidCoolingCapacity` | float | Working fluid for cooling capacity |
| `aif:spec:nominalCoolingCapacity` | float | Nominal cooling capacity |
| `aif:spec:maximumCoolingCapacity` | float | Maximum cooling capacity |
| `aif:spec:nominalFlow` | float | Nominal flow (2x pump running) in m³/s |
| `aif:spec:maximumFlow` | float | Maximum flow (3x pump running) in m³/s |
| `aif:spec:pumpFlowCurve` | float2_array | Pump flow curve (CMS vs KPa, 5 points required) |
| `aif:spec:maxSpeed` | float | Max speed (Hz) |
| `aif:spec:ratedSpeed` | float | Rated speed (Hz) |
| `aif:spec:numberOfPumps` | int | Number of pumps |
| `aif:spec:maximumPowerConsumption2XPumps` | float | Maximum power consumption (2x pumps) at maximum flow and external pressure drop |
| `aif:spec:maximumPowerConsumption3XPumps` | float | Maximum power consumption (3x pumps) at maximum flow and external pressure drop |
| `aif:spec:filterSizePumps` | string | Filter size (μ) for pumps |
| `aif:spec:pumpRedundancyStrategyPumps` | string | Pump redundancy strategy for pumps |
| `aif:spec:workingFluidPumps` | string | Working fluid for pumps |
| `aif:spec:wettedMaterialTcs` | string | Wetted material list for TCS |
| `aif:spec:wettedMaterialFws` | string | Wetted material list for FWS |
| `aif:spec:communication1` | float | Communication 1 |
| `aif:spec:communication2` | float | Communication 2 |
| `aif:spec:nominalVoltage` | float | Electrical nominal voltage (V) |
| `aif:spec:current` | float | Electrical current |
| `aif:spec:frequency` | float | Electrical frequency |
| `aif:spec:powerRating` | float | Electrical power rating (kW) |
| `aif:spec:powerFactor` | float | Electrical power factor |
| `aif:spec:efficiency` | float | Electrical efficiency |
| `aif:spec:wiringMethod` | string | Wiring method |
| `aif:spec:fwsSupplyPipingConnection` | float | FWS supply piping connection in mm |
| `aif:spec:fwsReturnPipingConnection` | float | FWS return piping connection in mm |
| `aif:spec:tcsSupplyPipingConnection` | float | TCS supply piping connection in mm |
| `aif:spec:tcsReturnPipingConnection` | float | TCS return piping connection in mm |
| `aif:spec:primaryFiltration` | string | Primary filtration (external with bypass for cleaning) |
| `aif:spec:primaryCircuitVolume` | float | Primary circuit volume in liters |
| `aif:spec:secondaryFiltration` | string | Secondary filtration (external with bypass for cleaning) |
| `aif:spec:secondaryCircuitVolume` | float | Secondary circuit volume in liters |
| `aif:spec:ratedVoltageIncomingPower` | float | Rated voltage incoming power |
| `aif:spec:ratedCableSize` | string | Rated cable size |
| `aif:spec:ratedMaxPower` | float | Rated max power |
| `aif:spec:incomingPowerFeeds` | float | Incoming power feeds |
| `aif:spec:redundancyScheme` | string | Redundancy scheme |
| `aif:spec:powerTransferDevice` | float | Power transfer device |
| `aif:spec:powerTransferDesign` | float | Power transfer design |
| `aif:spec:breaker` | string | Breaker |
| `aif:spec:fuse` | string | Fuse |
| `aif:spec:disconnect` | string | Disconnect |
| `aif:spec:motorSize` | string | Motor / pump size |
| `aif:spec:motorPowerInfo` | float | Motor / pump power info |
| `aif:spec:ratedVoltageRotatingEquipment` | float | Rated voltage rotating equipment |
| `aif:spec:ratedHp` | string | Rated HP |
| `aif:spec:powerFactorRotatingEquipment` | float | Power factor rotating equipment |
| `aif:spec:efficiencyRotatingEquipment` | float | Efficiency of rotating equipment |
| `aif:spec:auxiliaryPowerSourceAndConnections` | float | Auxiliary power source and connections |
| `aif:spec:controlWiresForExternalComm` | float | Control wires for external communication |
| `aif:spec:controlHmi` | string | Control HMI |

::::

::::{dropdown} CRAH (Computer Room Air Handler) — 31 attributes
:icon: list-unordered

| Attribute | Type | Description |
|---|---|---|
| `aif:spec:faceArea` | float | Face area in m² |
| `aif:spec:nominalCoolingCapacity` | float | Nominal cooling capacity in kW |
| `aif:spec:totalCapacity` | float | Total capacity in kW |
| `aif:spec:sensibleCapacity` | float | Sensible capacity in kW |
| `aif:spec:flowRate` | float | Flow rate in GPM |
| `aif:spec:returnAirVolume` | float | Return air volume in ACFM |
| `aif:spec:fanMotorPowerMax` | float | Fan motor power max in kW |
| `aif:spec:unitPressureDrop` | float | Unit pressure drop (ft of water) |
| `aif:spec:externalStaticUnitPressure` | float | External static unit pressure in Pa |
| `aif:spec:electricalPanelAccess` | float | Electrical panel access in mm |
| `aif:spec:nominalAirVolume` | float | Nominal air volume in CFM |
| `aif:spec:maximumHp` | float | Fan motor maximum horsepower |
| `aif:spec:numberOfFans` | int | Number of EC fans |
| `aif:spec:numberOfRows` | int | Number of rows of chilled water coil |
| `aif:spec:faceVelocity` | float | Face velocity in FPM of chilled water coil |
| `aif:spec:primaryPipeDiameter` | float | Primary pipe diameter |
| `aif:spec:secondaryPipeDiameter` | float | Secondary pipe diameter |
| `aif:spec:pipingConnection` | string | Piping connection (top and bottom) |
| `aif:spec:primaryControl` | string | Primary control |
| `aif:spec:powerSupply` | float | Power supply |
| `aif:spec:electricalNominalVoltage` | float | Electrical nominal voltage |
| `aif:spec:electricalCurrent` | float | Electrical current |
| `aif:spec:electricalFrequency` | float | Electrical frequency in Hz |
| `aif:spec:electricalPowerRating` | float | Electrical power rating |
| `aif:spec:electricalPhase` | int | Electrical phase |
| `aif:spec:electricalPanelOptions` | string | Electrical panel options |
| `aif:spec:humidification` | string | Humidification |
| `aif:spec:airFilter` | string | Air filter |
| `aif:spec:coil` | string | Coil name |
| `aif:spec:highVoltageOptions` | float | High voltage options |
| `aif:spec:monitoring` | string | Monitoring type |

::::

::::{dropdown} UPS (Uninterruptible Power Supply) — 31 attributes
:icon: list-unordered

| Attribute | Type | Description |
|---|---|---|
| `aif:spec:upsRating` | float | UPS rating in kW |
| `aif:spec:outputActivePower` | float | Output active power at 104°F (kW) |
| `aif:spec:electricalInputVoltage` | float | Electrical nominal voltage in V |
| `aif:spec:electricalCurrent` | float | Electrical current |
| `aif:spec:inputCurrentDistortion` | float | Input current distortion (THDi) at nominal voltage at full load |
| `aif:spec:electricalInputFrequency` | float | Electrical input frequency in Hz |
| `aif:spec:electricalInputPhase` | int | Electrical input phase |
| `aif:spec:inputPowerFactor` | float | Electrical power factor |
| `aif:spec:electricalPowerWalkIn` | float | Power walk-in (seconds) |
| `aif:spec:batteryType` | string | Battery type |
| `aif:spec:batteryFloatVoltage` | float | Battery float voltage (V) |
| `aif:spec:dcRippleVoltage` | float | DC ripple at float voltage |
| `aif:spec:nominalBatteryBus` | string | Nominal battery bus |
| `aif:spec:temperatureCompensatedBatteryCharging` | float | Temperature-compensated battery charging |
| `aif:spec:loadPowerFactor` | float | Load power factor supported (without derating) |
| `aif:spec:outputVoltage` | float | Output voltage |
| `aif:spec:electricalOutputFrequency` | float | Electrical output frequency in Hz |
| `aif:spec:electricalOutputPhase` | int | Electrical output phase |
| `aif:spec:outputThdNominalVoltage` | float | Output THD at nominal voltage at RMS value |
| `aif:spec:outputThdNominalVoltageWithNonLinearLoad` | float | Output THD at nominal voltage including a 100kVA non-linear load per IEC 6204 at RMS value |
| `aif:spec:transientRecoveryLoad` | string | Transient recovery 100 load step |
| `aif:spec:voltageDisplacement` | float | Voltage displacement |
| `aif:spec:overloadAtNominalVoltage` | float | Overload at nominal voltage and 77°F (25°C) |
| `aif:spec:upsEnclosureClass` | string | UPS enclosure class with and without front door open |
| `aif:spec:color` | string | Color |
| `aif:spec:operatingTemperature` | float | Operating temperature in °C |
| `aif:spec:relativeHumidity` | float | Relative humidity non-condensing |
| `aif:spec:operatingAltitude` | float | Operating altitude without derating |
| `aif:spec:communicationOptions` | float | Communication options |
| `aif:spec:cardCompatibility` | string | Card compatibility |
| `aif:spec:protocolsAvailable` | string | Protocols available |

::::

::::{dropdown} GB300 Rack (Compute Rack) — 18 attributes
:icon: list-unordered

| Attribute | Type | Units | Description |
|---|---|---|---|
| `aif:spec:namePlatePower` | int | W | Nameplate power rating |
| `aif:spec:requiredAirFlowRate` | float3_array | m³/s | Required air flow rate curve [Inlet Temp (°C), Flow] |
| `aif:spec:requiredLiquidFlowRate` | float3_array | LPM | Required liquid flow rate curve [Inlet Temp (°C), Flow (L/s), Flow (LPM)] |
| `aif:spec:heatCaptureRatio` | float | % | Percentage of total heat captured by liquid cooling |
| `aif:spec:liquidSidePqCurve` | string | — | Liquid-side pressure drop curve: y = pressure drop (kPa) as a function of x = flow rate (LPM) |
| `aif:spec:significantInternalStructure` | string | — | Significant internal structure |
| `aif:spec:doorsPerforations` | string | — | Door perforations |
| `aif:spec:numGPUs` | int | — | Number of discrete GPUs in rack |
| `aif:spec:maxPowerDcEdpp2` | float | kW | Max. power DC EDPP2 |
| `aif:spec:maxPowerDcEdpp1` | float | kW | Max. power DC EDPP1 |
| `aif:spec:maxPowerDcTdp` | float | kW | Max. power DC thermal design power |
| `aif:spec:maxPowerAcEdpp1` | float | kW | Max. power AC EDPP1 |
| `aif:spec:idlePowerDefault30Pct` | float | kW | Idle power at default 30% utilization |
| `aif:spec:idlePowerSmoothing90Pct` | float | kW | Idle power with power smoothing at 90% utilization |
| `aif:spec:rampUpRateDefault` | float | W/sec/GPU | Default ramp-up rate |
| `aif:spec:rampDownRateDefault` | float | W/sec/GPU | Default ramp-down rate |
| `aif:spec:liquidCooling` | float | kW | Liquid cooling |
| `aif:spec:airCooling` | float | kW | Air cooling |

::::

```{toctree}
:maxdepth: 1

Requirements <requirements>
```
