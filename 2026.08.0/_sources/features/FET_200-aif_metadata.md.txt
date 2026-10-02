# Feature: `FET200_AIF`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET200_AIF` |
| Runtime | `AIF` |
| Proprietary Techs | `None` |
| Latest Version | `0.1.0` |

## Description

Defines the metadata contract for AI Factory equipment. An asset that satisfies this
feature declares what it is and what it physically occupies: manufacturer, model number
and asset version; height, width, depth, weight, overall geometry, installation clearance
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
[Core Metadata capability](../capabilities/aif/metadata/capability-metadata.md).

## Dependency Graph

```{mermaid}
flowchart LR
    FET200["FET200_AIF\n0.1.0"]
    FET201["FET201_AIF\n0.1.0 / 0.2.0"]
    FET202["FET202_AIF\n0.1.0"]
    FET203["FET203_AIF\n0.1.0"]

    FET201 --> FET200
    FET202 --> FET201
    FET203 --> FET201

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET200 current
    class FET201,FET202,FET203 other
```

## Use Cases

Products or workflows that consume this feature:

- DSX / AI Factory operational twin, for facility layout and equipment placement.
- Equipment manufacturers publishing datacenter assets: Vertiv, Trane, Eaton, Siemens, Schneider.
- Model-based systems engineering and PLM hosts: Dassault 3DEXPERIENCE, PTC, Siemens.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[`AIF-Entity`](../profiles/aif-entity.md)** (`v0.1.0` and `v0.2.0`) — both profile versions select it unchanged; they differ only in the connection point vocabulary.

#### Feature Dependencies

None.

#### Requirement List

* Capability: [AIF/Metadata](../capabilities/aif/metadata/capability-metadata.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `AM.001` | [Properties-Sublayer-Required](../capabilities/aif/metadata/requirements/properties-sublayer-required.md) | [Implementation](../capabilities/aif/metadata/validation.py) |
| `AM.002` | [Asset-Class-Required](../capabilities/aif/metadata/requirements/asset-class-required.md) | [Implementation](../capabilities/aif/metadata/validation.py) |
| `AM.003` | [Asset-Identification-Metadata](../capabilities/aif/metadata/requirements/asset-identification-metadata.md) | [Implementation](../capabilities/aif/metadata/validation.py) |
| `AM.004` | [Physical-Dimensions-Metadata](../capabilities/aif/metadata/requirements/physical-dimensions-metadata.md) | [Implementation](../capabilities/aif/metadata/validation.py) |
| `AM.005` | [SimReady-Version-Tracking](../capabilities/aif/metadata/requirements/simready-version-tracking.md) | [Implementation](../capabilities/aif/metadata/validation.py) |
| `AM.006` | [Asset-Description-Required](../capabilities/aif/metadata/requirements/asset-description-required.md) | [Implementation](../capabilities/aif/metadata/validation.py) |
| `AM.007` | [Equipment-Class-Template-Compliance](../capabilities/aif/metadata/requirements/equipment-class-template-compliance.md) | [Implementation](../capabilities/aif/metadata/validation.py) |

`AM.007` selects the `aif:spec:*` attribute set from `aif:core:assetClass` and checks the
whole set is present. The attributes each class defines are named in the per-class
reference tables on the [Core Metadata capability](../capabilities/aif/metadata/capability-metadata.md) page.

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
