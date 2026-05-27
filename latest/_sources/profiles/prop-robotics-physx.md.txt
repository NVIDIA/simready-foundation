# Prop-Robotics-Physx Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Prop-Robotics-Physx` profile. It consolidates the required feature set, USD
properties, naming conventions, and composition expectations.

## Profile definition

The `Prop-Robotics-Physx` profile includes the following feature sets (see `profiles.toml` and the [feature dependency graph](../features/feature-dependency-graph)). Each feature's requirements and dependencies are defined in the feature specifications.

```toml
[Prop-Robotics-Physx]
"1.0.0" = {features = [
    {"FET000_CORE" = {version = "0.1.0"}}, # Core
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}}, # Minimal
    {"FET003_BASE_PHYSX" = {version = "0.1.0"}}, # RBD Physics (PhysX)
    {"FET004_BASE_PHYSX" = {version = "0.1.0"}}, # Multi-Body Physics (PhysX)
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}}, # Grasp Physics
    {"FET006_BASE_MDL" = {version = "0.1.0"}}, # Materials (MDL)
]}
"2.0.0" = {features = [
    {"FET000_CORE" = {version = "0.1.0"}}, # Core
    {"FET001_BASE_NEUTRAL" = {version = "1.0.0"}}, # Minimal
    {"FET003_BASE_PHYSX" = {version = "0.1.0"}}, # RBD Physics (PhysX)
    {"FET004_BASE_PHYSX" = {version = "0.1.0"}}, # Multi-Body Physics (PhysX)
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}}, # Grasp Physics
    {"FET006_BASE_MDL" = {version = "0.1.0"}}, # Materials (MDL)
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

### Multi-body physics (conditional)

Single-rigid-body props are valid for this profile when they satisfy
`FET003_BASE_NEUTRAL`. `FET004_BASE_NEUTRAL` applies only to props intentionally
authored as multi-body assemblies, with two or more rigid bodies connected by
joints or articulation relationships. For props with exactly one rigid body,
multi-body physics is not applicable and must not block profile conformance.

- Use `UsdPhysicsJoint` prims (or subtypes) to connect rigid bodies.
- Author `rel physics:body0` and `rel physics:body1` relationships.

### Grasp physics (required)

- Author grasp data according to `FET005_BASE_NEUTRAL` requirements.

### Materials (required)

- Author MDL materials per `FET006_BASE_MDL` requirements.
- Ensure all material and MDL asset paths are relative and exist.
- Bind materials to all non-guide meshes.

## Stage composition requirements

This profile does not require Isaac Sim composition. A single-layer USD is
acceptable. If you choose to split layers, keep all references and payloads
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
            string profile = "Prop-Robotics-Physx"
            string profile_version = "1.0.0"
        }
    }
}
```

## References

- [Feature dependency graph](../features/feature-dependency-graph) — requirements and dependencies for all features
- `nv_core/sr_specs/docs/profiles/profiles.toml`
- `nv_core/sr_specs/docs/features/FET_001-minimal.md`
- `nv_core/sr_specs/docs/features/FET_003-rigid_body_physics.md`
- `nv_core/sr_specs/docs/features/FET_004-simulate_multi_body_physics.md`
- `nv_core/sr_specs/docs/features/FET_005-simulate_grasp_physics.md`
- `nv_core/sr_specs/docs/features/FET_006-materials.md`
- `nv_core/sr_specs/docs/capabilities/core/naming_paths/requirements/prim-naming-convention.md`
- `nv_core/sr_specs/docs/capabilities/core/naming_paths/requirements/file-naming-convention.md`
