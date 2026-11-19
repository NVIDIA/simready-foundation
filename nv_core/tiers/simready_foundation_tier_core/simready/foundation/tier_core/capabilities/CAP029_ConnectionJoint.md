# Capability: `CAP029_ConnectionJoint`

| **Property** | **Value** |
|--------------|-----------|
| Capability Name | `CAP029_ConnectionJoint` |
| Runtime | `OpenUSD` |
| Proprietary Techs | `None` |
| Version token | `0-1-0` |

## Description

Defines the multibody-physics contract for a `jointed` connection. Where [CAP027_Connections](CAP027_Connections.md) declares that a socket and plug are paired and that the pairing resolves to two distinct rigid bodies, this capability requires the `UsdPhysicsFixedJoint` that holds them, states how strong the attachment is, and rates it against the socket's payload capacity.

Attach strength is declared with `physics:breakForce` and `physics:breakTorque`. Both are `UsdPhysicsJoint` attributes, so every `UsdPhysics` runtime reads the same two values and this capability covers PhysX, Newton, and MuJoCo alike. Authoring is required because the schema fallback is `inf`: an unauthored joint is silently unbreakable, which cannot be told apart from a deliberate choice to make it so. This is distinct from the `CN.005` payload rating, which bounds static mass rather than transmitted load.

The joint is authored data, not a value a runtime infers from the mate sites. The connection prim points at it with `rel simready:mate:joint`, so a consumer resolves the joint by lookup rather than by searching the stage for a matching body pair. Authoring it means the assembly holds its pose in any `UsdPhysics` runtime, including one that never reads the `simready:mate:` namespace, and it satisfies `RB.012` for nested rigid bodies so an assembly can be nested inside another assembly.

Authoring the joint does not remove it from runtime control. A tool-change runtime follows `simready:mate:joint` and sets `physics:jointEnabled = false`, retunes the joint, or deletes the prim; the connection data stays complete after the joint is gone, so the pairing can be re-engaged.

This capability applies only to connections whose `realization` is `jointed`. An assembly built entirely from `compound` connections does not need it, which is why the `Assembly` profile pins it as optional.

## Dependency Graph

```{mermaid}
flowchart LR
    CAP027_Connections_OpenUSD_0_1_0["CAP027_Connections.0-1-0"]
    FET_004_STANDARD_0_2_0["FET004_Multibody.0-2-0"]
    CAP029_ConnectionJoint_OpenUSD_0_1_0["CAP029_ConnectionJoint.0-1-0"]
    CAP029_ConnectionJoint_PhysX_0_1_0["CAP029_ConnectionJoint.PhysX.0-1-0"]
    CAP029_ConnectionJoint_Newton_0_1_0["CAP029_ConnectionJoint.Newton.0-1-0"]
    CAP029_ConnectionJoint_MuJoCo_0_1_0["CAP029_ConnectionJoint.MuJoCo.0-1-0"]
    CAP029_ConnectionJoint_OpenUSD_0_1_0 --> CAP027_Connections_OpenUSD_0_1_0
    CAP029_ConnectionJoint_OpenUSD_0_1_0 --> FET_004_STANDARD_0_2_0
    CAP029_ConnectionJoint_PhysX_0_1_0 --> CAP029_ConnectionJoint_OpenUSD_0_1_0
    CAP029_ConnectionJoint_Newton_0_1_0 --> CAP029_ConnectionJoint_OpenUSD_0_1_0
    CAP029_ConnectionJoint_MuJoCo_0_1_0 --> CAP029_ConnectionJoint_OpenUSD_0_1_0

    classDef current fill:#90EE90,stroke:#333
    class CAP029_ConnectionJoint_OpenUSD_0_1_0 current
```

## Use Cases

Products or workflows that consume this capability:

- SimReady validation of a robot body with a gripper or tool attached at a mechanical mate site.
- A tool-change runtime that disables, retunes, or destroys the connection joint to release a tool and restores it to re-attach.
- A runtime that loads an assembly without SimReady awareness and still gets a rigid attachment from the authored joint.
- Nesting a validated assembly inside a larger assembly, where `RB.012` requires a joint between the nested rigid bodies.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- Assembly v0.1.0 (optional)

#### Capability Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Connections](CAP027_Connections.md) (`CAP027_Connections.0-1-0`) |
| Dependency | [Simulate Multi-Body Physics](../features/FET004_Multibody.md) (`FET004_Multibody.0-2-0`) |

#### Requirement List

* Capability: [Assembly/Connections](../rules_and_reqs/assembly/connections/capability-connections.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `CN.005` | [CN.005](../rules_and_reqs/assembly/connections/requirements/payload-capacity.md) | Implemented (`validation.py`) |
| `CN.009` | [CN.009](../rules_and_reqs/assembly/connections/requirements/connection-joint.md) | Implemented (`validation.py`) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`

Validation or runtime pipeline:

- `ConnectionJointChecker` (`CN.009`) and `PayloadCapacityChecker` (`CN.005`) in `rules_and_reqs/assembly/connections/validation.py`.
- The connection joint must be authored where `simready:mate:joint` resolves with runtime payloads unloaded. Author one neutral `UsdPhysicsFixedJoint` in the assembly physics layer; runtime variants overlay attributes onto that prim rather than defining their own.
- Behavioral proof (the assembly holds under gravity and under rated load) is runtime-test territory and is not specified here.

## Samples

- [`UR10 + Robotiq 2F-85` assembly](../../../../../../../sample_content/common_assets/robots_general/ur10_robotiq_2f85/simready_usd/ur10_robotiq_2f85.usda)

## Evaluates

- None.

## Profile conversion helpers

None.
