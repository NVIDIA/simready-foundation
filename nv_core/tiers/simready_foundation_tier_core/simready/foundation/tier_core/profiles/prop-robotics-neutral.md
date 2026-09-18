# Prop-Robotics-Neutral Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Prop-Robotics-Neutral` profile. It consolidates the required feature set, USD
properties, naming conventions, and composition expectations.

## Profile definition

The `Prop-Robotics-Neutral` profile includes the following feature sets (see `prop_robotics_neutral.toml` and the [feature dependency graph](../features/feature-dependency-graph)). Each feature's requirements and dependencies are defined in the feature specifications.

```toml
[Prop-Robotics-Neutral]
"1.0.0" = {features = [
    {"FET_000_STANDARD" = {version = "0.1.0"}}, # Core
    {"FET_001_STANDARD" = {version = "0.1.0"}}, # Minimal
    {"FET_003_STANDARD" = {version = "0.1.0"}}, # RBD Physics
    {"FET_004_STANDARD" = {version = "0.1.0"}}, # Multi-Body Physics
    {"FET_005_STANDARD" = {version = "0.1.0"}}, # Grasp Physics
    {"FET_006_MDL" = {version = "0.1.0"}}, # Materials (MDL)
]}
"2.0.0" = {features = [
    {"FET_000_STANDARD" = {version = "0.1.0"}}, # Core
    {"FET_001_STANDARD" = {version = "1.0.0"}}, # Minimal
    {"FET_003_STANDARD" = {version = "0.1.0"}}, # RBD Physics
    {"FET_004_STANDARD" = {version = "0.1.0"}}, # Multi-Body Physics
    {"FET_005_STANDARD" = {version = "0.1.0"}}, # Grasp Physics
    {"FET_006_MDL" = {version = "0.1.0"}}, # Materials (MDL)
]}
"2.2.0" = {features = [
    {"FET_000_STANDARD" = {version = "0.1.0"}}, # Core
    {"FET_001_STANDARD" = {version = "1.0.1"}}, # Minimal
    {"FET_003_STANDARD" = {version = "0.2.0"}}, # RBD Physics
    {"FET_004_STANDARD" = {version = "0.2.0"}}, # Multi-Body Physics
    {"FET_005_STANDARD" = {version = "0.1.0"}}, # Grasp Physics
    {"FET_006_MDL" = {version = "0.1.0"}}, # Materials (MDL)
    {"FET_000_PHYSX" = {version = "0.1.0"}, optional=true}, # Core PhysX runtime variant
    {"FET_000_NEWTON" = {version = "0.1.0"}, optional=true}, # Core Newton runtime variant
    {"FET_000_MUJOCO" = {version = "0.1.0"}, optional=true}, # Core MuJoCo runtime variant
]}
```

Version `2.2.0` (and later) additionally offers the optional Core runtime
physics variant features. See [Runtime physics variants (optional)](#runtime-physics-variants-optional).

## Required USD properties and schemas

### Stage metadata (required)

- `defaultPrim` must be set on every layer.
- `upAxis = "Z"` and `metersPerUnit = 1` must be set on every stage.

### Rigid bodies and colliders (required)

- Apply `PhysicsRigidBodyAPI` to any simulated rigid body prim.
- Apply `PhysicsCollisionAPI` to collision-enabled prims.
- Rigid body prims must be `UsdGeomXformable`.

### Multi-body physics (conditional)

Single-rigid-body props are valid for this profile when they satisfy
`FET_003_STANDARD`. `FET_004_STANDARD` applies only to props intentionally
authored as multi-body assemblies, with two or more rigid bodies connected by
joints or articulation relationships. For props with exactly one rigid body,
multi-body physics is not applicable and must not block profile conformance.

- Use `UsdPhysicsJoint` prims (or subtypes) to connect rigid bodies.
- Author `rel physics:body0` and `rel physics:body1` relationships.

### Grasp physics (required)

- Author grasp data according to `FET_005_STANDARD` requirements.

### Materials (required)

- Author MDL materials per `FET_006_MDL` requirements.
- Ensure all material and MDL asset paths are relative and exist.
- Bind materials to all non-guide meshes.

### Runtime physics variants (optional)

Starting with profile version `2.2.0`, this profile offers three optional
runtime physics variant features that scaffold runtime-specific physics onto
the neutral Core asset:

- `FET_000_PHYSX` — adds a `PhysX` variant set, a `runnables/physics/physx`
  payload, and matching `SimReady_Metadata.Variants.Physics.PhysX` metadata.
- `FET_000_NEWTON` — adds the equivalent `Newton` variant set, payload, and
  metadata.
- `FET_000_MUJOCO` — adds the equivalent `MuJoCo` variant set, payload, and
  metadata.

These features are optional and do not block conformance when absent. Each
variant set defaults to `Disabled`, so the neutral asset behavior is unchanged
until a consumer selects `Enabled`. Author them following the reference layout
in `sample_content/common_assets/props_general/obs_orange_a02` (variant set on
the default prim, payload under `runnables/physics/`). The runtime-specific
collider/schema content inside each payload is authored by the corresponding
`FET_003_<RUNTIME>` physics feature, not by the Core variant feature.

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
            string profile = "Prop-Robotics-Neutral"
            string profile_version = "1.0.0"
        }
    }
}
```

## References

- [Feature dependency graph](../features/feature-dependency-graph) — requirements and dependencies for all features
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/prop_robotics_neutral.toml`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_001_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_005_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_006_MDL.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/naming_paths/requirements/prim-naming-convention.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/naming_paths/requirements/file-naming-convention.md`
