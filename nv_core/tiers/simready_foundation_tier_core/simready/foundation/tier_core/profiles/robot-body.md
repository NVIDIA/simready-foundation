# Robot-Body Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Robot-Body` profile. It consolidates the required feature set, USD properties,
naming conventions, and composition expectations for robot body assets.

`Robot-Body` version `2.0.0` is the consolidated robot profile. It supersedes
the separate `Robot-Body-Neutral`, `Robot-Body-Runnable`, and `Robot-Body-Isaac`
profiles by keeping a neutral OpenUSD core mandatory and exposing PhysX and
Isaac behavior as optional features. Version `2.1.0` keeps that menu, adds
required SimReady packaging and provenance metadata, and exposes optional
Newton and MuJoCo multiphysics runtime features (`FET004_Multibody.*`, `FET022_DrivenJoints.*`,
`CAP024_BaseArticulation.*`) alongside the existing PhysX variants. Version `2.2.0` keeps the
`2.1.0` set (including the Newton and MuJoCo multiphysics features) and adds
optional `CAP025_RosBridge.Ros.0-1-0` for Isaac ROS-Ready bridge wiring.
Version `2.3.0` adopts `CAP033_SimReadyPackage.0-4-0` for the SR.004 USD/sidecar
provenance union. Version `3.0.0` adds the visual-material baseline: required
UsdPreviewSurface plus optional display colour, OpenPBR, and MDL features. Version
`3.1.0` adds optional Object Forward, and version `4.0.0` keeps the `3.1.0` bundle
without the deprecated `CAP023_RobotMaterials.Isaac` and with material binding and coverage as
`FET009_MaterialCoverage`. It also requires `CAP000_Core.0-2-0`
and selects version `0-2-0` of the runtime and Isaac Core capabilities.

## Required Newton contracts — 4.0.0

Version 4.0.0 requires `FET003_RigidBody.Newton.0-1-0`,
`FET004_Multibody.Newton.0-1-0`, `FET022_DrivenJoints.Newton.0-1-0`,
`CAP000_Core.Newton.0-2-0`, and `CAP024_BaseArticulation.Newton.0-1-0`.
Install both Core and Newton tiers to resolve and validate this profile.
Their requirements and runtime evidence are blocking gates.

## Object Forward adoption — 3.1.0

`Robot-Body` 3.1.0 copies the complete 3.0.0 feature and capability bundle and
optionally includes [FET008_ObjectForward.0-1-0](../features/FET008_ObjectForward.md).
All existing selectors and optional flags are retained. Published profile
versions remain unchanged; select 3.1.0 explicitly to adopt this bundle.

Object Forward declares local semantic facing on the defaultPrim and explicit
components. Its Minimal dependency supplies UN.006: authored native `upAxis = "Z"`.
Select Object Forward for mobile/humanoid bodies with a semantic front;
industrial arms without a default facing need not adopt it.

Migration requires an explicit forward vector or visual evidence through
`simready-foundation-conform-fet-008-object-forward`; no adapter infers semantic
front automatically. Preserve staged output and AF.001 validation, then run the
Object Forward query and camera-response benchmarks. A passing static gate is
not runtime qualification. Robot-Gripper and GR.002 are unchanged.

## Robot Materials deprecation — 4.0.0

`Robot-Body` 4.0.0 leaves out `CAP023_RobotMaterials.Isaac`, which is deprecated. Versions
`2.0.0` through `3.1.0` select it as optional.

## Material binding — 4.0.0

`Robot-Body` 4.0.0 requires [`FET009_MaterialCoverage.0-1-0`](../features/FET009_MaterialCoverage.md) for material binding (`VM.MAT.001`) and its rendered coverage, and selects
`FET006_Materials.0-3-0` (required), `FET006_Materials.Openpbr.0-2-0` and
`FET006_Materials.MDL.0-3-0` (optional), which leave `VM.MAT.001` out.

## Required Core — 4.0.0

`Robot-Body` 4.0.0 requires the following Core configuration:

- It requires [`CAP000_Core.0-2-0`](../capabilities/CAP000_Core.md).
  The Core file-naming, layout, path, and undefined-prim requirements
  (`NP.002`-`NP.005`, `NP.007`, `NP.008`, `HI.010`) block validation. Through
  3.1.0 the profile reaches Core only through optional capabilities, so those
  requirements report as warnings.
- It requires `CAP000_Core.Newton.0-2-0` and selects version `0-2-0`
  of the optional `CAP000_Core.PhysX`, `CAP000_Core.MuJoCo`, and
  `CAP000_Core.Isaac` capabilities. Each depends on `CAP000_Core.0-2-0`, so 4.0.0 validates a
  single Core version and does not run `NP.006` or `SR.001`.

An asset that passed 3.1.0 must also pass the Core requirements to satisfy 4.0.0.
Repair them with `simready-foundation-conform-fet-000-standard` before the other
gates. No adapter is required.

## Profile definition

The `Robot-Body` profile includes the following feature set (see
`robot_body.toml` and the
[feature dependency graph](../../../../../../sr_specs/docs/shared/features/feature-dependency-graph.md)). Each
feature's requirements and dependencies are defined in the feature
specifications.

```toml
# Generated Foundations 2 projection. See ../catalog-map.json.

[Robot-Body]
"2.0.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET022_DrivenJoints.0-2-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET022_DrivenJoints.PhysX.0-2-0", optional = true},
    {selector = "FET022_DrivenJoints.Isaac.0-2-0", optional = true},
], capabilities = [
    {selector = "CAP021_RobotCore.Isaac.0-3-0", optional = true},
    {selector = "CAP024_BaseArticulation.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.PhysX.0-1-0", optional = true},
    {selector = "CAP000_Core.Isaac.0-1-0", optional = true},
    {selector = "CAP023_RobotMaterials.Isaac.0-1-0", optional = true},
    {selector = "CAP100_IsaacComposition.Isaac.0-3-0", optional = true},
]}
"2.1.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET022_DrivenJoints.0-2-0", optional = true},
    {selector = "FET003_RigidBody.PhysX.0-4-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET022_DrivenJoints.PhysX.0-2-0", optional = true},
    {selector = "FET003_RigidBody.Newton.0-1-0", optional = true},
    {selector = "FET004_Multibody.Newton.0-1-0", optional = true},
    {selector = "FET022_DrivenJoints.Newton.0-1-0", optional = true},
    {selector = "FET022_DrivenJoints.Isaac.0-2-0", optional = true},
], capabilities = [
    {selector = "CAP021_RobotCore.Isaac.0-3-0", optional = true},
    {selector = "CAP024_BaseArticulation.0-1-0", optional = true},
    {selector = "CAP031_SelfContainedPackage.0-1-0"},
    {selector = "CAP033_SimReadyPackage.0-3-0"},
    {selector = "CAP000_Core.PhysX.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.PhysX.0-1-0", optional = true},
    {selector = "CAP000_Core.Newton.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.Newton.0-1-0", optional = true},
    {selector = "CAP000_Core.MuJoCo.0-1-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP022_DrivenJoints.MuJoCo.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.MuJoCo.0-1-0", optional = true},
    {selector = "CAP000_Core.Isaac.0-1-0", optional = true},
    {selector = "CAP023_RobotMaterials.Isaac.0-1-0", optional = true},
    {selector = "CAP100_IsaacComposition.Isaac.0-3-0", optional = true},
]}
"2.2.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET022_DrivenJoints.0-2-0", optional = true},
    {selector = "FET003_RigidBody.PhysX.0-4-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET022_DrivenJoints.PhysX.0-2-0", optional = true},
    {selector = "FET003_RigidBody.Newton.0-1-0", optional = true},
    {selector = "FET004_Multibody.Newton.0-1-0", optional = true},
    {selector = "FET022_DrivenJoints.Newton.0-1-0", optional = true},
    {selector = "FET022_DrivenJoints.Isaac.0-2-0", optional = true},
], capabilities = [
    {selector = "CAP021_RobotCore.Isaac.0-3-0", optional = true},
    {selector = "CAP024_BaseArticulation.0-1-0", optional = true},
    {selector = "CAP025_RosBridge.Ros.0-1-0", optional = true},
    {selector = "CAP031_SelfContainedPackage.0-1-0"},
    {selector = "CAP033_SimReadyPackage.0-3-0"},
    {selector = "CAP000_Core.PhysX.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.PhysX.0-1-0", optional = true},
    {selector = "CAP000_Core.Newton.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.Newton.0-1-0", optional = true},
    {selector = "CAP000_Core.MuJoCo.0-1-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP022_DrivenJoints.MuJoCo.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.MuJoCo.0-1-0", optional = true},
    {selector = "CAP000_Core.Isaac.0-1-0", optional = true},
    {selector = "CAP023_RobotMaterials.Isaac.0-1-0", optional = true},
    {selector = "CAP100_IsaacComposition.Isaac.0-3-0", optional = true},
]}
"2.3.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET022_DrivenJoints.0-2-0", optional = true},
    {selector = "FET003_RigidBody.PhysX.0-4-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET022_DrivenJoints.PhysX.0-2-0", optional = true},
    {selector = "FET003_RigidBody.Newton.0-1-0", optional = true},
    {selector = "FET004_Multibody.Newton.0-1-0", optional = true},
    {selector = "FET022_DrivenJoints.Newton.0-1-0", optional = true},
    {selector = "FET022_DrivenJoints.Isaac.0-2-0", optional = true},
], capabilities = [
    {selector = "CAP021_RobotCore.Isaac.0-3-0", optional = true},
    {selector = "CAP024_BaseArticulation.0-1-0", optional = true},
    {selector = "CAP025_RosBridge.Ros.0-1-0", optional = true},
    {selector = "CAP031_SelfContainedPackage.0-1-0"},
    {selector = "CAP033_SimReadyPackage.0-4-0"},
    {selector = "CAP000_Core.PhysX.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.PhysX.0-1-0", optional = true},
    {selector = "CAP000_Core.Newton.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.Newton.0-1-0", optional = true},
    {selector = "CAP000_Core.MuJoCo.0-1-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP022_DrivenJoints.MuJoCo.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.MuJoCo.0-1-0", optional = true},
    {selector = "CAP000_Core.Isaac.0-1-0", optional = true},
    {selector = "CAP023_RobotMaterials.Isaac.0-1-0", optional = true},
    {selector = "CAP100_IsaacComposition.Isaac.0-3-0", optional = true},
]}
"3.0.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET022_DrivenJoints.0-2-0", optional = true},
    {selector = "FET006_Materials.0-2-0"},
    {selector = "FET006_Materials.Openpbr.0-1-0", optional = true},
    {selector = "FET006_Materials.MDL.0-2-0", optional = true},
    {selector = "FET010_DisplayColor.0-1-0", optional = true},
    {selector = "FET003_RigidBody.PhysX.0-4-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET022_DrivenJoints.PhysX.0-2-0", optional = true},
    {selector = "FET003_RigidBody.Newton.0-1-0", optional = true},
    {selector = "FET004_Multibody.Newton.0-1-0", optional = true},
    {selector = "FET022_DrivenJoints.Newton.0-1-0", optional = true},
    {selector = "FET022_DrivenJoints.Isaac.0-2-0", optional = true},
], capabilities = [
    {selector = "CAP021_RobotCore.Isaac.0-3-0", optional = true},
    {selector = "CAP024_BaseArticulation.0-1-0", optional = true},
    {selector = "CAP025_RosBridge.Ros.0-1-0", optional = true},
    {selector = "CAP031_SelfContainedPackage.0-1-0"},
    {selector = "CAP033_SimReadyPackage.0-4-0"},
    {selector = "CAP000_Core.PhysX.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.PhysX.0-1-0", optional = true},
    {selector = "CAP000_Core.Newton.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.Newton.0-1-0", optional = true},
    {selector = "CAP000_Core.MuJoCo.0-1-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP022_DrivenJoints.MuJoCo.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.MuJoCo.0-1-0", optional = true},
    {selector = "CAP000_Core.Isaac.0-1-0", optional = true},
    {selector = "CAP023_RobotMaterials.Isaac.0-1-0", optional = true},
    {selector = "CAP100_IsaacComposition.Isaac.0-3-0", optional = true},
]}

"3.1.0" = {features = [
    {selector = "FET008_ObjectForward.0-1-0", optional = true},
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET022_DrivenJoints.0-2-0", optional = true},
    {selector = "FET006_Materials.0-2-0"},
    {selector = "FET006_Materials.Openpbr.0-1-0", optional = true},
    {selector = "FET006_Materials.MDL.0-2-0", optional = true},
    {selector = "FET010_DisplayColor.0-1-0", optional = true},
    {selector = "FET003_RigidBody.PhysX.0-4-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET022_DrivenJoints.PhysX.0-2-0", optional = true},
    {selector = "FET003_RigidBody.Newton.0-1-0", optional = true},
    {selector = "FET004_Multibody.Newton.0-1-0", optional = true},
    {selector = "FET022_DrivenJoints.Newton.0-1-0", optional = true},
    {selector = "FET022_DrivenJoints.Isaac.0-2-0", optional = true},
], capabilities = [
    {selector = "CAP021_RobotCore.Isaac.0-3-0", optional = true},
    {selector = "CAP024_BaseArticulation.0-1-0", optional = true},
    {selector = "CAP025_RosBridge.Ros.0-1-0", optional = true},
    {selector = "CAP031_SelfContainedPackage.0-1-0"},
    {selector = "CAP033_SimReadyPackage.0-4-0"},
    {selector = "CAP000_Core.PhysX.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.PhysX.0-1-0", optional = true},
    {selector = "CAP000_Core.Newton.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.Newton.0-1-0", optional = true},
    {selector = "CAP000_Core.MuJoCo.0-1-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP022_DrivenJoints.MuJoCo.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.MuJoCo.0-1-0", optional = true},
    {selector = "CAP000_Core.Isaac.0-1-0", optional = true},
    {selector = "CAP023_RobotMaterials.Isaac.0-1-0", optional = true},
    {selector = "CAP100_IsaacComposition.Isaac.0-3-0", optional = true},
]}
"4.0.0" = {features = [
    {selector = "FET008_ObjectForward.0-1-0", optional = true},
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET022_DrivenJoints.0-2-0", optional = true},
    {selector = "FET006_Materials.0-3-0"},
    {selector = "FET006_Materials.Openpbr.0-2-0", optional = true},
    {selector = "FET006_Materials.MDL.0-3-0", optional = true},
    {selector = "FET009_MaterialCoverage.0-1-0"},
    {selector = "FET010_DisplayColor.0-1-0", optional = true},
    {selector = "FET003_RigidBody.PhysX.0-4-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET022_DrivenJoints.PhysX.0-2-0", optional = true},
    {selector = "FET003_RigidBody.Newton.0-1-0"},
    {selector = "FET004_Multibody.Newton.0-1-0"},
    {selector = "FET022_DrivenJoints.Newton.0-1-0"},
    {selector = "FET022_DrivenJoints.Isaac.0-2-0", optional = true},
], capabilities = [
    {selector = "CAP000_Core.0-2-0"},
    {selector = "CAP021_RobotCore.Isaac.0-3-0", optional = true},
    {selector = "CAP024_BaseArticulation.0-1-0", optional = true},
    {selector = "CAP025_RosBridge.Ros.0-1-0", optional = true},
    {selector = "CAP031_SelfContainedPackage.0-1-0"},
    {selector = "CAP033_SimReadyPackage.0-4-0"},
    {selector = "CAP000_Core.PhysX.0-2-0", optional = true},
    {selector = "CAP024_BaseArticulation.PhysX.0-1-0", optional = true},
    {selector = "CAP000_Core.Newton.0-2-0"},
    {selector = "CAP024_BaseArticulation.Newton.0-1-0"},
    {selector = "CAP000_Core.MuJoCo.0-2-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP022_DrivenJoints.MuJoCo.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.MuJoCo.0-1-0", optional = true},
    {selector = "CAP000_Core.Isaac.0-2-0", optional = true},
    {selector = "CAP100_IsaacComposition.Isaac.0-3-0", optional = true},
]}
```

### Required versus optional features

On `2.0.0` only two features are required, and from `2.1.0` the packaging and
provenance features join them. Version `3.0.0` also requires
`FET006_Materials`; the alternative visual-material and robot-specific features
remain optional through `3.1.0`. Version `4.0.0` requires the Newton
rigid-body, multibody, driven-joint, Core, and articulation contracts.

| Contract | Version | Status | Purpose |
|---|---|---|---|
| `CAP000_Core` | 0-2-0 (from profile `4.0.0`) | Required | Core file layout and anchored references |
| `FET001_MinimalPlaceableVisual` | 1-0-1 | Required | Minimal OpenUSD asset: units, hierarchy, mesh geometry |
| `FET003_RigidBody` | 0-2-0 | Required | Neutral rigid-body physics and colliders |
| `CAP031_SelfContainedPackage` | 0-1-0 | Required (`2.1.0`+) | Self-contained package source |
| `CAP033_SimReadyPackage` | 0-3-0 (`2.1.0`-`2.2.0`); 0-4-0 (`2.3.0`+) | Required (`2.1.0`+) | Thumbnail plus nested provenance or the SR.004 USD/sidecar union |
| `FET006_Materials` | 0-2-0 (`3.0.0`-`3.1.0`); 0-3-0 (from `4.0.0`) | Required | `UsdPreviewSurface` materials |
| `FET010_DisplayColor` | 0-1-0 (from profile `3.0.0`) | Optional | Display colour and opacity |
| `FET006_Materials.Openpbr` | 0-1-0 (`3.0.0`-`3.1.0`); 0-2-0 (from `4.0.0`) | Optional | OpenPBR materials |
| `FET006_Materials.MDL` | 0-2-0 (`3.0.0`-`3.1.0`); 0-3-0 (from `4.0.0`) | Optional | MDL materials |
| `FET009_MaterialCoverage` | 0-1-0 (from profile `4.0.0`) | Required | Every renderable `Gprim` resolves a material (`VM.MAT.001`), and the asset's own materials cover its silhouette in renders |
| `FET004_Multibody` | 0-2-0 | Optional | Neutral multibody joints |
| `CAP021_RobotCore.Isaac` | 0-3-0 | Optional | Robot identity: robot schema, robot type, root joint |
| `FET022_DrivenJoints` | 0-2-0 | Optional | Neutral driven joints |
| `CAP024_BaseArticulation` | 0-1-0 | Optional | Single articulation root |
| `CAP000_Core.PhysX` | 0-1-0; 0-2-0 from `4.0.0` | Optional (`2.1.0`+) | PhysX runtime-variant Core scaffolding (variant set + payload) |
| `FET004_Multibody.PhysX` | 0-4-0 | Optional | PhysX multibody, mass, and nesting rules |
| `FET022_DrivenJoints.PhysX` | 0-2-0 | Optional | PhysX drives and mimic joints |
| `CAP024_BaseArticulation.PhysX` | 0-1-0 | Optional | PhysX collision clearance between links |
| `FET003_RigidBody.Newton` | 0-1-0 | Required in `4.0.0`; optional earlier | Newton rigid bodies |
| `CAP000_Core.Newton` | 0-1-0; 0-2-0 from `4.0.0` | Required in `4.0.0`; optional earlier | Newton runtime-variant Core scaffolding (variant set + payload) |
| `FET004_Multibody.Newton` | 0-1-0 | Required in `4.0.0`; optional earlier | Newton multibody, mass, and nesting rules |
| `FET022_DrivenJoints.Newton` | 0-1-0 | Required in `4.0.0`; optional earlier | Newton driven joints |
| `CAP024_BaseArticulation.Newton` | 0-1-0 | Required in `4.0.0`; optional earlier | Newton articulation root |
| `CAP000_Core.MuJoCo` | 0-1-0; 0-2-0 from `4.0.0` | Optional (`2.1.0`+) | MuJoCo runtime-variant Core scaffolding (variant set + payload) |
| `CAP004_Multibody.MuJoCo` | 0-1-0 | Optional (`2.1.0`+) | MuJoCo multibody, mass, and nesting rules |
| `CAP022_DrivenJoints.MuJoCo` | 0-1-0 | Optional (`2.1.0`+) | MuJoCo driven joints |
| `CAP024_BaseArticulation.MuJoCo` | 0-1-0 | Optional (`2.1.0`+) | MuJoCo articulation root |
| `CAP000_Core.Isaac` | 0-1-0; 0-2-0 from `4.0.0` | Optional | Isaac packaging, thumbnail, physics-layer separation |
| `FET022_DrivenJoints.Isaac` | 0-2-0 | Optional | Isaac link and joint APIs |
| `CAP023_RobotMaterials.Isaac` | 0-1-0 | Optional (`2.0.0`-`3.1.0`); deprecated | Isaac robot material organization |
| `CAP100_IsaacComposition.Isaac` | 0-3-0 | Optional | Isaac Sim composition |
| `CAP025_RosBridge.Ros` | 0-1-0 | Optional (`2.2.0`) | Isaac ROS 2 bridge OmniGraph nodes (`ROS.001`) |

A practical robot body selects at least `FET004_Multibody`, `CAP021_RobotCore.Isaac`,
`FET022_DrivenJoints`, and `CAP024_BaseArticulation`. Add the PhysX features for a
runnable PhysX robot, and `CAP000_Core.Isaac` plus Isaac composition for an Isaac
Sim deliverable. On `2.2.0`, select `CAP025_RosBridge.Ros` when the robot ships ROS 2
bridge OmniGraph wiring.

From `2.1.0`, the profile also exposes each physics runtime as an optional
Core → multibody → driven-joints → articulation bundle. Alongside PhysX
(`CAP000_Core.PhysX`, `FET004_Multibody.PhysX`, `FET022_DrivenJoints.PhysX`, `CAP024_BaseArticulation.PhysX`) it adds
Newton (`CAP000_Core.Newton`, `FET004_Multibody.Newton`, `FET022_DrivenJoints.Newton`, `CAP024_BaseArticulation.Newton`)
and MuJoCo (`CAP000_Core.MuJoCo`, `CAP004_Multibody.MuJoCo`, `CAP022_DrivenJoints.MuJoCo`,
`CAP024_BaseArticulation.MuJoCo`). The `CAP000_Core.*` Core feature provides that runtime's
variant-set scaffolding and `runnables/physics/` payload, while the
`FET004_Multibody.*`, `FET022_DrivenJoints.*`, and `CAP024_BaseArticulation.*` contracts cover multibody, driven joints, and articulation.
Select a runtime's features when the robot carries that solver's physics payload;
`simready-validate` enables the matching variant before running the
runtime-specific rules. A missing runtime does not fail the profile, but a
present runtime must pass its rules. See
[Multiple Physics Solvers](../../../../../../sr_specs/docs/guides/multiphysics_solvers.md).

Feature versions in this profile pin the Standard/PhysX families rather than the
deprecated `FET004_Multibody.RobotPhysX` feature, which must not be used by new profile
versions. Rigid-body work stays in the FET003 family and multibody joint work
stays in the FET004 family.

Version `3.0.0` makes the baseline appearance mandatory: every conforming robot
body carries a `UsdPreviewSurface` material (`FET006_Materials`). Display colour
(`FET010_DisplayColor`), OpenPBR, and MDL remain optional, so an asset selects only
the alternative surface contracts its runtime needs.

## Required USD properties and schemas

### Stage metadata and hierarchy (`FET001_MinimalPlaceableVisual`)

- Set `upAxis = "Z"` (`UN.006`) and `metersPerUnit = 1.0` (`UN.007`).
- Set `defaultPrim` to an existing prim (`HI.004`).
- Parent all prims under a single stage root prim (`HI.001`) that inherits
  `UsdGeomXformable` (`HI.003`).
- Use anchored `./` or `../` reference paths that stay inside the asset root
  (`AA.001`) and point only at supported file types (`AA.002`).
- Author render geometry as `UsdGeom.Mesh` with
  `subdivisionScheme = "none"` (`VG.MESH.001`), valid `extent` (`VG.002`), valid
  topology (`VG.014`), counter-clockwise winding (`VG.029`), and normals through
  exactly one of `primvars:normals` or `normals` (`VG.027`, `VG.028`).
- Avoid coincident meshes occupying identical space (`VG.008`), and place the
  robot at the origin with a neutral root transform (`VG.025`).

### Rigid bodies and colliders (`FET003_RigidBody`)

- Apply `UsdPhysicsRigidBodyAPI` to at least one `UsdGeomXformable` prim
  (`RB.001`), and only to `UsdGeomXformable` prims (`RB.003`).
- Apply `UsdPhysicsCollisionAPI` only on `UsdGeom.Gprim` prims (`RB.COL.001`),
  and `UsdPhysicsMeshCollisionAPI` only on `UsdGeom.Mesh` paired with
  `UsdPhysicsCollisionAPI` (`RB.COL.002`, `RB.COL.003`).
- Keep world scale uniform on Sphere, Capsule, Cylinder, Cone, and Points
  colliders (`RB.COL.004`).
- Do not apply `PhysicsRigidBodyAPI` inside an `instanceable = true` prototype
  (`RB.005`).
- Author `float physics:mass` on the body or its descendant colliders
  (`RB.007`), keep the composed world transform free of skew (`RB.009`), and set
  `purpose = "guide"` on non-rendering collision meshes (`RB.010`).

## Optional feature requirements

### Multibody joints (`FET004_Multibody`, `FET004_Multibody.PhysX`)

- Connect links with a `UsdPhysicsJoint` subtype and author
  `rel physics:body0` and `rel physics:body1`; an empty side means world
  (`JT.001`).
- Target existing prims or leave the relationship empty (`JT.002`), with at most
  one target each (`JT.003`).
- Do not nest `PhysicsArticulationRootAPI` (`JT.ART.002`), and do not apply it
  to kinematic (`JT.ART.003`) or disabled/static (`JT.ART.004`) bodies.
- Apply `PhysicsRigidBodyAPI` to at least two separate `UsdGeomXformable`
  hierarchies (`RB.MB.001`).

`FET004_Multibody.PhysX.0-4-0` adds two rules on top of the neutral set:

- Every rigid-body subtree needs authored `physics:mass > 0`, or at least one
  owned collider with non-zero-volume `extent` for auto-mass (`RB.011`).
- Every nested `PhysicsRigidBodyAPI` ancestor/descendant pair must be connected
  by a stage joint targeting both bodies (`RB.012`).

### Robot core (`CAP021_RobotCore.Isaac`)

- Use lowercase, underscore-delimited asset file names and stable prim paths
  such as `/Carter/base_link` and `/Carter/Joints/left_wheel_joint`. The
  validator expects a `<Manufacturer>/<robot>/<robot.usd>` layout where the
  folder name matches the USD stem (`RC.003`).
- Set `defaultPrim` to the robot root, apply `IsaacRobotAPI`, and author
  non-empty `rel isaac:physics:robotLinks` and `rel isaac:physics:robotJoints`
  listing every link and joint prim (`RC.007`).
- Author `token isaac:robotType` on the default prim using one of
  `"End Effector"`, `"Manipulator"`, `"Humanoid"`, `"Wheeled"`, `"Holonomic"`,
  `"Quadruped"`, `"Mobile Manipulators"`, or `"Aerial"`. `"Default"` is invalid
  (`RC.008`).
- Pin the root joint, which is the first target of `isaac:physics:robotJoints`
  (`RC.009`). For `"Manipulator"` and `"End Effector"`, leave one of
  `physics:body0` or `physics:body1` empty or target a prim without
  `PhysicsRigidBodyAPI`. For every other robot type, both sides must target
  prims that have `PhysicsRigidBodyAPI`.

### Driven joints (`FET022_DrivenJoints`, `FET022_DrivenJoints.PhysX`, `FET022_DrivenJoints.Isaac`)

Neutral driven joints (`FET022_DrivenJoints`):

- On joints with `PhysicsDriveAPI:<angular|linear>`, author a finite
  `drive:<axis>:physics:maxForce` greater than zero (`DJ.001`).
- Apply `PhysicsJointStateAPI:angular` to non-fixed revolute joints and
  `PhysicsJointStateAPI:linear` to prismatic joints (`DJ.002`).
- Keep `physics:localPos0/1`, `physics:localRot0/1`, and the joint-state pose
  mutually consistent (`DJ.003`).
- Keep the articulation joint graph acyclic with at most one joint per
  rigid-body pair, excluding joints with
  `physics:excludeFromArticulation = true` (`DJ.011`).

PhysX driven joints (`FET022_DrivenJoints.PhysX`) add:

- Apply `PhysicsDriveAPI:<axis>` or `PhysxMimicJointAPI:<rotX|rotY|rotZ>` to
  non-fixed joints that participate in the articulation. When both are present,
  set drive stiffness and damping to exactly `0.0` (`DJ.004`, `DJ.006`).
- Author `float physxJoint:maxJointVelocity` greater than zero on joints with
  `PhysxJointAPI` (`DJ.005`).
- Give each mimic joint exactly one
  `rel physxMimicJoint:<axis>:referenceJoint` target, plus finite non-zero
  `physxMimicJoint:<axis>:gearing` and finite resolved
  `physxMimicJoint:<axis>:naturalFrequency` and
  `physxMimicJoint:<axis>:dampingRatio`. Zero schema defaults are valid;
  non-positive natural frequency selects rigid coupling. Both the mimic and
  reference joints need limits, and neither may set
  `physics:excludeFromArticulation = true` (`DJ.007`).

Isaac driven joints (`FET022_DrivenJoints.Isaac`) add:

- Apply the Isaac joint API to at least one prim (`DJ.008`) and the Isaac link
  API to at least one prim (`DJ.009`).
- Prepend `isaac:physics:robotLinks` and `isaac:physics:robotJoints` on the
  default prim carrying `IsaacRobotAPI` (`DJ.010`).

### Articulation (`CAP024_BaseArticulation`, `CAP024_BaseArticulation.PhysX`)

Apply exactly one `PhysicsArticulationRootAPI` on the kinematic-chain root
(`BA.001`). Zero roots and multiple roots both fail:

```usd
def Xform "Robot" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
}
```

`CAP024_BaseArticulation.PhysX` adds `BA.002`: collision meshes on non-adjacent articulation
links must not overlap at the default pose. This is verified by detecting
initial PhysX collider contacts rather than by inspecting authored attributes,
so it requires a runtime check.

### Isaac packaging (`CAP000_Core.Isaac`)

`CAP000_Core.Isaac.0-1-0` depends on `CAP000_Core.0-1-0`, and
`CAP000_Core.Isaac.0-2-0` (from profile `4.0.0`) depends on
`CAP000_Core.0-2-0`. Both add four packaging requirements:

- Keep the robot folder free of unreferenced files, with the interface layer at
  the asset root and payload, material, and physics content in subfolders
  (`RC.001`).
- Provide a thumbnail at `.thumbs/256x256/{robot_filename}.png` beside the robot
  `.usd` (`RC.004`).
- Author every `physics:*` attribute only in the physics layer, whose file name
  matches `*physics.usd`, `*physics.usda`, or `*physics.usdc`, as deltas over
  the base layer (`RC.005`).
- Apply every `Physics*` and `Physx*` API schema only in that physics layer, not
  in the base or interface layer (`RC.006`).

### Isaac composition (`CAP100_IsaacComposition.Isaac`)

`ISA.001` requires the main USD to have a default prim with `kind = "component"`
that references separate mesh and physics layers through relative paths:

- Organize materials under a `Scope "Looks"`, raw geometry under an invisible
  `Scope "Meshes"`, and visual references under an invisible `Scope "Visuals"`.
- Apply physics schemas and attributes in the physics payload only.
- Set `upAxis = "Z"`, `metersPerUnit = 1.0`, and a default prim in every file,
  keeping all reference and payload paths relative.

The `ISA.001` requirement page and the composition validator currently disagree
on exact payload file names. Check
`rules_and_reqs/isaac_sim/composition/validation.py` for the names the validator
expects before finalizing a layout.

### ROS Ready (version 2.2.0)

Version `2.2.0` adds optional `CAP025_RosBridge.Ros.0-1-0`. Use it when the robot asset
includes OmniGraph nodes whose `node:type` starts with `isaacsim.ros2.bridge.`
(`ROS.001`). Repair with `simready-foundation-conform-fet-025-ros` after Isaac
composition when ROS bridge wiring is in scope.

### Metadata union (version 2.3.0)

Version `2.3.0` keeps the `2.2.0` feature set and adopts
`CAP033_SimReadyPackage.0-4-0`. Provenance uses `SR.004` instead of `SR.003`: the
same field set is read from the union of root-layer `customLayerData`
(including optional nested `SimReady_Metadata`) and an optional same-directory
`<usd_stem>.json` sidecar. Nested `SimReady_Metadata` is no longer required on
its own. Assets that already passed `2.2.0` still satisfy `2.3.0`; no feature
adapter is required.

### SimReady Foundations 8.0 release (version 3.0.0)

Version `3.0.0` is the SimReady Foundations 8.0 release pin. It keeps the `2.3.0`
feature set and adds the baseline visual material contract: `FET006_Materials.0-2-0`
is required, and `FET010_DisplayColor`, `FET006_Materials.Openpbr` and `FET006_Materials.MDL` are
optional. An asset that passed `2.3.0` needs a `UsdPreviewSurface` on every bound
material to satisfy `3.0.0`.

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
            string profile = "Robot-Body"
            string profile_version = "3.0.0"
        }
    }
}
```

## Conformance workflow

Repair one feature gate at a time, in dependency order:

```text
validate Robot-Body
-> simready-foundation-conform-fet-000-standard (required on 4.0.0+)
-> simready-foundation-conform-fet-001-standard
-> simready-foundation-conform-fet-003-standard (or -physx)
-> simready-foundation-conform-fet-004-standard (or -physx)
-> simready-foundation-conform-fet-021-isaac
-> simready-foundation-conform-fet-000-isaac (only for Isaac packaging)
-> simready-foundation-conform-fet-022-standard (or -physx / -isaac)
-> simready-foundation-conform-fet-024-standard (or -physx)
-> simready-foundation-conform-fet-100-isaac (only for Isaac deliverables)
-> simready-foundation-conform-fet-031-standard (required on 2.1.0+)
-> simready-foundation-conform-fet-033-standard (required on 2.1.0+)
-> simready-foundation-conform-fet-025-ros (only when ROS-Ready is selected on 2.2.0+)
-> validate Robot-Body again
```

Get the body and joint topology in shape before the articulation gate. The
Standard articulation feature checks the single articulation root; the PhysX
feature also needs collision-clearance evidence for non-adjacent links.

## References

- [Feature dependency graph](../../../../../../sr_specs/docs/shared/features/feature-dependency-graph.md) — requirements and dependencies for all features
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot_body.toml`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.Isaac.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET001_MinimalPlaceableVisual.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET003_RigidBody.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.PhysX.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP021_RobotCore.Isaac.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET022_DrivenJoints.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET022_DrivenJoints.PhysX.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET022_DrivenJoints.Isaac.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP023_RobotMaterials.Isaac.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP024_BaseArticulation.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP024_BaseArticulation.PhysX.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP025_RosBridge.Ros.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP031_SelfContainedPackage.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP033_SimReadyPackage.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP100_IsaacComposition.Isaac.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/isaac_sim/robot_core/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/isaac_sim/composition/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/isaac_sim/ros_bridge/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/physics_driven_joints/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/base_articulation/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/physics_joints/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/physics_rigid_bodies/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/naming_paths/`
