# Capability: `CAP025_RosBridge.Ros`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP025_RosBridge.Ros` |
| Runtime                 | `Ros` |
| Proprietary Techs       | `Isaac Sim`, `ROS 2` |
| Versions                | `0-1-0` |

## Description

Defines a minimal Isaac Sim **ROS-Ready** contract: the stage authors at least
one OmniGraph ROS 2 bridge node (`isaacsim.ros2.bridge.*`). This proves ROS 2
bridge wiring exists on the stage. It does not validate topic names, QoS, TF,
or a live ROS 2 daemon.

## Dependency Graph

This capability has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this capability:

- SimReady validation verifies selected `CAP025_RosBridge.Ros` manifests.
- Inventory / triage of Isaac stages that claim ROS 2 bridge wiring.
- Optional profile opt-in for robot or scene packages that ship Action Graphs
  with ROS 2 publishers/subscribers.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): optional in `2.2.0`, `2.3.0`, `3.0.0`

#### Dependencies

None.

#### Requirement List

* Capability: [Isaac Sim/ROS Bridge](../rules_and_reqs/isaac_sim/ros_bridge/capability-ros_bridge.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `ROS.001` | [ROS.001](../rules_and_reqs/isaac_sim/ros_bridge/requirements/ros2-bridge-nodes-present.md) | `Ros2BridgeNodesPresent` |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, or an open Isaac stage/package root.

Validation or runtime pipeline:

- SimReady validation verifies the selected `CAP025_RosBridge.Ros` manifest by scanning
  composed USD for OmniGraph `node:type` values under `isaacsim.ros2.bridge.*`.

## Samples

- None checked in yet. Any Isaac stage with an Action Graph containing ROS 2
  bridge nodes (clock, joint state, twist, etc.) is a candidate sample.

## Evaluates

- None.

## Adapters

None.
