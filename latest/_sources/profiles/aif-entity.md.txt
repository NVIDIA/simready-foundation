# AIF-Entity Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`AIF-Entity` profile. A single profile covers all of the currently defined
NVIDIA AI Factory data center equipment classes. This set will continue to grow
and evolve as more equipment types are added; for now it covers the Coolant
Distribution Unit (CDU), Computer Room Air Handler (CRAH), Uninterruptible Power
Supply (UPS), and Compute Rack. Equipment-class differentiation is
driven by the `aif:core:assetClass` property and data-driven validation, not by
separate profiles.

## Profile definition

The `AIF-Entity` profile includes the following feature set (see `aif_entity.toml`
and the [feature dependency graph](../features/feature-dependency-graph)). Each
feature's requirements and dependencies are defined in the feature
specifications.

```toml
[AIF-Entity]
"0.1.0" = {features = [
    {"FET_000_STANDARD" = {version = "0.1.0"}},       # Core
    {"FET_001_STANDARD" = {version = "1.0.0"}},       # Minimal Placeable Visual
    {"FET200_AIF" = {version = "0.1.0"}},     # Core Metadata (capability; interim feature carrier)
    {"FET201_AIF" = {version = "0.1.0"}},     # Connection Points (capability; interim feature carrier)
    {"FET202_AIF" = {version = "0.1.0"}},     # Thermal Cooling (feature; assetClass-gated to CDU/CRAH)
    {"FET203_AIF" = {version = "0.1.0"}},     # Electrical (feature; assetClass-gated)
]}
"0.2.0" = {features = [ # Connection Points v0.2.0 (CP.010-CP.012 replace the v0.1.0 CP.002/CP.004 geometry and naming rules) and SimReady Central publishing (FET_031/FET_033)
    {"FET_000_STANDARD" = {version = "0.2.0"}},       # Core, without SR.001 and NP.006
    {"FET_001_STANDARD" = {version = "1.0.0"}},       # Minimal Placeable Visual
    {"FET200_AIF" = {version = "0.1.0"}},     # Core Metadata (capability; interim feature carrier)
    {"FET201_AIF" = {version = "0.2.0"}},     # Connection Points (capability; interim feature carrier)
    {"FET202_AIF" = {version = "0.2.0"}},     # Thermal Cooling (feature; assetClass-gated to CDU/CRAH)
    {"FET203_AIF" = {version = "0.2.0"}},     # Electrical (feature; assetClass-gated)
    {"FET_031_STANDARD" = {version = "0.1.0"}},       # Self-contained Package Source (AA.001)
    {"FET_033_STANDARD" = {version = "0.4.0"}},       # Thumbnail (SR.002) and USD/sidecar provenance union (SR.004)
]}
```

An asset authored to the v0.1.0 connection point vocabulary validates against
`AIF-Entity` 0.1.0, and one authored to v0.2.0 validates against 0.2.0. The two
never run together: CP.004 checks prim names against the
`<vendor>_<type>_<suffix>` pattern, which a v0.2.0 asset does not follow, and
CP.010 requires an Xform, which a v0.1.0 Plane or Disk mesh is not.

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
| `Compute Rack` | No | No | Metadata and connection points only |

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

Each rule below says which requirement enforces it. A rule marked *guideline*
is convention: following it makes an asset consistent with the rest of the
library, but no validator reports on it.

- The root stage must include a sublayer whose file name contains `properties`
  (`AM.001`) and one whose file name contains `connectionpoints` (`CP.005`).
  Both matches are case-insensitive. The geometry sublayer is a *guideline*.
- All layer paths must be relative. *Guideline.*
- `defaultPrim` must be set on the root layer, which every connection point
  rule starts from (`CP.001`), and on the properties sublayer (`AM.001`).
  Other layers: *guideline*.

## Naming conventions

### Prim naming

- Use `PascalCase` for prim names (e.g., `ConnectionPoints`). *Guideline.*
  The one prim name a validator checks is `ConnectionPoints` itself, which
  `CP.001` requires exactly.
- The default prim name should match the asset model identifier. *Guideline.*

### File naming

- Use the asset model identifier as the base name (e.g., `Generic_CRAH`).
  *Guideline.*
- Sublayer files: `<AssetName>_Properties.usda`, `<AssetName>_ConnectionPoints.usd`,
  `<AssetName>_Geometry.usd`. Validated only as far as the substrings above
  (`AM.001`, `CP.005`); the `<AssetName>_` prefix and the geometry file are
  *guideline*.
- Use lowercase for all file extensions. *Guideline.* `CP.005` accepts `.usd`,
  `.usda` and `.usdc` in any case.

### Connection point naming

Under `AIF-Entity` 0.1.0 these are enforced by `CP.004`. Under 0.2.0 the
connection point is described by its properties instead (`CP.010` to `CP.012`)
and the prim name is a *guideline*.

- Pattern: `<vendor>_<type>_<suffix>` (e.g., `acme_fws_supply_01`). `CP.004`.
- Vendor prefix: lowercase alphanumeric, words joined by `_`. `CP.004`.
- Valid type prefixes depend on the equipment class (see the Connection Points
  capability). `CP.004`.

## Root-layer metadata

AIF's own metadata lives in `aif:core:*` and `aif:spec:*` attributes on the
properties sublayer's default prim. The root-layer contract is separate, comes from
tier_core, and reads the root layer's `customLayerData`. The two profile versions
use different requirements for it:

| Profile version | Requirement | What it requires |
|---|---|---|
| 0.1.0 | [SR.001](../capabilities/core/sim_ready/requirements/metadata-whitelist.md), through `FET_000_STANDARD@0.1.0` | Five entries at the top level of `customLayerData`: the `SimReady_Metadata` dictionary itself, and `asset_name`, `asset_type`, `source_file` and `usd_date_generated` beside it |
| 0.2.0 | [SR.004](../capabilities/core/sim_ready/requirements/metadata-union.md), through `FET_033_STANDARD@0.4.0` | Eleven provenance fields in the union of root-layer `customLayerData` and a sibling `<usd stem>.json`, each field authored in exactly one of those two locations |

0.2.0 selects two further requirements for publishing to SimReady Central:
[SR.002](../capabilities/core/sim_ready/requirements/thumbnail-exist.md) requires a
thumbnail at `.thumbs/256x256/<usd file name>.png` beside the asset, and AA.001
through `FET_031_STANDARD@0.1.0` requires the package source to be self-contained.

An asset can satisfy both versions at once. SR.004 reads a nested
`SimReady_Metadata` dictionary and the top level of `customLayerData` as one side of
its comparison, and the sidecar as the other, so the four top-level fields SR.001
requires are not duplicates of their nested copies. A field authored in both the USD
and the sidecar is a failure.

```usd
customLayerData = {
    string asset_name = "Generic_CRAH"
    string asset_type = "equipment"
    string source_file = "Generic_CRAH.usd"
    string usd_date_generated = "2026-09-11"

    dictionary SimReady_Metadata = {
        string author = "nvidia"
        string asset_name = "Generic_CRAH"
        string asset_type = "equipment"
        string asset_license = "CC-BY 4.0"
        string category = "CRAH"
        string source_file = "Generic_CRAH.usd"
        string usd_date_generated = "2026-09-11"
        string qcode = "Q2479079"
        int rigid_body_count = 0
        float3 asset_extents = (1.84, 0.86, 1.974)
        float mass = 545.0

        dictionary validation = {
            string profile = "AIF-Entity"
            string profile_version = "0.1.0"
        }
    }
}
```

`asset_extents` is in metres, so it is `aif:core:overallGeometryDimensions` divided by
1000. `mass` is `aif:core:weight` in kilograms. `category` is `aif:core:assetClass`.
`qcode` is the Wikidata entity for the equipment class rather than for the product.
SR.004 checks only that it matches `^Q[0-9]+$`, so a wrong entity passes; resolve it
against Wikidata rather than guessing.

The nested `validation` dictionary is optional and records which profile the asset was
authored against.

## References

- [Feature dependency graph](../features/feature-dependency-graph)
- `aif_entity.toml`, the profile definition alongside this document
- [AIF Core Metadata capability](../capabilities/aif/metadata/capability-metadata)
- [Connection Points capability](../capabilities/aif/connection_points/capability-connection_points)
- [Thermal Cooling capability](../capabilities/aif/thermal_cooling/capability-thermal_cooling)
- [Electrical capability](../capabilities/aif/electrical/capability-electrical)
- [Thermal Cooling feature](../features/FET_202-thermal_cooling)
- [Electrical feature](../features/FET_203-electrical)
- [metadata-union (SR.004)](../capabilities/core/sim_ready/requirements/metadata-union.md)
- [thumbnail-exist (SR.002)](../capabilities/core/sim_ready/requirements/thumbnail-exist.md)
