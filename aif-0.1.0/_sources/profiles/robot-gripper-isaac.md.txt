# Robot-Gripper-Isaac Profile

This document describes how to author a USD asset that conforms to the
`Robot-Gripper-Isaac` profile. It consolidates the required feature set, USD
properties, naming conventions, and robot-specific composition requirements
for Isaac Sim.

## Profile definition

The `Robot-Gripper-Isaac` profile includes the following feature set (see `profiles.toml`).
Each feature's requirements and dependencies are defined in the feature specifications.

```toml
[Robot-Gripper-Isaac]
"0.1.0" = {features = [
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}}, # Minimal
    {"FET004_ROBOT_PHYSX" = {version = "0.2.0"}}, # Multi-Body Physics (Robot PhysX)
    {"FET021_ROBOT_CORE_ISAAC" = {version = "0.2.0"}}, # Robot Core (Isaac)
    {"FET022_DRIVEN_JOINTS_ISAAC" = {version = "0.1.0"}}, # Driven Joints (Isaac)
    {"FET024_BASE_ARTICULATION_PHYSX" = {version = "0.1.0"}}, # Articulation
    {"FET028_GRIPPER_ISAAC" = {version = "0.1.0"}}, # Gripper (Isaac)
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

- `apiSchemas` includes `IsaacRobotAPI`.
- `isaac:namespace` must be authored.
- `isaac:physics:robotJoints` relationship must be populated.
- `isaac:physics:robotLinks` relationship must be populated.

### Articulation root (required)

Apply `PhysicsArticulationRootAPI` to the root prim of the articulation:

```usd
def Xform "Robot" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
}
```

### Gripper site (required)

Every gripper interaction point must satisfy all Neutral Format requirements (GR.001–GR.004) and additionally carry `IsaacSiteAPI` with a non-empty `isaac:Description`.

- `token simready:attactment:socketType = "Gripper"` — discovery attribute (GR.001).
- `float custom:maxOpening` — maximum jaw separation in meters, must be strictly positive (GR.004).
- `BasisCurves` child `forward_axis` with at least 2 points (GR.002).
- `BasisCurves` child `grip_line` with at least 2 points (GR.003).
- `IsaacSiteAPI` applied via `prepend apiSchemas` (GR.ISA.001).
- `string isaac:Description` — non-empty string describing the site role (GR.ISA.001).

```usd
def Xform "gripper_01" (
    prepend apiSchemas = ["IsaacSiteAPI"]
)
{
    string isaac:Description = "Grasp approach point"
    double3 xformOp:translate = (0, 0.15, 0)
    uniform token[] xformOpOrder = ["xformOp:translate"]
    token simready:attactment:socketType = "Gripper"
    float custom:maxOpening = 0.085

    def BasisCurves "forward_axis"
    {
        point3f[] points = [(0, -1, 0), (0, 1, 0)]
        int[] curveVertexCounts = [2]
        uniform token type = "linear"
    }

    def BasisCurves "grip_line"
    {
        point3f[] points = [(-0.04, 0, 0), (0.04, 0, 0)]
        int[] curveVertexCounts = [2]
        uniform token type = "linear"
    }
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

### Prim naming

- Choose either `camelCase` or `snake_case` and use it consistently.
- Avoid spaces, special characters, and reserved keywords.
- Use descriptive, purpose-driven names.

### File naming

- Use lowercase file names.
- Use `.usd`, `.usda`, `.usdc`, or `.usdz` as appropriate.
- Use underscores or hyphens; avoid spaces and special characters.
- Avoid reserved names (e.g., `CON`, `PRN`, `AUX`, `NUL`).

## Validation metadata (recommended)

Include profile metadata in `customLayerData` to simplify validation workflows:

```usd
customLayerData = {
    dictionary SimReady_Metadata = {
        dictionary validation = {
            string profile = "Robot-Gripper-Isaac"
            string profile_version = "0.1.0"
        }
    }
}
```

## References

- `docs/profiles/profiles.toml`
- `docs/features/FET_028-gripper.md`
- `docs/capabilities/physics_bodies/physics_grippers/requirements/gripper-socket-type.md`
- `docs/capabilities/physics_bodies/physics_grippers/requirements/gripper-forward-axis.md`
- `docs/capabilities/physics_bodies/physics_grippers/requirements/gripper-grip-line.md`
- `docs/capabilities/physics_bodies/physics_grippers/requirements/gripper-max-opening.md`
- `docs/capabilities/physics_bodies/physics_grippers/requirements/gripper-site-api.md`
