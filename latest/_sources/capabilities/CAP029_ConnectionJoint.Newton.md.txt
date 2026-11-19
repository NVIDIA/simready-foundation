# Capability: `CAP029_ConnectionJoint.Newton`

| **Property** | **Value** |
|--------------|-----------|
| Capability Name | `CAP029_ConnectionJoint.Newton` |
| Runtime | `Newton` |
| Proprietary Techs | `Newton` |
| Version token | `0-1-0` |

## Description

Defines the Newton contract for a `jointed` connection joint. It depends on the Standard connections multibody-physics capability for the joint itself, then constrains what may be authored alongside it.

Newton's USD schema resolver maps `UsdPhysicsFixedJoint` directly and defines no separate Newton fixed-joint type, so the Newton delta is a set of prohibitions rather than a replacement schema. The connection joint stays a standard fixed joint and must not carry an invented `NewtonFixedJointAPI`. It must not apply `NewtonJointAPI`, whose attributes (`newton:armature`, `newton:damping`, `newton:friction`, `newton:velocityLimit`, `newton:limitStiffness`, `newton:limitDamping`) all describe the behavior of a degree of freedom that a fixed joint does not have.

Two positive requirements remain. Contact between the two mate bodies is filtered with `physics:collisionEnabled = false`, authored explicitly rather than left to importer defaults, in the same spirit as `NEWTON.BA.001` treating `newton:selfCollisionEnabled`. And when the connection fuses two articulations, exactly one `PhysicsArticulationRootAPI` may survive on the composed assembly, with `newton:selfCollisionEnabled` authored on the survivor.

## Dependency Graph

```{mermaid}
flowchart LR
    CAP029_ConnectionJoint_OpenUSD_0_1_0["CAP029_ConnectionJoint.0-1-0"]
    CAP029_ConnectionJoint_Newton_0_1_0["CAP029_ConnectionJoint.Newton.0-1-0"]
    CAP029_ConnectionJoint_Newton_0_1_0 --> CAP029_ConnectionJoint_OpenUSD_0_1_0

    classDef current fill:#90EE90,stroke:#333
    class CAP029_ConnectionJoint_Newton_0_1_0 current
```

## Use Cases

Products or workflows that consume this capability:

- SimReady validation of a Newton-ready robot assembly with a gripper or tool attached.
- Newton simulation of an assembly where the connection fuses the articulations of two child assets into one.

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
| `CN.NEWTON.001` | [CN.NEWTON.001](../rules_and_reqs/assembly/connections/requirements/newton-connection-joint.md) | Implemented (`validation.py`) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`

Validation or runtime pipeline:

- Static checkers are registered in `rules_and_reqs/assembly/connections/validation.py`.
- Newton data overlays the neutral connection joint, typically from a `runnables/physics/newton` layer.

## Samples

- None.

## Evaluates

- None.

## Profile conversion helpers

These callable helpers apply static capability changes to a staged output. They are not registered runtime feature adapters.

- `connection_joint_neutral_to_newton` (`CAP029_ConnectionJoint.0-1-0` to `CAP029_ConnectionJoint.Newton.0-1-0`), in `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_newton`. Resolves each `jointed` connection's `simready:mate:joint`, strips `NewtonJointAPI`, any invented `NewtonFixedJointAPI`, and the `newton:*` degree-of-freedom tuning attributes, authors `physics:collisionEnabled = false`, and authors `newton:selfCollisionEnabled` on any articulation root lacking it. Reducing a fused pair of articulations to a single root is left to the conform skill: choosing which root survives is an authoring intent decision.
