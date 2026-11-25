# Capability: `CAP200_AifMetadata`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP200_AifMetadata` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0`, `0-3-0` |

## Description

Defines the metadata contract for AI Factory equipment. An asset that satisfies this
feature declares what it is and what it physically occupies: manufacturer, model number
and asset version; height, width, depth, weight, installation clearance
and accessibility requirement; the SimReady specification version it was authored against;
a description and a link to its model documentation. It also declares its equipment class
in `aif:core:assetClass`, and carries the `aif:spec:*` attribute set that class defines.

Everything a facility-scale tool needs before it can place, orient or space a unit comes
from here, which is why the connection point, thermal and electrical features all sit on
top of it.

AIF Core Metadata is conceptually a **Capability** rather than a Feature: its rules check
attribute presence and change no simulation output. It is carried here as an interim
feature entry so profiles can select it, until SRF supports referencing a Capability
directly from a Profile. Authoritative documentation is the
[Core Metadata capability](../rules_and_reqs/aif/metadata/capability-metadata.md).

## Dependency Graph

```{mermaid}
flowchart LR
    FET200["CAP200_AifMetadata\n0-1-0"]
    FET201["CAP201_ConnectionPoints\n0-1-0 / 0-2-0"]
    FET202["CAP202_ThermalCooling\n0-1-0"]
    FET203["CAP203_Electrical\n0-1-0"]

    FET201 --> FET200
    FET202 --> FET201
    FET203 --> FET201

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET200 current
    class FET201,FET202,FET203 other
```

## Use Cases

Products or workflows that consume this capability:

- DSX / AI Factory operational twin, for facility layout and equipment placement.
- Equipment manufacturers publishing datacenter assets: Vertiv, Trane, Eaton, Siemens, Schneider.
- Model-based systems engineering and PLM hosts: Dassault 3DEXPERIENCE, PTC, Siemens.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [AIF-Entity](../profiles/aif-entity.md): required in `0.1.0`, `0.2.0`

#### Dependencies

None.

#### Requirement List

* Capability: [AIF/Metadata](../rules_and_reqs/aif/metadata/capability-metadata.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `AM.001` | [Properties-Sublayer-Required](../rules_and_reqs/aif/metadata/requirements/properties-sublayer-required.md) |
| `AM.002` | [Asset-Class-Required](../rules_and_reqs/aif/metadata/requirements/asset-class-required.md) |
| `AM.003` | [Asset-Identification-Metadata](../rules_and_reqs/aif/metadata/requirements/asset-identification-metadata.md) |
| `AM.004` | [Physical-Dimensions-Metadata](../rules_and_reqs/aif/metadata/requirements/physical-dimensions-metadata.md) |
| `AM.005` | [SimReady-Version-Tracking](../rules_and_reqs/aif/metadata/requirements/simready-version-tracking.md) |
| `AM.006` | [Asset-Description-Required](../rules_and_reqs/aif/metadata/requirements/asset-description-required.md) |
| `AM.007` | [Equipment-Class-Template-Compliance](../rules_and_reqs/aif/metadata/requirements/equipment-class-template-compliance.md) |

`AM.007` selects the `aif:spec:*` attribute set from `aif:core:assetClass` and checks the
whole set is present. The attributes each class defines are named in the per-class
reference tables on the [Core Metadata capability](../rules_and_reqs/aif/metadata/capability-metadata.md) page.

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Via the AIF pipeline samples, which convert vendor CAD to USD and author the metadata.

Validation or runtime pipeline:

- `simready-validate` — checks the metadata contract against the `AIF-Entity` profile.

## Samples

Sample assets, one per equipment class, under `sample_content/aif/`:

- `Generic_CDU` — generic CDU
- `gb300` — compute rack
- `Synthetic_CRAH` — generic CRAH
- `Synthetic_UPS` — generic UPS

## Benchmarks

- None. The metadata contract is a static check with no runtime behaviour to measure.

## Adapters

None.


## Version 0-3-0 — AIF 0.3

[AM.009](../rules_and_reqs/aif/metadata/requirements/physical-dimensions-metadata-0.3.md)
replaces AM.004 in `CAP200_AifMetadata.0-3-0`. Authors supply width, depth and height as scalars.
The capability uses
[AM.008](../rules_and_reqs/aif/metadata/requirements/equipment-class-template-compliance-0.3.md)
for equipment templates. AM.008 checks the USD types of common metadata on each equipment class.

```{toctree}
:maxdepth: 1
:hidden:

../rules_and_reqs/aif/metadata/requirements/equipment-class-template-compliance-0.3
```
