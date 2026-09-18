# Prop-Robotics-Isaac Profile

This document describes how to author a USD asset that conforms to the
`Prop-Robotics-Isaac` profile. It consolidates the required feature set, USD
properties, naming conventions, and Isaac Sim composition requirements.

## Profile definition

The `Prop-Robotics-Isaac` profile includes the following feature set (see `prop_robotics_isaac.toml` and the [feature dependency graph](../features/feature-dependency-graph)). Each feature's requirements and dependencies are defined in the feature specifications.

```toml
[Prop-Robotics-Isaac]
"1.0.0" = {features = [
    {"FET_001_STANDARD" = {version = "0.1.0"}}, # Minimal
    {"FET_003_PHYSX" = {version = "0.1.0"}}, # RBD Physics (PhysX)
    {"FET_004_PHYSX" = {version = "0.1.0"}, optional=true}, # Multi-Body Physics (PhysX)
    {"FET_005_STANDARD" = {version = "0.1.0"}}, # Grasp Physics
    {"FET_100_ISAAC" = {version = "0.1.0"}}, # Isaac composition
]}
"1.0.1" = {features = [
    {"FET_001_STANDARD" = {version = "1.0.1"}}, # Minimal
    {"FET_003_PHYSX" = {version = "0.1.0"}}, # RBD Physics (PhysX)
    {"FET_004_PHYSX" = {version = "0.1.0"}}, # Multi-Body Physics (PhysX)
    {"FET_005_STANDARD" = {version = "0.1.0"}}, # Grasp Physics
    {"FET_100_ISAAC" = {version = "0.1.0"}}, # Isaac composition
]}
"1.1.0" = {features = [
    {"FET_001_STANDARD" = {version = "1.0.1"}}, # Minimal
    {"FET_003_PHYSX" = {version = "0.3.0"}}, # RBD Physics (PhysX)
    {"FET_004_PHYSX" = {version = "0.3.0"}}, # Multi-Body Physics (PhysX)
    {"FET_005_STANDARD" = {version = "0.1.0"}}, # Grasp Physics
    {"FET_100_ISAAC" = {version = "0.2.0"}}, # Isaac composition
]}
"1.2.0" = {features = [
    {"FET_001_STANDARD" = {version = "1.0.1"}}, # Minimal
    {"FET_003_PHYSX" = {version = "0.4.0"}}, # RBD Physics (PhysX)
    {"FET_004_PHYSX" = {version = "0.4.0"}}, # Multi-Body Physics (PhysX)
    {"FET_005_STANDARD" = {version = "0.1.0"}}, # Grasp Physics
    {"FET_100_ISAAC" = {version = "0.4.0"}}, # Isaac composition
]}
```

### Version 1.2.0

Version 1.2.0 aligns the PhysX rigid-body and multibody gates with the latest
`FET_003_PHYSX@0.4.0` and `FET_004_PHYSX@0.4.0` contracts and adopts
`FET_100_ISAAC@0.4.0` for Isaac composition. The validation requirement set for
Isaac composition (`ISA.001`) is unchanged from 1.1.0; the difference is the
composition pipeline. Assets are now produced by the standalone, Kit-free
`simready.asset_transformer` package
(`nv_core/cip_specs/isaac_asset_transformer`) using the
`simready_physx_to_isaac_prop` transform.

Migration from 1.1.0 re-runs the Isaac composition adapter path
(`FET_001_STANDARD@1.0.1` -> `FET_100_ISAAC@0.4.0`) in
`nv_core/cip_specs/asset_handler_modules/physx_to_isaacsim`, then re-runs the
PhysX rigid-body and multibody conform gates for the `0.4.0` feature contracts.
Earlier profile versions remain valid for assets already pinned to them.

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

- Author grasp data according to `FET_005_STANDARD` requirements.

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
            string profile_version = "1.2.0"
        }
    }
}
```

## References

- [Feature dependency graph](../features/feature-dependency-graph) — requirements and dependencies for all features
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/prop_robotics_isaac.toml`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_001_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_PHYSX.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_PHYSX.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_005_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_100_ISAAC.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/isaac_sim/composition/requirements/composition.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/naming_paths/requirements/prim-naming-convention.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/naming_paths/requirements/file-naming-convention.md`
