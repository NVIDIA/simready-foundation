---
name: simready-foundation-conform-fet-029-physx
description: "Use for repairing exact CAP029_ConnectionJoint.PhysX SimReady PhysX connection-joint conformance. Use when a profile, validation report, or user request names CAP029_ConnectionJoint.PhysX; default to version 0-1-0 unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - physx
---

# SimReady Conform CAP029_ConnectionJoint.PhysX

## Purpose

The skill command retains its historical `fet` name for compatibility; the selected contract is a Foundations 2 capability with static validation.

Use this exact capability skill when the selected profile, validation report, or user request names `CAP029_ConnectionJoint.PhysX`. PhysX maps `UsdPhysicsFixedJoint` directly, so this gate mostly constrains what may be layered onto an authored connection joint rather than adding to it.

Default to `CAP029_ConnectionJoint.PhysX.0-1-0`.

## Source of Truth

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP029_ConnectionJoint.PhysX.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP029_ConnectionJoint.PhysX.md`

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0-1-0` | `CAP029_ConnectionJoint.0-1-0` | `CN.PHYSX.001` |

## Workflow

1. Confirm the assembly already satisfies `CAP029_ConnectionJoint`. Every `jointed` connection must already have an authored joint reachable through `simready:mate:joint`. Do not author the joint here; if it is missing, return to `simready-foundation-conform-fet-029-standard`.
2. Enumerate connections with `realization = "jointed"` and resolve each `simready:mate:joint` target. If there are none, report `skipped`.
3. Remove `PhysxJointAPI` and any `physxJoint:` attribute from each connection joint. A fixed joint has no degree of freedom for them to tune. If break thresholds were written as `physxJoint:breakForce` / `physxJoint:breakTorque`, remove them and make sure `physics:breakForce` / `physics:breakTorque` are authored instead (`CN.009`).
4. Author `bool physics:collisionEnabled = false`. The mate convention places the coupling faces coincident, so contact on that overlapping pair fights the joint holding the pose.
5. Leave `physics:excludeFromArticulation` unset, or author it `false`. If a stage carries `true` on a connection joint, clear it.
6. Resolve articulation membership for both mate bodies: walk each toward the stage root looking for `PhysicsArticulationRootAPI`, checking both the enclosing-prim and root-joint placements. When both are articulated, the connection fuses the two articulations, so deactivate or remove the plug asset's articulation root and leave exactly one on the composed assembly.
7. Validate with `CN.PHYSX.001` and inspect the staged USDA against the requirement doc.

## Capability Guidance

- Work on the neutral joint that `CN.009` requires. Do not create a second PhysX-specific joint prim: `simready:mate:joint` must keep resolving to one target.
- Prefer authoring the overlay in a `runnables/physics/physx` layer when the asset uses runtime variant scaffolding, and keep the neutral joint in the assembly physics layer so the relationship resolves with payloads unloaded. Note that removing an attribute through a layer is `RemoveProperty` in the layer that authored it; an overlay cannot delete an opinion from a weaker layer by re-authoring it.
- A fixed connection joint needs no PhysX joint data. `physxJoint:armature`, `physxJoint:jointFriction`, and `physxJoint:maxJointVelocity` all tune a degree of freedom it does not have, so this gate forbids them, as `CN.NEWTON.001` and `CN.MUJOCO.001` do for their own namespaces.
- Giving up the plug asset's articulation root is the load-bearing edit for the arm-plus-gripper case. Each asset ships its own root, and the fused articulation must end up with one. This is a separate edit from deactivating the plug's world pin (`CN.009`), and the two are often different prims.
- The connection joint belongs to the articulation it fuses, so it is solved with it. `physics:excludeFromArticulation = true` belongs to a mechanism that closes a loop inside one asset, such as a four-bar linkage (`DJ.011`).
- Attach strength is `CN.009`. `physics:breakForce` and `physics:breakTorque` are `UsdPhysicsJoint` attributes, so they are already authored on the input stage; if they are missing, return to `simready-foundation-conform-fet-029-standard`.
- Do not author PhysX drive or limit data on a fixed joint.
- PhysX self-collision lives on the articulation root as `physxArticulation:enabledSelfCollisions`, not on the joint. If the fused articulation needs it retuned, that is a `FET_024_PHYSX` edit on the surviving root, not part of this gate.

## Report Fields

| Field | Meaning |
|---|---|
| `capability` | `CAP029_ConnectionJoint.PhysX.0-1-0` |
| `input` | Source assembly |
| `output` | Staged assembly path |
| `requirements_repaired` | `CN.PHYSX.001` |
| `validation` | `CN.PHYSX.001` result plus any inspection used |
| `status` | `passed`, `failed`, `skipped`, or `blocked` |
| `next_step` | None; the PhysX connection-joint gate is the last connection gate |
