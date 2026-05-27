# Robot-Body-Runnable Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Robot-Body-Runnable` profile. It consolidates the required feature set, USD
properties, naming conventions, and composition expectations for runnable
robot assets (PhysX multibody with robot core runnable).

## Profile definition

The `Robot-Body-Runnable` profile includes the following feature set:

```toml
[Robot-Body-Runnable]
"1.0.0" = {features = [
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}}, # Minimal
    {"FET003_BASE_NEUTRAL" = {version = "0.1.0"}}, # RBD Physics (Neutral)
    {"FET004_ROBOT_PHYSX" = {version = "0.1.0"}}, # Multi-body physics (Robot PhysX)
    {"FET021_ROBOT_CORE_RUNNABLE" = {version = "0.2.0"}}, # Robot Core (Runnable)
    {"FET022_DRIVEN_JOINTS_PHYSX" = {version = "0.1.0"}}, # Driven Joints (PhysX)
    {"FET024_BASE_ARTICULATION_PHYSX" = {version = "0.1.0"}}, # Articulation
]}
```

## Required USD properties and schemas

### Stage metadata (required)

- `defaultPrim` must be set on every layer.
- `upAxis = "Z"` and `metersPerUnit = 1` must be set on every stage.

### PhysX rigid bodies and colliders (required)

- Apply `PhysicsRigidBodyAPI` to any simulated rigid body prim.
- Apply `PhysicsCollisionAPI` to collision-enabled prims.
- Use a valid `physics:approximation` type for mesh colliders (e.g. convex hull or SDF).
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

### Articulation root (required)

Apply `PhysicsArticulationRootAPI` to the root prim of the articulation:

```usd
def Xform "Robot" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
}
```

## Robot core (runnable) requirements

Robot core runnable (FET021_ROBOT_CORE_RUNNABLE) enforces folder layout, naming,
and composition suitable for runnable robot assets. Refer to the capability
docs for robot core requirements (e.g. clean folder, no overrides, thumbnail).

## Stage composition requirements

This profile does not require Isaac Sim–specific composition. A single-layer USD
is acceptable. If you choose to split layers, keep all references and payloads
relative and consistent.

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
            string profile = "Robot-Body-Runnable"
            string profile_version = "1.0.0"
        }
    }
}
```

## References

- `nv_core/sr_specs/docs/profiles/profiles.toml`
- `nv_core/sr_specs/docs/features/FET_003-rigid_body_physics.md`
- `nv_core/sr_specs/docs/features/FET_004-simulate_multi_body_physics.md`
- `nv_core/sr_specs/docs/features/FET_021-robot_core.md`
- `nv_core/sr_specs/docs/features/FET_022-driven_joints.md`
- `nv_core/sr_specs/docs/features/FET_024-base_articulation.md`
- `nv_core/sr_specs/docs/capabilities/physics_bodies/physics_driven_joints/`
- `nv_core/sr_specs/docs/capabilities/physics_bodies/base_articulation/`
- `nv_core/sr_specs/docs/capabilities/core/naming_paths/`
