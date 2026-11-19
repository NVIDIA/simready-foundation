# connection-point-domain-namespace

| Code     | CP.012 |
|----------|--------|
| Validator| {oav-validator-latest-link}`cp-012` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`normative` |

## Summary

A connection point's domain-specific properties must sit in the namespace named by its `simready:connectionPoint:domain` value, and a production-complete connection point carries every property that namespace defines.

## Description

Each domain namespace carries two kinds of property: the physical geometry of that class of connection, and the operating parameters a simulation tool needs to set up an analysis. A connection declaring `domain = "thermal"` carries `simready:connectionPoint:thermal:` properties; authoring `electrical:` properties on it is an error.

Physical geometry lives in the domain namespaces rather than the base namespace because port dimensions differ in shape across domains. Thermal ports are circular and take a diameter; network ports are rectangular and take width and height; hardwired electrical connections have no port dimension at all.

### Thermal domain (`simready:connectionPoint:thermal:`)

For piped fluid connections: cooling loops, condensate, chilled water. In datacenter usage "thermal" means liquid cooling. Air is the separate airflow domain.

| Property | Type | Description |
|----------|------|-------------|
| `thermal:portDiameter` | float (meters) | Internal pipe diameter |
| `thermal:matingDepth` | float (meters) | Flange engagement or coupling insertion depth |
| `thermal:designFlowRate` | float (L/s) | Nominal operating flow rate |
| `thermal:maxFlowRate` | float (L/s) | Rated maximum flow rate |
| `thermal:designTemperature` | float (Celsius) | Nominal operating temperature at this connection |
| `thermal:maxTemperature` | float (Celsius) | Rated temperature limit |
| `thermal:operatingPressure` | float (Pa, gauge) | Nominal operating pressure |
| `thermal:maxPressure` | float (Pa, gauge) | Rated pressure limit |
| `thermal:fluidType` | token | Working fluid, encoding concentration where relevant: `water`, `glycol_water_25`, `glycol_water_30`, `glycol_water_50`, `refrigerant_R410A`, `refrigerant_R134a`, `refrigerant_R454B`, `dielectric` |
| `thermal:flangeRating` | token | Flange standard designation (e.g. `ANSI_150`) |
| `thermal:flangeSize` | token | Nominal pipe size designation (e.g. `NPS4`) |

`fluidType` is a single descriptive token rather than a fluid name plus a separate concentration. Emerging refrigerant blends make concentration a poor standalone property, and the fluid name is what a simulation tool looks up. New tokens follow the pattern `{fluid_category}_{specifier}`.

### Electrical domain (`simready:connectionPoint:electrical:`)

For power connections: mains feeds, PDU outputs, UPS bypass.

| Property | Type | Description |
|----------|------|-------------|
| `electrical:matingDepth` | float (meters) | Plug insertion depth; `0.0` for hardwired connections |
| `electrical:nominalVoltage` | float (V) | Site-specific nominal voltage |
| `electrical:maxCurrent` | float (A) | Rated maximum current draw |
| `electrical:phases` | int | Number of phases, typically 3 for datacenter equipment |
| `electrical:frequency` | float (Hz) | Line frequency, 50 or 60 Hz, site-specific |
| `electrical:connectorType` | token | Physical connection method (e.g. `hardwired`, `IEC_60309`, `NEMA_L21_30`, `dry_contact`) |
| `electrical:ratedPower` | float (W) | Rated power capacity of this connection |
| `electrical:breakerRating` | float (A) | Upstream breaker protection rating |
| `electrical:powerFactor` | float (0-1) | Manufacturer-specified power factor |

Dry contacts are the documented exception to completeness. A dry contact is a relay output with no voltage of its own that opens or closes a circuit to signal a condition. It uses `connectorType = "dry_contact"`, populates `nominalVoltage` and `maxCurrent` as switching limits, and omits `phases`, `frequency` and `powerFactor`, which describe power distribution and have no meaning here.

### Network domain (`simready:connectionPoint:network:`)

For data and control connections: high-speed compute fabric, management, building management.

| Property | Type | Description |
|----------|------|-------------|
| `network:portWidth` | float (meters) | Connector opening width |
| `network:portHeight` | float (meters) | Connector opening height |
| `network:matingDepth` | float (meters) | Plug insertion depth |
| `network:portType` | token | Physical connector type (e.g. `RJ45`, `SFP_plus`, `QSFP28`, `QSFP_DD`, `OSFP`) |
| `network:protocol` | token | Communication protocol (e.g. `BACnet_IP`, `Modbus_TCP`, `SNMP`, `Ethernet`) |
| `network:dataRate` | token | Maximum data rate (e.g. `100Mbps`, `25GbE`, `100GbE`, `400GbE`, `800GbE`) |
| `network:medium` | token | Physical medium (e.g. `copper`, `fiber`, `DAC`) |
| `network:fabricRole` | token | Role in the network fabric (e.g. `compute`, `storage`, `mgmt`, `bms`) |
| `network:supportedLineRates` | token[] | Supported line rate configurations |
| `network:supportedConfigurations` | token[] | Breakout configurations (e.g. `1x800G`, `2x400G`, `4x200G`) |
| `network:allowedTransceivers` | token[] | Compatible transceiver types (e.g. `DR4`, `FR4`, `LR4`) |
| `network:hotPlugCapable` | bool | Whether the port supports hot-plug |

### Airflow domain (`simready:connectionPoint:airflow:`)

For air intake and exhaust: equipment ventilation, hot and cold aisle faces, CRAH and CRAC supply and return. Most datacenter equipment rejects some heat to the surrounding air even when liquid-cooled, so a CFD tool modelling the data hall needs to know where air enters and leaves each unit, at what volume and temperature.

| Property | Type | Description |
|----------|------|-------------|
| `airflow:interfaceWidth` | float (meters) | Width of the contiguous airflow interface region |
| `airflow:interfaceHeight` | float (meters) | Height of the contiguous airflow interface region |
| `airflow:freeAreaRatio` | float (0-1) | Fraction of the interface area open to airflow, e.g. `0.7` for a 70% perforated panel |
| `airflow:designAirflowRate` | float (m^3/s) | Nominal airflow volume rate through this interface |
| `airflow:maxAirflowRate` | float (m^3/s) | Rated maximum airflow volume rate |
| `airflow:designTemperature` | float (Celsius) | Expected air temperature at this interface under nominal conditions |
| `airflow:maxTemperature` | float (Celsius) | Rated air temperature limit |
| `airflow:staticPressure` | float (Pa, differential) | Pressure differential across the interface or filter |
| `airflow:filterType` | token | Filter specification if present (e.g. `MERV_8`, `none`) |

### Property completeness

Every property defined in a domain namespace should be present on every connection of that domain, including where the value is zero. A hardwired electrical connection has no plug to insert, so it authors `matingDepth = 0.0` rather than omitting the property.

Zero is a measured value like any other: it says the quantity is zero. Omitting the property says nothing at all, and leaves a consumer unable to tell a property that does not apply to this connection from one nobody has authored yet.

### Validation profiles

Completeness is the target state, and assets reach it incrementally as engineering data arrives from datasheets, PLM systems and SME input. Validators report which of three profiles an asset satisfies:

| Profile | Content | Validator behaviour |
|---------|---------|--------------------|
| **Stub** | All five base properties, no domain properties | Reported as incomplete, with the number of properties outstanding |
| **Draft** | All five base properties and at least one domain property | Each missing domain property is named in a warning |
| **Production** | All base properties and every domain property defined for the declared domain | No issue reported |

Stub and draft let assets enter the pipeline before the engineering data exists. A connection point must reach production completeness before it is simulation-ready and before it enters the SimReady catalog. Validation reports which profile a connection point reaches; it does not fail on an incomplete one.

## Why is it required?

- A simulation tool reads its boundary conditions straight from the connection point, so a partially populated namespace means a manual data-entry step per asset
- Namespacing by domain lets a consumer filter to the connections it cares about without knowing anything about the equipment class
- Per-connection values replace the v0.1.0 pattern of one unit-level number, so a CDU with four ports at different diameters can be described accurately
- The three profiles keep progressive authoring honest by naming what is missing, instead of an asset appearing complete because absent properties look like inapplicable ones

## Examples

One production-complete connection per domain, each as a complete stage. The
values are the ones the tier's own `Synthetic_CP2_*` fixtures carry, so the
examples and the fixtures cannot drift apart. The five base-namespace
properties come first in each block; everything after them is the domain
namespace.

### Valid: thermal, a facility-water supply flange on a CDU

```usd
def Xform "Generic_CDU"
{
    def Scope "ConnectionPoints"
    {
        def Xform "acme_thermal_main"
        {
            uniform token purpose = "guide"
            token simready:connectionPoint:domain = "thermal"
            token simready:connectionPoint:direction = "supply"
            token simready:connectionPoint:system = "FWS"
            token simready:connectionPoint:disconnectType = "flanged"
            float simready:connectionPoint:serviceClearance = 0.6

            float simready:connectionPoint:thermal:portDiameter = 0.05
            float simready:connectionPoint:thermal:matingDepth = 0.02
            float simready:connectionPoint:thermal:designFlowRate = 12.5
            float simready:connectionPoint:thermal:maxFlowRate = 15.0
            float simready:connectionPoint:thermal:designTemperature = 18.0
            float simready:connectionPoint:thermal:maxTemperature = 25.0
            float simready:connectionPoint:thermal:operatingPressure = 400000
            float simready:connectionPoint:thermal:maxPressure = 1000000
            token simready:connectionPoint:thermal:fluidType = "water"
            token simready:connectionPoint:thermal:flangeRating = "ANSI_150"
            token simready:connectionPoint:thermal:flangeSize = "NPS4"
        }
    }
}
```

### Valid: electrical, a hardwired three-phase feed on a UPS

`matingDepth` is an explicit zero: a hardwired feed has no connector to mate.
Omitting it instead would leave the connection at draft completeness.

```usd
def Xform "Generic_UPS"
{
    def Scope "ConnectionPoints"
    {
        def Xform "acme_electrical_main"
        {
            uniform token purpose = "guide"
            token simready:connectionPoint:domain = "electrical"
            token simready:connectionPoint:direction = "input"
            token simready:connectionPoint:system = "power"
            token simready:connectionPoint:disconnectType = "hardwired"
            float simready:connectionPoint:serviceClearance = 0.6

            float simready:connectionPoint:electrical:matingDepth = 0.0
            float simready:connectionPoint:electrical:nominalVoltage = 480.0
            float simready:connectionPoint:electrical:maxCurrent = 1458.0
            int simready:connectionPoint:electrical:phases = 3
            float simready:connectionPoint:electrical:frequency = 60.0
            token simready:connectionPoint:electrical:connectorType = "hardwired"
            float simready:connectionPoint:electrical:ratedPower = 1200000.0
            float simready:connectionPoint:electrical:breakerRating = 2000.0
            float simready:connectionPoint:electrical:powerFactor = 0.99
        }
    }
}
```

### Valid: network, an OSFP port on a compute rack

```usd
def Xform "Generic_ComputeRack"
{
    def Scope "ConnectionPoints"
    {
        def Xform "acme_network_main"
        {
            uniform token purpose = "guide"
            token simready:connectionPoint:domain = "network"
            token simready:connectionPoint:direction = "bidirectional"
            token simready:connectionPoint:system = "high_speed_data"
            token simready:connectionPoint:disconnectType = "OSFP"
            float simready:connectionPoint:serviceClearance = 0.6

            float simready:connectionPoint:network:portWidth = 0.022
            float simready:connectionPoint:network:portHeight = 0.009
            float simready:connectionPoint:network:matingDepth = 0.015
            token simready:connectionPoint:network:portType = "OSFP"
            token simready:connectionPoint:network:protocol = "Ethernet"
            token simready:connectionPoint:network:dataRate = "800GbE"
            token simready:connectionPoint:network:medium = "fiber"
            token simready:connectionPoint:network:fabricRole = "compute"
            token[] simready:connectionPoint:network:supportedLineRates = ["800GbE", "400GbE"]
            token[] simready:connectionPoint:network:supportedConfigurations = ["1x800G", "2x400G"]
            token[] simready:connectionPoint:network:allowedTransceivers = ["DR4", "FR4"]
            bool simready:connectionPoint:network:hotPlugCapable = 1
        }
    }
}
```

### Valid: airflow, the intake face of a CRAH

```usd
def Xform "Generic_CRAH"
{
    def Scope "ConnectionPoints"
    {
        def Xform "acme_airflow_main"
        {
            uniform token purpose = "guide"
            token simready:connectionPoint:domain = "airflow"
            token simready:connectionPoint:direction = "input"
            token simready:connectionPoint:system = "equipment_cooling"
            token simready:connectionPoint:disconnectType = "open_vent"
            float simready:connectionPoint:serviceClearance = 0.6

            float simready:connectionPoint:airflow:interfaceWidth = 0.6
            float simready:connectionPoint:airflow:interfaceHeight = 2.0
            float simready:connectionPoint:airflow:freeAreaRatio = 0.7
            float simready:connectionPoint:airflow:designAirflowRate = 1.07
            float simready:connectionPoint:airflow:maxAirflowRate = 1.28
            float simready:connectionPoint:airflow:designTemperature = 24.0
            float simready:connectionPoint:airflow:maxTemperature = 45.0
            float simready:connectionPoint:airflow:staticPressure = 50.0
            token simready:connectionPoint:airflow:filterType = "none"
        }
    }
}
```

### Warned: a draft connection, one domain property authored

The five base properties and a single thermal property. The validator reports
the connection as draft and names the ten properties still missing. That is a
warning, not a failure: the asset is in the pipeline, not yet simulation-ready.

```usd
def Xform "Generic_CDU"
{
    def Scope "ConnectionPoints"
    {
        def Xform "acme_thermal_main"
        {
            uniform token purpose = "guide"
            token simready:connectionPoint:domain = "thermal"
            token simready:connectionPoint:direction = "supply"
            token simready:connectionPoint:system = "FWS"
            token simready:connectionPoint:disconnectType = "flanged"
            float simready:connectionPoint:serviceClearance = 0.6

            float simready:connectionPoint:thermal:designFlowRate = 12.5
        }
    }
}
```

### Invalid: a property from another domain's namespace

A thermal connection carrying an `electrical:` property. The namespace does not
match the declared domain, and that is a failure regardless of completeness.

```usd
def Xform "Generic_CDU"
{
    def Scope "ConnectionPoints"
    {
        def Xform "acme_thermal_main"
        {
            uniform token purpose = "guide"
            token simready:connectionPoint:domain = "thermal"
            token simready:connectionPoint:direction = "supply"
            token simready:connectionPoint:system = "FWS"
            token simready:connectionPoint:disconnectType = "flanged"
            float simready:connectionPoint:serviceClearance = 0.15

            float simready:connectionPoint:electrical:nominalVoltage = 480.0
        }
    }
}
```

## How to comply

1. Read the `simready:connectionPoint:domain` value on the connection point
2. Author properties from that domain's namespace only
3. Author every property the namespace defines, using an explicit zero where the value is not physically meaningful
4. Convert datasheet values to SI at authoring time: meters, Celsius, Pascals, L/s, m^3/s, volts, amperes, watts, hertz
5. Where engineering data is not yet available, expect the validator to report stub or draft and treat it as work outstanding

## Related requirements

- CP.010 `connection-point-prim-structure`: establishes the Xform and the mandatory `domain` property this requirement keys off
- CP.011 `connection-point-base-namespace`: the base namespace that a stub-profile connection point satisfies on its own

## For More Information

- [SimReady units and scale](https://docs.omniverse.nvidia.com/usd/latest/learn-openusd/independent/asset-structure-principles.html)
