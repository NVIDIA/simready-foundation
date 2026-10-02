# Runtime Physics Isolation Matrix

> **Status: enforced.** This document is the policy guide for the runtime
> physics isolation rules `RV.010` (variant-section purity) and `RV.011`
> (composed-stage isolation), implemented in
> `runtime_variants/validation.py` and required by the `FET_000_PHYSX`,
> `FET_000_NEWTON`, and `FET_000_MUJOCO` features. The allow / require / forbid
> table below is the authoritative policy those checkers apply.

## Purpose

When a single physics runtime variant is selected on a SimReady asset, the
**composed** stage must contain only the schemas and attributes that the
selected runtime can consume, plus the runtime-neutral base. Anything else is a
leak that can silently break the runtime (for example a stray
`physics:approximation = "sdf"` under Newton, or a value other than
`convexHull` under MuJoCo).

The variant scaffolding rules (`RV.001`–`RV.009`) only check the variant set,
payload location, and metadata; they never inspect what the composed stage
actually carries. This matrix is the missing policy: the authoritative
allow / require / forbid table, per runtime, at the composed-stage level.

## Scope and model

- **Evaluated on the composed stage, per selection.** For each declared physics
  variant `V`, compose with `V = Enabled` and every other physics variant set
  `= Disabled`. The *target runtime* is `V`. Classify every authored
  physics-domain schema/attribute on the composed prims.
- **Neutral / all-Disabled** is treated as its own target ("Standard"): no
  runtime is selected, so only runtime-neutral data may be present.
- Composition strength (LIVRPS) matters: a value can leak from the neutral base,
  from another variant set left `Disabled`, or from a payload. This check does
  not care *where* the opinion came from, only what the composed result is.

### Classification legend

| Symbol | Meaning |
|---|---|
| **REQ** | Required for a conforming asset of this runtime (where applicable to the prim). |
| **OK** | Allowed to be present. |
| **N/A** | Not consumed by this runtime; expected absent. Presence is a warning (leak), not necessarily fatal. |
| **FORBID** | Must not be present under this selection; presence is a failure (pollution / conflict). |

## Namespace legend

| Group | Identifies by | Examples |
|---|---|---|
| Neutral (OpenUSD) | `UsdPhysics.*` schemas, `physics:` attribute namespace, `UsdGeom` collider geometry | `PhysicsCollisionAPI`, `PhysicsMeshCollisionAPI`, `PhysicsRigidBodyAPI`, `PhysicsMassAPI`, `PhysicsArticulationRootAPI`, `PhysicsScene`, `PhysicsJoint`, `PhysicsDriveAPI`, `PhysicsMaterialAPI`, `physics:mass`, `physics:density`, `physics:collisionEnabled` |
| PhysX | schema prefix `Physx`, attribute prefixes `physx*:` | `PhysxCollisionAPI`, `PhysxSDFMeshCollisionAPI`, `PhysxMeshMergeCollisionAPI`, `PhysxSceneAPI`, `physxCollision:*`, `physxScene:*` |
| Newton | schema prefix `Newton`, attribute prefix `newton:` | `NewtonCollisionAPI`, `NewtonMeshCollisionAPI`, `NewtonSDFCollisionAPI`, `NewtonArticulationRootAPI`, `NewtonSceneAPI`, `newton:contactGap`, `newton:sdf*`, `newton:selfCollisionEnabled` |
| MuJoCo | schema prefix `Mjc`, attribute prefix `mjc:` | `MjcCollisionAPI`, `MjcMeshCollisionAPI`, `MjcSceneAPI`, `MjcJointAPI`, `mjc:group`, `mjc:inertia`, `mjc:option:*` |

## Master matrix

Rows are namespace groups; columns are the target runtime of the composed
stage.

| Namespace group | Standard (neutral) | PhysX | Newton | MuJoCo |
|---|---|---|---|---|
| Neutral `UsdPhysics.*` / `physics:*` | REQ/OK | OK | OK | OK |
| PhysX schemas / `physx*:` attrs | FORBID | REQ/OK | FORBID | FORBID |
| Newton collision (`NewtonCollisionAPI`, `newton:contact*`) | FORBID | FORBID | REQ/OK | OK (inherited by `MjcCollisionAPI`) |
| Newton mesh/SDF (`NewtonMeshCollisionAPI` / `NewtonSDFCollisionAPI`, `newton:sdf*`) | FORBID | FORBID | REQ/OK (exactly one per mesh) | FORBID (not inherited by `MjcCollisionAPI`; MuJoCo uses `MjcMeshCollisionAPI`) |
| Newton scene / articulation (`NewtonSceneAPI`, `NewtonArticulationRootAPI`, `newton:selfCollisionEnabled`) | FORBID | FORBID | OK | FORBID |
| MuJoCo collision (`MjcCollisionAPI`, `MjcMeshCollisionAPI`, `mjc:group`, `mjc:*` collider) | FORBID | FORBID | FORBID (strict; see Resolved Decision 1) | REQ/OK |
| MuJoCo scene (`MjcSceneAPI`, `mjc:option:*`) | FORBID | FORBID | FORBID | OK |
| `MjcArticulationRootAPI` / `MjcArticulationRoot` type | FORBID | FORBID | FORBID | FORBID (`MUJOCO.BA.001`; MuJoCo has no such schema) |
| `NewtonJointAPI` | FORBID | FORBID | FORBID (`NEWTON.DJ.002`; Newton defines no such API) | FORBID |

Notes:
- "REQ" applies only where the prim role makes it required (e.g. a mesh collider
  or the articulation root). A prop with no articulation does not require
  articulation-root schemas. A `UsdPhysics.Scene` is a scenario-level concern and
  is not required for a single asset, so its runtime scene APIs are `OK` (allowed)
  rather than required.
- Neutral data is always OK because every runtime layers on top of it.

## Value-level attribute rules

Some attributes are neutral by *name* but runtime-sensitive by *value*. These
need value checks, not just presence checks.

### `physics:approximation`

| Target | Rule |
|---|---|
| Standard (neutral) | Unauthored, or a neutral OpenUSD token (`none`, `convexHull`, `convexDecomposition`, `boundingSphere`, `boundingCube`, `meshSimplification`). `sdf` is a PhysX extension token and should not appear on the neutral base. |
| PhysX | Any valid PhysX approximation token. When `sdf`, pair with `PhysxSDFMeshCollisionAPI`. |
| Newton | **Not consumed by Newton.** Newton selects its representation from `NewtonMeshCollisionAPI` / `NewtonSDFCollisionAPI` + `newton:sdf*`. Expected absent; `sdf` here is misleading and should FORBID. |
| MuJoCo | **Must equal `convexHull`** when `MjcCollisionAPI` + `PhysicsMeshCollisionAPI` are present (`MUJOCO.COL.002`). |

This attribute is the canonical example of why the neutral base must not carry
runtime-interpreted attributes: promoting a single `physics:approximation` to
the base forces every runnable to override it to a runtime-valid value, and
Newton would have to override an attribute it does not even consume. Preferred
design: leave `physics:approximation` off the neutral base and author it only in
the runnables that consume it (PhysX `sdf`, MuJoCo `convexHull`; Newton none).

## Documented sharing / inheritance (why some cross-runtime cells are OK)

- **`MjcCollisionAPI` prepends `NewtonCollisionAPI`** in the official MuJoCo USD
  schema (see `physics_bodies/physics_rigid_bodies/requirements/mujoco-collider-api.md`).
  MuJoCo collision *is-a* Newton collision, so under MuJoCo the inherited
  `NewtonCollisionAPI` and its `newton:contact*` attributes are legitimately
  present. This inheritance is one-directional (Mjc → Newton); it does **not**
  by itself justify a Newton layer carrying MuJoCo collision data.
- **`NewtonSDFCollisionAPI` and `NewtonMeshCollisionAPI` inherit
  `NewtonCollisionAPI`** (see `newton-collider-api.md`). Listing
  `NewtonCollisionAPI` alongside the SDF variant is redundant, and a single mesh
  must not carry both mesh and SDF representations.

## Negative rules already in force (encode as-is)

- `MUJOCO.BA.001`: no prim may apply `MjcArticulationRootAPI` or use the
  `MjcArticulationRoot` type; MuJoCo articulation roots stay on
  `UsdPhysics.ArticulationRootAPI`.
- `NEWTON.DJ.002`: `NewtonJointAPI` must not be applied; Newton has no such
  schema.

## Resolved Decisions

1. **Strict Newton isolation.** A Newton runtime layer uses only `Newton*`
   collision schemas and `newton:*` attributes. `Mjc*` schemas and `mjc:*`
   attributes under a Newton selection are **FORBID**. The one-directional
   inheritance (`Mjc → Newton`) does not license a Newton layer to carry the
   more-specific MuJoCo schema. *Applied:* `obs_orange_a02/runnables/physics/newton.usda`
   was updated to drop `MjcCollisionAPI` and `mjc:group`, leaving
   `["NewtonCollisionAPI", "PhysicsMeshCollisionAPI", "NewtonMeshCollisionAPI"]`
   + `newton:contactGap`.

2. **Severity: warn on inert leaks, fail on conflicts and foreign schemas.**
   - **Warning (`N/A`):** a not-consumed but harmless attribute, e.g. a neutral
     `physics:approximation` token appearing under Newton.
   - **Failure (`FORBID`):** any foreign-runtime schema/attribute for the
     selected runtime, and any value conflict (e.g. `physics:approximation="sdf"`
     under Newton, or any non-`convexHull` value under MuJoCo).

3. **Neutral base is strictly runtime-agnostic.** The neutral base
   (all variants `Disabled`) may carry only neutral `UsdPhysics` / `physics:*`
   data and geometry. `Physx*`, `Newton*`, and `Mjc*` schemas/attributes on the
   base are **FORBID**.

## Mapping to the validators

This matrix is the data table behind two implemented rules in
`runtime_variants/validation.py`:

- **Structural (`RV.010`, cheap, static):** each physics variant's `Enabled`
  option contains only the `prepend payload` arc and no inline prim overrides;
  the `Disabled` option is empty. (Prevents the variant-opinion leak class fixed
  in `obs_orange_a02`.) Implemented by `RuntimeVariantSectionPurityChecker`.
- **Semantic (`RV.011`, composed-per-variant):** for each declared physics
  variant (and the neutral base), compose that selection and evaluate authored
  physics schemas/attributes against the matrix above, including the
  `physics:approximation` value rules. Reports foreign-schema pollution and
  value conflicts against the selected runtime. Implemented by
  `RuntimePhysicsIsolationChecker`.
