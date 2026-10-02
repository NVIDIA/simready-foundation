# Feature: `FET_010_STANDARD`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_010_STANDARD` |
| Runtime | `STANDARD` |
| Proprietary Techs | `None` |
| Latest Version | `0.1.0` |

## Description

Defines the display colour material contract. An asset that satisfies this feature
resolves `primvars:displayColor` on its renderable Gprims, in a defined colour space
and with every component inside its valid range. `primvars:displayOpacity` is
optional; where it is authored, the same value constraints apply to it.

Display colour has no shading network, so it is the appearance layer available to
consumers that do not evaluate materials, including low-fidelity and non-ray-traced
render paths. It is a feature in its own right, not a variant of the material
features `FET_006_STANDARD`, `FET_006_MDL` and `FET_006_OPENPBR`: it draws on a
different capability and depends on none of them. An asset may have any combination,
and a consumer uses what it can evaluate.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this feature:

- Isaac Lab vision and reinforcement-learning training, where scenes render without ray tracing.
- CAD-origin assets that reach a simulator before any material authoring has happened.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

Optional display-colour gate:

- Robotics Prop v4.0.0, Robot Body v3.0.0, Robot Gripper v3.0.0

Those profile versions are added by the visual-materials specification change, which merges after this one.

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Visualization/Display Color](../capabilities/visualization/display_color/capability-display_color.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `DISP.001` | [DISP.001](../capabilities/visualization/display_color/requirements/display-color-coverage.md) | [Implementation](../capabilities/visualization/display_color/validation.py) |
| `DISP.002` | [DISP.002](../capabilities/visualization/display_color/requirements/display-color-values.md) | [Implementation](../capabilities/visualization/display_color/validation.py) |
| `DISP.003` | [DISP.003](../capabilities/visualization/display_color/requirements/display-opacity-values.md) | [Implementation](../capabilities/visualization/display_color/validation.py) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc` as applicable.

Validation or runtime pipeline:

- SimReady validation verifies display colour coverage, values and opacity.

## Samples

- None.

## Benchmarks

- None. The runtime check is a low-fidelity render diff: render the asset, render
  again with the display colour altered, and again with it removed, then compare
  the three frames.

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET_006_STANDARD@0.1.0` | `FET_010_STANDARD@0.1.0` | `nv_core/cip_specs/asset_handler_modules/neutral_to_display_color` | Planned | Authors `primvars:displayColor` on every renderable Gprim, derived from the bound material's albedo by UV-masked, area-weighted sampling in linear light. |
| `FET_006_OPENPBR@0.1.0` | `FET_010_STANDARD@0.1.0` | `nv_core/cip_specs/asset_handler_modules/neutral_to_display_color` | Planned | Same adapter. Reads OpenPBR `base_color` where a material carries one. |
| `FET_006_MDL@0.1.0` | `FET_010_STANDARD@0.1.0` | `nv_core/cip_specs/asset_handler_modules/neutral_to_display_color` | Planned | Same adapter. Falls back to the MDL diffuse where neither of the above is present. |

One implementation behind three entry points. It resolves the source in a fixed order —
OpenPBR `base_color`, then UsdPreviewSurface `diffuseColor`, then MDL — so the result will
not depend on which feature the registry entered from. The three are declared separately so
a path exists from any of the three starting features.

All three rows are Planned. The adapter module is not published yet, nor is the
`FET_006_OPENPBR` card the second row keys off, and the same transformation is planned as a
`simready-foundation-conform-fet-010-standard` skill for running it without Kit.
