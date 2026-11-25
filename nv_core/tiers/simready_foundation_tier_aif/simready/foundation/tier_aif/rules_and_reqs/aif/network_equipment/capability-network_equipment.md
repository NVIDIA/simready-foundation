# AIF Network Equipment

**Capability:** AIF Network Equipment (NET)

## Overview

Defines physical equipment identity and logical node configuration used before
DSX Air simulation starts. Network interfaces use Connection Points 0.2.0.
This is a non-standard data capability in the AIF tier; it introduces no runtime
behavior or simulator adapter.

| Requirement | Purpose |
|---|---|
| NET.001 | Typed network-equipment identity and physical metadata |
| NET.002 | Typed node allocation and optional image reference |
| NET.003 | At least one discoverable network connection point |
| NET.004 | Unconditional class eligibility for the dedicated Networking profile |

## Scope and review status

The initial 0.3.0 contract is proposed for review under OMPE-119214. CPU allocation
is a positive integer whose CPU unit and supported DSX Air range remain unresolved.
Memory uses MB and storage uses GB as requested by the source; byte-base mapping,
supported images and node models require consumer review. The validator proves
local data structure, types and elementary bounds, not DSX Air acceptance or
engineering plausibility. OS image references are preserved as opaque strings;
image availability, bootability and licensing are outside offline validation.

Cables and scene-level equipment links require a separate contract. A reusable
equipment asset declares its own ports; links between instances belong to the
assembled scene. No proprietary OEM dataset is included by this capability.

## Dependencies and compatibility

AIF-Entity 0.3.0 selects CAP204_NetworkEquipment.0-3-0, which depends on
CAP200_AifMetadata.0-3-0 and CAP201_ConnectionPoints.0-3-0. These carry the source
card's metadata and CP2 vocabulary into the AIF 0.3 contracts. NET.001–NET.003
apply only to network equipment, based on both the Properties-layer and composed
class values. AM.008 rejects unknown classes. The versioned class registry keeps
network equipment unavailable to legacy AM.007; existing AIF-Entity 0.1.0 and 0.2.0
retain their published class behavior and selected requirement sets.

The worksheet proposes `_mm` / `_kg` suffixes on inherited `aif:core` properties.
This contract retains the published identifiers `height`, `width`, `depth`,
`weight`, `installationClearance` and `accessibilityRequirement` in that namespace.
Their units remain mm / kg as specified by AM.009. Dimensions use the scalar
width, depth and height properties. AM.009 rejects retired
`overallGeometryDimensions` declarations. Renaming inherited properties requires
a separately reviewed metadata migration. The new `memory_MB` and
`storage_GB` identifiers follow the worksheet directly.

```{toctree}
:maxdepth: 1

Requirements <requirements>
```

## Dedicated Networking profile

`Networking@0.3.0` selects FET207_Networking.DSXAir.0-3-0 in addition to CAP204.
The feature's NET.004 eligibility check requires the network-equipment class unconditionally.
AIF-Entity continues to select only CAP204 and its conditional NET.001–NET.003
checks. The standalone profile adds class eligibility without changing the
published AIF-Entity selections or acceptance of other recognized equipment.
