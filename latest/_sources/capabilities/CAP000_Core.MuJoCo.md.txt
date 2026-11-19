# Capability: `CAP000_Core.MuJoCo`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP000_Core.MuJoCo` |
| Runtime                 | `MuJoCo` |
| Proprietary Techs       | `MuJoCo` |
| Versions                | `0-1-0`, `0-2-0` |

## Description

The Core (MuJoCo) feature adds the MuJoCo physics runtime variant to a SimReady
asset on top of the neutral Core contract. A satisfying asset exposes a `MuJoCo`
variant set on its root that, when enabled, composes a MuJoCo runtime payload
from `runnables/physics/mujoco.usd`, while the neutral asset stays unchanged when
the variant is disabled.

This capability only deals with the MuJoCo runtime variant. PhysX and Newton
variants are provided by `CAP000_Core.PhysX` and `CAP000_Core.Newton`.

## Dependency Graph

```{mermaid}
flowchart LR
    FET000MUJOCO["CAP000_Core.MuJoCo\n0-1-0"]
    FET000STD["CAP000_Core\n0-1-0"]
    FET000MUJOCO2["CAP000_Core.MuJoCo\n0-2-0"]
    FET000STD2["CAP000_Core\n0-2-0"]

    FET000MUJOCO --> FET000STD
    FET000MUJOCO2 --> FET000STD2

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET000MUJOCO,FET000MUJOCO2 current
    class FET000STD,FET000STD2 other
```

## Use Cases

- Assets that must run under the MuJoCo solver while remaining valid as a neutral
  SimReady asset.
- Pipelines that switch an asset into MuJoCo by selecting a single variant.

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
        * [MuJoCo-Variant-Set](../rules_and_reqs/core/runtime_variants/requirements/mujoco-variant-set.md)
            * RV.007 | Version 0.1.0
        * [MuJoCo-Runtime-Payload](../rules_and_reqs/core/runtime_variants/requirements/mujoco-runtime-payload.md)
            * RV.008 | Version 0.1.0
        * [MuJoCo-Variant-Metadata](../rules_and_reqs/core/runtime_variants/requirements/mujoco-variant-metadata.md)
            * RV.009 | Version 0.1.0
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

Same as version `0-1-0`: RV.007, RV.008, RV.009, RV.010, RV.011.

Inherited from `CAP000_Core.0-2-0`: NP.002, NP.003, NP.004, NP.005,
NP.007, NP.008, HI.010.

#### Changes From Version 0-1-0

Version `0-2-0` depends on `CAP000_Core.0-2-0`, so it no longer brings
in `NP.006` or `SR.001`. Its own requirements are unchanged.

</details>

## Pipelines

Validation or runtime pipeline:

- SimReady validation - verifies the MuJoCo runtime variant requirement IDs listed
  in the feature manifest.

## Samples

- None. (The `obs_orange_a02` prop demonstrates `PhysX` and `Newton`; a `MuJoCo`
  variant would add `runnables/physics/mujoco.usd`.)

## Evaluates

- None.

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `CAP000_Core.0-1-0` | `CAP000_Core.MuJoCo.0-1-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Creates `MuJoCo=Disabled/Enabled`, wires the anchored MuJoCo runnable payload, and stamps variant metadata. |
