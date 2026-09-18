---
name: simready-foundation-conform-fet-025-ros
description: "Use for repairing exact FET_025_ROS SimReady conformance for Isaac ROS-Ready bridge-node presence. Use when a profile, validation report, or user request names FET_025_ROS; default to version `0.1.0`."
license: Apache-2.0
metadata:
  author: "Cursor Agent"
  tags:
    - simready
    - conformance
    - isaac
    - ros2
---

# SimReady Conform FET_025_ROS

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_025_ROS`. It stages or reports Isaac ROS-Ready conformance for OmniGraph ROS 2 bridge nodes.

Default to `FET_025_ROS@0.1.0`.

## Source of Truth

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_025_ROS-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_025_ROS.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/isaac_sim/ros_bridge/requirements/ros2-bridge-nodes-present.md`

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | None | `ROS.001` |

## Workflow

1. Confirm the input stage/asset exists and the selected feature is `FET_025_ROS@0.1.0`.
2. Validate for `ROS.001` (at least one OmniGraph `node:type` starting with `isaacsim.ros2.bridge.`).
3. If missing, prefer repairing in Isaac Sim by authoring an Action Graph with at least one ROS 2 bridge node, then saving the USD.
4. Do **not** invent arbitrary bridge nodes with placeholder topics in headless USD-only repair unless the user provides the intended ROS graph contract.
5. Re-validate and summarize.

## Feature Guidance

- Passing `ROS.001` means bridge wiring is authored, not that topics/TF/QoS are correct.
- Auto-authoring a full ROS graph without user intent is blocked; report `blocked` and ask for the intended publishers/subscribers.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_025_ROS@0.1.0`. |
| `input` | Source asset or stage inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | Next exact feature skill or user/runtime evidence needed. |
