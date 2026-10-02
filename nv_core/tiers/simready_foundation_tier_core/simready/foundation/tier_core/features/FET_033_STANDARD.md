# Feature: `FET_033_STANDARD`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_033_STANDARD` |
| Runtime | `STANDARD` |
| Proprietary Techs | `None` |
| Latest Version | `0.4.0` |

## Description

Defines the Standard SimReady package overlay. It adds SimReady-specific
root-asset expectations — thumbnail presence and package provenance
metadata — on top of self-contained package source validation. Versions
`0.2.0` and `0.3.0` use nested `SimReady_Metadata` (`SR.003`). Version
`0.4.0` replaces `SR.003` with the USD/sidecar provenance union (`SR.004`).

See the [Thumbnail Guidelines](../guides/thumbnail_guidelines.md)
for the `simready.thumbnail` generation workflow and authoring guidance
associated with `SR.002`.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_031_STANDARD_0_1_0["FET_031_STANDARD\n0.1.0"]
    FET_033_STANDARD_0_4_0["FET_033_STANDARD\n0.4.0"]
    FET_033_STANDARD_0_4_0 --> FET_031_STANDARD_0_1_0

    class FET_033_STANDARD_0_4_0 current
    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

Products or workflows that consume this feature:

- Package candidate validation verifies thumbnails and SimReady provenance
  metadata next to intended SimReady root assets.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- Package-Candidate v1.0.0

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET_031_STANDARD@0.1.0` |

#### Requirement List

* Capability: [Core/SimReady](../capabilities/core/sim_ready/capability-sim_ready.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `SR.002` | [SR.002](../capabilities/core/sim_ready/requirements/thumbnail-exist.md) | [Implementation](../capabilities/core/sim_ready/validation.py) |

</details>

### Version 0.2.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- Package-Candidate v1.1.0

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET_031_STANDARD@0.1.0` |

#### Requirement List

* Capability: [Core/SimReady](../capabilities/core/sim_ready/capability-sim_ready.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `SR.002` | [SR.002](../capabilities/core/sim_ready/requirements/thumbnail-exist.md) | [Implementation](../capabilities/core/sim_ready/validation.py) |
| `SR.003` | [SR.003](../capabilities/core/sim_ready/requirements/nested-simready-metadata.md) | [Implementation](../capabilities/core/sim_ready/validation.py) |

#### Changes From Version 0.1.0

Version 0.2.0 keeps `SR.002` and adds `SR.003`, which requires SimReady package
provenance fields inside the root-layer `SimReady_Metadata` dictionary
(`author`, `asset_name`, `asset_type`, `asset_license`, `category`,
`source_file`, and `usd_date_generated`). Each required field must be non-empty.

</details>

### Version 0.3.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robotics-Prop](../profiles/robotics-prop.md) v3.2.0
- [Robot-Body](../profiles/robot-body.md) v2.1.0 and v2.2.0
- [Robot-Gripper](../profiles/profiles.md#profile-comparison) v2.1.0
- Package-Candidate v1.2.0

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET_031_STANDARD@0.1.0` |

#### Requirement List

* Capability: [Core/SimReady](../capabilities/core/sim_ready/capability-sim_ready.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `SR.002` | [SR.002](../capabilities/core/sim_ready/requirements/thumbnail-exist.md) | [Implementation](../capabilities/core/sim_ready/validation.py) |
| `SR.003` | [SR.003](../capabilities/core/sim_ready/requirements/nested-simready-metadata.md) | [Implementation](../capabilities/core/sim_ready/validation.py) |

#### Changes From Version 0.2.0

Version 0.3.0 keeps the same requirement set (`SR.002`, `SR.003`) but reflects a
stricter `SR.003` contract. In addition to the original provenance fields, the
nested `SimReady_Metadata` dictionary must now also carry asset-level descriptive
fields: `qcode` (Wikidata Q-Code), `rigid_body_count` (non-negative integer),
`asset_extents` (float3 size in meters, XYZ), and `mass` (positive kilograms).
Because these fields are required, assets that satisfied `0.2.0` with only the
original provenance fields must add the new fields to satisfy `0.3.0`.

</details>

### Version 0.4.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- Package-Candidate v1.3.0
- Robotics-Prop v3.3.0, v4.0.0
- Robot-Body v2.3.0, v3.0.0
- Robot-Gripper v2.2.0, v3.0.0

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET_031_STANDARD@0.1.0` |

#### Requirement List

* Capability: [Core/SimReady](../capabilities/core/sim_ready/capability-sim_ready.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `SR.002` | [SR.002](../capabilities/core/sim_ready/requirements/thumbnail-exist.md) | [Implementation](../capabilities/core/sim_ready/validation.py) |
| `SR.004` | [SR.004](../capabilities/core/sim_ready/requirements/metadata-union.md) | [Implementation](../capabilities/core/sim_ready/validation.py) |

#### Changes From Version 0.3.0

Version 0.4.0 keeps `SR.002` and the `0.3.0` provenance field set, but replaces
`SR.003` with `SR.004`. Provenance fields are read from the union of root-layer
`customLayerData` (including optional nested `SimReady_Metadata`) and an optional
same-directory `<usd_stem>.json` sidecar. Neither the nested dictionary nor the
sidecar is required on its own. A field must not be authored in both locations.
The required fields remain `author`, `asset_name`, `asset_type`, `asset_license`,
`category`, `source_file`, `usd_date_generated`, `qcode`, `rigid_body_count`,
`asset_extents`, and `mass`. Nested-only assets that already passed `0.3.0`
still satisfy `SR.004`.

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- Package candidate validation verifies thumbnails and SimReady provenance
  metadata next to intended SimReady root assets.

## Samples

- None.

## Benchmarks

- None.

## Adapters

None.
