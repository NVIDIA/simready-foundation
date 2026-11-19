# Capability: `CAP000_Core`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP000_Core` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0`, `0-2-0` |

## Description

The Core feature defines the minimum standard structure for a portable SimReady
USD asset. It covers asset file naming, directory layout, path portability,
resolvable asset paths, and undefined prim cleanup. Version `0-1-0` also
requires SimReady identity metadata (`SR.001`).

`NP.005` was relaxed to `0.2.0` in place on both shipped versions: the main
asset file's name no longer has to contain its containing folder's name, and
no particular nesting depth is required. The folder holding the main asset
file must still contain no other USD file. This is a non-breaking relaxation
(no asset that passed `0.1.0` can fail `0.2.0`), applied in place rather than
as a new feature version because no asset-path manifest pins a per-requirement
version.

This is the neutral, OpenUSD-only Core contract and does not require any
physics runtime variants or Isaac packaging rules. Runtime-specific physics
variant scaffolding is provided by the runtime Core features
[`CAP000_Core.PhysX`](CAP000_Core.PhysX.md), [`CAP000_Core.Newton`](../../../../../simready_foundation_tier_newton/simready/foundation/tier_newton/capabilities/CAP000_Core.Newton.md),
and [`CAP000_Core.MuJoCo`](CAP000_Core.MuJoCo.md). Isaac packaging and physics-layer
placement are provided by [`CAP000_Core.Isaac`](CAP000_Core.Isaac.md). Each of those
features depends on this capability.

An asset that satisfies this capability can be discovered, loaded, packaged, and
validated as a well-formed SimReady USD asset before additional visual,
material, physics, robot, or runtime-specific feature contracts are applied.

## Dependency Graph

This capability has no dependencies and no other features depend on it directly.

## Use Cases

- Baseline SimReady asset validation.
- USD asset packaging and portability checks.
- Shared prerequisite checks for higher-level SimReady profiles.
- Early validation of exported assets before runtime-specific feature authoring.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [AIF-Entity](../../../../../simready_foundation_tier_aif/simready/foundation/tier_aif/profiles/aif-entity.md): required in `0.1.0`
- [Open-Taxonomy-ADE20K](../profiles/open-taxonomy-ade20k.md): required in `0.1.0`
- [Open-Taxonomy-COCO](../profiles/open-taxonomy-coco.md): required in `0.1.0`
- [Open-Taxonomy-Cityscapes](../profiles/open-taxonomy-cityscapes.md): required in `0.1.0`
- [Open-Taxonomy-ImageNet1K](../profiles/open-taxonomy-imagenet_1k.md): required in `0.1.0`
- [Open-Taxonomy-PascalVOC](../profiles/open-taxonomy-pascal_voc.md): required in `0.1.0`
- [Open-Taxonomy-SUNRGBD](../profiles/open-taxonomy-sunrgbd.md): required in `0.1.0`
- [Robotics-Prop](../profiles/robotics-prop.md): required in `3.0.0`, `3.1.0`, `3.2.0`

#### Dependencies

None.

#### Requirement List

* Capability: [Core/Naming Paths](../rules_and_reqs/core/naming_paths/capability-naming_paths.md)
    * Requirements:
        * [File-Naming-Convention](../rules_and_reqs/core/naming_paths/requirements/file-naming-convention.md)
            * NP.002 | Version 0.1.0
        * [Directory-Structure](../rules_and_reqs/core/naming_paths/requirements/directory-structure.md)
            * NP.003 | Version 0.1.0
        * [Path-Length-Limits](../rules_and_reqs/core/naming_paths/requirements/path-length-limits.md)
            * NP.004 | Version 0.1.0
        * [Asset-Folder-Structure](../rules_and_reqs/core/naming_paths/requirements/asset-folder-structure.md)
            * NP.005 | Version 0.2.0
        * [Metadata-Location](../rules_and_reqs/core/naming_paths/requirements/metadata-location.md)
            * NP.006 | Version 0.1.0
        * [Relative-Paths](../rules_and_reqs/core/naming_paths/requirements/relative-paths.md)
            * NP.007 | Version 0.1.0
        * [AssetPath-Validation](../rules_and_reqs/core/naming_paths/requirements/assetpath-validation.md)
            * NP.008 | Version 0.1.0
* Capability: [Core/SimReady](../rules_and_reqs/core/sim_ready/capability-sim_ready.md)
    * Requirements:
        * [Metadata-Whitelist](../rules_and_reqs/core/sim_ready/requirements/metadata-whitelist.md)
            * SR.001 | Version 0.1.0
* Capability: [Hierarchy](../rules_and_reqs/hierarchy/requirements.md)
    * Requirements:
        * [Undefined-Prims](../rules_and_reqs/hierarchy/requirements/undefined-prims.md)
            * HI.010 | Version 0.1.0

</details>

### Version 0-2-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [AIF-Entity](../../../../../simready_foundation_tier_aif/simready/foundation/tier_aif/profiles/aif-entity.md): required in `0.2.0`
- [NuRec](../profiles/nurec.md): required in `1.0.0`
- [Robot-Body](../profiles/robot-body.md): required in `4.0.0`
- [Robot-Gripper](../profiles/robot-gripper.md): required in `4.0.0`
- [Robotics-Prop](../profiles/robotics-prop.md): required in `3.3.0`, `4.0.0`, `5.0.0`

#### Dependencies

None.

#### Requirement List

Same as version `0-1-0`, except `NP.006` and `SR.001` are omitted.

* Capability: [Core/Naming Paths](../rules_and_reqs/core/naming_paths/capability-naming_paths.md)
    * Requirements:
        * [File-Naming-Convention](../rules_and_reqs/core/naming_paths/requirements/file-naming-convention.md)
            * NP.002 | Version 0.1.0
        * [Directory-Structure](../rules_and_reqs/core/naming_paths/requirements/directory-structure.md)
            * NP.003 | Version 0.1.0
        * [Path-Length-Limits](../rules_and_reqs/core/naming_paths/requirements/path-length-limits.md)
            * NP.004 | Version 0.1.0
        * [Asset-Folder-Structure](../rules_and_reqs/core/naming_paths/requirements/asset-folder-structure.md)
            * NP.005 | Version 0.2.0
        * [Relative-Paths](../rules_and_reqs/core/naming_paths/requirements/relative-paths.md)
            * NP.007 | Version 0.1.0
        * [AssetPath-Validation](../rules_and_reqs/core/naming_paths/requirements/assetpath-validation.md)
            * NP.008 | Version 0.1.0
* Capability: [Hierarchy](../rules_and_reqs/hierarchy/requirements.md)
    * Requirements:
        * [Undefined-Prims](../rules_and_reqs/hierarchy/requirements/undefined-prims.md)
            * HI.010 | Version 0.1.0

#### Changes From Version 0-1-0

Version `0-2-0` drops `NP.006` and `SR.001`. Nested provenance is `SR.003` on
`CAP033_SimReadyPackage.0-3-0`; USD/sidecar union is `SR.004` on
`CAP033_SimReadyPackage.0-4-0` for profiles that pin packaging.

</details>

## Pipelines

Source file type:

- `.blend`
  - Via Blender SimReady Add-ons
- `.mjcf`
  - Via Blender SimReady Add-ons and MJCF2USD Tool
- `.step`
  - Via Blender SimReady Add-ons and CAD Converter

Validation or runtime pipeline:

- SimReady validation - verifies the Core requirement IDs listed in the feature
  manifest.

## Samples

- [sample_content/common_assets/props_general/obs_lamp_revolute_a01/simready_usd/sm_obs_lamp_revolute_a01_01.usda](../../../../../../../sample_content/common_assets/props_general/obs_lamp_revolute_a01/simready_usd/sm_obs_lamp_revolute_a01_01.usda)

## Evaluates

- None.

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `CAP000_Core.0-1-0` | `CAP000_Core.PhysX.0-1-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Creates the pure PhysX runtime variant, anchored payload, and discovery metadata without authoring body physics. |
| `CAP000_Core.0-1-0` | `CAP000_Core.Newton.0-1-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Creates the pure Newton runtime variant, anchored payload, and discovery metadata without authoring body physics. |
| `CAP000_Core.0-1-0` | `CAP000_Core.MuJoCo.0-1-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Creates the pure MuJoCo runtime variant, anchored payload, and discovery metadata without authoring body physics. |
