# Feature: `FET_006_OPENPBR`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_006_OPENPBR` |
| Runtime | `OPENPBR` |
| Proprietary Techs | `None` |
| Latest Version | `0.1.0` |

## Description

Defines the OpenPBR material contract. The final surface is authored as an OpenPBR shading network
on `outputs:mtlx:surface`, so the asset renders in RTX and perception runtimes without a
vendor-specific material. This is a sibling runtime contract to `FET_006_STANDARD` and
`FET_006_MDL`, not a dependency on either. OpenPBR is the recommended target for new SimReady
assets; the MDL format stays permitted for existing content. The UsdPreviewSurface preview is a
separate feature (`FET_006_STANDARD`); profiles that require both list both.

> **Draft (2026-07).** Proposed OpenPBR format for FET-006. VM.PBR.001, VM.PBR.002,
> VM.PBR.003 and VM.TEX.004 are new requirement pages.
> VM.PBR.001 is phased-permissive: OpenPBR (MaterialX) is the conformant standard and an MDL
> surface is permitted during migration, with a future version tightening to OpenPBR-required.
> All four rules are implemented in this repository, in the Visualization/Materials
> `validation.py` that the requirement table below names. `usd-validation-nvidia` defines no
> rule for any of them, so nothing upstream backstops them.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies OpenPBR surface output, parameter ranges, MaterialX graph structure,
  shader input types, material binding, texture colour space, and texture size requirements.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

Optional OpenPBR material gate:

- Robotics Prop v4.0.0
- Robot Body v3.0.0
- Robot Gripper v3.0.0

Each of those versions also lists `FET_010_STANDARD`. A profile version loads only once
that feature is defined.

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Visualization/Materials](../capabilities/visualization/materials/capability-materials.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `com.nvidia.usd.VM.BIND.001` | Defined by `usd-validation-nvidia` | `MaterialOutOfScopeChecker` |
| `VM.BIND.002` | [VM.BIND.002](../capabilities/visualization/materials/requirements/material-shader-inputs.md) | [Implementation](../capabilities/visualization/materials/validation.py) |
| `VM.MAT.001` | [VM.MAT.001](../capabilities/visualization/materials/requirements/material-assignment.md) | [Implementation](../capabilities/visualization/materials/validation.py) |
| `VM.PBR.001` | [VM.PBR.001](../capabilities/visualization/materials/requirements/material-final-surface.md) | [Implementation](../capabilities/visualization/materials/validation.py) |
| `VM.PBR.002` | [VM.PBR.002](../capabilities/visualization/materials/requirements/material-pbr-parameter-ranges.md) | [Implementation](../capabilities/visualization/materials/validation.py) |
| `VM.PBR.003` | [VM.PBR.003](../capabilities/visualization/materials/requirements/material-shading-network-structure.md) | [Implementation](../capabilities/visualization/materials/validation.py) |
| `VM.TEX.001` | [VM.TEX.001](../capabilities/visualization/materials/requirements/material-texture-maxsize.md) | [Implementation](../capabilities/visualization/materials/validation.py) |
| `VM.TEX.004` | [VM.TEX.004](../capabilities/visualization/materials/requirements/material-texture-colorspace-openpbr.md) | [Implementation](../capabilities/visualization/materials/validation.py) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies OpenPBR surface output, parameter ranges, MaterialX graph structure,
  material binding, texture colour space, and texture size requirements.

## Samples

- All 14 props under `sample_content/common_assets/props_general/` author an OpenPBR surface
  on `outputs:mtlx:surface`, alongside the OmniPBR (MDL) surface and the UsdPreviewSurface
  preview each already had. 36 materials in total, with texture-driven channels reconnected
  as `tiledimage` readers.

## Benchmarks

- None.

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET_006_STANDARD@0.1.0` | `FET_006_OPENPBR@0.1.0` | `nv_core/cip_specs/asset_handler_modules/neutral_to_openpbr` | Planned | Authors an OpenPBR surface on `outputs:mtlx:surface`, reading the material's UsdPreviewSurface preview for base colour, roughness, metalness and normal. Reconnects texture-driven channels as `tiledimage` readers instead of flattening them to constants. |
| `FET_006_MDL@0.1.0` | `FET_006_OPENPBR@0.1.0` | `nv_core/cip_specs/asset_handler_modules/neutral_to_openpbr` | Planned | Same adapter and the same output. Where a material has an OmniPBR or OmniGlass MDL shader, that source takes precedence over the preview surface, since it holds the higher-fidelity values. |

Both entry points share one implementation, which reads whichever source surface a material
provides. They are declared separately so the registry can resolve a path from either
starting feature.

The adapter is not in this release: the path above is where it lands, and neither entry
point resolves until it does. The rows describe the intended behaviour so the registry
shape and the migration story can be reviewed alongside the requirements.
