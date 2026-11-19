# Capability: `CAP029_ConnectionJoint.MuJoCo`

| **Property** | **Value** |
|--------------|-----------|
| Capability Name | `CAP029_ConnectionJoint.MuJoCo` |
| Runtime | `MuJoCo` |
| Proprietary Techs | `MuJoCo` |
| Version token | `0-1-0` |

## Description

Defines the MuJoCo contract for a `jointed` connection joint. It depends on the Standard connections multibody-physics capability for the joint itself, then constrains what may be authored alongside it.

MuJoCo has no fixed joint. The official mjcPhysics schema defines scene, collider, mesh-collider, site, joint, actuator, equality, and tendon schemas but no fixed-joint type, because a rigid attachment is expressed by fusing the two bodies or by an equality constraint that the importer derives. A MuJoCo-ready connection therefore authors the same standard `UsdPhysicsFixedJoint` as every other runtime, and this capability specifies what must not be layered onto it: no invented `MjcWeldAPI` or `MjcFixedJointAPI`, no `MjcJointAPI` (which marks an articulation degree of freedom that a fixed joint does not have), and no `MjcActuator` targeting the connection joint.

Contact between the two mate bodies is filtered with `physics:collisionEnabled = false`. The coupling faces are coincident, and contact authored between two bodies the solver treats as one is both wasteful and a source of instability.

Where an attachment is permanent, `realization = "compound"` under [CAP027_Connections](CAP027_Connections.md) expresses the fused body directly and is the better fit for MuJoCo than a jointed connection.

## Dependency Graph

```{mermaid}
flowchart LR
    CAP029_ConnectionJoint_OpenUSD_0_1_0["CAP029_ConnectionJoint.0-1-0"]
    CAP029_ConnectionJoint_MuJoCo_0_1_0["CAP029_ConnectionJoint.MuJoCo.0-1-0"]
    CAP029_ConnectionJoint_MuJoCo_0_1_0 --> CAP029_ConnectionJoint_OpenUSD_0_1_0

    classDef current fill:#90EE90,stroke:#333
    class CAP029_ConnectionJoint_MuJoCo_0_1_0 current
```

## Use Cases

Products or workflows that consume this capability:

- SimReady validation of a MuJoCo-ready robot assembly with a gripper or tool attached.
- MuJoCo import of an assembly where the connection joint must fuse rather than actuate.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- Assembly v0.1.0 (optional)

#### Capability Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Connections Multibody-Physics](CAP029_ConnectionJoint.md) (`CAP029_ConnectionJoint.0-1-0`) |

#### Requirement List

* Capability: [Assembly/Connections](../rules_and_reqs/assembly/connections/capability-connections.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `CN.MUJOCO.001` | [CN.MUJOCO.001](../rules_and_reqs/assembly/connections/requirements/mujoco-connection-joint.md) | Implemented (`validation.py`) |

</details>

## Pipelines

Source file type:

- `.mjcf`, `.xml`, `.usd`, `.usda`, `.usdc`

Validation or runtime pipeline:

- Static checkers are registered in `rules_and_reqs/assembly/connections/validation.py`.
- MuJoCo data overlays the neutral connection joint, typically from a `runnables/physics/mujoco` layer.

## Samples

- None.

## Evaluates

- None.

## Profile conversion helpers

These callable helpers apply static capability changes to a staged output. They are not registered runtime feature adapters.

- `connection_joint_neutral_to_mujoco` (`CAP029_ConnectionJoint.0-1-0` to `CAP029_ConnectionJoint.MuJoCo.0-1-0`), in `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_mujoco`. Resolves each `jointed` connection's `simready:mate:joint`, strips `MjcJointAPI` and any invented weld or fixed-joint API, drops the connection joint from `MjcActuator` target lists (deactivating an actuator only when the connection joint was its sole target), and authors `physics:collisionEnabled = false`. Converting a permanent `jointed` connection to `compound` changes the rigid-body topology and is left to the conform skill.
