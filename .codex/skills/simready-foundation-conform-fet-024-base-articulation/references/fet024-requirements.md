# FET024 Requirement Repair Map

Use this reference when a validation report or inspection identifies `FET024_BASE_ARTICULATION_NEUTRAL` or `FET024_BASE_ARTICULATION_PHYSX` failures. Load the selected JSON manifest first:

- `FET_024-base_articulation_neutral-0.1.0.json`
- `FET_024-base_articulation_physx-0.1.0.json`

The feature markdown and requirement docs are useful context, but the selected manifest and current validation report decide which IDs are in scope.

## Manifest Requirements

| Feature Variant | Requirements |
|---|---|
| `FET024_BASE_ARTICULATION_NEUTRAL@0.1.0` | `BA.001` |
| `FET024_BASE_ARTICULATION_PHYSX@0.1.0` | Depends on `FET024_BASE_ARTICULATION_NEUTRAL@0.1.0`; manifest lists `BA.002` |

## Requirement Map

| Requirement | What It Means | Safe Repair | Block When |
|---|---|---|---|
| `BA.001` | The articulated asset must have exactly one `UsdPhysics.ArticulationRootAPI` application. | Apply `ArticulationRootAPI` to the clear articulation root, or remove duplicate root API opinions after choosing the canonical root. | The correct root body, root joint, or robot root is ambiguous; there are multiple mechanisms; or root placement conflicts with robot type/pinning semantics. |
| `BA.002` | For the PhysX variant, collision meshes on non-adjacent articulation links must not overlap or clash at the default pose. | Use reported contact pairs and joint adjacency to identify non-adjacent collisions, then repair with an approved collider strategy such as simpler collision proxies, collider clearance, or corrected collision approximation. | PhysX runtime/contact validation is unavailable, collision pairs are unknown, or repair would require changing robot geometry, joint transforms, default pose, or unapproved collider generation. |

## Validator Contract

Current BaseArticulation validation:

- `BA.001` traverses the composed stage and counts prims with `UsdPhysics.ArticulationRootAPI`.
- `BA.001` fails when the count is zero.
- `BA.001` fails when the count is greater than one.
- `BA.002` requires `PhysxSchema` in the local environment.
- `BA.002` computes body adjacency from joints with `PhysxJointAPI` and their `physics:body0` / `physics:body1` relationships.
- `BA.002` is intended to compare contact pairs against adjacency and fail when non-adjacent colliders touch.
- In the current source, the helper that should gather initial contact pairs may return an empty set when runtime contact reporting is unavailable. Record this validation limitation when BA.002 matters.

## Root Selection Guidance

Use this decision order before authoring `ArticulationRootAPI`:

1. Prefer explicit source metadata or user-supplied root intent.
2. If FET021 robot type and robot joints are present, use them to distinguish fixed-base and floating-base behavior.
3. For fixed-base manipulators or end effectors, choose the root joint or robot root only when the authored USD pattern makes that clear.
4. For mobile or floating robots, choose the root rigid body when it clearly owns the articulation tree.
5. If the robot-body profile authoring guide expects the default robot root and that root owns the links and joints, the default prim can be the correct root.
6. If multiple plausible roots remain, block instead of adding an arbitrary API.

Do not use this skill to create a missing robot topology. If links or joints do not exist, hand off to the multibody or joint feature workflow first.

## BA.002 Collision Guidance

Use this decision order for PhysX collision overlap failures:

1. Capture the reported non-adjacent collider pair paths.
2. Map each collider to its owning rigid body/link.
3. Confirm the two bodies are not adjacent through a participating PhysX joint.
4. Inspect whether the overlap comes from collision proxy shape, default pose, transform, or an unintended collider.
5. Repair only the collision representation when possible; do not move visual geometry or joint frames just to pass BA.002.
6. Prefer user-approved simplified colliders or collision approximation changes over arbitrary scale/translate edits.

## USD Authoring Notes

Use USD APIs where available instead of string editing:

- Use `UsdPhysics.ArticulationRootAPI.Apply(prim)` for BA.001.
- Inspect `prim.HasAPI(UsdPhysics.ArticulationRootAPI)` to find existing roots.
- Use `UsdPhysics.Joint(prim)` and its body relationships to inspect topology.
- For PhysX adjacency, inspect `PhysxSchema.PhysxJointAPI` only when available and selected by the profile.
- Preserve authored layer/source policy when moving or applying physics APIs.

## Report Template

For each repair attempt, record:

| Field | Meaning |
|---|---|
| `requirement_id` | Requirement being repaired. |
| `status` | `repaired`, `already_passed`, `blocked`, or `failed`. |
| `affected_prims` | Articulation roots, joints, bodies, or colliders inspected or changed. |
| `old_value` and `new_value` | API schema, root path, collider approximation, or collision proxy changed. |
| `variant` | Selected FET024 feature ID and version. |
| `outputs` | Files written or references changed. |
| `reason` | Short explanation, especially for blocked items or validator/runtime limitations. |
