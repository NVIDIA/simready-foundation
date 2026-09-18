# Robot-Body-Isaac Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Robot-Body-Isaac` profile. It consolidates the required feature set, USD
properties, naming conventions, and robot-specific composition requirements.

## Profile definition

The `Robot-Body-Isaac` profile includes the following feature set (see `robot_body_isaac.toml` and the [feature dependency graph](../features/feature-dependency-graph)). Each feature's requirements and dependencies are defined in the feature specifications.

```toml
[Robot-Body-Isaac]
"1.0.0" = {features = [
    {"FET_001_STANDARD" = {version = "0.1.0"}}, # Minimal
    {"FET_003_STANDARD" = {version = "0.1.0"}}, # RBD Physics (Standard)
    {"FET_004_ROBOT_PHYSX" = {version = "0.1.0"}}, # Multi-body physics (Robot PhysX)
    {"FET_021_ISAAC" = {version = "0.2.0"}}, # Robot Core (Isaac)
    {"FET_022_ISAAC" = {version = "0.1.0"}}, # Driven Joints (Isaac)
    {"FET_024_PHYSX" = {version = "0.1.0"}}, # Articulation
    {"FET_100_ISAAC" = {version = "0.1.0"}}, # Isaac composition
]}
"1.2.0" = {features = [
    {"FET_001_STANDARD" = {version = "0.1.0"}}, # Minimal
    {"FET_003_PHYSX" = {version = "0.4.0"}}, # RBD Physics (PhysX)
    {"FET_004_PHYSX" = {version = "0.4.0"}}, # Multi-body physics (PhysX)
    {"FET_021_ISAAC" = {version = "0.2.0"}}, # Robot Core (Isaac)
    {"FET_022_ISAAC" = {version = "0.2.0"}}, # Driven Joints (Isaac)
    {"FET_024_PHYSX" = {version = "0.1.0"}}, # Articulation
    {"FET_101_ISAAC" = {version = "0.1.0"}}, # Robot Isaac composition
]}
```

### Version 1.2.0 notes

Version 1.2.0 pins the PhysX rigid-body/multibody contract
(`FET_003_PHYSX@0.4.0`, `FET_004_PHYSX@0.4.0`) and adopts the robot Isaac
composition feature `FET_101_ISAAC@0.1.0` in place of the prop-oriented
`FET_100_ISAAC`. `FET_101_ISAAC` routes robot assets to the standalone
`simready.asset_transformer` robot transform (`simready_physx_to_isaac_robot`),
so the composed asset carries the Isaac robot schema (`IsaacRobotAPI`,
`isaac:physics:robotLinks`, `isaac:physics:robotJoints`) required by the
`FET_021_ISAAC` robot-core checks.

## Required USD properties and schemas

### Stage metadata (required)

- `defaultPrim` must be set on every layer.
- `upAxis = "Z"` and `metersPerUnit = 1` must be set on every stage.

### PhysX rigid bodies and colliders (required)

- Apply `PhysicsRigidBodyAPI` to any simulated rigid body prim.
- Apply `PhysicsCollisionAPI` to collision-enabled prims.
- Author `physics:approximation = "sdf"` for PhysX collider approximation.
- Rigid body prims must be `UsdGeomXformable`.

### Multi-body joints (required)

- Use `UsdPhysicsJoint` prims (or subtypes) to connect rigid bodies.
- Author `rel physics:body0` and `rel physics:body1` relationships.
- Apply `PhysxJointAPI` when authoring PhysX-specific joint properties.

### Driven joints (required)

- Apply `PhysicsDriveAPI:*` or `PhysxMimicJointAPI:*` to driven joints.
- Apply `PhysicsJointStateAPI:*` to driven joints.
- Author `physxJoint:maxJointVelocity` with a positive value.
- When a joint has both drive and mimic APIs, drive stiffness and damping must
  be exactly `0.0`.
- Mimic joints must set a single valid `physxMimicJoint:*:referenceJoint` and
  author `physxMimicJoint:*:gearing`, `physxMimicJoint:*:naturalFrequency`, and
  `physxMimicJoint:*:dampingRatio`.

### Robot schema (required)

Apply `IsaacRobotAPI` to the default prim and populate robot relationships:

- `apiSchemas` includes `IsaacRobotAPI`
- `isaac:namespace`
- `isaac:physics:robotJoints` relationship
- `isaac:physics:robotLinks` relationship

### Articulation root (required)

Apply `PhysicsArticulationRootAPI` to the root prim of the articulation:

```usd
def Xform "Robot" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
}
```

## Robot composition requirements

Robot core requirements enforce a modular layout for physics data and a clean
asset folder structure.

### Physics layer separation

- Author physics schemas and physics attributes in the physics layer only.
- Keep base/visual layers free of physics schemas and physics attributes.

### Clean folder layout

- Robot asset folders must not contain unreferenced files.
- Keep the interface layer at the root, with subfolders for payloads.

Example layout:

```
Manufacturer/
  robot.usd
  Payload/
    material.usda
    base.usda
    geometry.usdc
    instances.usda
    Physics/
      physics.usda
      physx.usda
```

### No overrides

- Author changes in source layers, not session or override layers.
- Avoid muting or overriding schema-defining layers.

### Thumbnail requirement

- Provide a thumbnail at `.thumbs/256x256/{robot name}.png`.

## Naming conventions

### Robot naming

- Use lowercase, underscore-separated file names.
- Use stable prim paths for robot roots and joints.

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
            string profile = "Robot-Body-Isaac"
            string profile_version = "1.0.0"
        }
    }
}
```

## References

- [Feature dependency graph](../features/feature-dependency-graph) — requirements and dependencies for all features
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot_body_isaac.toml`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_021_ISAAC.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_022_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_024_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/isaac_sim/robot_core/requirements/robot-schema.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/isaac_sim/robot_core/requirements/robot-naming.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/isaac_sim/robot_core/requirements/clean-folder.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/isaac_sim/robot_core/requirements/no-overrides.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/isaac_sim/robot_core/requirements/thumbnail-exist.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/isaac_sim/robot_core/requirements/verify-robot-physics-attribute-source-layer.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/isaac_sim/robot_core/requirements/verify-robot-physics-schema-source-layer.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/base_articulation/requirements/has-articulation-root.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_driven_joints/requirements/physics-joint-has-drive-or-mimic-api.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_driven_joints/requirements/physics-joint-max-velocity.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_driven_joints/requirements/drive-joint-value-reasonable.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_driven_joints/requirements/mimic-api-check.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/naming_paths/requirements/prim-naming-convention.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/naming_paths/requirements/file-naming-convention.md`
