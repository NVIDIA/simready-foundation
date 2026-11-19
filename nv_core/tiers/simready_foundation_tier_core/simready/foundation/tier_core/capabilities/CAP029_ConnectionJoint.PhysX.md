# Capability: `CAP029_ConnectionJoint.PhysX`

| **Property** | **Value** |
|--------------|-----------|
| Capability Name | `CAP029_ConnectionJoint.PhysX` |
| Runtime | `PhysX` |
| Proprietary Techs | `PhysX` |
| Version token | `0-1-0` |

## Description

Defines the PhysX contract for a `jointed` connection joint. It depends on the Standard connections multibody-physics capability for the joint itself, then constrains what PhysX data may be layered onto it.

PhysX consumes standard USD physics joints and maps `UsdPhysicsFixedJoint` directly, so this capability is a set of constraints rather than a replacement schema, matching the shape of [CAP029_ConnectionJoint.Newton](CAP029_ConnectionJoint.Newton.md) and [CAP029_ConnectionJoint.MuJoCo](CAP029_ConnectionJoint.MuJoCo.md).

Three concerns are covered. `PhysxJointAPI` degree-of-freedom tuning is forbidden: `physxJoint:armature`, `physxJoint:jointFriction`, and `physxJoint:maxJointVelocity` all describe the behavior of a degree of freedom, and a fixed connection joint has none. The rule covers the whole `physxJoint:` namespace, including names no PhysX schema defines. Contact between the two mate bodies is filtered with `physics:collisionEnabled = false`, because the mate convention places the coupling faces coincident and contact on that overlapping pair works against the joint holding the pose. Articulation fusion is resolved: when both mate bodies sit under articulation roots, the connection joint fuses the two articulations into one, so the joint is part of that articulation with `physics:excludeFromArticulation` false or unset, and the assembly gives up the plug asset's articulation root so exactly one root survives.

Attach strength belongs to `CN.009`. `physics:breakForce` and `physics:breakTorque` are `UsdPhysicsJoint` attributes that PhysX reads directly, so one requirement covers every runtime.

PhysX attributes are overlaid onto the neutral `UsdPhysicsFixedJoint` required by `CN.009` rather than authored on a separate prim, so `rel simready:mate:joint` resolves to the same joint regardless of which runtime variant is loaded.

## Dependency Graph

```{mermaid}
flowchart LR
    CAP029_ConnectionJoint_OpenUSD_0_1_0["CAP029_ConnectionJoint.0-1-0"]
    CAP029_ConnectionJoint_PhysX_0_1_0["CAP029_ConnectionJoint.PhysX.0-1-0"]
    CAP029_ConnectionJoint_PhysX_0_1_0 --> CAP029_ConnectionJoint_OpenUSD_0_1_0

    classDef current fill:#90EE90,stroke:#333
    class CAP029_ConnectionJoint_PhysX_0_1_0 current
```

## Use Cases

Products or workflows that consume this capability:

- SimReady validation of a PhysX-ready robot assembly with a gripper or tool attached.
- A PhysX tool-change runtime that releases a tool by breaking or disabling the connection joint.
- PhysX simulation of an arm plus gripper where each asset ships its own articulation root.

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
| `CN.PHYSX.001` | [CN.PHYSX.001](../rules_and_reqs/assembly/connections/requirements/physx-connection-joint.md) | Implemented (`validation.py`) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`

Validation or runtime pipeline:

- `PhysxConnectionJointChecker` (`CN.PHYSX.001`) in `rules_and_reqs/assembly/connections/validation.py`.
- PhysX joint attributes overlay the neutral connection joint, typically from a `runnables/physics/physx` layer.

## Samples

- None.

## Evaluates

- None.

## Profile conversion helpers

These callable helpers apply static capability changes to a staged output. They are not registered runtime feature adapters.

- `connection_joint_neutral_to_physx` (`CAP029_ConnectionJoint.0-1-0` to `CAP029_ConnectionJoint.PhysX.0-1-0`), in `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_physx`. Resolves each `jointed` connection's `simready:mate:joint`, authors `physics:collisionEnabled = false`, removes `PhysxJointAPI` and any `physxJoint:` attribute from the connection joint, and clears `physics:excludeFromArticulation` where it is true. It does not author break thresholds, which `CN.009` requires on the input stage, and it does not restructure articulation roots, which is a composition edit on the assembly. It overlays the neutral joint and never creates one.
