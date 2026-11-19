---
name: simready-foundation-conform-fet-003-physx
description: "Use for repairing exact FET003_RigidBody.PhysX SimReady conformance for rigid body physics (physx) conformance. Use when a profile, validation report, or user request names FET003_RigidBody.PhysX; default to `FET003_RigidBody.PhysX.0-4-0` unless a profile or report pins another version. Foundations 1 ID: FET_003_PHYSX."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - physx
---

# SimReady Conform FET003_RigidBody.PhysX

## OpenUSD Competence

Running this conform skill is expert USD authoring. Reason from the OpenUSD /
Pixar USD spec rather than pattern-matching a validator message: composition
arcs and LIVRPS strength ordering, value resolution and list editing
(prepend, append, explicit, delete), the `def`/`over`/`class`
specifiers, native instancing and model hierarchy, stage units and up-axis,
and the `UsdGeom`, `UsdShade`, and `UsdPhysics` schemas. Make the exact native
edit on the correct prim, arc, and layer, derive values from the asset's real
geometry and composition, then reopen the composed stage to confirm the
opinion resolves as intended before claiming the gate passes. Never fabricate
data to satisfy a validator token. The repository-root `AGENTS.md`
"Master-Level OpenUSD Competence for Conform Work" section is the full
statement.

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET003_RigidBody.PhysX`. It repairs or stages rigid body physics (physx) conformance without drifting into another runtime contract.

Default to `FET003_RigidBody.PhysX.0-4-0` when the user asks for this feature without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET003_RigidBody.PhysX.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET003_RigidBody.PhysX.0-2-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET003_RigidBody.PhysX.0-3-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET003_RigidBody.PhysX.0-4-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET003_RigidBody.PhysX.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `FET003_RigidBody.PhysX.0-1-0` | FET003_RigidBody.0-1-0 | `COL.001` |
| `FET003_RigidBody.PhysX.0-2-0` | None | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.006`, `RB.007`, `RB.009`, `RB.010`, `PHYSX.COL.001`, `PHYSX.COL.002` |
| `FET003_RigidBody.PhysX.0-3-0` | None | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.007`, `RB.009`, `RB.010`, `PHYSX.COL.001`, `PHYSX.COL.002` |
| `FET003_RigidBody.PhysX.0-4-0` | None | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.007`, `RB.009`, `RB.010`, `PHYSX.COL.001`, `PHYSX.COL.002` |

## Feature Adapter

When the input already conforms to the neutral base feature, prefer the deterministic feature adapter to author the runtime-specific data first (via the `workspace upgrade` command; see `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`), then repair only the residual requirements below.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_physx` | `rigid_body_neutral_to_prop_physx` | `FET003_RigidBody.0-1-0` -> `FET003_RigidBody.PhysX.0-1-0` | Mesh extents on all meshes. |

- The adapter runs on a staged output stage and never creates geometry; it only annotates existing prims. Ensure colliders/rigid bodies already exist.
- It reaches `FET003_RigidBody.PhysX.0-1-0` only. The default `FET003_RigidBody.PhysX.0-4-0` (and `FET003_RigidBody.PhysX.0-2-0`/`FET003_RigidBody.PhysX.0-3-0`) adds `RB.*` rigid-body and `PHYSX.COL.001`/`PHYSX.COL.002` requirements that the adapter does not author; repair those manually per the Workflow below.

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET003_RigidBody.PhysX` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET003_RigidBody.PhysX` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET003_RigidBody.PhysX` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair the selected PhysX rigid-body feature and use PhysX-only collider schema only when the manifest allows it.
- Keep multibody joint and articulation work in FET004_Multibody.PhysX or related robot features.
- Record whether runtime or validator evidence was available for PhysX collider behavior.
- **PhysX collider schema placement and `PhysxMeshMergeCollisionAPI` (`PHYSX.COL.001`, `PHYSX.COL.002`):**
  - `PHYSX.COL.001` allows `PhysicsCollisionAPI` only on a `UsdGeom.Gprim` (`Mesh`, `Cube`, `Sphere`, `Capsule`, `Cylinder`) or on an `Xform` that applies `PhysxMeshMergeCollisionAPI` **and** whose `collection:collisionmeshes` collection resolves to at least one `UsdGeom.Gprim`. Remove `PhysicsCollisionAPI` / `PhysicsMeshCollisionAPI` from empty container `Xform`s, or move them onto the actual `UsdGeom.Mesh` colliders (de-instancing the link collider hierarchy in `physics.usda` when colliders are inside instanceable references, as on `I2RT/yam`, so `instances.usda` stays free of physics schemas per `RC.005`/`RC.006`).
  - **Do not apply `PhysxMeshMergeCollisionAPI` to single-mesh `UsdGeom.Mesh` colliders:** Converters sometimes stamp `prepend apiSchemas = ["PhysxMeshMergeCollisionAPI"]` directly onto individual `UsdGeom.Mesh` collider `over`s in `runnables/physics/physx.usda` without a valid `collisionmeshes` collection (for example on `Ufactory/uf850`, `xarm6`, `xarm7`, `lite6`, `OpenArm/openarm_unimanual`, `openarm_bimanual`, `UniversalRobots/ur20`, `comau/n-220-27`). On a single `UsdGeom.Mesh` collider, remove `PhysxMeshMergeCollisionAPI` while preserving `PhysicsCollisionAPI`, `PhysicsMeshCollisionAPI`, `PhysxCollisionAPI`, and `physics:approximation`.
  - **Concave link self-obstruction (`PhysxSDFMeshCollisionAPI`):** When a convex-hull collider approximation (`physics:approximation = "convexHull"`) on a concave robot link or housing bridges across an internal cavity and obstructs adjacent link travel (such as `nhc12_link_4_r/mesh_9` on `Yaskawa/Motoman_Next/NHC12`), switch that mesh in `runnables/physics/physx.usda` to `prepend apiSchemas = ["PhysxCollisionAPI", "PhysxSDFMeshCollisionAPI"]` with `token physics:approximation = "sdf"` (and appropriate SDF resolution, e.g. `int physxSDFMeshCollision:sdfResolution = 256`, `int physxSDFMeshCollision:sdfSubgridResolution = 6`) or `"convexDecomposition"`.
  - **Runtime physics layer isolation (`RC.005`, `RC.006`, `RV.011`):** In robot assets that also validate against `CAP000_Core.Isaac` (`RC.005`, `RC.006`), note that `RC.005` checks that `physics:*` attributes (other than `physics:collisionEnabled` on a `PhysicsCollisionAPI` prim) are authored in layers whose filename matches `physics.usd*` (`_PHYSICS_LAYER_RE`). If `runnables/physics/physx.usda` authors `physics:approximation` or `state:*:physics:*` directly when `RC.005` is evaluated with PhysX enabled, either keep neutral `physics:*` attributes in a `*physics.usda` layer (or a `runnables/physics/physics.usda` sublayer as in `Yahboom/Dofbot`) or rely on `PhysxCookedDataAPI:*` in `physx.usda` where appropriate.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `FET003_RigidBody.PhysX.0-4-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
