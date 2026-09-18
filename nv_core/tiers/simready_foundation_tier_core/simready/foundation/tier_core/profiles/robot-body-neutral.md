# Robot-Body-Neutral Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Robot-Body-Neutral` profile. It consolidates the required feature set, USD
properties, naming conventions, and composition expectations.

## Profile definition

The `Robot-Body-Neutral` profile includes the following feature set (see `robot_body_neutral.toml` and the [feature dependency graph](../features/feature-dependency-graph)). Each feature's requirements and dependencies are defined in the feature specifications.

```toml
[Robot-Body-Neutral]
"1.0.0" = {features = [
    {"FET_001_STANDARD" = {version = "0.1.0"}}, # Minimal
    {"FET_003_STANDARD" = {version = "0.1.0"}}, # RBD Physics
    {"FET_004_STANDARD" = {version = "0.1.0"}}, # Multi-Body Physics
    {"FET_022_STANDARD" = {version = "0.1.0"}}, # Driven Joints
    {"FET_024_STANDARD" = {version = "0.1.0"}}, # Articulation
]}
```

## Required USD properties and schemas

### Stage metadata (required)

- `defaultPrim` must be set on every layer.
- `upAxis = "Z"` and `metersPerUnit = 1` must be set on every stage.

### Rigid bodies and colliders (required)

- Apply `PhysicsRigidBodyAPI` to any simulated rigid body prim.
- Apply `PhysicsCollisionAPI` to collision-enabled prims.
- Rigid body prims must be `UsdGeomXformable`.

### Multi-body joints (required)

- Use `UsdPhysicsJoint` prims (or subtypes) to connect rigid bodies.
- Author `rel physics:body0` and `rel physics:body1` relationships.

### Driven joints (required)

- Apply `PhysicsDriveAPI:*` and `PhysicsJointStateAPI:*` to driven joints.
- Author `drive:*:physics:maxForce` with a positive, finite value.
- Ensure joint state and drive targets are consistent with authored transforms.

### Articulation root (required)

Apply `PhysicsArticulationRootAPI` to the root prim of the articulation:

```usd
def Xform "Robot" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
}
```

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
            string profile = "Robot-Body-Neutral"
            string profile_version = "1.0.0"
        }
    }
}
```

## References

- [Feature dependency graph](../features/feature-dependency-graph) — requirements and dependencies for all features
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot_body_neutral.toml`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_022_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_024_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_joints/requirements/joint-capability.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_driven_joints/requirements/physics-drive-and-joint-state.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_driven_joints/requirements/joint-has-joint-state-api.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_driven_joints/requirements/joint-has-correct-transform-and-state.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/base_articulation/requirements/has-articulation-root.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/naming_paths/requirements/prim-naming-convention.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/naming_paths/requirements/file-naming-convention.md`
