# Robot-Gripper Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Robot-Gripper` profile.

`Robot-Gripper` is the consolidated gripper profile. It replaces the separate
`Robot-Gripper-Neutral` and `Robot-Gripper-Isaac` profiles with a single profile
whose neutral OpenUSD core is mandatory and whose solver- and runtime-specific
behavior is selected through runtime features. Newton is required in `4.0.0`.

## Required Newton contracts — 4.0.0

Version 4.0.0 requires `FET003_RigidBody.Newton.0-1-0`,
`FET004_Multibody.Newton.0-1-0`, `FET022_DrivenJoints.Newton.0-1-0`,
`CAP000_Core.Newton.0-2-0`, and `CAP024_BaseArticulation.Newton.0-1-0`.
Install both Core and Newton tiers to resolve and validate this profile.
Their requirements and runtime evidence are blocking gates.

## Material binding — 4.0.0

`Robot-Gripper` 4.0.0 requires [`FET009_MaterialCoverage.0-1-0`](../features/FET009_MaterialCoverage.md) for material binding (`VM.MAT.001`) and its rendered coverage, and selects
`FET006_Materials.0-3-0` (required), `FET006_Materials.Openpbr.0-2-0` and
`FET006_Materials.MDL.0-3-0` (optional), which leave `VM.MAT.001` out.

## Required Core — 4.0.0

`Robot-Gripper` 4.0.0 requires the following Core configuration:

- It requires [`CAP000_Core.0-2-0`](../capabilities/CAP000_Core.md).
  The Core file-naming, layout, path, and undefined-prim requirements
  (`NP.002`-`NP.005`, `NP.007`, `NP.008`, `HI.010`) block validation. Through
  3.0.0 the profile does not select Core. From 2.1.0 the optional runtime Core
  capabilities bring it in, so those requirements report only as warnings.
- It requires `CAP000_Core.Newton.0-2-0` and selects version `0-2-0`
  of the optional `CAP000_Core.PhysX` and `CAP000_Core.MuJoCo` capabilities. Each depends on
  `CAP000_Core.0-2-0`, so 4.0.0 validates a single Core version and does
  not run `NP.006` or `SR.001`.

An asset that passed 3.0.0 must also pass the Core requirements to satisfy 4.0.0.
Repair them with `simready-foundation-conform-fet-000-standard` before the other
gates. No adapter is required.

## Profile definition

The `Robot-Gripper` profile includes the following feature set (see
`robot_gripper.toml` and the
[feature dependency graph](../../../../../../sr_specs/docs/shared/features/feature-dependency-graph.md)). Each
feature's requirements and dependencies are defined in the feature
specifications.

```toml
# Generated Foundations 2 projection. See ../catalog-map.json.

[Robot-Gripper]
"2.0.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET022_DrivenJoints.0-2-0", optional = true},
    {selector = "FET028_Gripper.0-1-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET022_DrivenJoints.PhysX.0-2-0", optional = true},
    {selector = "FET022_DrivenJoints.Isaac.0-2-0", optional = true},
    {selector = "FET028_Gripper.Isaac.0-1-0", optional = true},
], capabilities = [
    {selector = "CAP024_BaseArticulation.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.PhysX.0-1-0", optional = true},
    {selector = "CAP021_RobotCore.Isaac.0-2-0", optional = true},
    {selector = "CAP100_IsaacComposition.Isaac.0-3-0", optional = true},
]}
"2.1.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET022_DrivenJoints.0-2-0", optional = true},
    {selector = "FET028_Gripper.0-1-0", optional = true},
    {selector = "FET003_RigidBody.PhysX.0-4-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET022_DrivenJoints.PhysX.0-2-0", optional = true},
    {selector = "FET003_RigidBody.Newton.0-1-0", optional = true},
    {selector = "FET004_Multibody.Newton.0-1-0", optional = true},
    {selector = "FET022_DrivenJoints.Newton.0-1-0", optional = true},
    {selector = "FET022_DrivenJoints.Isaac.0-2-0", optional = true},
    {selector = "FET028_Gripper.Isaac.0-1-0", optional = true},
], capabilities = [
    {selector = "CAP024_BaseArticulation.0-1-0", optional = true},
    {selector = "CAP031_SelfContainedPackage.0-1-0"},
    {selector = "CAP033_SimReadyPackage.0-3-0"},
    {selector = "CAP000_Core.PhysX.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.PhysX.0-1-0", optional = true},
    {selector = "CAP021_RobotCore.Isaac.0-2-0", optional = true},
    {selector = "CAP000_Core.Newton.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.Newton.0-1-0", optional = true},
    {selector = "CAP000_Core.MuJoCo.0-1-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP022_DrivenJoints.MuJoCo.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.MuJoCo.0-1-0", optional = true},
    {selector = "CAP028_Gripper.MuJoCo.0-1-0", optional = true},
    {selector = "CAP100_IsaacComposition.Isaac.0-3-0", optional = true},
]}
"2.2.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET022_DrivenJoints.0-2-0", optional = true},
    {selector = "FET028_Gripper.0-1-0", optional = true},
    {selector = "FET003_RigidBody.PhysX.0-4-0", optional = true},
    {selector = "FET004_Multibody.PhysX.0-4-0", optional = true},
    {selector = "FET022_DrivenJoints.PhysX.0-2-0", optional = true},
    {selector = "FET003_RigidBody.Newton.0-1-0", optional = true},
    {selector = "FET004_Multibody.Newton.0-1-0", optional = true},
    {selector = "FET022_DrivenJoints.Newton.0-1-0", optional = true},
    {selector = "FET022_DrivenJoints.Isaac.0-2-0", optional = true},
    {selector = "FET028_Gripper.Isaac.0-1-0", optional = true},
], capabilities = [
    {selector = "CAP024_BaseArticulation.0-1-0", optional = true},
    {selector = "CAP031_SelfContainedPackage.0-1-0"},
    {selector = "CAP033_SimReadyPackage.0-4-0"},
    {selector = "CAP000_Core.PhysX.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.PhysX.0-1-0", optional = true},
    {selector = "CAP021_RobotCore.Isaac.0-2-0", optional = true},
    {selector = "CAP000_Core.Newton.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.Newton.0-1-0", optional = true},
    {selector = "CAP000_Core.MuJoCo.0-1-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP022_DrivenJoints.MuJoCo.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.MuJoCo.0-1-0", optional = true},
    {selector = "CAP028_Gripper.MuJoCo.0-1-0", optional = true},
    {selector = "CAP100_IsaacComposition.Isaac.0-3-0", optional = true},
]}
"3.0.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET022_DrivenJoints.0-2-0", optional = true},
    {selector = "FET028_Gripper.0-1-0", optional = true},
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
    {selector = "FET028_Gripper.Isaac.0-1-0", optional = true},
], capabilities = [
    {selector = "CAP024_BaseArticulation.0-1-0", optional = true},
    {selector = "CAP031_SelfContainedPackage.0-1-0"},
    {selector = "CAP033_SimReadyPackage.0-4-0"},
    {selector = "CAP000_Core.PhysX.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.PhysX.0-1-0", optional = true},
    {selector = "CAP021_RobotCore.Isaac.0-2-0", optional = true},
    {selector = "CAP000_Core.Newton.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.Newton.0-1-0", optional = true},
    {selector = "CAP000_Core.MuJoCo.0-1-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP022_DrivenJoints.MuJoCo.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.MuJoCo.0-1-0", optional = true},
    {selector = "CAP028_Gripper.MuJoCo.0-1-0", optional = true},
    {selector = "CAP100_IsaacComposition.Isaac.0-3-0", optional = true},
]}
"4.0.0" = {features = [
    {selector = "FET001_MinimalPlaceableVisual.1-0-1"},
    {selector = "FET003_RigidBody.0-2-0"},
    {selector = "FET004_Multibody.0-2-0", optional = true},
    {selector = "FET022_DrivenJoints.0-2-0", optional = true},
    {selector = "FET028_Gripper.0-1-0", optional = true},
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
    {selector = "FET028_Gripper.Isaac.0-1-0", optional = true},
], capabilities = [
    {selector = "CAP000_Core.0-2-0"},
    {selector = "CAP024_BaseArticulation.0-1-0", optional = true},
    {selector = "CAP031_SelfContainedPackage.0-1-0"},
    {selector = "CAP033_SimReadyPackage.0-4-0"},
    {selector = "CAP000_Core.PhysX.0-2-0", optional = true},
    {selector = "CAP024_BaseArticulation.PhysX.0-1-0", optional = true},
    {selector = "CAP021_RobotCore.Isaac.0-2-0", optional = true},
    {selector = "CAP000_Core.Newton.0-2-0"},
    {selector = "CAP024_BaseArticulation.Newton.0-1-0"},
    {selector = "CAP000_Core.MuJoCo.0-2-0", optional = true},
    {selector = "CAP003_RigidBody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP004_Multibody.MuJoCo.0-1-0", optional = true},
    {selector = "CAP022_DrivenJoints.MuJoCo.0-1-0", optional = true},
    {selector = "CAP024_BaseArticulation.MuJoCo.0-1-0", optional = true},
    {selector = "CAP028_Gripper.MuJoCo.0-1-0", optional = true},
    {selector = "CAP100_IsaacComposition.Isaac.0-3-0", optional = true},
]}
```

### Required versus optional features

Two features are required in version `2.0.0`; packaging and provenance join them
from `2.1.0`. Version `3.0.0` also requires the baseline visual-material feature
`FET006_Materials`; every gripper-specific or alternative visual feature stays
optional and is validated only when the asset selects it.

| Contract | Version | Status | Purpose |
|---|---|---|---|
| `CAP000_Core` | 0-2-0 (from profile `4.0.0`) | Required | Core file layout and anchored references |
| `FET001_MinimalPlaceableVisual` | 1-0-1 | Required | Minimal OpenUSD asset: units, hierarchy, mesh geometry |
| `FET003_RigidBody` | 0-2-0 | Required | Neutral rigid-body physics and colliders |
| `FET006_Materials` | 0-2-0 (`3.0.0`); 0-3-0 (from `4.0.0`) | Required | `UsdPreviewSurface` materials |
| `FET010_DisplayColor` | 0-1-0 (from profile `3.0.0`) | Optional | Display colour and opacity |
| `FET006_Materials.Openpbr` | 0-1-0 (`3.0.0`); 0-2-0 (from `4.0.0`) | Optional | OpenPBR materials |
| `FET006_Materials.MDL` | 0-2-0 (`3.0.0`); 0-3-0 (from `4.0.0`) | Optional | MDL materials |
| `FET009_MaterialCoverage` | 0-1-0 (from profile `4.0.0`) | Required | Every renderable `Gprim` resolves a material (`VM.MAT.001`), and the asset's own materials cover its silhouette in renders |
| `FET004_Multibody` | 0-2-0 | Optional | Neutral multibody joints |
| `FET022_DrivenJoints` | 0-2-0 | Optional | Neutral driven joints |
| `CAP024_BaseArticulation` | 0-1-0 | Optional | Single articulation root |
| `FET003_RigidBody.Newton` | 0-1-0 | Required in `4.0.0`; optional earlier | Newton rigid bodies |
| `FET004_Multibody.Newton` | 0-1-0 | Required in `4.0.0`; optional earlier | Newton multibody joints |
| `FET022_DrivenJoints.Newton` | 0-1-0 | Required in `4.0.0`; optional earlier | Newton driven joints |
| `CAP000_Core.Newton` | 0-2-0 in `4.0.0`; 0-1-0 earlier | Required in `4.0.0`; optional earlier | Newton runtime-variant scaffolding |
| `CAP024_BaseArticulation.Newton` | 0-1-0 | Required in `4.0.0`; optional earlier | Newton articulation root |
| `FET028_Gripper` | 0-1-0 | Optional | Gripper site: socket type, forward axis, grip line, max opening |
| `FET004_Multibody.PhysX` | 0-4-0 | Optional | PhysX multibody, mass, and nesting rules |
| `FET022_DrivenJoints.PhysX` | 0-2-0 | Optional | PhysX drives and mimic joints |
| `CAP024_BaseArticulation.PhysX` | 0-1-0 | Optional | PhysX collision clearance between links |
| `CAP021_RobotCore.Isaac` | 0-2-0 | Optional | Robot identity: robot schema, robot type, root joint |
| `FET022_DrivenJoints.Isaac` | 0-2-0 | Optional | Isaac link and joint APIs |
| `FET028_Gripper.Isaac` | 0-1-0 | Optional | Isaac gripper site |
| `CAP100_IsaacComposition.Isaac` | 0-3-0 | Optional | Isaac Sim composition |

A practical end-effector selects at least `FET004_Multibody`,
`FET022_DrivenJoints`, `CAP024_BaseArticulation`, and `FET028_Gripper`. Add the PhysX
features for a runnable PhysX gripper, and the Isaac features for an Isaac Sim
deliverable.

Version `3.0.0` makes the baseline appearance mandatory: every conforming
gripper carries a `UsdPreviewSurface` material (`FET006_Materials`). Display
colour (`FET010_DisplayColor`), OpenPBR and MDL remain optional, so an asset
picks whichever final surface its runtime needs and `DISP.001` to `DISP.003` are
validated only on an asset that selects display colour. Requirements shared between a
required and an optional feature stay required. From `3.0.0`, `FET006_Materials`
makes `com.nvidia.usd.VM.BIND.001`, `com.nvidia.usd.VM.PS.001`, `VM.PS.002`,
`VM.TEX.001` and `VM.TEX.003` mandatory, and `VM.MAT.001` in `3.0.0`. From `4.0.0`,
`VM.MAT.001` is required through `FET009_MaterialCoverage` instead.
`VM.BIND.002` and the OpenPBR (`VM.PBR.001` to `VM.PBR.003`, `VM.TEX.004`) and MDL
(`VM.MDL.001`, `com.nvidia.usd.VM.MDL.002`, `VM.MDL.003`, `VM.TEX.005`) requirements stay optional.

## Required USD properties and schemas

### Stage metadata and hierarchy (`FET001_MinimalPlaceableVisual`)

- Set `defaultPrim` on every layer, and `upAxis = "Z"` with `metersPerUnit = 1`
  on every stage.
- Keep the prim hierarchy anchored under the default prim.

### Rigid bodies and colliders (`FET003_RigidBody`)

- Apply `PhysicsRigidBodyAPI` to any simulated rigid body prim, which must be
  `UsdGeomXformable`.
- Apply `PhysicsCollisionAPI` to collision-enabled prims.

### Materials (`FET006_Materials`, `FET010_DisplayColor`, `FET006_Materials.Openpbr`, and `FET006_Materials.MDL`)

Required from version `3.0.0`. The material requirements are identical to those
in the [Robotics-Prop guide](robotics-prop.md), which describes each requirement in
full. From `4.0.0` the profile also requires `FET009_MaterialCoverage`, which that
guide describes under Material coverage.

## Optional feature requirements

### Gripper site (`FET028_Gripper`)

Every gripper interaction point must be an `Xform` prim carrying:

- `token simready:attactment:socketType = "Gripper"` — discovery attribute.
- `float custom:maxOpening` — maximum jaw separation in meters, strictly
  positive.
- A `BasisCurves` child named `forward_axis` with at least 2 points encoding the
  approach direction.
- A `BasisCurves` child named `grip_line` with at least 2 points encoding the
  graspable-tube axis, whose segment length equals the physical width of the
  grip pads.

The gripper site prim may have any name, and multiple sites on one end-effector
are supported.

### Multibody joints, driven joints, and articulation

`FET004_Multibody.*`, `FET022_DrivenJoints.*`, and `CAP024_BaseArticulation.*` carry the same requirements as in the
[Robot-Body guide](robot-body.md).

## Validation metadata (recommended)

Include profile metadata in `customLayerData` to simplify validation workflows:

```usd
customLayerData = {
    dictionary SimReady_Metadata = {
        dictionary validation = {
            string profile = "Robot-Gripper"
            string profile_version = "3.0.0"
        }
    }
}
```

## References

- `docs/profiles/robot_gripper.toml`
- `docs/features/FET028_Gripper.md`
- `docs/features/FET006_Materials.md`
- `docs/features/FET010_DisplayColor.md`
- `docs/rules_and_reqs/physics_bodies/physics_grippers/requirements/gripper-socket-type.md`
- `docs/rules_and_reqs/physics_bodies/physics_grippers/requirements/gripper-forward-axis.md`
- `docs/rules_and_reqs/physics_bodies/physics_grippers/requirements/gripper-grip-line.md`
- `docs/rules_and_reqs/physics_bodies/physics_grippers/requirements/gripper-max-opening.md`
