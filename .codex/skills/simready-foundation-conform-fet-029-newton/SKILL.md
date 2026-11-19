---
name: simready-foundation-conform-fet-029-newton
description: "Use for repairing exact CAP029_ConnectionJoint.Newton SimReady Newton connection-joint conformance. Use when a profile, validation report, or user request names CAP029_ConnectionJoint.Newton; default to version 0-1-0 unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - newton
---

# SimReady Conform CAP029_ConnectionJoint.Newton

## Purpose

The skill command retains its historical `fet` name for compatibility; the selected contract is a Foundations 2 capability with static validation.

Use this exact capability skill when the selected profile, validation report, or user request names `CAP029_ConnectionJoint.Newton`. It constrains what may be authored alongside an authored connection joint so Newton imports it correctly.

Default to `CAP029_ConnectionJoint.Newton.0-1-0`.

## Source of Truth

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP029_ConnectionJoint.Newton.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP029_ConnectionJoint.Newton.md`

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0-1-0` | `CAP029_ConnectionJoint.0-1-0` | `CN.NEWTON.001` |

## Workflow

1. Confirm the assembly already satisfies `CAP029_ConnectionJoint`. Every `jointed` connection must already have an authored joint reachable through `simready:mate:joint`. Do not author the joint here; if it is missing, return to `simready-foundation-conform-fet-029-standard`.
2. Enumerate connections with `realization = "jointed"` and resolve each `simready:mate:joint` target. If there are none, report `skipped`.
3. Confirm each connection joint is a `UsdPhysicsFixedJoint`. Remove any `NewtonFixedJointAPI` or `NewtonFixedJoint` authoring: Newton defines no such schema and maps the standard fixed joint directly.
4. Remove `NewtonJointAPI` from the connection joint, along with any `newton:armature`, `newton:damping`, `newton:friction`, `newton:velocityLimit`, `newton:limitStiffness`, or `newton:limitDamping` authored on it. Every one of those describes a degree of freedom that a fixed joint does not have.
5. Author `bool physics:collisionEnabled = false` on each connection joint. The coupling faces are coincident, so contact on that pair fights the joint.
6. When the connection fuses two articulations, reduce the composed assembly to exactly one `PhysicsArticulationRootAPI` by deactivating the plug asset's root, then author `bool newton:selfCollisionEnabled` on the survivor per `NEWTON.BA.001`.
7. Static validators are not registered yet. Inspect the staged USDA against the requirement docs.

## Capability Guidance

- This gate is mostly subtractive. Newton consumes standard USD joints, so the repair is removing PhysX-shaped or invented Newton data rather than adding a Newton joint schema.
- Do not create a second Newton-specific joint prim: `simready:mate:joint` must keep resolving to one target.
- Prefer authoring the overlay in a `runnables/physics/newton` layer when the asset uses runtime variant scaffolding, and keep the neutral joint in the assembly physics layer so the relationship resolves with payloads unloaded.
- Set `newton:selfCollisionEnabled = true` only when the Newton runtime should enable self-collisions for the fused articulation. Once two assets are inside one articulation, that value governs contact across the joined flange.
- `NewtonJointAPI` is correct on the part's own driven joints. Only strip it from the connection joint.

## Report Fields

| Field | Meaning |
|---|---|
| `capability` | `CAP029_ConnectionJoint.Newton.0-1-0` |
| `input` | Source assembly |
| `output` | Staged assembly path |
| `requirements_repaired` | `CN.NEWTON.001` |
| `validation` | Inspection used (validators deferred) |
| `status` | `passed`, `failed`, `skipped`, or `blocked` |
| `next_step` | None; the Newton connection-joint gate is the last connection gate |
