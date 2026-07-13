# FET003 Requirement Repair Map

Use this reference when a validation report or inspection identifies `FET003_BASE_NEUTRAL` or `FET003_BASE_PHYSX` failures. Load the selected JSON manifest first:

- `FET_003_base_neutral-0.1.0-rigid_body_physics.json`
- `FET_003_base_physx-0.1.0-rigid_body_physics.json`
- `FET_003_base_physx-0.2.0-rigid_body_physics.json`

The feature markdown and requirement docs are useful context, but the selected manifest and current validation report decide which IDs are in scope.

## Manifest Requirements

| Feature Variant | Requirements |
|---|---|
| `FET003_BASE_NEUTRAL@0.1.0` | `RB.COL.001`, `RB.COL.002`, `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.006`, `RB.007`, `RB.009`, `RB.010` |
| `FET003_BASE_PHYSX@0.1.0` | Depends on `FET003_BASE_NEUTRAL@0.1.0`; manifest lists `COL.001`, while the feature markdown describes `PHYSX.COL.001`. If validation reports a different ID, follow the report and note the mismatch. |
| `FET003_BASE_PHYSX@0.2.0` | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.006`, `RB.007`, `RB.009`, `RB.010`, `PHYSX.COL.001`, `PHYSX.COL.002` |

## Requirement Map

| Requirement | What It Means | Safe Repair | Block When |
|---|---|---|---|
| `RB.001` | The asset contains at least one rigid body. | Apply `UsdPhysics.RigidBodyAPI` to a clear `UsdGeomXformable` body root intended to be dynamically simulated. For a simple prop, this is often the asset root or a single xformable child that owns the visual/collider hierarchy. | The asset could be static, has multiple plausible body roots, or requires articulated/multibody semantics. |
| `RB.003` | `UsdPhysics.RigidBodyAPI` is applied only to `UsdGeomXformable` prims. | Move the API from a non-xformable prim to the nearest correct xformable body root, preserving descendants and transforms. | Moving the body root changes simulation semantics or no valid xformable owner exists. |
| `RB.005` | Rigid bodies cannot be inside scene graph instances or instance proxies. The root prim of a rigid body hierarchy may be instanced. | Put `RigidBodyAPI` on the instance root when that matches the intended body, or stage a non-instanceable copy before authoring physics. | De-instancing would duplicate shared payloads unexpectedly, break composition, or change published package semantics. |
| `RB.006` | Nested rigid bodies must use reset xform stack, otherwise nested bodies are invalid. | Collapse to one rigid body root when the asset is a unibody, or add a reset xform stack only when nested bodies are genuinely intended and transform semantics are clear. | Nested bodies imply joints or articulation that should be handled by FET004. |
| `RB.007` | Each rigid body, or descendant collision shapes, must have mass specified with `physics:mass`. | Apply `UsdPhysicsMassAPI` and `physics:mass` to the rigid body or collision shapes using an explicit property source, source metadata, or user-approved value. | Mass is unknown and property prediction or assignment was not requested or approved. Do not invent physical mass silently. |
| `RB.009` | Rigid bodies cannot have skew in their world transform matrix. | Bake or decompose transforms so the rigid body world transform has translation, rotation, and supported scale only, preserving composed bounds. | Skew comes from external layers, animation, or transform stacks that cannot be safely rewritten. |
| `RB.010` | Invisible collision meshes must have `purpose = "guide"`. | Set `purpose` to `guide` on collision-only meshes that are hidden or explicitly non-renderable. | The mesh may be both visual and collision geometry, or visibility/purpose intent is unclear. |
| `RB.COL.001` | For neutral OpenUSD, `CollisionAPI` belongs on colliding `UsdGeomGprim` prims, not Xforms. | Move or add `CollisionAPI` on the correct Gprim collider. Remove it from invalid non-Gprim prims after a valid replacement exists. | A non-Gprim collider is intentional because a PhysX feature variant is selected; use the PhysX rules instead. |
| `RB.COL.002` | `MeshCollisionAPI` may only be applied to `UsdGeomMesh` prims and must be paired with `CollisionAPI`. | Add missing `CollisionAPI` to a mesh with `MeshCollisionAPI`, or remove/move `MeshCollisionAPI` from non-mesh prims. | The selected PhysX variant allows mesh merge on a non-mesh prim; use `PHYSX.COL.002` instead. |
| `RB.COL.003` | Feature docs describe mesh-collision legality; current validators may also report non-uniform collider scale under this ID. | If the failure is mesh-collision related, apply the `RB.COL.002` repair pattern. If the failure is scale related, use the `RB.COL.004` scale repair pattern and note the report/doc mismatch. | The report does not make clear whether the failure is mesh-collision or scale related. |
| `RB.COL.004` | Sphere, Capsule, Cylinder, Cone, and Points collision shapes must have uniform world scale. Mesh and Cube are the neutral exceptions. | Bake non-uniform scale into a mesh/cube collider, replace the simple collider with a correctly sized mesh/proxy, or adjust scale to uniform while preserving physical intent. | The non-uniform scale represents the intended collision shape and no equivalent supported collider can be authored safely. |
| `PHYSX.COL.001` | PhysX allows `CollisionAPI` on a Gprim or on an Xform with `PhysxMeshMergeCollisionAPI` whose `collisionmeshes` collection includes at least one Gprim. | For PhysX profiles, either move `CollisionAPI` to a Gprim or complete the mesh-merge Xform with `PhysxMeshMergeCollisionAPI` and a valid `collisionmeshes` collection. | PhysX schemas are unavailable, the collection cannot resolve, or the target profile is neutral. |
| `PHYSX.COL.002` | PhysX allows `MeshCollisionAPI` on a `UsdGeomMesh` or on a prim with `PhysxMeshMergeCollisionAPI`; `CollisionAPI` is always required too. | Add missing `CollisionAPI`, move `MeshCollisionAPI` to a mesh, or use a valid PhysX mesh-merge prim with a valid collection. | The target profile is neutral, PhysX schemas are unavailable, or mesh merge would hide which geometry participates in collision. |

## Common Repair Decisions

Use this decision order before editing:

1. Choose the body root: one body root for a simple prop; multiple body roots only when independent rigid bodies are clearly intended; hand off to FET004 for joints/articulation.
2. Choose the collision representation: existing collider geometry first, then explicit source-provided collider meshes, then user-approved visual mesh reuse or proxy generation.
3. Choose the mass source: explicit value, property report, source metadata, or user-approved default. Without one, block `RB.007`.
4. Choose the variant: neutral repairs must stay in OpenUSD schemas; PhysX repairs may use `PhysxMeshMergeCollisionAPI` only for selected PhysX variants.

## USD Authoring Notes

Rigid-body and collider schemas should be authored with USD schema APIs when available instead of string editing. For example, use `UsdPhysics.RigidBodyAPI.Apply(prim)`, `UsdPhysics.CollisionAPI.Apply(prim)`, `UsdPhysics.MeshCollisionAPI.Apply(prim)`, and `UsdPhysics.MassAPI.Apply(prim)`.

When repairing scale or skew, record composed bounds before and after. Any transform bake should preserve physical size and avoid changing FET001 unit conformance.

When removing an invalid API, confirm that no inherited or weaker-layer opinion still applies the same API after composition.

## Report Template

For each repair attempt, record:

| Field | Meaning |
|---|---|
| `requirement_id` | Requirement being repaired. |
| `status` | `repaired`, `already_passed`, `blocked`, or `failed`. |
| `affected_prims` | Prim paths inspected or changed. |
| `old_value` and `new_value` | API schema, mass, purpose, transform, scale, or collection values changed. |
| `variant` | Selected FET003 feature ID and version. |
| `outputs` | Files written or references changed. |
| `reason` | Short explanation, especially for blocked items or manifest/report mismatches. |
