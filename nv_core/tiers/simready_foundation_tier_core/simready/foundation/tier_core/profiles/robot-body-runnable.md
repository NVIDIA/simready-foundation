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
    {"FET_001_STANDARD" = {version = "0.1.0"}}, # Minimal
    {"FET_003_STANDARD" = {version = "0.1.0"}}, # RBD Physics (Standard)
    {"FET_004_ROBOT_PHYSX" = {version = "0.1.0"}}, # Multi-body physics (Robot PhysX)
    {"FET_021_ISAAC" = {version = "0.3.0"}}, # Robot Core
    {"FET_022_PHYSX" = {version = "0.1.0"}}, # Driven Joints (PhysX)
    {"FET_024_PHYSX" = {version = "0.1.0"}}, # Articulation
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

Robot core (`FET_021_ISAAC`) enforces robot naming, robot schema metadata,
robot type, and root-joint pinning suitable for runnable robot assets. Refer to
the capability docs for robot core requirements.

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

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot_body_runnable.toml`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_ROBOT_PHYSX.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_021_ISAAC.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_022_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_024_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_driven_joints/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/base_articulation/`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/naming_paths/`
