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
| Runtime Variants (RV) | Variant set names, payload paths, metadata, purity, isolation | [Runtime Variants](../capabilities/core/runtime_variants/capability-runtime_variants.md) |
| Runtime features | Solver rigid-body and multibody rules (`FET_003_*`, `FET_004_*`) | Feature pages below |
| Profiles | Which optional runtime features a prop profile accepts | [Robotics-Prop](../profiles/robotics-prop.md), [Prop-Robotics-Physx](../profiles/prop-robotics-physx.md) |

### Feature expansion pattern

Neutral features describe OpenUSD physics. Each solver expands them with a
runtime-tagged feature that the validator enables before checking:

| Concern | Neutral | PhysX | Newton | MuJoCo |
| --- | --- | --- | --- | --- |
| Core scaffolding | `FET_000_STANDARD` | `FET_000_PHYSX` | `FET_000_NEWTON` | `FET_000_MUJOCO` |
| Rigid body | `FET_003_STANDARD` | `FET_003_PHYSX` | `FET_003_NEWTON` | `FET_003_MUJOCO` |
| Multibody | `FET_004_STANDARD` | `FET_004_PHYSX` | `FET_004_NEWTON` | `FET_004_MUJOCO` |

Physics runtime features set a `runtime` field (`PhysX`, `Newton`, or
`MuJoCo`) so `simready-validate` enables that variant set before those rules
run. See [Runtime Variant Field](features/features.md#runtime-variant-field-runtime).

### Isolation rules

When `PhysX = Enabled` and the other physics variants stay `Disabled`, the
composed stage may contain only:

- Neutral `UsdPhysics` / `physics:` data
- PhysX schemas and `physx*:` attributes

Newton or MuJoCo schemas in that composition fail `RV.011`. The same rule
applies when Newton or MuJoCo is selected. With all physics variants
`Disabled`, no solver-specific schemas may remain.

Authoritative policy:
[Runtime Physics Isolation Matrix](../capabilities/core/runtime_variants/runtime-physics-isolation-matrix.md).

Common mistakes:

- Authoring `physics:approximation = "sdf"` on the neutral base (PhysX-only)
- Merging PhysX and Newton schemas into one payload
- Leaving a second runtime variant `Enabled` while validating another

## Author a multiphysics prop

### Prerequisites

- A prop that already meets the neutral robotics contract
  (`FET_000_STANDARD`, `FET_001_STANDARD`, plus the physics features you need)
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
        prepend payload = @../runnables/physics/physx.usd@
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

| Payload | Feature contracts | Typical content |
| --- | --- | --- |
| `runnables/physics/physx.usd` | `FET_003_PHYSX`, `FET_004_PHYSX` | PhysX collider APIs; SDF approximation when required |
| `runnables/physics/newton.usd` | `FET_003_NEWTON`, `FET_004_NEWTON` | `NewtonCollisionAPI` plus mesh or SDF collision API |
| `runnables/physics/mujoco.usd` | `FET_003_MUJOCO`, `FET_004_MUJOCO` | `MjcCollisionAPI` / `MjcMeshCollisionAPI`; convex hull |

### 5. Opt into features on a profile that allows them

`Robotics-Prop@3.1.0` and `Prop-Robotics-Physx@2.2.0` (and later) list the
`FET_000_*` / `FET_003_*` / `FET_004_*` runtime features as **optional**. A
missing runtime does not fail the profile; a present runtime must pass its
rules.

Stamp validation metadata with the profile name and version you target. See
[Robotics-Prop runtime physics variants](../profiles/robotics-prop.md#runtime-physics-variants-version-310).

### 6. Validate per runtime

`simready-validate` groups profile features by the `runtime` field and checks
each group with only that variant enabled. To inspect a payload manually,
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
Core `FET_000_*` features own the variant scaffolding around those payloads.
See [Feature Adapters](feature_adapters/feature_adapters.md).

<details>
<summary><strong>Related specification pages</strong></summary>

- [Runtime Variants capability](../capabilities/core/runtime_variants/capability-runtime_variants.md)
- [Runtime Physics Isolation Matrix](../capabilities/core/runtime_variants/runtime-physics-isolation-matrix.md)
- [FET_000_PHYSX](../features/FET_000_PHYSX.md) ·
  [FET_000_NEWTON](../features/FET_000_NEWTON.md) ·
  [FET_000_MUJOCO](../features/FET_000_MUJOCO.md)
- [FET_003_PHYSX](../features/FET_003_PHYSX.md) ·
  [FET_003_NEWTON](../features/FET_003_NEWTON.md) ·
  [FET_003_MUJOCO](../features/FET_003_MUJOCO.md)
- [FET_004_PHYSX](../features/FET_004_PHYSX.md) ·
  [FET_004_NEWTON](../features/FET_004_NEWTON.md) ·
  [FET_004_MUJOCO](../features/FET_004_MUJOCO.md)
- [Features guide — runtime field](features/features.md#runtime-variant-field-runtime)
- [SimReady Benchmark](benchmark/benchmark.md)

</details>
