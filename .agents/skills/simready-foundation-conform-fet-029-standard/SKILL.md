---
name: simready-foundation-conform-fet-029-standard
description: "Use for repairing exact CAP029_ConnectionJoint SimReady connection multibody-physics conformance. Use when a profile, validation report, or user request names CAP029_ConnectionJoint; default to version 0-1-0 unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - standard
---

# SimReady Conform CAP029_ConnectionJoint

## Purpose

The skill command retains its historical `fet` name for compatibility; the selected contract is a Foundations 2 capability with static validation.

Use this exact capability skill when the selected profile, validation report, or user request names `CAP029_ConnectionJoint`. It authors the `UsdPhysicsFixedJoint` that holds a `jointed` connection, declares how strong the attachment is, and rates it against the socket's payload capacity.

This skill applies only to connections whose `simready:mate:realization` is `jointed`. Skip `compound` connections entirely: they have no joint, and `CN.005` and `CN.009` do not apply to them.

Default to `CAP029_ConnectionJoint.0-1-0`.

## Source of Truth

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP029_ConnectionJoint.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP029_ConnectionJoint.md`

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0-1-0` | `CAP027_Connections.0-1-0`, `FET004_Multibody.0-2-0` | `CN.005`, `CN.009` |

## Workflow

1. Confirm the assembly already satisfies `CAP027_Connections`. Every connection must already carry `realization`, `socket`, and `plug`. Do not create geometry and do not create connections.
2. Enumerate connections with `realization = "jointed"`. If there are none, report `skipped`.
3. For each, resolve both mate bodies per `MC.003`: the nearest ancestor with an **enabled** `PhysicsRigidBodyAPI`. A part carrying `physics:rigidBodyEnabled = false` is transparent to the walk, so a site inside a demoted part resolves to the compound body above it, and that is the prim the joint targets. Confirm the two are distinct. If they are the same prim, the asset's `realization` token is wrong; report that as a `CN.006` failure rather than authoring a self-joint.
4. Author a `UsdPhysicsFixedJoint` with `physics:body0` set to the socket mate body and `physics:body1` set to the plug mate body. Body order is not significant, but keep socket as `body0` for readability.
5. Compute each mate site's transform expressed in its own mate body and author the result as `physics:localPos0` / `physics:localRot0` (socket) and `physics:localPos1` / `physics:localRot1` (plug). These must hold the two mate frames coincident. Derive them from the composed stage; never leave them unauthored and never guess.
6. Author `rel simready:mate:joint` on the connection prim targeting that joint, with exactly one target.
7. Author `float physics:breakForce` and `float physics:breakTorque`. Use `inf` for a permanent attachment. Derive a finite value only from a stated mechanical rating; never invent a breaking load. Author both via the typed API (`UsdPhysics.Joint.CreateBreakForceAttr`) so they land as schema attributes rather than custom ones.
8. Deactivate any competing world pin the plug asset carried standalone, such as a gripper `root_joint`. An active world pin over-constrains the pairing.
9. Check `CN.005`: sum `physics:mass` from prims with `PhysicsMassAPI` in the plug mate-body subtree and compare to the socket's `maxPayload`. Walk down and stop at the first prim on each branch that authors `physics:mass`; that value stands for its whole subtree. Stopping is what keeps a compound aggregate from being added to the part masses beneath it, so a plug that is itself a compound contributes one aggregate. Do not read `SR.003` `customLayerData` mass; it does not compose across a reference. If any branch yields no explicit mass, report `CN.005` as warn and do not fail on it.
10. Validate with `CN.005` and `CN.009`, then inspect the staged USDA against the requirement docs.

## Capability Guidance

- The joint is authored, not inferred. An authored joint keeps the assembly rigid in a runtime that does not read `simready:mate:`, and it satisfies `RB.012` so the assembly can be nested inside another assembly.
- Authoring the joint does not take it away from the runtime. A tool-change runtime follows `simready:mate:joint` and sets `physics:jointEnabled = false`, retunes, or deletes the prim. Do not add custom attributes to describe that lifecycle.
- The joint must be a `UsdPhysicsFixedJoint`. A connection is a rigid attachment; a joint with degrees of freedom does not express it. Do not repurpose a part's existing revolute or prismatic joint.
- Author the joint where `simready:mate:joint` resolves with runtime payloads unloaded. One neutral joint belongs in the assembly physics layer. Runtime variants overlay attributes onto that same prim; do not create a second joint per runtime.
- Attach strength belongs to this gate. `physics:breakForce` and `physics:breakTorque` are `UsdPhysicsJoint` attributes that PhysX, Newton, and MuJoCo all read, so authoring them here covers every runtime. Both are required even when the answer is `inf`, because the schema fallback is `inf` and an unauthored joint is silently unbreakable.
- Do not invent a mass or a payload rating to force `CN.005` to pass.

## Report Fields

| Field | Meaning |
|---|---|
| `capability` | `CAP029_ConnectionJoint.0-1-0` |
| `input` | Source assembly |
| `output` | Staged assembly path |
| `requirements_repaired` | `CN.005`, `CN.009` as applicable |
| `validation` | `CN.005` and `CN.009` results plus any inspection used |
| `status` | `passed`, `failed`, `skipped`, or `blocked` |
| `next_step` | The selected exact `FET_029` runtime skill (`simready-foundation-conform-fet-029-physx`, `-newton`, or `-mujoco`) when the profile pins one |
