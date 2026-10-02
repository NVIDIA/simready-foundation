# Robot-Gripper Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Robot-Gripper` profile.

`Robot-Gripper` is the consolidated gripper profile. It replaces the separate
`Robot-Gripper-Neutral` and `Robot-Gripper-Isaac` profiles with a single profile
whose neutral OpenUSD core is mandatory and whose solver- and runtime-specific
behavior is selected through optional features.

## Profile definition

The `Robot-Gripper` profile includes the following feature set (see
`robot_gripper.toml` and the
[feature dependency graph](../features/feature-dependency-graph)). Each
feature's requirements and dependencies are defined in the feature
specifications.

```toml
[Robot-Gripper]
"2.0.0" = {features = [
    {"FET_001_STANDARD" = {version = "1.0.1"}}, # "Minimal"
    {"FET_003_STANDARD" = {version = "0.2.0"}}, # "RBD Physics"
    {"FET_004_STANDARD" = {version = "0.2.0"}, optional=true}, # "Simulate Multi-Body Physics"
    {"FET_022_STANDARD" = {version = "0.2.0"}, optional=true}, # "Driven Joints"
    {"FET_024_STANDARD" = {version = "0.1.0"}, optional=true}, # "Articulation"
    {"FET_028_STANDARD" = {version = "0.1.0"}, optional=true}, # "Gripper"

    {"FET_004_PHYSX" = {version = "0.4.0"}, optional=true}, # "Simulate Multi-Body Physics (PhysX)"
    {"FET_022_PHYSX" = {version = "0.2.0"}, optional=true}, # "Driven Joints (PhysX)"
    {"FET_024_PHYSX" = {version = "0.1.0"}, optional=true}, # "Articulation (PhysX)"
    {"FET_021_ISAAC" = {version = "0.2.0"}, optional=true}, # "Robot Core (Isaac)"

    {"FET_022_ISAAC" = {version = "0.2.0"}, optional=true}, # "Driven Joints (Isaac)"
    {"FET_028_ISAAC" = {version = "0.1.0"}, optional=true}, # "Gripper (Isaac)"
    {"FET_100_ISAAC" = {version = "0.3.0"}, optional=true}, # "Isaac composition"
]}
"2.1.0" = {features = [ # Add required SimReady packaging + provenance metadata (FET_031_STANDARD, FET_033_STANDARD@0.3.0 / SR.003); add optional Newton/MuJoCo multiphysics runtime features and per-runtime Core scaffolding (FET_000_PHYSX/NEWTON/MUJOCO)
    {"FET_001_STANDARD" = {version = "1.0.1"}}, # "Minimal"
    {"FET_003_STANDARD" = {version = "0.2.0"}}, # "RBD Physics"
    {"FET_004_STANDARD" = {version = "0.2.0"}, optional=true}, # "Simulate Multi-Body Physics"
    {"FET_022_STANDARD" = {version = "0.2.0"}, optional=true}, # "Driven Joints"
    {"FET_024_STANDARD" = {version = "0.1.0"}, optional=true}, # "Articulation"
    {"FET_028_STANDARD" = {version = "0.1.0"}, optional=true}, # "Gripper"

    # SimReady packaging + provenance metadata (required)
    {"FET_031_STANDARD" = {version = "0.1.0"}}, # "Self-contained Package Source"
    {"FET_033_STANDARD" = {version = "0.3.0"}}, # "Metadata (thumbnail + nested provenance metadata)"

    # PhysX runtime core / rbd / multibody / driven joints / articulation
    {"FET_000_PHYSX" = {version = "0.1.0"}, optional=true}, # "Core PhysX runtime variant"
    {"FET_003_PHYSX" = {version = "0.4.0"}, optional=true}, # "RBD Physics (PhysX)"
    {"FET_004_PHYSX" = {version = "0.4.0"}, optional=true}, # "Simulate Multi-Body Physics (PhysX)"
    {"FET_022_PHYSX" = {version = "0.2.0"}, optional=true}, # "Driven Joints (PhysX)"
    {"FET_024_PHYSX" = {version = "0.1.0"}, optional=true}, # "Articulation (PhysX)"
    {"FET_021_ISAAC" = {version = "0.2.0"}, optional=true}, # "Robot Core (Isaac)"

    # Newton runtime core / rbd / multibody / driven joints / articulation
    {"FET_000_NEWTON" = {version = "0.1.0"}, optional=true}, # "Core Newton runtime variant"
    {"FET_003_NEWTON" = {version = "0.1.0"}, optional=true}, # "RBD Physics (Newton)"
    {"FET_004_NEWTON" = {version = "0.1.0"}, optional=true}, # "Simulate Multi-Body Physics (Newton)"
    {"FET_022_NEWTON" = {version = "0.1.0"}, optional=true}, # "Driven Joints (Newton)"
    {"FET_024_NEWTON" = {version = "0.1.0"}, optional=true}, # "Articulation (Newton)"

    # MuJoCo runtime core / rbd / multibody / driven joints / articulation / gripper
    {"FET_000_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Core MuJoCo runtime variant"
    {"FET_003_MUJOCO" = {version = "0.1.0"}, optional=true}, # "RBD Physics (MuJoCo)"
    {"FET_004_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Simulate Multi-Body Physics (MuJoCo)"
    {"FET_022_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Driven Joints (MuJoCo)"
    {"FET_024_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Articulation (MuJoCo)"
    {"FET_028_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Gripper (MuJoCo)"

    {"FET_022_ISAAC" = {version = "0.2.0"}, optional=true}, # "Driven Joints (Isaac)"
    {"FET_028_ISAAC" = {version = "0.1.0"}, optional=true}, # "Gripper (Isaac)"
    {"FET_100_ISAAC" = {version = "0.3.0"}, optional=true}, # "Isaac composition"
]}
"2.2.0" = {features = [ # Adopt FET_033_STANDARD@0.4.0 (SR.004 USD/sidecar union)
    {"FET_001_STANDARD" = {version = "1.0.1"}}, # "Minimal"
    {"FET_003_STANDARD" = {version = "0.2.0"}}, # "RBD Physics"
    {"FET_004_STANDARD" = {version = "0.2.0"}, optional=true}, # "Simulate Multi-Body Physics"
    {"FET_022_STANDARD" = {version = "0.2.0"}, optional=true}, # "Driven Joints"
    {"FET_024_STANDARD" = {version = "0.1.0"}, optional=true}, # "Articulation"
    {"FET_028_STANDARD" = {version = "0.1.0"}, optional=true}, # "Gripper"

    # SimReady packaging + provenance metadata (required)
    {"FET_031_STANDARD" = {version = "0.1.0"}}, # "Self-contained Package Source"
    {"FET_033_STANDARD" = {version = "0.4.0"}}, # "Metadata (thumbnail + USD/sidecar provenance union / SR.004)"

    # PhysX runtime core / rbd / multibody / driven joints / articulation
    {"FET_000_PHYSX" = {version = "0.1.0"}, optional=true}, # "Core PhysX runtime variant"
    {"FET_003_PHYSX" = {version = "0.4.0"}, optional=true}, # "RBD Physics (PhysX)"
    {"FET_004_PHYSX" = {version = "0.4.0"}, optional=true}, # "Simulate Multi-Body Physics (PhysX)"
    {"FET_022_PHYSX" = {version = "0.2.0"}, optional=true}, # "Driven Joints (PhysX)"
    {"FET_024_PHYSX" = {version = "0.1.0"}, optional=true}, # "Articulation (PhysX)"
    {"FET_021_ISAAC" = {version = "0.2.0"}, optional=true}, # "Robot Core (Isaac)"

    # Newton runtime core / rbd / multibody / driven joints / articulation
    {"FET_000_NEWTON" = {version = "0.1.0"}, optional=true}, # "Core Newton runtime variant"
    {"FET_003_NEWTON" = {version = "0.1.0"}, optional=true}, # "RBD Physics (Newton)"
    {"FET_004_NEWTON" = {version = "0.1.0"}, optional=true}, # "Simulate Multi-Body Physics (Newton)"
    {"FET_022_NEWTON" = {version = "0.1.0"}, optional=true}, # "Driven Joints (Newton)"
    {"FET_024_NEWTON" = {version = "0.1.0"}, optional=true}, # "Articulation (Newton)"

    # MuJoCo runtime core / rbd / multibody / driven joints / articulation / gripper
    {"FET_000_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Core MuJoCo runtime variant"
    {"FET_003_MUJOCO" = {version = "0.1.0"}, optional=true}, # "RBD Physics (MuJoCo)"
    {"FET_004_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Simulate Multi-Body Physics (MuJoCo)"
    {"FET_022_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Driven Joints (MuJoCo)"
    {"FET_024_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Articulation (MuJoCo)"
    {"FET_028_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Gripper (MuJoCo)"

    {"FET_022_ISAAC" = {version = "0.2.0"}, optional=true}, # "Driven Joints (Isaac)"
    {"FET_028_ISAAC" = {version = "0.1.0"}, optional=true}, # "Gripper (Isaac)"
    {"FET_100_ISAAC" = {version = "0.3.0"}, optional=true}, # "Isaac composition"
]}
"3.0.0" = {features = [ # Require UsdPreviewSurface; display colour, OpenPBR and MDL stay optional
    {"FET_001_STANDARD" = {version = "1.0.1"}}, # "Minimal"
    {"FET_003_STANDARD" = {version = "0.2.0"}}, # "RBD Physics"
    {"FET_004_STANDARD" = {version = "0.2.0"}, optional=true}, # "Simulate Multi-Body Physics"
    {"FET_022_STANDARD" = {version = "0.2.0"}, optional=true}, # "Driven Joints"
    {"FET_024_STANDARD" = {version = "0.1.0"}, optional=true}, # "Articulation"
    {"FET_028_STANDARD" = {version = "0.1.0"}, optional=true}, # "Gripper"
    {"FET_006_STANDARD" = {version = "0.2.0"}}, # "Materials - UsdPreviewSurface (required)"
    {"FET_006_OPENPBR" = {version = "0.1.0"}, optional=true}, # "Materials - OpenPBR (optional)"
    {"FET_006_MDL" = {version = "0.2.0"}, optional=true}, # "Materials - MDL (optional)"
    {"FET_010_STANDARD" = {version = "0.1.0"}, optional=true}, # "Display Color (optional)"

    # SimReady packaging + provenance metadata (required)
    {"FET_031_STANDARD" = {version = "0.1.0"}}, # "Self-contained Package Source"
    {"FET_033_STANDARD" = {version = "0.4.0"}}, # "Metadata (thumbnail + USD/sidecar provenance union / SR.004)"

    # PhysX runtime core / rbd / multibody / driven joints / articulation
    {"FET_000_PHYSX" = {version = "0.1.0"}, optional=true}, # "Core PhysX runtime variant"
    {"FET_003_PHYSX" = {version = "0.4.0"}, optional=true}, # "RBD Physics (PhysX)"
    {"FET_004_PHYSX" = {version = "0.4.0"}, optional=true}, # "Simulate Multi-Body Physics (PhysX)"
    {"FET_022_PHYSX" = {version = "0.2.0"}, optional=true}, # "Driven Joints (PhysX)"
    {"FET_024_PHYSX" = {version = "0.1.0"}, optional=true}, # "Articulation (PhysX)"
    {"FET_021_ISAAC" = {version = "0.2.0"}, optional=true}, # "Robot Core (Isaac)"

    # Newton runtime core / rbd / multibody / driven joints / articulation
    {"FET_000_NEWTON" = {version = "0.1.0"}, optional=true}, # "Core Newton runtime variant"
    {"FET_003_NEWTON" = {version = "0.1.0"}, optional=true}, # "RBD Physics (Newton)"
    {"FET_004_NEWTON" = {version = "0.1.0"}, optional=true}, # "Simulate Multi-Body Physics (Newton)"
    {"FET_022_NEWTON" = {version = "0.1.0"}, optional=true}, # "Driven Joints (Newton)"
    {"FET_024_NEWTON" = {version = "0.1.0"}, optional=true}, # "Articulation (Newton)"

    # MuJoCo runtime core / rbd / multibody / driven joints / articulation / gripper
    {"FET_000_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Core MuJoCo runtime variant"
    {"FET_003_MUJOCO" = {version = "0.1.0"}, optional=true}, # "RBD Physics (MuJoCo)"
    {"FET_004_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Simulate Multi-Body Physics (MuJoCo)"
    {"FET_022_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Driven Joints (MuJoCo)"
    {"FET_024_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Articulation (MuJoCo)"
    {"FET_028_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Gripper (MuJoCo)"

    {"FET_022_ISAAC" = {version = "0.2.0"}, optional=true}, # "Driven Joints (Isaac)"
    {"FET_028_ISAAC" = {version = "0.1.0"}, optional=true}, # "Gripper (Isaac)"
    {"FET_100_ISAAC" = {version = "0.3.0"}, optional=true}, # "Isaac composition"
]}

```

### Required versus optional features

Two features are required in version `2.0.0`; packaging and provenance join them
from `2.1.0`. Version `3.0.0` also requires the baseline visual-material feature
`FET_006_STANDARD`; every gripper-specific or alternative visual feature stays
optional and is validated only when the asset selects it.

| Feature | Version | Status | Purpose |
|---|---|---|---|
| `FET_001_STANDARD` | 1.0.1 | Required | Minimal OpenUSD asset: units, hierarchy, mesh geometry |
| `FET_003_STANDARD` | 0.2.0 | Required | Neutral rigid-body physics and colliders |
| `FET_006_STANDARD` | 0.2.0 (from profile `3.0.0`) | Required | `UsdPreviewSurface` materials |
| `FET_010_STANDARD` | 0.1.0 (from profile `3.0.0`) | Optional | Display colour and opacity |
| `FET_006_OPENPBR` | 0.1.0 (from profile `3.0.0`) | Optional | OpenPBR materials |
| `FET_006_MDL` | 0.2.0 (from profile `3.0.0`) | Optional | MDL materials |
| `FET_004_STANDARD` | 0.2.0 | Optional | Neutral multibody joints |
| `FET_022_STANDARD` | 0.2.0 | Optional | Neutral driven joints |
| `FET_024_STANDARD` | 0.1.0 | Optional | Single articulation root |
| `FET_028_STANDARD` | 0.1.0 | Optional | Gripper site: socket type, forward axis, grip line, max opening |
| `FET_004_PHYSX` | 0.4.0 | Optional | PhysX multibody, mass, and nesting rules |
| `FET_022_PHYSX` | 0.2.0 | Optional | PhysX drives and mimic joints |
| `FET_024_PHYSX` | 0.1.0 | Optional | PhysX collision clearance between links |
| `FET_021_ISAAC` | 0.2.0 | Optional | Robot identity: robot schema, robot type, root joint |
| `FET_022_ISAAC` | 0.2.0 | Optional | Isaac link and joint APIs |
| `FET_028_ISAAC` | 0.1.0 | Optional | Isaac gripper site |
| `FET_100_ISAAC` | 0.3.0 | Optional | Isaac Sim composition |

A practical end-effector selects at least `FET_004_STANDARD`,
`FET_022_STANDARD`, `FET_024_STANDARD`, and `FET_028_STANDARD`. Add the PhysX
features for a runnable PhysX gripper, and the Isaac features for an Isaac Sim
deliverable.

Version `3.0.0` makes the baseline appearance mandatory: every conforming
gripper carries a `UsdPreviewSurface` material (`FET_006_STANDARD`). Display
colour (`FET_010_STANDARD`), OpenPBR and MDL remain optional, so an asset
picks whichever final surface its runtime needs and `DISP.001` to `DISP.003` are
validated only on an asset that selects display colour. Requirements shared between a
required and an optional feature stay required: `VM.MAT.001`, `VM.TEX.001`,
`com.nvidia.usd.VM.BIND.001`, and `com.nvidia.usd.VM.PS.001` are mandatory from
`3.0.0`. `VM.PBR.*` (OpenPBR) and `VM.BIND.002`, `VM.MDL.001`,
`com.nvidia.usd.VM.MDL.002`, `VM.TEX.002` (MDL) stay optional.

## Required USD properties and schemas

### Stage metadata and hierarchy (`FET_001_STANDARD`)

- Set `defaultPrim` on every layer, and `upAxis = "Z"` with `metersPerUnit = 1`
  on every stage.
- Keep the prim hierarchy anchored under the default prim.

### Rigid bodies and colliders (`FET_003_STANDARD`)

- Apply `PhysicsRigidBodyAPI` to any simulated rigid body prim, which must be
  `UsdGeomXformable`.
- Apply `PhysicsCollisionAPI` to collision-enabled prims.

### Materials (`FET_006_STANDARD`, `FET_010_STANDARD`, `FET_006_OPENPBR`, and `FET_006_MDL`)

Required from version `3.0.0`. The material requirements are identical to those
in the [Robotics-Prop guide](robotics-prop), which describes each requirement in
full.

## Optional feature requirements

### Gripper site (`FET_028_STANDARD`)

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

`FET_004_*`, `FET_022_*`, and `FET_024_*` carry the same requirements as in the
[Robot-Body guide](robot-body).

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
- `docs/features/FET_028_STANDARD.md`
- `docs/features/FET_006_STANDARD.md`
- `docs/features/FET_010_STANDARD.md`
- `docs/capabilities/physics_bodies/physics_grippers/requirements/gripper-socket-type.md`
- `docs/capabilities/physics_bodies/physics_grippers/requirements/gripper-forward-axis.md`
- `docs/capabilities/physics_bodies/physics_grippers/requirements/gripper-grip-line.md`
- `docs/capabilities/physics_bodies/physics_grippers/requirements/gripper-max-opening.md`
