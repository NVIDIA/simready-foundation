# AIF-Entity Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`AIF-Entity` profile. A single profile covers all of the currently defined
NVIDIA AI Factory data center equipment classes. This set will continue to grow
and evolve as more equipment types are added; for now it covers the Coolant
Distribution Unit (CDU), Computer Room Air Handler (CRAH), Uninterruptible Power
Supply (UPS), and Compute Rack (e.g. GB300). Equipment-class differentiation is
driven by the `aif:core:assetClass` property and data-driven validation, not by
separate profiles.

## Profile definition

The `AIF-Entity` profile includes the following feature set (see `profiles.toml`
and the [feature dependency graph](../features/feature-dependency-graph)). Each
feature's requirements and dependencies are defined in the feature
specifications.

```toml
[AIF-Entity]
"0.1.0" = {features = [
    {"FET000_CORE" = {version = "0.1.0"}},            # Core
    {"FET001_BASE_NEUTRAL" = {version = "1.0.0"}},    # Minimal Placeable Visual
    {"FET200_AIF_NEUTRAL" = {version = "0.1.0"}},     # Core Metadata (capability; interim feature carrier)
    {"FET201_AIF_NEUTRAL" = {version = "0.1.0"}},     # Connection Points (capability; interim feature carrier)
    {"FET202_AIF_NEUTRAL" = {version = "0.1.0"}},     # Thermal Cooling (feature; assetClass-gated to CDU/CRAH)
    {"FET203_AIF_NEUTRAL" = {version = "0.1.0"}},     # Electrical (feature; assetClass-gated)
]}
```

### Features and capabilities

The `AIF-Entity` profile composes two kinds of rule set:

- **Features** (These rule sets change simulation output):
  [Thermal Cooling](../features/FET_202-thermal_cooling) (`FET202`) and
  [Electrical](../features/FET_203-electrical) (`FET203`). These are gated by
  `aif:core:assetClass` -- thermal applies to CDU and CRAH; electrical applies
  to CDU, CRAH, and UPS.
- **Capabilities** (These rule sets organize and validate, without changing
  simulation output): [AIF Core Metadata](../capabilities/aif/metadata/capability-metadata)
  and [Connection Points](../capabilities/aif/connection_points/capability-connection_points).

```{note}
NOTE: The AIF Core Metadata and Connection Points rules are currently carried
inline in the `FET200`/`FET201` feature JSON as an interim measure so they still
validate, until SRF supports Profile-to-Capability referencing.
```

## Equipment-class differentiation

A single profile validates all four equipment classes. The
`aif:core:assetClass` property selects which expected attribute set and
connection-point types apply. The validators read `assetClass`, look up the
per-class expectations from configuration, and validate generically.

| `aif:core:assetClass` | Thermal | Electrical | Notes |
|-----------------------|---------|------------|-------|
| `CDU` | Yes | Yes | Facility/technology water loops; full attribute set |
| `CRAH` | Yes | Yes | Air-side cooling; liquid connection points |
| `UPS` | No | Yes | Power conditioning; no thermal loop |
| `Rack` | No | No | Compute rack (e.g. GB300); metadata + connection points |

## Required USD properties and schemas

### Stage metadata (required)

- `defaultPrim` must be set on every layer.
- `upAxis = "Z"` and `metersPerUnit = 1` must be set on every stage.

### AIF core attributes (required on default prim in `*Properties.usda`)

Set `aif:core:assetClass` to identify the equipment class (`"CDU"`, `"CRAH"`,
`"UPS"`, or `"Rack"`). The full `aif:core:*` identity, dimension, and
documentation attribute set, plus the `aif:spec:*` attributes defined for the
declared equipment class, must be present. See the
[AIF Core Metadata capability](../capabilities/aif/metadata/capability-metadata) for
the authoritative attribute list and the per-class `aif:spec:*` requirements
validated by AM.007 (equipment-class template compliance).

### Connection points (required)

Connection point prims must be authored under a `ConnectionPoints` Scope prim
directly beneath the default prim, following the `<vendor>_<type>_<suffix>`
naming pattern (e.g. `nvidia_fws_supply_01`) and composed as a separate
`<AssetName>_ConnectionPoints.usd` sublayer. The valid connection-point types
depend on the equipment class. See the
[Connection Points capability](../capabilities/aif/connection_points/capability-connection_points)
for the authoritative type enumeration per class.

## Stage composition requirements

```
<AssetName>.usd                    <- root stage (sublayer references only)
  <AssetName>_Properties.usda      <- all aif:core:* and aif:spec:* attributes
  <AssetName>_ConnectionPoints.usd <- ConnectionPoints Scope prim and children
  <AssetName>_Geometry.usd         <- mesh geometry (or references to it)
```

- The root stage must reference `*Properties.usda` and `*ConnectionPoints.usd` as sublayers.
- All layer paths must be relative.
- `defaultPrim` must be set on every layer.

## Naming conventions

### Prim naming

- Use `PascalCase` for prim names (e.g., `CW375`, `ConnectionPoints`).
- The default prim name should match the asset model identifier.

### File naming

- Use the asset model identifier as the base name (e.g., `CW375`).
- Sublayer files: `<AssetName>_Properties.usda`, `<AssetName>_ConnectionPoints.usd`, `<AssetName>_Geometry.usd`.
- Use lowercase for all file extensions.

### Connection point naming

- Pattern: `<vendor>_<type>_<suffix>` (e.g., `nvidia_fws_supply_01`).
- Vendor prefix: lowercase alphanumeric only.
- Valid type prefixes depend on the equipment class (see the Connection Points capability).

## Validation metadata (recommended)

Include profile metadata in `customLayerData` to simplify validation workflows:

```usd
customLayerData = {
    dictionary SimReady_Metadata = {
        dictionary validation = {
            string profile = "AIF-Entity"
            string profile_version = "0.1.0"
        }
    }
}
```

## References

- [Feature dependency graph](../features/feature-dependency-graph)
- `nv_core/sr_specs/docs/profiles/profiles.toml`
- [AIF Core Metadata capability](../capabilities/aif/metadata/capability-metadata)
- [Connection Points capability](../capabilities/aif/connection_points/capability-connection_points)
- [Thermal Cooling capability](../capabilities/aif/thermal_cooling/capability-thermal_cooling)
- [Electrical capability](../capabilities/aif/electrical/capability-electrical)
- `nv_core/sr_specs/docs/features/FET_202-thermal_cooling.md`
- `nv_core/sr_specs/docs/features/FET_203-electrical.md`
