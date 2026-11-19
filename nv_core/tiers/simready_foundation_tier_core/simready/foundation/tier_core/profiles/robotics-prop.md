# Robotics-Prop Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Robotics-Prop` profile. It consolidates the required feature set, USD
properties, naming conventions, and the optional runtime variants that this
profile exposes.

`Robotics-Prop` is the consolidated prop profile. It replaces the former
separate neutral and runtime-specific prop profiles with a single
profile whose neutral OpenUSD core is mandatory and whose solver-specific
behavior is selected through optional features.

## SimReady Foundations 10.0 — 5.0.0

`Robotics-Prop` 5.0.0 requires
[`FET008_ObjectForward.0-1-0`](../features/FET008_ObjectForward.md) for
semantic facing and
[`FET009_MaterialCoverage.0-1-0`](../features/FET009_MaterialCoverage.md)
for material binding (`VM.MAT.001`) and rendered coverage.
It selects `FET006_Materials.0-3-0` (required),
`FET006_Materials.Openpbr.0-2-0` and `FET006_Materials.MDL.0-3-0` (optional),
and the optional PhysX, Newton, and MuJoCo Core capabilities at `0-2-0`.
Version 4.0.0 is the SimReady Foundations 8.0 contract.

Migration from 4.0.0 requires an authored forward vector or visual evidence
through `simready-foundation-conform-fet-008-object-forward`, material-coverage
validation, and the selected features' runtime tests. Preserve staged output
and independent validation evidence for every requested profile.

## Profile definition

The `Robotics-Prop` profile includes the following feature set (see
`robotics_prop.toml` and the
[feature dependency graph](../../../../../../sr_specs/docs/shared/features/feature-dependency-graph.md)). Each
feature's requirements and dependencies are defined in the feature
specifications.

```toml
# Generated Foundations 2 projection. See ../catalog-map.json.

[Robotics-Prop]
"3.0.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET005_Grasp.0-1-0", optional = true},
    {selector = "FET006_Materials.0-1-0", optional = true},
    {selector = "FET006_Materials.MDL.0-1-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET004_Multibody.Newton.0-1-0", optional = true},
], capabilities = [
    {selector = "CAP000_Core.0-1-0"},
    {selector = "CAP007_NonVisualMaterials.0-2-0", optional = true},
]}
"3.1.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET005_Grasp.0-1-0", optional = true},
    {selector = "FET006_Materials.0-1-0", optional = true},
    {selector = "FET006_Materials.MDL.0-1-0", optional = true},
    {selector = "FET003_RigidBody.PhysX.0-4-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET003_RigidBody.Newton.0-1-0", optional = true},
    {selector = "FET004_Multibody.Newton.0-1-0", optional = true},
], capabilities = [
    {selector = "CAP000_Core.0-1-0"},
    {selector = "CAP007_NonVisualMaterials.0-2-0", optional = true},
    {selector = "CAP000_Core.PhysX.0-1-0", optional = true},
    {selector = "CAP000_Core.Newton.0-1-0", optional = true},
    {selector = "CAP000_Core.MuJoCo.0-1-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
]}
"3.2.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET005_Grasp.0-1-0", optional = true},
    {selector = "FET006_Materials.0-1-0", optional = true},
    {selector = "FET006_Materials.MDL.0-1-0", optional = true},
    {selector = "FET011_SemanticLabels.0-2-0"},
    {selector = "FET011_SemanticLabels.RTX.0-1-0"},
    {selector = "FET003_RigidBody.PhysX.0-4-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET003_RigidBody.Newton.0-1-0", optional = true},
    {selector = "FET004_Multibody.Newton.0-1-0", optional = true},
], capabilities = [
    {selector = "CAP000_Core.0-1-0"},
    {selector = "CAP007_NonVisualMaterials.0-2-0", optional = true},
    {selector = "CAP046_WikidataLabels.0-1-0"},
    {selector = "CAP031_SelfContainedPackage.0-1-0"},
    {selector = "CAP033_SimReadyPackage.0-3-0"},
    {selector = "CAP100_IsaacComposition.Isaac.0-4-0", optional = true},
    {selector = "CAP000_Core.PhysX.0-1-0", optional = true},
    {selector = "CAP000_Core.Newton.0-1-0", optional = true},
    {selector = "CAP000_Core.MuJoCo.0-1-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
]}
"3.3.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET005_Grasp.0-1-0", optional = true},
    {selector = "FET006_Materials.0-1-0", optional = true},
    {selector = "FET006_Materials.MDL.0-1-0", optional = true},
    {selector = "FET011_SemanticLabels.0-2-0"},
    {selector = "FET011_SemanticLabels.RTX.0-1-0"},
    {selector = "FET003_RigidBody.PhysX.0-4-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET003_RigidBody.Newton.0-1-0", optional = true},
    {selector = "FET004_Multibody.Newton.0-1-0", optional = true},
], capabilities = [
    {selector = "CAP000_Core.0-2-0"},
    {selector = "CAP007_NonVisualMaterials.0-2-0", optional = true},
    {selector = "CAP046_WikidataLabels.0-1-0"},
    {selector = "CAP031_SelfContainedPackage.0-1-0"},
    {selector = "CAP033_SimReadyPackage.0-4-0"},
    {selector = "CAP100_IsaacComposition.Isaac.0-4-0", optional = true},
    {selector = "CAP000_Core.PhysX.0-1-0", optional = true},
    {selector = "CAP000_Core.Newton.0-1-0", optional = true},
    {selector = "CAP000_Core.MuJoCo.0-1-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
]}
"4.0.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET005_Grasp.0-1-0", optional = true},
    {selector = "FET006_Materials.0-2-0"},
    {selector = "FET006_Materials.Openpbr.0-1-0", optional = true},
    {selector = "FET006_Materials.MDL.0-2-0", optional = true},
    {selector = "FET010_DisplayColor.0-1-0", optional = true},
    {selector = "FET011_SemanticLabels.0-2-0"},
    {selector = "FET011_SemanticLabels.RTX.0-1-0"},
    {selector = "FET003_RigidBody.PhysX.0-4-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET003_RigidBody.Newton.0-1-0", optional = true},
    {selector = "FET004_Multibody.Newton.0-1-0", optional = true},
], capabilities = [
    {selector = "CAP000_Core.0-2-0"},
    {selector = "CAP007_NonVisualMaterials.0-2-0", optional = true},
    {selector = "CAP046_WikidataLabels.0-1-0"},
    {selector = "CAP031_SelfContainedPackage.0-1-0"},
    {selector = "CAP033_SimReadyPackage.0-4-0"},
    {selector = "CAP100_IsaacComposition.Isaac.0-4-0", optional = true},
    {selector = "CAP000_Core.PhysX.0-1-0", optional = true},
    {selector = "CAP000_Core.Newton.0-1-0", optional = true},
    {selector = "CAP000_Core.MuJoCo.0-1-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
]}

"5.0.0" = {features = [
    {selector = "FET008_ObjectForward.0-1-0"},
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET005_Grasp.0-1-0", optional = true},
    {selector = "FET006_Materials.0-3-0"},
    {selector = "FET006_Materials.Openpbr.0-2-0", optional = true},
    {selector = "FET006_Materials.MDL.0-3-0", optional = true},
    {selector = "FET009_MaterialCoverage.0-1-0"},
    {selector = "FET010_DisplayColor.0-1-0", optional = true},
    {selector = "FET011_SemanticLabels.0-2-0"},
    {selector = "FET011_SemanticLabels.RTX.0-1-0"},
    {selector = "FET003_RigidBody.PhysX.0-4-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET003_RigidBody.Newton.0-1-0", optional = true},
    {selector = "FET004_Multibody.Newton.0-1-0", optional = true},
], capabilities = [
    {selector = "CAP000_Core.0-2-0"},
    {selector = "CAP007_NonVisualMaterials.0-2-0", optional = true},
    {selector = "CAP046_WikidataLabels.0-1-0"},
    {selector = "CAP031_SelfContainedPackage.0-1-0"},
    {selector = "CAP033_SimReadyPackage.0-4-0"},
    {selector = "CAP100_IsaacComposition.Isaac.0-4-0", optional = true},
    {selector = "CAP000_Core.PhysX.0-2-0", optional = true},
    {selector = "CAP000_Core.Newton.0-2-0", optional = true},
    {selector = "CAP000_Core.MuJoCo.0-2-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
]}
```

Version `3.2.0` additionally makes SimReady semantic labels, packaging source,
and provenance metadata required, and adds Kit-free Isaac Sim composition as an
optional feature. The neutral runtime-variant scaffolding also stays optional, so
the Isaac-composed asset and the neutral runtime variants are validated together
on the same asset. See [Version 3.2.0 changes](#version-3-2-0-changes).

Version `3.3.0` keeps that `3.2.0` menu and adopts `CAP000_Core.0-2-0`
(drops `NP.006` and `SR.001`) plus `CAP033_SimReadyPackage.0-4-0` (`SR.004` USD/sidecar
union). See [Version 3.3.0 changes](#version-3-3-0-changes).

Version `4.0.0` is the SimReady Foundations 8.0 release of that same `3.3.0` contract. See
[Version 4.0.0 changes](#version-4-0-0-changes).

### Required versus optional features

`FET006_Materials` and `FET006_Materials.MDL` remain optional through version `3.3.0`.
Version `4.0.0` makes `FET006_Materials` part of the required baseline and adds
display colour and OpenPBR as optional alternatives.

| Contract | Version | Status | Purpose |
|---|---|---|---|
| `CAP000_Core` | 0-2-0 (`3.3.0` and later; earlier versions pin 0-1-0) | Required | Core file layout and anchored references |
| `FET001_MinimalPlaceableVisual` | 1-0-1 | Required | Minimal OpenUSD asset: units, hierarchy, mesh geometry |
| `FET003_RigidBody` | 0-2-0 | Required | Neutral rigid-body physics and colliders |
| `FET004_Multibody` | 0-2-0 | Optional | Neutral multibody joints |
| `FET005_Grasp` | 0-1-0 | Optional | Grasp physics (physics material + grasp line) |
| `FET006_Materials` | 0-1-0 optional through `3.3.0`; 0-2-0 required from `4.0.0`; 0-3-0 required from `5.0.0` | Version-dependent | `UsdPreviewSurface` materials |
| `FET010_DisplayColor` | 0-1-0 (from profile `4.0.0`) | Optional | Display colour and opacity |
| `FET006_Materials.MDL` | 0-1-0 through `3.3.0`; 0-2-0 from `4.0.0`; 0-3-0 from `5.0.0` | Optional | MDL materials |
| `FET006_Materials.Openpbr` | 0-1-0 (`4.0.0`); 0-2-0 (from `5.0.0`) | Optional | OpenPBR materials |
| `FET009_MaterialCoverage` | 0-1-0 (from profile `5.0.0`) | Required | Every renderable `Gprim` resolves a material (`VM.MAT.001`), and the asset's own materials cover its silhouette in renders |
| `CAP007_NonVisualMaterials` | 0-2-0 | Optional | Non-visual sensor materials |

A single-rigid-body prop satisfies the required set through `FET003_RigidBody`
alone. Select `FET004_Multibody` only for props intentionally authored as a
multibody assembly with joints.

Version `3.1.0` additionally exposes optional PhysX, Newton, and MuJoCo runtime
variants. Each runtime is a three-feature chain: `CAP000_Core.<Runtime>` for the
variant scaffolding, `FET003_RigidBody.<Runtime>` for rigid bodies, and
`FET004_Multibody.<Runtime>` for multibody joints.

Version `4.0.0` makes the baseline appearance mandatory: every conforming asset
carries a `UsdPreviewSurface` material (`FET006_Materials`). Display colour,
OpenPBR and MDL remain optional, so an asset picks whichever final surface its
runtime needs without being forced to author them all.
Requirements shared between a required and an optional feature stay required. From
`4.0.0`, `FET006_Materials` makes `com.nvidia.usd.VM.BIND.001`,
`com.nvidia.usd.VM.PS.001`, `VM.PS.002`, `VM.TEX.001` and `VM.TEX.003` mandatory, and
`VM.MAT.001` in `4.0.0`. From `5.0.0`, `VM.MAT.001` is required through
`FET009_MaterialCoverage` instead.
`VM.BIND.002` and the OpenPBR (`VM.PBR.001` to `VM.PBR.003`, `VM.TEX.004`) and MDL
(`VM.MDL.001`, `com.nvidia.usd.VM.MDL.002`, `VM.MDL.003`, `VM.TEX.005`) requirements stay optional.

## Required USD properties and schemas

### Core file layout (`CAP000_Core`)

- Keep the folder holding the main asset file free of other USD files
  (`NP.005`).
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

### Stage metadata and hierarchy (`FET001_MinimalPlaceableVisual`)

- Set `upAxis = "Z"` (`UN.006`) and `metersPerUnit = 1.0` (`UN.007`).
- Set `defaultPrim` to an existing prim (`HI.004`).
- Parent all prims under a single stage root prim (`HI.001`) that inherits
  `UsdGeomXformable`, typically `def Xform` (`HI.003`). A `Scope`, `Material`,
  or `Shader` root is invalid.
- Use anchored `./` or `../` reference paths that do not escape the asset root
  (`AA.001`), pointing only at supported file types: USD, `.png`, `.jpeg`,
  `.jpg`, `.exr`, `.m4a`, `.mp3`, `.wav` (`AA.002`).

### Geometry (`FET001_MinimalPlaceableVisual`)

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

### Rigid bodies and colliders (`FET003_RigidBody`)

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

### Material binding (`FET009_MaterialCoverage`)

Required from profile `5.0.0`:

- Resolve a material for every renderable Gprim at the `full` purpose, bound on the prim
  or inherited from an ancestor. A Gprim with material-bind `GeomSubset` children resolves
  one for each subset (`VM.MAT.001`).

`simready-foundation-conform-fet-009-standard` repairs a `VM.MAT.001` failure. Through
`5.0.0`, `FET006_Materials` 0-2-0 holds `VM.MAT.001` instead, and
`simready-foundation-conform-fet-006-standard` repairs it.

## Optional feature requirements

### Multibody joints (`FET004_Multibody`)

- Connect constrained bodies with a `UsdPhysicsJoint` subtype and author
  `rel physics:body0` and `rel physics:body1`; an empty side means world
  (`JT.001`).
- Target existing prims, or leave the relationship empty (`JT.002`), with at
  most one target each (`JT.003`).
- Do not nest `PhysicsArticulationRootAPI` (`JT.ART.002`), and do not apply it
  to kinematic (`JT.ART.003`) or disabled/static (`JT.ART.004`) bodies.
- Apply `PhysicsRigidBodyAPI` to at least two separate `UsdGeomXformable`
  hierarchies (`RB.MB.001`).

### Grasp physics (`FET005_Grasp`)

- Bind a physics material to every collider through
  `rel material:binding:physics` (`PMT.001`).
- Author at least one grasp line that intersects graspable geometry, typically a
  `UsdGeom.BasisCurves` with two points, `int[] curveVertexCounts = [2]`, and
  `uniform token type = "linear"` (`GSP.001`).

`GSP.001` is a visual-semantic requirement with no executable validator. The
grasp line must cross a region a gripper can actually close on, so it needs
visual review rather than an arbitrary line.

### Materials (`FET006_Materials`, `FET010_DisplayColor`, `FET006_Materials.Openpbr`, and `FET006_Materials.MDL`)

From profile `4.0.0`, `FET006_Materials` is required rather than optional;
`FET010_DisplayColor`, `FET006_Materials.Openpbr` and `FET006_Materials.MDL` stay optional.
Through `3.3.0`, the Standard and MDL material features remain optional and the
display-colour and OpenPBR features are not listed.

`FET006_Materials` covers `UsdPreviewSurface` assets:

- Bind materials from inside a payload to materials defined in that payload
  scope (`com.nvidia.usd.VM.BIND.001`).
- Use only spec-defined `UsdPreviewSurface` inputs, types, and tokens, and do
  not time-sample uniform token inputs (`com.nvidia.usd.VM.PS.001`).

Both are defined and enforced by `usd-validation-nvidia` rather than by this
repository.

From version 0-2-0 (profile `4.0.0`) it also adds:

- Connect a `UsdPreviewSurface` on `outputs:surface` of every material a renderable Gprim
  resolves (`VM.PS.002`).
- Keep texture images at or below 16384 px in both dimensions (`VM.TEX.001`).
- Declare `inputs:sourceColorSpace` on every texture to match how its input reads the
  image: `sRGB` or `raw` on albedo reaching `diffuseColor`, matching the image's encoding;
  `sRGB` on `emissiveColor` and `specularColor`; `raw` on data (`VM.TEX.003`).
- Resolve a bound material for every renderable Gprim (`VM.MAT.001`), in version 0-2-0
  only. From 0-3-0 (profile `5.0.0`), `FET009_MaterialCoverage` holds it.

`FET010_DisplayColor` covers the display-colour appearance layer, from profile
`4.0.0`:

- Resolve a display colour on every renderable Gprim, authored on the prim or
  inherited from an ancestor (`DISP.001`).
- Keep authored `primvars:displayColor` values within the range a consumer can
  interpret, in the colour space resolved for the attribute (`DISP.002`).
- Keep authored `primvars:displayOpacity` values within their valid range
  (`DISP.003`).

Display colour carries no shading network, so it is the appearance available to
consumers that do not evaluate materials. It is a sibling of the other three
material features, not a dependency of any of them.

`FET006_Materials.Openpbr` covers OpenPBR (MaterialX) assets, from profile `4.0.0`:

- Author an OpenPBR surface on `outputs:mtlx:surface` (`VM.PBR.001`).
- Keep OpenPBR parameter values within their defined ranges (`VM.PBR.002`).
- Keep the MaterialX graph structurally valid, with no dangling connections (`VM.PBR.003`).
- Declare `colorSpace` on every texture input to match how it reads the image (`VM.TEX.004`).
- Plus `com.nvidia.usd.VM.BIND.001`, `VM.BIND.002` and `VM.TEX.001`, and `VM.MAT.001` in
  version 0-1-0.

`FET006_Materials.MDL` covers MDL assets and adds:

- Match shader `inputs:*` types to the MDL module or SDR spec (`VM.BIND.002`).
- Resolve a bound material for every renderable Gprim (`VM.MAT.001`), through version 0-2-0.
- Connect an MDL surface on `outputs:mdl:surface` of every material a renderable Gprim
  resolves (`VM.MDL.003`), from version 0-2-0.
- Author a non-empty `uniform asset info:mdl:sourceAsset` with an explicit
  relative `.mdl` path (`./` or `../`) that exists (`VM.MDL.001`), using
  `info:implementationSource = "sourceAsset"` rather than the deprecated
  `mdlMaterial` form (`com.nvidia.usd.VM.MDL.002`).
- Keep texture images at or below 16384 px in both dimensions (`VM.TEX.001`).
- Author `colorSpace` metadata on each `asset inputs:*` texture input of the MDL
  shader: `srgb_rec709_scene` or `raw` on `diffuse_texture`, matching the image's
  encoding; `srgb_rec709_scene` on the other colour textures — `emissive_color_texture`,
  and on OmniGlass `glass_color_texture` and `reflection_color_texture`; and `raw` on
  every other texture input, including roughness, metalness, ambient occlusion, ORM,
  opacity, emissive mask, and normal and detail-normal maps (`VM.TEX.002` in version 0-1-0,
  `VM.TEX.005` from 0-2-0). This is `colorSpace` metadata on the input,
  not the `UsdUVTexture` attribute `inputs:sourceColorSpace`, which states the same
  thing in a different vocabulary for a shader class this requirement does not cover.
  The 8-bit normal-map scale and bias convention belongs to that reader too, and is
  not checked here.

### Material coverage (`FET009_MaterialCoverage`)

Required from profile `5.0.0`. Rendered, at least `min_material_coverage` (default `0.98`)
of the asset's silhouette shows its own materials instead of test-owned control materials
(`VM.MAT.001`):

- in the universal render context, for every asset;
- in the `mtlx` and `mdl` render contexts, for an asset whose geometry resolves a material
  with a surface on that context at the `full` purpose. An asset with none skips that
  measurement.

The runtime tests render in Kit with RTX. The
[feature page](../features/FET009_MaterialCoverage.md) lists their requirements and
what coverage does not establish.
`simready-foundation-conform-fet-009-standard` repairs a coverage failure.

### Non-visual sensor materials (`CAP007_NonVisualMaterials`)

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

### Variant scaffolding (`CAP000_Core.PhysX`, `CAP000_Core.Newton`, `CAP000_Core.MuJoCo`)

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
        prepend payload = @./runnables/physics/physx.usd@
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

### PhysX rigid bodies and multibody (`FET003_RigidBody.PhysX`, `FET004_Multibody.PhysX`)

- Apply `PhysicsCollisionAPI` on a `UsdGeom.Gprim`, or on an Xform that also has
  `PhysxMeshMergeCollisionAPI` whose `collection:collisionmeshes:includes`
  resolves to at least one Gprim (`PHYSX.COL.001`).
- Apply `PhysicsMeshCollisionAPI` on a `UsdGeom.Mesh` or a prim with
  `PhysxMeshMergeCollisionAPI`, always alongside `PhysicsCollisionAPI`
  (`PHYSX.COL.002`).
- `FET004_Multibody.PhysX.0-4-0` adds the mass and nesting rules: every rigid-body
  subtree needs authored `physics:mass > 0` or a collider with non-zero volume
  for auto-mass (`RB.011`), and nested rigid bodies must be connected by a joint
  (`RB.012`).

`physics:approximation = "sdf"` is a PhysX-only value. Authoring it in the
neutral base layer fails `RV.011`.

### Newton rigid bodies and multibody (`FET003_RigidBody.Newton`, `FET004_Multibody.Newton`)

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

### MuJoCo rigid bodies and multibody (`CAP003_RigidBody.MuJoCo`, `CAP004_Multibody.MuJoCo`)

- Apply `MjcCollisionAPI` alongside `PhysicsCollisionAPI` on every active MuJoCo
  collider `UsdGeom.Gprim` (`MUJOCO.COL.001`).
- Apply `MjcMeshCollisionAPI` only on `UsdGeom.Mesh`, with
  `uniform token mjc:inertia` in `{legacy, convex, exact, shell}` and
  `uniform int mjc:maxhullvert >= -1` (`MUJOCO.COL.002`).
- Mesh colliders carrying both `PhysicsMeshCollisionAPI` and `MjcCollisionAPI`
  must set `uniform token physics:approximation = "convexHull"`.

(version-3-2-0-changes)=
## Version 3.2.0 changes

Version `3.2.0` keeps the full `3.1.0` feature set and adds required SimReady
semantic-label, packaging-source, and provenance-metadata features:

| Contract | Version | Status | Purpose |
|---|---|---|---|
| `FET011_SemanticLabels` | 0-2-0 | Required | Semantic labels |
| `FET011_SemanticLabels.RTX` | 0-1-0 | Required | Semantic labels (RTX) |
| `CAP046_WikidataLabels` | 0-1-0 | Required | Wikidata Q-Code |
| `CAP031_SelfContainedPackage` | 0-1-0 | Required | Self-contained package source (`AA.001`) |
| `CAP033_SimReadyPackage` | 0-3-0 | Required | Thumbnail (`SR.002`) and nested provenance metadata (`SR.003`) |
| `CAP100_IsaacComposition.Isaac` | 0-4-0 | Optional | Kit-free Isaac Sim composition (`ISA.001`) |

`CAP033_SimReadyPackage.0-3-0` requires a PNG thumbnail at
`.thumbs/256x256/<asset_filename>.png` next to the root asset, and a
`customLayerData.SimReady_Metadata` dictionary carrying the string provenance
fields (`author`, `asset_name`, `asset_type`, `asset_license`, `category`,
`source_file`, `usd_date_generated`) plus the asset-descriptive fields `qcode`
(Wikidata Q-Code), `rigid_body_count` (non-negative int), `asset_extents`
(float3 meters, XYZ), and `mass` (positive kilograms). Derive the physical
fields from the actual asset rather than fabricating them.

### Isaac Sim composition (`CAP100_IsaacComposition.Isaac`)

`CAP100_IsaacComposition.Isaac.0-4-0` (`ISA.001`) is optional at the profile level. When it is
present, it requires the package to be a standalone Isaac component:

- The interface prim sets `kind = component`.
- A `payloads/` directory holds `base.usda`, `geometries.usd`, `instances.usda`,
  and `materials.usda`.
- The interface references `./payloads/base.usda`.

`CAP100_IsaacComposition.Isaac.0-4-0` depends on the PhysX rigid-body chain, so its PhysX
requirements are validated as dependencies even though `CAP000_Core.PhysX` and
`FET003_RigidBody.PhysX` stay optional at the profile level. The neutral runtime-variant
scaffolding (`CAP000_Core.PhysX`/`CAP000_Core.Newton`/`CAP000_Core.MuJoCo`) also stays
optional, so the Isaac `payloads/` perf layout and the neutral
`runnables/physics/<stem>.usd` runtime variants coexist on the same asset. The
default composition is the neutral base (all runtimes `Disabled`), which also
satisfies `FET003_RigidBody`.

The Isaac composition is produced by public, Kit-free
`isaacsim-asset-isolated==6.2.0.1` via the
`simready_physx_to_isaac_prop` profile retained by the thin
`simready.asset_transformer` integration. The integration also provides
SimReady-specific rules and small guarded temporary transformer patches while
preserving public rule FQCNs. Run it with Python 3.12 and
`pip install "simready-foundation-tier-core[isaac]"`. This optional extra also
installs `isaacsim-robot-schema==6.2.0.0`; both Isaac packages come from PyPI.
The transform builds the component interface and `payloads/` perf layers.
Provenance is a separate step that
derives the `CAP033_SimReadyPackage.0-3-0` `SR.003` physical fields
(`rigid_body_count`, summed authored `mass`, world-space `asset_extents`) from
the *source* stage — the composed interface hides mass inside instanced payload
prototypes — and stamps them, along with the string provenance fields and a
`256x256` `SR.002` thumbnail, into the composed interface's
`customLayerData.SimReady_Metadata`. Physical fields must be derived from the
actual asset, never fabricated. On `3.3.0` and `4.0.0` the same fields may also
live in the USD/sidecar union (`CAP033_SimReadyPackage.0-4-0`).

(version-3-3-0-changes)=
## Version 3.3.0 changes

Version `3.3.0` keeps the full `3.2.0` feature set. The only contract changes
are feature-version bumps:

| Contract | From | To | Why |
|---|---|---|---|
| `CAP000_Core` | 0-1-0 | 0-2-0 | Drop `NP.006` and `SR.001`. Nested provenance stays `SR.003` on `CAP033_SimReadyPackage.0-3-0`; union provenance is `SR.004` on `CAP033_SimReadyPackage.0-4-0`. |
| `CAP033_SimReadyPackage` | 0-3-0 | 0-4-0 | Replace `SR.003` with `SR.004`. Same field set; fields are read from the USD/sidecar union. Nested `SimReady_Metadata` is no longer required on its own. |

Assets that already passed `3.2.0` with nested `SimReady_Metadata` still satisfy
`3.3.0`. No feature adapter is required; a sidecar JSON is an optional extra
location, not a new required file.

(version-4-0-0-changes)=
## Version 4.0.0 changes

Version `4.0.0` is the SimReady Foundations 8.0 release pin. It keeps the `3.3.0`
feature set and adds the baseline visual material contract: `FET006_Materials.0-2-0`
is required, and `FET010_DisplayColor`, `FET006_Materials.Openpbr` and `FET006_Materials.MDL` are
optional. An asset that passed `3.3.0` needs a `UsdPreviewSurface` on every bound
material to satisfy `4.0.0`.

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
            string profile_version = "4.0.0"
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

- [Feature dependency graph](../../../../../../sr_specs/docs/shared/features/feature-dependency-graph.md) — requirements and dependencies for all features
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/robotics_prop.toml`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET001_MinimalPlaceableVisual.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET003_RigidBody.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET005_Grasp.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET006_Materials.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET006_Materials.MDL.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP007_NonVisualMaterials.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/naming_paths/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/atomic_asset/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/sim_ready/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/units/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/hierarchy/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/visualization/geometry/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/visualization/materials/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/physics_rigid_bodies/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/physics_joints/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/physics_materials/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/physics_graspable/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/nonvisual_sensors/nonvisual_materials/`
