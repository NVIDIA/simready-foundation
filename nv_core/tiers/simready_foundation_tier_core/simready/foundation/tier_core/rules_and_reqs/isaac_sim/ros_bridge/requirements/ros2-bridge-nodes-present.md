# ros2-bridge-nodes-present

| Code     | ROS.001 |
|----------|---------|
| Validator| Ros2BridgeNodesPresent |
| Compatibility | {compatibility}`Isaac Sim` |
| Tags     | {tag}`essential` |

## Summary

The stage must contain at least one OmniGraph node whose `node:type` starts with `isaacsim.ros2.bridge.`.

## Description

A stage is treated as having authored Isaac ROS 2 bridge wiring when any composed
prim exposes an OmniGraph node type token beginning with:

```text
isaacsim.ros2.bridge.
```

Typical examples include:

- `isaacsim.ros2.bridge.ROS2Context`
- `isaacsim.ros2.bridge.ROS2PublishClock`
- `isaacsim.ros2.bridge.ROS2PublishJointState`
- `isaacsim.ros2.bridge.ROS2SubscribeTwist`

Detection is based on USD-authored OmniGraph node metadata (usually attribute
`node:type` on an `OmniGraphNode` prim), not on a live ROS 2 daemon.

This requirement does **not** validate topic names, QoS, TF correctness, or that
ROS 2 is running.

## Why is it required?

ROS-ready Isaac stages need at least one bridge node so the simulation can
publish/subscribe ROS 2 traffic through OmniGraph. Absence of all such nodes
means no Isaac ROS 2 bridge wiring is authored on the stage.

## Examples

```usda
# Valid: Action Graph contains a ROS 2 bridge node
def OmniGraph "ActionGraph" {
    def OmniGraphNode "PublishClock" {
        uniform token node:type = "isaacsim.ros2.bridge.ROS2PublishClock"
        int node:typeVersion = 1
    }
}

# Invalid: graphs/nodes exist but none are isaacsim.ros2.bridge.*
def OmniGraph "ActionGraph" {
    def OmniGraphNode "OnTick" {
        uniform token node:type = "omni.graph.action.OnTick"
        int node:typeVersion = 1
    }
}
```

## How to comply

1. In Isaac Sim, create or open an Action Graph on the stage.
2. Add at least one node from the Isaac ROS 2 bridge set
   (`isaacsim.ros2.bridge.*`).
3. Save the stage so `node:type` is authored into USD.
