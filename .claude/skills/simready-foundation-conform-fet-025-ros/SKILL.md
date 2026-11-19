---
name: simready-foundation-conform-fet-025-ros
description: "Use for repairing exact CAP025_RosBridge.Ros SimReady conformance for Isaac ROS-Ready bridge-node presence. Use when a profile, validation report, or user request names CAP025_RosBridge.Ros; default to `CAP025_RosBridge.Ros.0-1-0`. Foundations 1 ID: FET_025_ROS."
license: Apache-2.0
metadata:
  author: "Cursor Agent"
  tags:
    - simready
    - conformance
    - isaac
    - ros2
---

# SimReady Conform CAP025_RosBridge.Ros

## OpenUSD Competence

Running this conform skill is expert USD authoring. Reason from the OpenUSD /
Pixar USD spec rather than pattern-matching a validator message: composition
arcs and LIVRPS strength ordering, value resolution and list editing
(prepend, append, explicit, delete), the `def`/`over`/`class`
specifiers, native instancing and model hierarchy, stage units and up-axis,
and the `UsdGeom`, `UsdShade`, and `UsdPhysics` schemas. Make the exact native
edit on the correct prim, arc, and layer, derive values from the asset's real
geometry and composition, then reopen the composed stage to confirm the
opinion resolves as intended before claiming the gate passes. Never fabricate
data to satisfy a validator token. The repository-root `AGENTS.md`
"Master-Level OpenUSD Competence for Conform Work" section is the full
statement.

## Purpose

Use this exact capability skill when the selected profile, validation report, or user request names `CAP025_RosBridge.Ros`. It stages or reports Isaac ROS-Ready conformance for OmniGraph ROS 2 bridge nodes.

Default to `CAP025_RosBridge.Ros.0-1-0`.

## Source of Truth

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP025_RosBridge.Ros.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP025_RosBridge.Ros.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/isaac_sim/ros_bridge/requirements/ros2-bridge-nodes-present.md`

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `CAP025_RosBridge.Ros.0-1-0` | None | `ROS.001` |

## Workflow

1. Confirm the input stage/asset exists and the selected feature is `CAP025_RosBridge.Ros.0-1-0`.
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
| `feature` | Exact contract ID, for example `CAP025_RosBridge.Ros.0-1-0`. |
| `input` | Source asset or stage inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | Next exact capability skill or user/runtime evidence needed. |
