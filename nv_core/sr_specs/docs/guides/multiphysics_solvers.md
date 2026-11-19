# Multiple Physics Solvers

## Goal

Author and validate one SimReady prop so it can run under PhysX, Newton, or
MuJoCo without a separate USD file per solver.

After this guide you can:

- Explain how runtime physics variants isolate solvers on one asset
- Map Core / Rigid Body / Multibody features to each solver
- Point validators and samples at the correct runtime selection
- Find the requirement, profile, and isolation references

## Why multiple solvers on one asset

Robotics pipelines rarely share one physics backend. PhysX is the reference
path for Isaac Sim, Newton is the target runtime for Isaac Lab, and MuJoCo
remains common for research and interchange. Separate USD files per solver
break shared packaging, thumbnails, materials, and semantics.

SimReady Foundation uses **runtime physics variants**: a neutral OpenUSD base
plus optional payload layers. Each solver opts in through a USD variant set.
With every physics variant `Disabled`, the base stays valid. Enabling one
runtime composes only that runtime's schemas on top of neutral physics data.

For prop assets, use the samples linked below as the reference layout. Robot
body multiphysics support may differ by profile version — check the profile
you target.

## How it works

```{mermaid}
flowchart TB
    Base["Neutral SimReady base<br/>UsdPhysics + visuals + materials"]
    Base --> VS["Variant sets on defaultPrim<br/>PhysX / Newton / MuJoCo"]
    VS -->|Enabled| PX["runnables/physics/physx.usd"]
    VS -->|Enabled| NW["runnables/physics/newton.usd"]
    VS -->|Enabled| MJ["runnables/physics/mujoco.usd"]
    VS -->|Disabled| Empty["Empty section<br/>no foreign schemas"]
```

Three layers enforce the contract:

| Layer | What it defines | Where to read |
| --- | --- | --- |
| Runtime Variants (RV) | Variant set names, payload paths, metadata, purity, isolation | [Runtime Variants](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/capability-runtime_variants.md) |
| Runtime features | Solver rigid-body and multibody rules (`FET003_RigidBody.*`, `FET004_Multibody.*`; MuJoCo uses the `CAP003_RigidBody.MuJoCo` and `CAP004_Multibody.MuJoCo` capabilities) | Feature pages below |
| Profiles | Which optional runtime features a prop profile accepts | [Robotics-Prop](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/robotics-prop.md) |

### Feature expansion pattern

Neutral features describe OpenUSD physics. Each solver expands them with a
runtime-tagged feature that the validator enables before checking:

| Concern | Neutral | PhysX | Newton | MuJoCo |
| --- | --- | --- | --- | --- |
| Core scaffolding | `CAP000_Core` | `CAP000_Core.PhysX` | `CAP000_Core.Newton` | `CAP000_Core.MuJoCo` |
| Rigid body | `FET003_RigidBody` | `FET003_RigidBody.PhysX` | `FET003_RigidBody.Newton` | `CAP003_RigidBody.MuJoCo` |
| Multibody | `FET004_Multibody` | `FET004_Multibody.PhysX` | `FET004_Multibody.Newton` | `CAP004_Multibody.MuJoCo` |

Physics runtime features carry their runtime (`PhysX`, `Newton`, or `MuJoCo`)
as the middle segment of their dotted ID, and `simready-validate` enables that
variant set before those rules run. See
[Foundations 2 model](features/features.md#foundations-2-model).

### Isolation rules

When `PhysX = Enabled` and the other physics variants stay `Disabled`, the
composed stage may contain only:

- Neutral `UsdPhysics` / `physics:` data
- PhysX schemas and `physx*:` attributes

Newton or MuJoCo schemas in that composition fail `RV.011`. The same rule
applies when Newton or MuJoCo is selected. With all physics variants
`Disabled`, no solver-specific schemas may remain.

Authoritative policy:
[Runtime Physics Isolation Matrix](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/runtime-physics-isolation-matrix.md).

Common mistakes:

- Authoring `physics:approximation = "sdf"` on the neutral base (PhysX-only)
- Merging PhysX and Newton schemas into one payload
- Leaving a second runtime variant `Enabled` while validating another

## Author a multiphysics prop

### Prerequisites

- A prop that already meets the neutral robotics contract
  (`CAP000_Core`, `FET001_MinimalPlaceableVisual`, plus the
  physics features you need)
- Familiarity with USD variant sets and payloads
- `simready-validate` for the target Foundation release

### 1. Keep solver data out of the neutral base

Author shared visuals, materials, mass, and OpenUSD physics on the root asset.
Do not apply `Physx*`, `Newton*`, or `Mjc*` schemas on the base layer.

### 2. Add one variant set per runtime on `defaultPrim`

Name each set exactly `PhysX`, `Newton`, or `MuJoCo`. Expose `Disabled` /
`Enabled`, and default to `Disabled`:

```usd
variantSet "PhysX" = {
    "Disabled" {
    }
    "Enabled" {
        prepend payload = @./runnables/physics/physx.usd@
    }
}
```

Repeat for `Newton` → `runnables/physics/newton.usd` and
`MuJoCo` → `runnables/physics/mujoco.usd`. The `Enabled` section must contain
only that anchored payload (`RV.010`).

### 3. Record variant metadata

Under root-layer `customLayerData.SimReady_Metadata.Variants.Physics`, record
`prim`, `variantSetName`, and `activateOption` for each runtime (`RV.003`,
`RV.006`, `RV.009`). Profile authoring guides show the expected shape.

### 4. Author each payload for one solver only

| Payload | Contracts | Typical content |
| --- | --- | --- |
| `runnables/physics/physx.usd` | `FET003_RigidBody.PhysX`, `FET004_Multibody.PhysX` | PhysX collider APIs; SDF approximation when required |
| `runnables/physics/newton.usd` | `FET003_RigidBody.Newton`, `FET004_Multibody.Newton` | `NewtonCollisionAPI` plus mesh or SDF collision API |
| `runnables/physics/mujoco.usd` | `CAP003_RigidBody.MuJoCo`, `CAP004_Multibody.MuJoCo` | `MjcCollisionAPI` / `MjcMeshCollisionAPI`; convex hull |

### 5. Opt into features on a profile that allows them

`Robotics-Prop@3.2.0` selects every PhysX, Newton, and MuJoCo contract in the
table above as **optional**.
Failures contributed only by those optional features are reported as
non-blocking evidence; a requirement is blocking if another required selector
also contributes it.

The robot profiles differ. `Robot-Body@4.0.0` and `Robot-Gripper@4.0.0`
**require** five Newton contracts: `FET003_RigidBody.Newton`,
`FET004_Multibody.Newton`, `FET022_DrivenJoints.Newton`,
`CAP000_Core.Newton`, and `CAP024_BaseArticulation.Newton`.
Install the Newton tier next to Core first. If you do not, validation
fails on selectors it cannot resolve.

Record validation evidence under the profile target you requested; do not stamp
one profile as exclusive asset identity. See
[Robotics-Prop runtime physics variants](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/robotics-prop.md#runtime-physics-variants-version-310).

### 6. Validate per runtime

Validation derives each runtime from the second segment of the dotted feature
ID and checks each runtime group with only that variant enabled. To inspect a
payload manually,
enable one variant (Composer or USD APIs), keep the others `Disabled`, then
validate against the matching feature set.

## Reference samples

| Sample | Role |
| --- | --- |
| [`obs_orange_a02`](../../../../sample_content/common_assets/props_general/obs_orange_a02/simready_usd/sm_obs_orange_a02_01.usd) | Unibody prop with PhysX, Newton, and MuJoCo payloads under `runnables/physics/` |
| [`obs_electricians_large_tool_box_a01`](../../../../sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd) | Multibody prop with the same runtime-variant layout |

## Feature adapters

Feature adapters mutate neutral physics into a runtime-specific contract
(Neutral → PhysX, Neutral → Newton, and so on). They author payload content;
the `CAP000_Core.*` capabilities own the variant scaffolding around those payloads.
See [Feature Adapters](feature_adapters/feature_adapters.md).

<details>
<summary><strong>Related specification pages</strong></summary>

- [Runtime Variants capability](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/capability-runtime_variants.md)
- [Runtime Physics Isolation Matrix](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/runtime-physics-isolation-matrix.md)
- [CAP000_Core.PhysX](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.PhysX.md) ·
  [CAP000_Core.Newton](../../../tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/capabilities/CAP000_Core.Newton.md) ·
  [CAP000_Core.MuJoCo](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.MuJoCo.md)
- [FET003_RigidBody.PhysX](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET003_RigidBody.PhysX.md) ·
  [FET003_RigidBody.Newton](../../../tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/features/FET003_RigidBody.Newton.md) ·
  [CAP003_RigidBody.MuJoCo](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP003_RigidBody.MuJoCo.md)
- [FET004_Multibody.PhysX](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.PhysX.md) ·
  [FET004_Multibody.Newton](../../../tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/features/FET004_Multibody.Newton.md) ·
  [CAP004_Multibody.MuJoCo](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP004_Multibody.MuJoCo.md)
- [Features guide — runtime segment](features/features.md#foundations-2-model)
- [SimReady Evaluate](evaluate/evaluate.md)

</details>
