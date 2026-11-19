# Capability: `CAP000_Core.Newton`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP000_Core.Newton` |
| Runtime                 | `Newton` |
| Proprietary Techs       | `Newton` |
| Versions                | `0-1-0`, `0-2-0` |

## Description

The Core (Newton) feature adds the Newton physics runtime variant to a SimReady
asset on top of the neutral Core contract. A satisfying asset exposes a `Newton`
variant set on its root that, when enabled, composes a Newton runtime payload
from `runnables/physics/newton.usd`, while the neutral asset stays unchanged when
the variant is disabled.

This capability only deals with the Newton runtime variant. PhysX and MuJoCo
variants are provided by `CAP000_Core.PhysX` and `CAP000_Core.MuJoCo`.

## Dependency Graph

```{mermaid}
flowchart LR
    FET000NEWTON["CAP000_Core.Newton\n0-1-0"]
    FET000STD["CAP000_Core\n0-1-0"]
    FET000NEWTON2["CAP000_Core.Newton\n0-2-0"]
    FET000STD2["CAP000_Core\n0-2-0"]

    FET000NEWTON --> FET000STD
    FET000NEWTON2 --> FET000STD2

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET000NEWTON,FET000NEWTON2 current
    class FET000STD,FET000STD2 other
```

## Use Cases

- Assets that must run under the Newton solver while remaining valid as a neutral
  SimReady asset.
- Pipelines that switch an asset into Newton by selecting a single variant.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot-body.md): optional in `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`
- [Robot-Gripper](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot-gripper.md): optional in `2.1.0`, `2.2.0`, `3.0.0`
- [Robotics-Prop](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/profiles/robotics-prop.md): optional in `3.1.0`, `3.2.0`, `3.3.0`, `4.0.0`

#### Dependencies

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [Core](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.md) (`CAP000_Core.0-1-0`) |

#### Requirement List

* Capability: [Core/Runtime Variants](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/capability-runtime_variants.md)
    * Requirements:
        * [Newton-Variant-Set](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/requirements/newton-variant-set.md)
            * RV.004 | Version 0.1.0
        * [Newton-Runtime-Payload](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/requirements/newton-runtime-payload.md)
            * RV.005 | Version 0.1.0
        * [Newton-Variant-Metadata](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/requirements/newton-variant-metadata.md)
            * RV.006 | Version 0.1.0
        * [Runtime-Variant-Section-Purity](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/requirements/runtime-variant-section-purity.md)
            * RV.010 | Version 0.1.0
        * [Runtime-Physics-Isolation](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/requirements/runtime-physics-isolation.md)
            * RV.011 | Version 0.1.0

Inherited from `CAP000_Core.0-1-0`: NP.002, NP.003, NP.004, NP.005, NP.006,
NP.007, NP.008, SR.001, HI.010.

</details>

### Version 0-2-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot-body.md): required in `4.0.0`
- [Robot-Gripper](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot-gripper.md): required in `4.0.0`
- [Robotics-Prop](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/profiles/robotics-prop.md): optional in `5.0.0`

#### Dependencies

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [Core](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.md) (`CAP000_Core.0-2-0`) |

#### Requirement List

Same as version `0-1-0`: RV.004, RV.005, RV.006, RV.010, RV.011.

Inherited from `CAP000_Core.0-2-0`: NP.002, NP.003, NP.004, NP.005,
NP.007, NP.008, HI.010.

#### Changes From Version 0-1-0

Version `0-2-0` depends on `CAP000_Core.0-2-0`, so it no longer brings
in `NP.006` or `SR.001`. Its own requirements are unchanged.

</details>

## Pipelines

Validation or runtime pipeline:

- SimReady validation - verifies the Newton runtime variant requirement IDs listed
  in the feature manifest.

## Samples

- `sample_content/common_assets/props_general/obs_orange_a02/simready_usd/sm_obs_orange_a02_01.usd` - `Newton` variant set with a `runnables/physics/newton.usd` payload.

## Evaluates

- None.

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `CAP000_Core.0-1-0` | `CAP000_Core.Newton.0-1-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Creates `Newton=Disabled/Enabled`, wires the anchored Newton runnable payload, and stamps variant metadata. |
