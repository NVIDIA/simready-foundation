# Robotics-Prop Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Robotics-Prop` profile. It consolidates the required feature set, USD
properties, naming conventions, and the optional runtime variants that this
profile exposes.

`Robotics-Prop` is the consolidated prop profile. It replaces the separate
`Prop-Robotics-Neutral` and `Prop-Robotics-Physx` profiles with a single
profile whose neutral OpenUSD core is mandatory and whose solver-specific
behavior is selected through optional features.

## Profile definition

The `Robotics-Prop` profile includes the following feature set (see
`robotics_prop.toml` and the
[feature dependency graph](../features/feature-dependency-graph)). Each
feature's requirements and dependencies are defined in the feature
specifications.

```toml
[Robotics-Prop]
"3.0.0" = {features = [
    {"FET_000_STANDARD" = {version = "0.1.0"}}, # "Core"
    {"FET_001_STANDARD" = {version = "1.0.1"}}, # "Minimal"
    {"FET_003_STANDARD" = {version = "0.2.0"}}, # "RBD Physics"
    {"FET_004_STANDARD" = {version = "0.2.0"}, optional=true}, # "Simulate Multi-Body Physics"
    {"FET_005_STANDARD" = {version = "0.1.0"}, optional=true}, # "Simulate Grasp Physics"
    {"FET_006_STANDARD" = {version = "0.1.0"}, optional=true}, # "Materials (USDPreview)"
    {"FET_006_MDL" = {version = "0.1.0"}, optional=true}, # "Materials (MDL)"
    {"FET_007_STANDARD" = {version = "0.2.0"}, optional=true}, # "Non-Visual Materials"

    {"FET_004_PHYSX" = {version = "0.4.0"}, optional=true}, # "Simulate Multi-Body Physics and SDF collision approximation"

    {"FET_004_NEWTON" = {version = "0.1.0"}, optional=true}, # "Simulate Multi-Body Physics (Newton)"
]}
"3.1.0" = {features = [ # Add optional runtime physics variant scaffolding (FET_000_* / FET_003_* / FET_004_*)
    {"FET_000_STANDARD" = {version = "0.1.0"}}, # "Core"
    {"FET_001_STANDARD" = {version = "1.0.1"}}, # "Minimal"
    {"FET_003_STANDARD" = {version = "0.2.0"}}, # "RBD Physics"
    {"FET_004_STANDARD" = {version = "0.2.0"}, optional=true}, # "Simulate Multi-Body Physics"
    {"FET_005_STANDARD" = {version = "0.1.0"}, optional=true}, # "Simulate Grasp Physics"
    {"FET_006_STANDARD" = {version = "0.1.0"}, optional=true}, # "Materials (USDPreview)"
    {"FET_006_MDL" = {version = "0.1.0"}, optional=true}, # "Materials (MDL)"
    {"FET_007_STANDARD" = {version = "0.2.0"}, optional=true}, # "Non-Visual Materials"

    # PhysX runtime variant (Core -> Rigid Body -> Multibody)
    {"FET_000_PHYSX" = {version = "0.1.0"}, optional=true}, # "Core PhysX runtime variant"
    {"FET_003_PHYSX" = {version = "0.4.0"}, optional=true}, # "Rigid Body Physics (PhysX)"
    {"FET_004_PHYSX" = {version = "0.4.0"}, optional=true}, # "Simulate Multi-Body Physics and SDF collision approximation"

    # Newton runtime variant (Core -> Rigid Body -> Multibody)
    {"FET_000_NEWTON" = {version = "0.1.0"}, optional=true}, # "Core Newton runtime variant"
    {"FET_003_NEWTON" = {version = "0.1.0"}, optional=true}, # "Rigid Body Physics (Newton)"
    {"FET_004_NEWTON" = {version = "0.1.0"}, optional=true}, # "Simulate Multi-Body Physics (Newton)"

    # MuJoCo runtime variant (Core -> Rigid Body -> Multibody)
    {"FET_000_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Core MuJoCo runtime variant"
    {"FET_003_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Rigid Body Physics (MuJoCo)"
    {"FET_004_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Simulate Multi-Body Physics (MuJoCo)"
]}
```

### Required versus optional features

Only three features are required. Everything else is marked `optional=true` and
is validated only when the asset selects it.

| Feature | Version | Status | Purpose |
|---|---|---|---|
| `FET_000_STANDARD` | 0.1.0 | Required | Core file layout, anchored references, SimReady metadata |
| `FET_001_STANDARD` | 1.0.1 | Required | Minimal OpenUSD asset: units, hierarchy, mesh geometry |
| `FET_003_STANDARD` | 0.2.0 | Required | Neutral rigid-body physics and colliders |
| `FET_004_STANDARD` | 0.2.0 | Optional | Neutral multibody joints |
| `FET_005_STANDARD` | 0.1.0 | Optional | Grasp physics (physics material + grasp line) |
| `FET_006_STANDARD` | 0.1.0 | Optional | `UsdPreviewSurface` materials |
| `FET_006_MDL` | 0.1.0 | Optional | MDL materials |
| `FET_007_STANDARD` | 0.2.0 | Optional | Non-visual sensor materials |

A single-rigid-body prop satisfies the required set through `FET_003_STANDARD`
alone. Select `FET_004_STANDARD` only for props intentionally authored as a
multibody assembly with joints.

Version `3.1.0` additionally exposes optional PhysX, Newton, and MuJoCo runtime
variants. Each runtime is a three-feature chain: `FET_000_<RUNTIME>` for the
variant scaffolding, `FET_003_<RUNTIME>` for rigid bodies, and
`FET_004_<RUNTIME>` for multibody joints.

## Required USD properties and schemas

### Core file layout (`FET_000_STANDARD`)

- Lay the asset out as `<asset_root>/<intermediate_folder>/<main.usd>`, with the
  main USD filename containing the root folder name and exactly one USD file in
  the intermediate folder (`NP.005`).
- Use lowercase file names with `.usd`, `.usda`, `.usdc`, or `.usdz`
  extensions, separating words with `_` or `-` (`NP.002`).
- Use lowercase directory names and group supporting content into purpose
  folders such as `materials/`, `textures/`, `geometry/`, and `physics/`
  (`NP.003`).
- Keep path strings within platform limits (`NP.004`).
- Author asset metadata in root-layer `customLayerData` and/or a sidecar
  `[asset_name].json` beside the USD file (`NP.006`).
- Make every `references`, `payloads`, `subLayers`, and texture `asset` path
  relative with `./` or `../` (`NP.007`), and make sure each one resolves to a
  file that exists on disk (`NP.008`).
- Author `dictionary SimReady_Metadata` in root-layer `customLayerData` with
  string fields `asset_name`, `asset_type`, `source_file`, and
  `usd_date_generated` in ISO `YYYY-MM-DD` form (`SR.001`).
- Do not leave orphan `over` prims with no underlying `def` (`HI.010`).

### Stage metadata and hierarchy (`FET_001_STANDARD`)

- Set `upAxis = "Z"` (`UN.006`) and `metersPerUnit = 1.0` (`UN.007`).
- Set `defaultPrim` to an existing prim (`HI.004`).
- Parent all prims under a single stage root prim (`HI.001`) that inherits
  `UsdGeomXformable`, typically `def Xform` (`HI.003`). A `Scope`, `Material`,
  or `Shader` root is invalid.
- Use anchored `./` or `../` reference paths that do not escape the asset root
  (`AA.001`), pointing only at supported file types: USD, `.png`, `.jpeg`,
  `.jpg`, `.exr`, `.m4a`, `.mp3`, `.wav` (`AA.002`).

### Geometry (`FET_001_STANDARD`)

- Author render geometry as `UsdGeom.Mesh` with
  `uniform token subdivisionScheme = "none"` (`VG.MESH.001`).
- Author correct `float3[] extent` on boundable geometry (`VG.002`).
- Keep mesh topology valid: `faceVertexIndices` in range, no degenerate faces
  (`VG.014`), using counter-clockwise winding (`VG.029`).
- Author normals through either `normal3f[] primvars:normals` or
  `normal3f[] normals`, but never both on the same mesh (`VG.027`). Normals must
  be unit length and point outward consistently with the winding (`VG.028`).
- Avoid coincident meshes occupying identical space (`VG.008`).
- Place the asset at the origin with a neutral root transform (`VG.025`).

### Rigid bodies and colliders (`FET_003_STANDARD`)

- Apply `UsdPhysicsRigidBodyAPI` to at least one `UsdGeomXformable` prim
  (`RB.001`), and only to `UsdGeomXformable` prims (`RB.003`).
- Apply `UsdPhysicsCollisionAPI` only on `UsdGeom.Gprim` prims, not on bare
  Xforms (`RB.COL.001`).
- Apply `UsdPhysicsMeshCollisionAPI` only on `UsdGeom.Mesh`, always paired with
  `UsdPhysicsCollisionAPI` (`RB.COL.002`, `RB.COL.003`).
- Keep world scale uniform on Sphere, Capsule, Cylinder, Cone, and Points
  colliders; Mesh and Cube may be scaled non-uniformly (`RB.COL.004`).
- Do not apply `PhysicsRigidBodyAPI` inside an `instanceable = true` prototype;
  apply it on the instance root instead (`RB.005`).
- Author `float physics:mass` on the body or its descendant colliders
  (`RB.007`).
- Keep the composed world transform of a rigid body free of skew (`RB.009`).
- Set `uniform token purpose = "guide"` on collision-only meshes that should not
  render (`RB.010`).

## Optional feature requirements

### Multibody joints (`FET_004_STANDARD`)

- Connect constrained bodies with a `UsdPhysicsJoint` subtype and author
  `rel physics:body0` and `rel physics:body1`; an empty side means world
  (`JT.001`).
- Target existing prims, or leave the relationship empty (`JT.002`), with at
  most one target each (`JT.003`).
- Do not nest `PhysicsArticulationRootAPI` (`JT.ART.002`), and do not apply it
  to kinematic (`JT.ART.003`) or disabled/static (`JT.ART.004`) bodies.
- Apply `PhysicsRigidBodyAPI` to at least two separate `UsdGeomXformable`
  hierarchies (`RB.MB.001`).

### Grasp physics (`FET_005_STANDARD`)

- Bind a physics material to every collider through
  `rel material:binding:physics` (`PMT.001`).
- Author at least one grasp line that intersects graspable geometry, typically a
  `UsdGeom.BasisCurves` with two points, `int[] curveVertexCounts = [2]`, and
  `uniform token type = "linear"` (`GSP.001`).

`GSP.001` is a visual-semantic requirement with no executable validator. The
grasp line must cross a region a gripper can actually close on, so it needs
visual review rather than an arbitrary line.

### Materials (`FET_006_STANDARD` and `FET_006_MDL`)

`FET_006_STANDARD` covers `UsdPreviewSurface` assets:

- Bind materials from inside a payload to materials defined in that payload
  scope (`VM.BIND.001`).
- Use only spec-defined `UsdPreviewSurface` inputs, types, and tokens, and do
  not time-sample uniform token inputs (`VM.PS.001`).

`FET_006_MDL` covers MDL assets and adds:

- Match shader `inputs:*` types to the MDL module or SDR spec (`VM.BIND.002`).
- Resolve a bound material for every renderable Gprim (`VM.MAT.001`).
- Author a non-empty `uniform asset info:mdl:sourceAsset` with a `./`-relative
  `.mdl` path that exists (`VM.MDL.001`), using
  `info:implementationSource = "sourceAsset"` rather than the deprecated
  `mdlMaterial` form (`VM.MDL.002`).
- Keep texture images at or below 16384 px in both dimensions (`VM.TEX.001`).
- Set `inputs:sourceColorSpace = "sRGB"` on base color textures and `"raw"` on
  metallic, roughness, height, opacity, and normal maps; 8-bit normal maps also
  need `inputs:scale = (2, 2, 2, 1)` and `inputs:bias = (-1, -1, -1, 0)`
  (`VM.TEX.002`).

### Non-visual sensor materials (`FET_007_STANDARD`)

- Author `token[] omni:simready:nonvisual:attributes` (`NVM.001`),
  `token omni:simready:nonvisual:base` (`NVM.002`), and
  `token omni:simready:nonvisual:coating` (`NVM.003`) using the token values
  allowed by the non-visual materials capability.
- Author these tokens only on materials actually bound to geometry (`NVM.004`),
  keep them semantically consistent with the visual material (`NVM.005`), and do
  not time-sample them (`NVM.006`).

## Runtime physics variants (version 3.1.0)

Version `3.1.0` adds optional runtime variant scaffolding so one asset can carry
PhysX, Newton, and MuJoCo physics without any runtime seeing another's schemas.

### Variant scaffolding (`FET_000_PHYSX`, `FET_000_NEWTON`, `FET_000_MUJOCO`)

On the stage `defaultPrim`, author one variant set per runtime, named exactly
`PhysX`, `Newton`, or `MuJoCo`, each with `Disabled` and `Enabled` options and a
default selection of `Disabled` (`RV.001`, `RV.004`, `RV.007`).

The `Enabled` option must contain exactly one anchored payload and nothing else
(`RV.002`, `RV.005`, `RV.008`, `RV.010`):

```usd
variantSet "PhysX" = {
    "Disabled" {
    }
    "Enabled" {
        prepend payload = @../runnables/physics/physx.usd@
    }
}
```

Record the activation in root-layer `customLayerData` under
`SimReady_Metadata.Variants.Physics.<Runtime>` with `prim`, `variantSetName`,
and `activateOption` keys (`RV.003`, `RV.006`, `RV.009`).

With one runtime enabled and the others disabled, the composed stage must
contain only neutral `UsdPhysics`/`physics:` data plus that runtime's own
schemas (`RV.011`). Foreign-runtime data leaking into the composed stage is a
failure.

### PhysX rigid bodies and multibody (`FET_003_PHYSX`, `FET_004_PHYSX`)

- Apply `PhysicsCollisionAPI` on a `UsdGeom.Gprim`, or on an Xform that also has
  `PhysxMeshMergeCollisionAPI` whose `collection:collisionmeshes:includes`
  resolves to at least one Gprim (`PHYSX.COL.001`).
- Apply `PhysicsMeshCollisionAPI` on a `UsdGeom.Mesh` or a prim with
  `PhysxMeshMergeCollisionAPI`, always alongside `PhysicsCollisionAPI`
  (`PHYSX.COL.002`).
- `FET_004_PHYSX@0.4.0` adds the mass and nesting rules: every rigid-body
  subtree needs authored `physics:mass > 0` or a collider with non-zero volume
  for auto-mass (`RB.011`), and nested rigid bodies must be connected by a joint
  (`RB.012`).

`physics:approximation = "sdf"` is a PhysX-only value. Authoring it in the
neutral base layer fails `RV.011`.

### Newton rigid bodies and multibody (`FET_003_NEWTON`, `FET_004_NEWTON`)

- Apply either `NewtonMeshCollisionAPI` or `NewtonSDFCollisionAPI` on a
  `UsdGeom.Mesh`, but not both (`NEWTON.COL.001`).
- Keep authored SDF values valid: non-negative `newton:contactMargin`,
  `newton:contactGap`, and `newton:sdfPadding`; a positive
  `newton:sdfMaxResolution` divisible by 8; `newton:sdfTextureFormat` in
  `{uint8, uint16, float32}`; and
  `newton:sdfNarrowBandInner < newton:sdfNarrowBandOuter` (`NEWTON.COL.002`).
- Apply `NewtonMassAPI` only on `Xformable` prims, with `double[] newton:inertia`
  either empty or exactly six finite elements (`NEWTON.MAS.001`).
- Apply `NewtonMaterialAPI` only on a `UsdShade.Material` that also has
  `PhysicsMaterialAPI` (`NEWTON.MAT.001`).

### MuJoCo rigid bodies and multibody (`FET_003_MUJOCO`, `FET_004_MUJOCO`)

- Apply `MjcCollisionAPI` alongside `PhysicsCollisionAPI` on every active MuJoCo
  collider `UsdGeom.Gprim` (`MUJOCO.COL.001`).
- Apply `MjcMeshCollisionAPI` only on `UsdGeom.Mesh`, with
  `uniform token mjc:inertia` in `{legacy, convex, exact, shell}` and
  `uniform int mjc:maxhullvert >= -1` (`MUJOCO.COL.002`).
- Mesh colliders carrying both `PhysicsMeshCollisionAPI` and `MjcCollisionAPI`
  must set `uniform token physics:approximation = "convexHull"`.

## Naming conventions

### Prim naming

- Choose either `camelCase` or `snake_case` and use it consistently.
- Avoid spaces, special characters, and reserved keywords.
- Use descriptive, purpose-driven names.
- Use prefixes by prim type when appropriate (e.g., `mesh_`, `material_`).

### File naming

- Use lowercase file names.
- Use `.usd`, `.usda`, `.usdc`, or `.usdz` as appropriate.
- Use underscores or hyphens; avoid spaces and special characters.
- Avoid reserved names (e.g., `CON`, `PRN`, `AUX`, `NUL`).
- Use version numbers when appropriate (e.g., `_v1.0`).

## Validation metadata (recommended)

Include profile metadata in `customLayerData` to simplify validation workflows:

```usd
customLayerData = {
    dictionary SimReady_Metadata = {
        dictionary validation = {
            string profile = "Robotics-Prop"
            string profile_version = "3.1.0"
        }
    }
}
```

## Conformance workflow

Repair one feature gate at a time, in dependency order:

```text
validate Robotics-Prop
-> simready-foundation-conform-fet-000-standard
-> simready-foundation-conform-fet-001-standard
-> simready-foundation-conform-fet-003-standard (or -physx / -newton / -mujoco)
-> simready-foundation-conform-fet-004-standard (only for multibody props)
-> simready-foundation-conform-fet-005-standard
-> simready-foundation-conform-fet-006-standard or -mdl
-> simready-foundation-conform-fet-007-standard (only when selected)
-> validate Robotics-Prop again
```

## References

- [Feature dependency graph](../features/feature-dependency-graph) — requirements and dependencies for all features
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/robotics_prop.toml`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_000_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_001_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_005_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_006_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_006_MDL.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_007_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/naming_paths/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/atomic_asset/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/runtime_variants/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/sim_ready/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/units/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/hierarchy/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/visualization/geometry/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/visualization/materials/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_rigid_bodies/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_joints/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_materials/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_graspable/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/nonvisual_sensors/nonvisual_materials/`
