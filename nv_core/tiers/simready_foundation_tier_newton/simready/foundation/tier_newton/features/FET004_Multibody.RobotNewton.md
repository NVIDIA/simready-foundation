# Feature: `FET004_Multibody.RobotNewton`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET004_Multibody.RobotNewton` |
| Runtime                 | `RobotNewton` |
| Proprietary Techs       | `Newton` |
| Versions                | `0-1-0` |

## Description

The Robot Newton Multi-Body Physics feature is a robot-specific Newton
multibody contract. It mirrors the robot PhysX shape, replaces PhysX collider
requirements with Newton collider requirements, and intentionally does not
require `RB.COL.001` because robot assets may use nested collision authoring
patterns.

### Newton Authoring Notes

Editorial guidance (does not change the requirement IDs below):

- **Single enabled fixed base joint**: Newton's USD importer resolves any joint `physics:body0` target without an enabled `PhysicsRigidBodyAPI` to the world (`parent = -1`). If a robot carries both a legacy fixed root joint (targeting a non-rigid-body `/Robot` or `/Robot/world` `Xform`) and a `__fixed_base_joint`, disable the redundant joint (`bool physics:jointEnabled = 0`) in `runnables/physics/newton.usda` so Newton does not fail merging two world-to-base `FixedJoint`s into a D6 joint. Do not disable internal `PhysicsFixedJoint`s whose child prims carry `PhysicsRigidBodyAPI` inside the articulation root, as an unjointed rigid body under the articulation root creates a second Newton articulation and fails `SingleArticulation.initialize()`.
- **Directed parent-to-child articulation tree**: Every joint in the articulation (`physics:excludeFromArticulation = false`) must point from parent (`physics:body0`, closer to the articulation root) to child (`physics:body1`, farther from the root). When swapping `body0`/`body1` and `localPos0`/`localPos1`, `localRot0`/`localRot1` on an inverted serial joint, also convert its signed coordinate ($q' = -q$ for the same `physics:axis`) by negating and swapping asymmetric `lowerLimit`/`upperLimit`, negating non-zero `state:<axis>:physics:*`, `drive:<axis>:physics:target*`, and signed `newton:constEffort` values, reversing and negating `newton:lookupPositions` while reversing `newton:lookupEfforts` (keeping effort capacities non-negative and positions sorted), and updating the sign of `newton:mimicCoef0`/`newton:mimicCoef1` on any `NewtonMimicAPI` coupling that involves the reversed joint. In closed-loop / 4-bar mechanisms (`DJ.011`), set `physics:excludeFromArticulation = true` on the loop-closing joint rather than the root-side chain entry joint so Newton's topological sort does not encounter reversed joints.
- **Mesh collider approximation and self-collision contact behavior**: On robot links containing multiple collision sub-meshes, prefer `PhysicsMeshCollisionAPI` with `uniform token physics:approximation = "convexHull"` (when convex hulls preserve clearance) and `physics:filteredPairs` for legitimately overlapping adjacent links. Only set `bool newton:selfCollisionEnabled = 0` on the articulation root when source evidence establishes that self-collision is unintended; do not disable intended self-collision merely to pass a test or work around an engine contact-budget limitation.

## Dependency Graph

This feature has no JSON feature dependencies. It carries an explicit
robot-specific requirement list.

```{mermaid}
flowchart LR
    FET004RN["FET004_Multibody.RobotNewton\n0-1-0"]
    FET022N["FET022_DrivenJoints.Newton\n0-1-0"]

    FET022N --> FET004RN

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET004RN current
    class FET022N other
```

## Use Cases

- Future Newton robot profiles that need a robot-specific collider exemption.
- Newton robot link and joint topology before driven-joint or articulation gates.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

No profile selects this version.

#### Feature Dependencies

None.

#### Requirement List

| Capability | Requirements |
|------------|--------------|
| Physics Rigid Bodies | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.007`, `RB.009`, `RB.010`, `RB.MB.001`, `NEWTON.COL.001`, `NEWTON.COL.002`, `NEWTON.MAS.001`, `RB.011`, `RB.012` |
| Physics Materials | `NEWTON.MAT.001` |
| Physics Joints | `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004` |

</details>

## Pipelines

Source file type:

- `.urdf` / `.mjcf`
  - Via robot conversion workflows that preserve robot link structure.

Validation or runtime pipeline:

- SimReady validation - verifies the selected `FET004_Multibody.RobotNewton` manifest.

## Samples

- None.

## Evaluates

 - [Newton multibody observations](../runtime_tests/docs/runtime-tests.md#qualified-joint-movement-observations)
   - `joint_movement_newton` (independently owned Newton procedure).

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET003_RigidBody.0-1-0` | `FET004_Multibody.RobotNewton.0-1-0` | `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_newton` | Done | Computes mesh extents and applies Newton mesh-collision schemas (`newton:contactGap`), and applies `NewtonMaterialAPI` with default friction tuning to bound physics materials. |
