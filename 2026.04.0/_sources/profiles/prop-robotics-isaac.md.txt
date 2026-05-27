# Prop-Robotics-Isaac Profile

This document describes how to author a USD asset that conforms to the
`Prop-Robotics-Isaac` profile. It consolidates the required feature set, USD
properties, naming conventions, and Isaac Sim composition requirements.

## Profile definition

The `Prop-Robotics-Isaac` profile includes the following feature set (see `profiles.toml` and the [feature dependency graph](../features/feature-dependency-graph)). Each feature's requirements and dependencies are defined in the feature specifications.

```toml
[Prop-Robotics-Isaac]
"1.0.0" = {features = [
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}}, # Minimal
    {"FET003_BASE_PHYSX" = {version = "0.1.0"}}, # RBD Physics (PhysX)
    {"FET004_BASE_PHYSX" = {version = "0.1.0"}}, # Multi-Body Physics (PhysX)
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}}, # Grasp Physics
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

### Grasp physics (required)

- Author grasp data according to `FET005_BASE_NEUTRAL` requirements.

## Isaac Sim composition requirements

Assets must follow the Isaac Sim composition pattern with a main USD that
references and payloads separate mesh and physics layers.

### Required structure

```text
asset_name.usd                 # Main composition file
payloads/
  asset_name_meshes.usd        # Geometry and materials
  asset_name_base.usd          # Base reference layer
  asset_name_physics.usd       # Physics data
configuration/
  asset_name_physics.usd       # Configuration layer combining base+physics
```

### Composition rules

- The main USD must have a default prim with `kind = "component"`.
- Use relative paths for all references and payloads.
- Materials are organized under a `Looks` scope in the meshes payload.
- Raw meshes live under a `Meshes` scope (invisible).
- Visual hierarchy lives under a `Visuals` scope (invisible).
- Physics schemas and attributes are applied in the physics payload only.

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
            string profile = "Prop-Robotics-Isaac"
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
- `nv_core/sr_specs/docs/features/FET_100-isaacsim-0.1.0-composition.md`
- `nv_core/sr_specs/docs/capabilities/isaac_sim/composition/requirements/composition.md`
- `nv_core/sr_specs/docs/capabilities/core/naming_paths/requirements/prim-naming-convention.md`
- `nv_core/sr_specs/docs/capabilities/core/naming_paths/requirements/file-naming-convention.md`
