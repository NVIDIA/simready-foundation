# Robot-Body Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Robot-Body` profile. It consolidates the required feature set, USD properties,
naming conventions, and composition expectations for robot body assets.

`Robot-Body` version `2.0.0` is the consolidated robot profile. It supersedes
the separate `Robot-Body-Neutral`, `Robot-Body-Runnable`, and `Robot-Body-Isaac`
profiles by keeping a neutral OpenUSD core mandatory and exposing PhysX and
Isaac behavior as optional features. Version `2.1.0` keeps that menu, adds
required SimReady packaging and provenance metadata, and exposes optional
Newton and MuJoCo multiphysics runtime features (`FET_004_*`, `FET_022_*`,
`FET_024_*`) alongside the existing PhysX variants. Version `2.2.0` keeps the
`2.1.0` set (including the Newton and MuJoCo multiphysics features) and adds
optional `FET_025_ROS@0.1.0` for Isaac ROS-Ready bridge wiring.

## Profile definition

The `Robot-Body` profile includes the following feature set (see
`robot_body.toml` and the
[feature dependency graph](../features/feature-dependency-graph)). Each
feature's requirements and dependencies are defined in the feature
specifications.

```toml
[Robot-Body]
"2.0.0" = {features = [
    {"FET_001_STANDARD" = {version = "1.0.1"}}, # "Minimal"
    {"FET_003_STANDARD" = {version = "0.2.0"}}, # "RBD Physics"
    {"FET_004_STANDARD" = {version = "0.2.0"}, optional=true}, # "Simulate Multi-Body Physics"
    {"FET_021_ISAAC" = {version = "0.3.0"}, optional=true}, # "Robot Core (Isaac identity)"
    {"FET_022_STANDARD" = {version = "0.2.0"}, optional=true}, # "Driven Joints"
    {"FET_024_STANDARD" = {version = "0.1.0"}, optional=true}, # "Articulation"

    {"FET_004_PHYSX" = {version = "0.4.0"}, optional=true}, # "Simulate Multi-Body Physics (PhysX)"
    {"FET_022_PHYSX" = {version = "0.2.0"}, optional=true}, # "Driven Joints (PhysX)"
    {"FET_024_PHYSX" = {version = "0.1.0"}, optional=true}, # "Articulation (PhysX)"

    {"FET_000_ISAAC" = {version = "0.1.0"}, optional=true}, # "Core (Isaac) packaging"
    {"FET_022_ISAAC" = {version = "0.2.0"}, optional=true}, # "Driven Joints (Isaac)"
    {"FET_023_ISAAC" = {version = "0.1.0"}, optional=true}, # "Robot Materials (Isaac)"
    {"FET_100_ISAAC" = {version = "0.3.0"}, optional=true}, # "Isaac composition"
]}
"2.1.0" = {features = [ # Add required SimReady packaging + provenance metadata (FET_031_STANDARD, FET_033_STANDARD@0.3.0 / SR.003); add optional Newton/MuJoCo multiphysics runtime features and per-runtime Core scaffolding (FET_000_PHYSX/NEWTON/MUJOCO)
    {"FET_001_STANDARD" = {version = "1.0.1"}}, # "Minimal"
    {"FET_003_STANDARD" = {version = "0.2.0"}}, # "RBD Physics"
    {"FET_004_STANDARD" = {version = "0.2.0"}, optional=true}, # "Simulate Multi-Body Physics"
    {"FET_021_ISAAC" = {version = "0.3.0"}, optional=true}, # "Robot Core (Isaac identity)"
    {"FET_022_STANDARD" = {version = "0.2.0"}, optional=true}, # "Driven Joints"
    {"FET_024_STANDARD" = {version = "0.1.0"}, optional=true}, # "Articulation"

    # SimReady packaging + provenance metadata (required)
    {"FET_031_STANDARD" = {version = "0.1.0"}}, # "Self-contained Package Source"
    {"FET_033_STANDARD" = {version = "0.3.0"}}, # "Metadata (thumbnail + nested provenance metadata)"

    # PhysX runtime core / multibody / driven joints / articulation
    {"FET_000_PHYSX" = {version = "0.1.0"}, optional=true}, # "Core PhysX runtime variant"
    {"FET_004_PHYSX" = {version = "0.4.0"}, optional=true}, # "Simulate Multi-Body Physics (PhysX)"
    {"FET_022_PHYSX" = {version = "0.2.0"}, optional=true}, # "Driven Joints (PhysX)"
    {"FET_024_PHYSX" = {version = "0.1.0"}, optional=true}, # "Articulation (PhysX)"

    # Newton runtime core / multibody / driven joints / articulation
    {"FET_000_NEWTON" = {version = "0.1.0"}, optional=true}, # "Core Newton runtime variant"
    {"FET_004_NEWTON" = {version = "0.1.0"}, optional=true}, # "Simulate Multi-Body Physics (Newton)"
    {"FET_022_NEWTON" = {version = "0.1.0"}, optional=true}, # "Driven Joints (Newton)"
    {"FET_024_NEWTON" = {version = "0.1.0"}, optional=true}, # "Articulation (Newton)"

    # MuJoCo runtime core / multibody / driven joints / articulation
    {"FET_000_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Core MuJoCo runtime variant"
    {"FET_004_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Simulate Multi-Body Physics (MuJoCo)"
    {"FET_022_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Driven Joints (MuJoCo)"
    {"FET_024_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Articulation (MuJoCo)"

    {"FET_000_ISAAC" = {version = "0.1.0"}, optional=true}, # "Core (Isaac) packaging"
    {"FET_022_ISAAC" = {version = "0.2.0"}, optional=true}, # "Driven Joints (Isaac)"
    {"FET_023_ISAAC" = {version = "0.1.0"}, optional=true}, # "Robot Materials (Isaac)"
    {"FET_100_ISAAC" = {version = "0.3.0"}, optional=true}, # "Isaac composition"
]}
"2.2.0" = {features = [ # Add optional Isaac ROS-Ready bridge wiring (FET_025_ROS); add optional Newton/MuJoCo multiphysics runtime features and per-runtime Core scaffolding (FET_000_PHYSX/NEWTON/MUJOCO)
    {"FET_001_STANDARD" = {version = "1.0.1"}}, # "Minimal"
    {"FET_003_STANDARD" = {version = "0.2.0"}}, # "RBD Physics"
    {"FET_004_STANDARD" = {version = "0.2.0"}, optional=true}, # "Simulate Multi-Body Physics"
    {"FET_021_ISAAC" = {version = "0.3.0"}, optional=true}, # "Robot Core (Isaac identity)"
    {"FET_022_STANDARD" = {version = "0.2.0"}, optional=true}, # "Driven Joints"
    {"FET_024_STANDARD" = {version = "0.1.0"}, optional=true}, # "Articulation"
    {"FET_025_ROS" = {version = "0.1.0"}, optional=true}, # "ROS Ready (Isaac)"

    # SimReady packaging + provenance metadata (required)
    {"FET_031_STANDARD" = {version = "0.1.0"}}, # "Self-contained Package Source"
    {"FET_033_STANDARD" = {version = "0.3.0"}}, # "Metadata (thumbnail + nested provenance metadata)"

    # PhysX runtime core / multibody / driven joints / articulation
    {"FET_000_PHYSX" = {version = "0.1.0"}, optional=true}, # "Core PhysX runtime variant"
    {"FET_004_PHYSX" = {version = "0.4.0"}, optional=true}, # "Simulate Multi-Body Physics (PhysX)"
    {"FET_022_PHYSX" = {version = "0.2.0"}, optional=true}, # "Driven Joints (PhysX)"
    {"FET_024_PHYSX" = {version = "0.1.0"}, optional=true}, # "Articulation (PhysX)"

    # Newton runtime core / multibody / driven joints / articulation
    {"FET_000_NEWTON" = {version = "0.1.0"}, optional=true}, # "Core Newton runtime variant"
    {"FET_004_NEWTON" = {version = "0.1.0"}, optional=true}, # "Simulate Multi-Body Physics (Newton)"
    {"FET_022_NEWTON" = {version = "0.1.0"}, optional=true}, # "Driven Joints (Newton)"
    {"FET_024_NEWTON" = {version = "0.1.0"}, optional=true}, # "Articulation (Newton)"

    # MuJoCo runtime core / multibody / driven joints / articulation
    {"FET_000_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Core MuJoCo runtime variant"
    {"FET_004_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Simulate Multi-Body Physics (MuJoCo)"
    {"FET_022_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Driven Joints (MuJoCo)"
    {"FET_024_MUJOCO" = {version = "0.1.0"}, optional=true}, # "Articulation (MuJoCo)"

    {"FET_000_ISAAC" = {version = "0.1.0"}, optional=true}, # "Core (Isaac) packaging"
    {"FET_022_ISAAC" = {version = "0.2.0"}, optional=true}, # "Driven Joints (Isaac)"
    {"FET_023_ISAAC" = {version = "0.1.0"}, optional=true}, # "Robot Materials (Isaac)"
    {"FET_100_ISAAC" = {version = "0.3.0"}, optional=true}, # "Isaac composition"
]}
```

### Required versus optional features

On `2.0.0` only two features are required, and from `2.1.0` the packaging and
provenance features join them. Every robot-specific feature is marked
`optional=true` and is validated only when the asset selects it.

| Feature | Version | Status | Purpose |
|---|---|---|---|
| `FET_001_STANDARD` | 1.0.1 | Required | Minimal OpenUSD asset: units, hierarchy, mesh geometry |
| `FET_003_STANDARD` | 0.2.0 | Required | Neutral rigid-body physics and colliders |
| `FET_031_STANDARD` | 0.1.0 | Required (`2.1.0`+) | Self-contained package source |
| `FET_033_STANDARD` | 0.3.0 | Required (`2.1.0`+) | Thumbnail and nested provenance metadata |
| `FET_004_STANDARD` | 0.2.0 | Optional | Neutral multibody joints |
| `FET_021_ISAAC` | 0.3.0 | Optional | Robot identity: robot schema, robot type, root joint |
| `FET_022_STANDARD` | 0.2.0 | Optional | Neutral driven joints |
| `FET_024_STANDARD` | 0.1.0 | Optional | Single articulation root |
| `FET_000_PHYSX` | 0.1.0 | Optional (`2.1.0`+) | PhysX runtime-variant Core scaffolding (variant set + payload) |
| `FET_004_PHYSX` | 0.4.0 | Optional | PhysX multibody, mass, and nesting rules |
| `FET_022_PHYSX` | 0.2.0 | Optional | PhysX drives and mimic joints |
| `FET_024_PHYSX` | 0.1.0 | Optional | PhysX collision clearance between links |
| `FET_000_NEWTON` | 0.1.0 | Optional (`2.1.0`+) | Newton runtime-variant Core scaffolding (variant set + payload) |
| `FET_004_NEWTON` | 0.1.0 | Optional (`2.1.0`+) | Newton multibody, mass, and nesting rules |
| `FET_022_NEWTON` | 0.1.0 | Optional (`2.1.0`+) | Newton driven joints |
| `FET_024_NEWTON` | 0.1.0 | Optional (`2.1.0`+) | Newton articulation root |
| `FET_000_MUJOCO` | 0.1.0 | Optional (`2.1.0`+) | MuJoCo runtime-variant Core scaffolding (variant set + payload) |
| `FET_004_MUJOCO` | 0.1.0 | Optional (`2.1.0`+) | MuJoCo multibody, mass, and nesting rules |
| `FET_022_MUJOCO` | 0.1.0 | Optional (`2.1.0`+) | MuJoCo driven joints |
| `FET_024_MUJOCO` | 0.1.0 | Optional (`2.1.0`+) | MuJoCo articulation root |
| `FET_000_ISAAC` | 0.1.0 | Optional | Isaac packaging, thumbnail, physics-layer separation |
| `FET_022_ISAAC` | 0.2.0 | Optional | Isaac link and joint APIs |
| `FET_023_ISAAC` | 0.1.0 | Optional | Isaac robot material organization |
| `FET_100_ISAAC` | 0.3.0 | Optional | Isaac Sim composition |
| `FET_025_ROS` | 0.1.0 | Optional (`2.2.0`) | Isaac ROS 2 bridge OmniGraph nodes (`ROS.001`) |

A practical robot body selects at least `FET_004_STANDARD`, `FET_021_ISAAC`,
`FET_022_STANDARD`, and `FET_024_STANDARD`. Add the PhysX features for a
runnable PhysX robot, and `FET_000_ISAAC` plus Isaac composition for an Isaac
Sim deliverable. On `2.2.0`, select `FET_025_ROS` when the robot ships ROS 2
bridge OmniGraph wiring.

From `2.1.0`, the profile also exposes each physics runtime as an optional
Core → multibody → driven-joints → articulation bundle. Alongside PhysX
(`FET_000_PHYSX`, `FET_004_PHYSX`, `FET_022_PHYSX`, `FET_024_PHYSX`) it adds
Newton (`FET_000_NEWTON`, `FET_004_NEWTON`, `FET_022_NEWTON`, `FET_024_NEWTON`)
and MuJoCo (`FET_000_MUJOCO`, `FET_004_MUJOCO`, `FET_022_MUJOCO`,
`FET_024_MUJOCO`). The `FET_000_*` Core feature provides that runtime's
variant-set scaffolding and `runnables/physics/` payload, while the
`FET_004/022/024_*` features cover multibody, driven joints, and articulation.
Select a runtime's features when the robot carries that solver's physics payload;
`simready-validate` enables the matching variant before running the
runtime-specific rules. A missing runtime does not fail the profile, but a
present runtime must pass its rules. See
[Multiple Physics Solvers](../guides/multiphysics_solvers.md).

Feature versions in this profile pin the Standard/PhysX families rather than the
legacy `FET_004_ROBOT_PHYSX` feature. Rigid-body work stays in the FET_003
family and multibody joint work stays in the FET_004 family.

## Required USD properties and schemas

### Stage metadata and hierarchy (`FET_001_STANDARD`)

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

### Rigid bodies and colliders (`FET_003_STANDARD`)

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

### Multibody joints (`FET_004_STANDARD`, `FET_004_PHYSX`)

- Connect links with a `UsdPhysicsJoint` subtype and author
  `rel physics:body0` and `rel physics:body1`; an empty side means world
  (`JT.001`).
- Target existing prims or leave the relationship empty (`JT.002`), with at most
  one target each (`JT.003`).
- Do not nest `PhysicsArticulationRootAPI` (`JT.ART.002`), and do not apply it
  to kinematic (`JT.ART.003`) or disabled/static (`JT.ART.004`) bodies.
- Apply `PhysicsRigidBodyAPI` to at least two separate `UsdGeomXformable`
  hierarchies (`RB.MB.001`).

`FET_004_PHYSX@0.4.0` adds two rules on top of the neutral set:

- Every rigid-body subtree needs authored `physics:mass > 0`, or at least one
  owned collider with non-zero-volume `extent` for auto-mass (`RB.011`).
- Every nested `PhysicsRigidBodyAPI` ancestor/descendant pair must be connected
  by a stage joint targeting both bodies (`RB.012`).

### Robot core (`FET_021_ISAAC`)

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

### Driven joints (`FET_022_STANDARD`, `FET_022_PHYSX`, `FET_022_ISAAC`)

Neutral driven joints (`FET_022_STANDARD`):

- On joints with `PhysicsDriveAPI:<angular|linear>`, author a finite
  `drive:<axis>:physics:maxForce` greater than zero (`DJ.001`).
- Apply `PhysicsJointStateAPI:angular` to non-fixed revolute joints and
  `PhysicsJointStateAPI:linear` to prismatic joints (`DJ.002`).
- Keep `physics:localPos0/1`, `physics:localRot0/1`, and the joint-state pose
  mutually consistent (`DJ.003`).
- Keep the articulation joint graph acyclic with at most one joint per
  rigid-body pair, excluding joints with
  `physics:excludeFromArticulation = true` (`DJ.011`).

PhysX driven joints (`FET_022_PHYSX`) add:

- Apply `PhysicsDriveAPI:<axis>` or `PhysxMimicJointAPI:<rotX|rotY|rotZ>` to
  non-fixed joints that participate in the articulation. When both are present,
  set drive stiffness and damping to exactly `0.0` (`DJ.004`, `DJ.006`).
- Author `float physxJoint:maxJointVelocity` greater than zero on joints with
  `PhysxJointAPI` (`DJ.005`).
- Give each mimic joint exactly one
  `rel physxMimicJoint:<axis>:referenceJoint` target, plus non-zero
  `physxMimicJoint:<axis>:gearing` and `physxMimicJoint:<axis>:naturalFrequency`
  and an authored `physxMimicJoint:<axis>:dampingRatio`. Both the mimic and
  reference joints need limits, and neither may set
  `physics:excludeFromArticulation = true` (`DJ.007`).

Isaac driven joints (`FET_022_ISAAC`) add:

- Apply the Isaac joint API to at least one prim (`DJ.008`) and the Isaac link
  API to at least one prim (`DJ.009`).
- Prepend `isaac:physics:robotLinks` and `isaac:physics:robotJoints` on the
  default prim carrying `IsaacRobotAPI` (`DJ.010`).

### Articulation (`FET_024_STANDARD`, `FET_024_PHYSX`)

Apply exactly one `PhysicsArticulationRootAPI` on the kinematic-chain root
(`BA.001`). Zero roots and multiple roots both fail:

```usd
def Xform "Robot" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
}
```

`FET_024_PHYSX` adds `BA.002`: collision meshes on non-adjacent articulation
links must not overlap at the default pose. This is verified by detecting
initial PhysX collider contacts rather than by inspecting authored attributes,
so it requires a runtime check.

### Isaac packaging (`FET_000_ISAAC`)

`FET_000_ISAAC@0.1.0` depends on `FET_000_STANDARD@0.1.0` and adds four
packaging requirements:

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

### Isaac composition (`FET_100_ISAAC`)

`ISA.001` requires the main USD to have a default prim with `kind = "component"`
that references separate mesh and physics layers through relative paths:

- Organize materials under a `Scope "Looks"`, raw geometry under an invisible
  `Scope "Meshes"`, and visual references under an invisible `Scope "Visuals"`.
- Apply physics schemas and attributes in the physics payload only.
- Set `upAxis = "Z"`, `metersPerUnit = 1.0`, and a default prim in every file,
  keeping all reference and payload paths relative.

The `ISA.001` requirement page and the composition validator currently disagree
on exact payload file names. Check
`capabilities/isaac_sim/composition/validation.py` for the names the validator
expects before finalizing a layout.

### ROS Ready (version 2.2.0)

Version `2.2.0` adds optional `FET_025_ROS@0.1.0`. Use it when the robot asset
includes OmniGraph nodes whose `node:type` starts with `isaacsim.ros2.bridge.`
(`ROS.001`). Repair with `simready-foundation-conform-fet-025-ros` after Isaac
composition when ROS bridge wiring is in scope.

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
            string profile_version = "2.2.0"
        }
    }
}
```

## Conformance workflow

Repair one feature gate at a time, in dependency order:

```text
validate Robot-Body
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
-> simready-foundation-conform-fet-025-ros (only when ROS-Ready is selected on 2.2.0)
-> validate Robot-Body again
```

Get the body and joint topology in shape before the articulation gate. The
Standard articulation feature checks the single articulation root; the PhysX
feature also needs collision-clearance evidence for non-adjacent links.

## References

- [Feature dependency graph](../features/feature-dependency-graph) — requirements and dependencies for all features
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot_body.toml`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_000_ISAAC.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_001_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_PHYSX.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_021_ISAAC.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_022_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_022_PHYSX.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_022_ISAAC.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_023_ISAAC.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_024_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_024_PHYSX.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_025_ROS.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_031_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_033_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_100_ISAAC.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/isaac_sim/robot_core/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/isaac_sim/composition/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/isaac_sim/ros_bridge/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_driven_joints/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/base_articulation/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_joints/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_rigid_bodies/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/naming_paths/`
