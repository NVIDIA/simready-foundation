# Robot-Body-Isaac Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Robot-Body-Isaac` profile. It consolidates the required feature set, USD
properties, naming conventions, and robot-specific composition requirements.

## Profile definition

The `Robot-Body-Isaac` profile includes the following feature set (see `profiles.toml` and the [feature dependency graph](../features/feature-dependency-graph)). Each feature's requirements and dependencies are defined in the feature specifications.

```toml
[Robot-Body-Isaac]
"1.0.0" = {features = [
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}}, # Minimal
    {"FET003_BASE_NEUTRAL" = {version = "0.1.0"}}, # RBD Physics (Neutral)
    {"FET004_ROBOT_PHYSX" = {version = "0.1.0"}}, # Multi-body physics (Robot PhysX)
    {"FET021_ROBOT_CORE_ISAAC" = {version = "0.2.0"}}, # Robot Core (Isaac)
    {"FET022_DRIVEN_JOINTS_ISAAC" = {version = "0.1.0"}}, # Driven Joints (Isaac)
    {"FET024_BASE_ARTICULATION_PHYSX" = {version = "0.1.0"}}, # Articulation
    {"FET100_BASE_ISAACSIM" = {version = "0.1.0"}}, # Isaac composition
]}
```

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
- `nv_core/sr_specs/docs/profiles/profiles.toml`
- `nv_core/sr_specs/docs/features/FET_021-robot_core.md`
- `nv_core/sr_specs/docs/features/FET_022-driven_joints.md`
- `nv_core/sr_specs/docs/features/FET_024-base_articulation.md`
- `nv_core/sr_specs/docs/capabilities/isaac_sim/robot_core/requirements/robot-schema.md`
- `nv_core/sr_specs/docs/capabilities/isaac_sim/robot_core/requirements/robot-naming.md`
- `nv_core/sr_specs/docs/capabilities/isaac_sim/robot_core/requirements/clean-folder.md`
- `nv_core/sr_specs/docs/capabilities/isaac_sim/robot_core/requirements/no-overrides.md`
- `nv_core/sr_specs/docs/capabilities/isaac_sim/robot_core/requirements/thumbnail-exist.md`
- `nv_core/sr_specs/docs/capabilities/isaac_sim/robot_core/requirements/verify-robot-physics-attribute-source-layer.md`
- `nv_core/sr_specs/docs/capabilities/isaac_sim/robot_core/requirements/verify-robot-physics-schema-source-layer.md`
- `nv_core/sr_specs/docs/capabilities/physics_bodies/base_articulation/requirements/has-articulation-root.md`
- `nv_core/sr_specs/docs/capabilities/physics_bodies/physics_driven_joints/requirements/physics-joint-has-drive-or-mimic-api.md`
- `nv_core/sr_specs/docs/capabilities/physics_bodies/physics_driven_joints/requirements/physics-joint-max-velocity.md`
- `nv_core/sr_specs/docs/capabilities/physics_bodies/physics_driven_joints/requirements/drive-joint-value-reasonable.md`
- `nv_core/sr_specs/docs/capabilities/physics_bodies/physics_driven_joints/requirements/mimic-api-check.md`
- `nv_core/sr_specs/docs/capabilities/core/naming_paths/requirements/prim-naming-convention.md`
- `nv_core/sr_specs/docs/capabilities/core/naming_paths/requirements/file-naming-convention.md`
