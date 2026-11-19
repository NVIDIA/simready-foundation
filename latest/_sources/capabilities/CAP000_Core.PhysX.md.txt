# Capability: `CAP000_Core.PhysX`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP000_Core.PhysX` |
| Runtime                 | `PhysX` |
| Proprietary Techs       | `PhysX` |
| Versions                | `0-1-0`, `0-2-0` |

## Description

The Core (PhysX) feature adds the PhysX physics runtime variant to a SimReady
asset on top of the neutral Core contract. A satisfying asset exposes a `PhysX`
variant set on its root that, when enabled, composes a PhysX runtime payload from
`runnables/physics/physx.usd`, while the neutral asset stays unchanged when the
variant is disabled.

This capability only deals with the PhysX runtime variant. Newton and MuJoCo
variants are provided by `CAP000_Core.Newton` and `CAP000_Core.MuJoCo`.

## Dependency Graph

```{mermaid}
flowchart LR
    FET000PHYSX["CAP000_Core.PhysX\n0-1-0"]
    FET000STD["CAP000_Core\n0-1-0"]
    FET000PHYSX2["CAP000_Core.PhysX\n0-2-0"]
    FET000STD2["CAP000_Core\n0-2-0"]

    FET000PHYSX --> FET000STD
    FET000PHYSX2 --> FET000STD2

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET000PHYSX,FET000PHYSX2 current
    class FET000STD,FET000STD2 other
```

## Use Cases

- Assets that must run under the PhysX solver while remaining valid as a neutral
  SimReady asset.
- Pipelines that switch an asset into PhysX by selecting a single variant.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): optional in `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`
- [Robot-Gripper](../profiles/robot-gripper.md): optional in `2.1.0`, `2.2.0`, `3.0.0`
- [Robotics-Prop](../profiles/robotics-prop.md): optional in `3.1.0`, `3.2.0`, `3.3.0`, `4.0.0`

#### Dependencies

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [Core](CAP000_Core.md) (`CAP000_Core.0-1-0`) |

#### Requirement List

* Capability: [Core/Runtime Variants](../rules_and_reqs/core/runtime_variants/capability-runtime_variants.md)
    * Requirements:
        * [PhysX-Variant-Set](../rules_and_reqs/core/runtime_variants/requirements/physx-variant-set.md)
            * RV.001 | Version 0.1.0
        * [PhysX-Runtime-Payload](../rules_and_reqs/core/runtime_variants/requirements/physx-runtime-payload.md)
            * RV.002 | Version 0.1.0
        * [PhysX-Variant-Metadata](../rules_and_reqs/core/runtime_variants/requirements/physx-variant-metadata.md)
            * RV.003 | Version 0.1.0
        * [Runtime-Variant-Section-Purity](../rules_and_reqs/core/runtime_variants/requirements/runtime-variant-section-purity.md)
            * RV.010 | Version 0.1.0
        * [Runtime-Physics-Isolation](../rules_and_reqs/core/runtime_variants/requirements/runtime-physics-isolation.md)
            * RV.011 | Version 0.1.0

Inherited from `CAP000_Core.0-1-0`: NP.002, NP.003, NP.004, NP.005, NP.006,
NP.007, NP.008, SR.001, HI.010.

</details>

### Version 0-2-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): optional in `4.0.0`
- [Robot-Gripper](../profiles/robot-gripper.md): optional in `4.0.0`
- [Robotics-Prop](../profiles/robotics-prop.md): optional in `5.0.0`

#### Dependencies

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [Core](CAP000_Core.md) (`CAP000_Core.0-2-0`) |

#### Requirement List

Same as version `0-1-0`: RV.001, RV.002, RV.003, RV.010, RV.011.

Inherited from `CAP000_Core.0-2-0`: NP.002, NP.003, NP.004, NP.005,
NP.007, NP.008, HI.010.

#### Changes From Version 0-1-0

Version `0-2-0` depends on `CAP000_Core.0-2-0`, so it no longer brings
in `NP.006` or `SR.001`. Its own requirements are unchanged.

</details>

## Pipelines

Validation or runtime pipeline:

- SimReady validation - verifies the PhysX runtime variant requirement IDs listed
  in the feature manifest.

## Samples

- `sample_content/common_assets/props_general/obs_orange_a02/simready_usd/sm_obs_orange_a02_01.usd` - `PhysX` variant set with a `runnables/physics/physx.usd` payload.

## Evaluates

- None.

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `CAP000_Core.0-1-0` | `CAP000_Core.PhysX.0-1-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Creates `PhysX=Disabled/Enabled`, wires the anchored PhysX runnable payload, and stamps variant metadata. |
