---
name: simready-foundation-conform-fet-029-mujoco
description: "Use for repairing exact CAP029_ConnectionJoint.MuJoCo SimReady MuJoCo connection-joint conformance. Use when a profile, validation report, or user request names CAP029_ConnectionJoint.MuJoCo; default to version 0-1-0 unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - mujoco
---

# SimReady Conform CAP029_ConnectionJoint.MuJoCo

## Purpose

The skill command retains its historical `fet` name for compatibility; the selected contract is a Foundations 2 capability with static validation.

Use this exact capability skill when the selected profile, validation report, or user request names `CAP029_ConnectionJoint.MuJoCo`. It constrains what may be authored alongside an authored connection joint so MuJoCo imports it as a rigid attachment rather than a controllable degree of freedom.

Default to `CAP029_ConnectionJoint.MuJoCo.0-1-0`.

## Source of Truth

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP029_ConnectionJoint.MuJoCo.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP029_ConnectionJoint.MuJoCo.md`

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0-1-0` | `CAP029_ConnectionJoint.0-1-0` | `CN.MUJOCO.001` |

## Workflow

1. Confirm the assembly already satisfies `CAP029_ConnectionJoint`. Every `jointed` connection must already have an authored joint reachable through `simready:mate:joint`. Do not author the joint here; if it is missing, return to `simready-foundation-conform-fet-029-standard`.
2. Enumerate connections with `realization = "jointed"` and resolve each `simready:mate:joint` target. If there are none, report `skipped`.
3. Confirm each connection joint is a `UsdPhysicsFixedJoint`. Remove any `MjcWeldAPI`, `MjcFixedJointAPI`, `MjcWeld`, or `MjcFixedJoint` authoring: the official mjcPhysics schema defines none of these.
4. Remove `MjcJointAPI` from the connection joint, and remove any `MjcActuator` that targets it. Both mark an articulation degree of freedom, which a fixed joint is not.
5. Author `bool physics:collisionEnabled = false` on each connection joint. MuJoCo fuses or welds the pair, and contact between two bodies the solver treats as one is wasteful and destabilizing.
6. Where the attachment is permanent rather than a tool change, raise `realization = "compound"` with the user as the better MuJoCo fit. Do not convert a `jointed` connection to `compound` without confirmation: it changes the rigid-body topology and is a scope change beyond this gate.
7. Static validators are not registered yet. Inspect the staged USDA against the requirement docs.

## Capability Guidance

- MuJoCo has no fixed joint. The standard `UsdPhysicsFixedJoint` is the correct authoring; the repair is removing MuJoCo data that misrepresents it, not adding a MuJoCo weld prim.
- Do not create a second MuJoCo-specific joint prim: `simready:mate:joint` must keep resolving to one target.
- Prefer authoring the overlay in a `runnables/physics/mujoco` layer when the asset uses runtime variant scaffolding, and keep the neutral joint in the assembly physics layer so the relationship resolves with payloads unloaded.
- `MjcJointAPI` is correct on the part's own non-fixed articulation joints, and `MjcActuator` is correct pointing at those. Only strip them from the connection joint.

## Report Fields

| Field | Meaning |
|---|---|
| `capability` | `CAP029_ConnectionJoint.MuJoCo.0-1-0` |
| `input` | Source assembly |
| `output` | Staged assembly path |
| `requirements_repaired` | `CN.MUJOCO.001` |
| `validation` | Inspection used (validators deferred) |
| `status` | `passed`, `failed`, `skipped`, or `blocked` |
| `next_step` | None; the MuJoCo connection-joint gate is the last connection gate |
