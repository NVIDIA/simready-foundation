# Robot-Gripper-Neutral Profile

This document describes how to author a USD asset that conforms to the
`Robot-Gripper-Neutral` profile. It consolidates the required feature set, USD
properties, naming conventions, and composition expectations.

## Profile definition

The `Robot-Gripper-Neutral` profile includes the following feature set (see `profiles.toml`).
Each feature's requirements and dependencies are defined in the feature specifications.

```toml
[Robot-Gripper-Neutral]
"0.1.0" = {features = [
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}}, # Minimal
    {"FET003_BASE_NEUTRAL" = {version = "0.1.0"}}, # RBD Physics
    {"FET004_BASE_NEUTRAL" = {version = "0.1.0"}}, # Multi-Body Physics
    {"FET022_DRIVEN_JOINTS_NEUTRAL" = {version = "0.1.0"}}, # Driven Joints
    {"FET024_BASE_ARTICULATION_NEUTRAL" = {version = "0.1.0"}}, # Articulation
    {"FET028_GRIPPER_NEUTRAL" = {version = "0.1.0"}}, # Gripper
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

### Gripper site (required)

Every gripper interaction point must be an `Xform` prim with the following attributes:

- `token simready:attactment:socketType = "Gripper"` — discovery attribute; marks the prim as a gripper site.
- `float custom:maxOpening` — maximum jaw separation in meters, must be strictly positive.
- A `BasisCurves` child named `forward_axis` with at least 2 points encoding the approach direction (`p1 - p0`).
- A `BasisCurves` child named `grip_line` with at least 2 points encoding the graspable-tube axis. The segment length (`|p1 - p0|`) equals the physical width of the grip pads.

```usd
def Xform "gripper_01"
{
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

The gripper site prim may have any name. Multiple gripper sites on a single end-effector are supported; each must carry the `simready:attactment:socketType` attribute.

## Stage composition requirements

This profile does not require Isaac Sim composition. A single-layer USD is
acceptable. If layers are split, keep all references and payloads relative and
consistent.

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
            string profile = "Robot-Gripper-Neutral"
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
