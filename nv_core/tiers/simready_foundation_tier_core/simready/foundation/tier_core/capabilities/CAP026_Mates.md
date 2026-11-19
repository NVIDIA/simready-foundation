# Capability: `CAP026_Mates`


| **Property**      | **Value**          |
| ----------------- | ------------------ |
| Capability Name      | `CAP026_Mates` |
| Runtime | `OpenUSD` |
| Proprietary Techs | `None`             |
| Version token | `0-1-0`            |


## Description

A standalone asset declares mechanical mate sites so it can mount or be mounted: sockets on an arm flange, plugs on a gripper, tool, or sensor. Sites carry catalog `interface` identity and socket payload rating. They do not hold joints or refer to a partner asset.

This static mate capability occupies family `026`.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_003_STANDARD_0_2_0["FET003_RigidBody.0-2-0"]
    CAP026_Mates_OpenUSD_0_1_0["CAP026_Mates.0-1-0"]
    CAP027_Connections_OpenUSD_0_1_0["CAP027_Connections.0-1-0"]
    CAP026_Mates_OpenUSD_0_1_0 --> FET_003_STANDARD_0_2_0
    CAP027_Connections_OpenUSD_0_1_0 --> CAP026_Mates_OpenUSD_0_1_0

    classDef current fill:#90EE90,stroke:#333
    class CAP026_Mates_OpenUSD_0_1_0 current
```



## Use Cases

Products or workflows that consume this capability:

- SimReady validation of a robot arm or end-effector that exposes a mechanical mount.
- SimReady validation of a stackable or interlocking prop that exposes a mating face.
- Catalog tooling that reads `interface` and `maxPayload` before an assembly exists.



## Requirements



### Version 0-1-0

**Details**

#### Used in Profiles

- Assembly v0.1.0 (required)
- Robot-Assembly v0.1.0 (required)



#### Capability Dependencies


| **Property** | **Value**                                                            |
| ------------ | -------------------------------------------------------------------- |
| Dependency   | [Rigid Body Physics](../features/FET003_RigidBody.md) (`FET003_RigidBody.0-2-0`) |




#### Requirement List

- Capability: [Assembly/Mates](../rules_and_reqs/assembly/mates/capability-mates.md)


| Requirement | Requirement Doc                                                                   | Rule                                                                     |
| ----------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `MC.001`    | [MC.001](../rules_and_reqs/assembly/mates/requirements/mate-site-xform.md)          | Implemented (`validation.py`) |
| `MC.002`    | [MC.002](../rules_and_reqs/assembly/mates/requirements/mechanical-role.md)          | Implemented (`validation.py`) |
| `MC.003`    | [MC.003](../rules_and_reqs/assembly/mates/requirements/mate-body-rigid-ancestor.md) | Implemented (`validation.py`) |
| `MC.004`    | [MC.004](../rules_and_reqs/assembly/mates/requirements/mechanical-interface.md)     | Implemented (`validation.py`) |
| `MC.005`    | [MC.005](../rules_and_reqs/assembly/mates/requirements/mate-insertion-vector.md)    | Implemented (`validation.py`) |
| `MC.006`    | [MC.006](../rules_and_reqs/assembly/mates/requirements/socket-max-payload.md)       | Implemented (`validation.py`) |
| `MC.007`    | [MC.007](../rules_and_reqs/assembly/mates/requirements/mechanical-kind.md)          | Implemented (`validation.py`) |




## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`

Validation or runtime pipeline:

- Static mate checkers are registered in `rules_and_reqs/assembly/mates/validation.py`.
- Runtime proof that an interface claim is true, or that insertion is collision-free, is out of static reach.



## Samples

- `UR10` [socket on](../../../../../../../sample_content/common_assets/robots_general/ur10/simready_usd/payloads/base.usda) `wrist_3_link/tool_mount_01`
- `Robotiq 2F-85` [plug on](../../../../../../../sample_content/common_assets/robots_general/Robotiq/2F-85/simready_usd/2F-85.usda) `base_link/tool_plug_01`



## Evaluates

- None.



## Profile conversion helpers

None.