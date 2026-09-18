# Feature: `FET_025_ROS`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_025_ROS` |
| Runtime | `ROS` |
| Proprietary Techs | `Isaac Sim`, `ROS 2` |
| Latest Version | `0.1.0` |

## Description

Defines a minimal Isaac Sim **ROS-Ready** contract: the stage authors at least
one OmniGraph ROS 2 bridge node (`isaacsim.ros2.bridge.*`). This proves ROS 2
bridge wiring exists on the stage. It does not validate topic names, QoS, TF,
or a live ROS 2 daemon.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies selected `FET_025_ROS` manifests.
- Inventory / triage of Isaac stages that claim ROS 2 bridge wiring.
- Optional profile opt-in for robot or scene packages that ship Action Graphs
  with ROS 2 publishers/subscribers.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- `Robot-Body` version `2.2.0` (optional)

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Isaac Sim/ROS Bridge](../capabilities/isaac_sim/ros_bridge/capability-ros_bridge.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `ROS.001` | [ROS.001](../capabilities/isaac_sim/ros_bridge/requirements/ros2-bridge-nodes-present.md) | [Ros2BridgeNodesPresent](../capabilities/isaac_sim/ros_bridge/validation.py) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, or an open Isaac stage/package root.

Validation or runtime pipeline:

- SimReady validation verifies the selected `FET_025_ROS` manifest by scanning
  composed USD for OmniGraph `node:type` values under `isaacsim.ros2.bridge.*`.

## Samples

- None checked in yet. Any Isaac stage with an Action Graph containing ROS 2
  bridge nodes (clock, joint state, twist, etc.) is a candidate sample.

## Benchmarks

- None.

## Adapters

None.
