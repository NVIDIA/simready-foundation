---
name: simready-foundation-conform-fet-004-simulate-multi-body-physics
description: "Use for repairing SimReady multibody physics: rigid bodies, joints, articulation roots, and PhysX variants."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - physics
---


# SimReady Conform FET-004 Simulate Multi-Body Physics

## Purpose
Use this workflow skill after FET000_CORE, FET001_BASE_NEUTRAL, and the selected FET003 rigid-body variant are already in a reasonable state and the next validation gate is `FET004_BASE_NEUTRAL`, `FET004_BASE_PHYSX`, or `FET004_ROBOT_PHYSX`. It repairs multibody structure: multiple existing rigid bodies, joints between them, articulation-root placement, and variant-specific PhysX requirements.

This is an authoring and repair skill, not the final validator. Work on a staged copy under the requested output directory, rerun the same FET004 validation gate after each repair stage, and stop at the first remaining FET004 validation failure that needs asset-design intent, source conversion, collider redesign, or geometry that is not already present.

## Hard Constraint

Do not create new geometry to satisfy FET004.

- Do not add cubes, meshes, collider proxies, visual parts, or duplicate/split geometry solely to produce a second rigid body or a joint target.
- Do not invent a second body for `RB.MB.001` when the asset contains only one real physical part.
- Do not generate collision geometry for PhysX FET004 failures. Reuse existing collider or visual geometry only, or hand back to FET003/source conversion when required geometry is missing.
- It is acceptable to author non-geometry USD physics structure, such as `UsdPhysicsJoint` prims, relationships, rigid-body schemas, articulation schemas, or physics attributes, but only when those opinions target existing prims that already represent real asset parts.

If an asset is a single-rigid-body prop and the selected profile documents FET004 as optional or conditional, treat FET004 as not applicable. Report that the asset satisfies prop physics through FET003 and should not be forced through FET004 unless the user supplies multibody intent or a source asset with separate body geometry.

## Profile Conditionality

Before repairing FET004, read the target profile documentation and profile index:

- `nv_core/sr_specs/docs/profiles/profiles.md`
- `nv_core/sr_specs/docs/profiles/<profile-slug>.md`
- `nv_core/sr_specs/docs/profiles/profiles.toml`

If the selected profile describes FET004 as optional or conditional, use that text as authoritative workflow guidance for the conforming stage. A TOML comment is human-readable guidance, not machine-readable validation policy, so also prefer explicit profile markdown or profile-index notes when available.

Do not decide FET004 applicability by mesh count alone. An asset may have several meshes and still be one rigid body. FET004 applies when the asset has more than one intended rigid body, joints, articulations, robot links, or source multibody structure. For a prop with one intended physical body and no joints/articulation intent, record FET004 as `skipped/not applicable` when the profile allows it.

## Prerequisites

Read the source-of-truth files named below before editing. Work on staged outputs where the skill requires them, and keep validation evidence with the result.

## Source of Truth

Before changing an asset, load the exact FET004 manifest selected by the profile:

- `nv_core/sr_specs/docs/features/FET_004_base_neutral-0.1.0-simulate_multi_body_physics.json`
- `nv_core/sr_specs/docs/features/FET_004_base_physx-0.1.0-simulate_multi_body_phyics.json`
- `nv_core/sr_specs/docs/features/FET_004_base_physx-0.2.0-simulate_multi_body_phyics.json`
- `nv_core/sr_specs/docs/features/FET_004_robot_physx-0.1.0-simulate_multi_body_phyics.json`
- `nv_core/sr_specs/docs/features/FET_004_robot_physx-0.2.0-simulate_multi_body_phyics.json`
- `nv_core/sr_specs/docs/features/FET_004-simulate_multi_body_physics.md`

Treat the selected JSON manifest as authoritative for requirement IDs. If the markdown, manifest, validator, or report disagree, follow the validation report for the current gate and call out the mismatch in the stage summary.

For per-requirement repair details, read `references/fet004-requirements.md` when a FET004 validation report or inspection identifies matching failures.

## Inputs

Collect these before editing:

| Input | Requirement |
|---|---|
| `usd_asset` | Required `.usd`, `.usda`, `.usdc`, or unpacked USD-family asset to repair. |
| `output_root` | Required or inferred folder for staged assets and reports. |
| `simready_profile` | Profile being validated, such as `prop-robotics-physx`, `robot-body-neutral`, `robot-body-runnable`, or another profile that includes FET004. |
| `profile_version` | Profile version, if supplied by the user or validation command. |
| `validation_report` | Preferred JSON or markdown report from the failing profile or feature validation gate. |
| `fet004_variant` | Selected feature ID and version, such as `FET004_BASE_NEUTRAL@0.1.0`, `FET004_BASE_PHYSX@0.2.0`, or `FET004_ROBOT_PHYSX@0.2.0`. Infer from the profile when possible. |
| `profile_condition_notes` | Any profile markdown, profile index, or TOML comments that mark FET004 optional, conditional, required, or not applicable. |
| `multibody_intent` | Whether the asset is intentionally a multibody assembly, articulated prop, or robot body. Infer only from profile, existing rigid bodies/joints, source metadata, or user instruction. |
| `body_map` | Existing prims that correspond to real physical bodies. Build this from current rigid-body APIs, existing xformable part roots, joint targets, robot links, or source hierarchy. |
| `joint_intent` | Existing joint prims, source CAD/URDF/MJCF joint data, robot joint relationships, naming, or user-approved constraints. |

## Instructions

Use this checklist when changing the repository:

1. Confirm the input asset exists, then read the target profile docs and profile index for optional or conditional feature notes before deciding whether to repair FET004.
2. Parse the validation report and filter to FET004 failures. Do not repair later profile features such as FET005 grasp physics, FET006 materials, FET021 robot core, FET022 driven joints, or FET024 base articulation in this skill.
3. Load the selected FET004 manifest version and the requirement repair map.
4. Decide whether FET004 applies:
   - Apply FET004 when the profile requires it and the asset has at least two intended physical bodies, existing joints, robot links, articulation intent, or clear multibody source metadata.
   - Skip FET004 as not applicable when the selected profile marks it optional or conditional and the asset is a single intended rigid body with no joints or articulation intent.
   - Treat mesh count as supporting evidence only; multiple meshes do not by themselves make an asset multibody.
   - Block when validation demands a second body but the USD contains no existing geometry or xformable part that can honestly represent that body.
5. Create a staged output folder under `output_root`; do not mutate the source unless the user explicitly asks for in-place repair.
6. Inspect the stage before editing:
   - default prim, root prim, units, and composed bounds
   - existing `UsdPhysics.RigidBodyAPI`, `CollisionAPI`, `MeshCollisionAPI`, `MassAPI`, joint prims, and articulation roots
   - existing xformable part roots and geometry that could correspond to separate physical bodies
   - joint `physics:body0` and `physics:body1` targets, including missing, empty, multiple, or non-rigid targets
   - static, disabled, or kinematic flags on bodies participating in articulations
   - PhysX schemas and collider relationships when a PhysX FET004 variant is selected
7. Apply repairs in this order:
   - Fix or remove invalid joint relationship targets before adding new joint opinions.
   - Apply `UsdPhysics.RigidBodyAPI` only to existing xformable prims that already represent distinct physical bodies.
   - Author or retarget `UsdPhysicsJoint` prims only when body pairing and joint type are known from existing data or user intent.
   - Ensure each joint body relationship targets an existing prim and has at most one target.
   - Move or remove nested `UsdPhysics.ArticulationRootAPI` only when the correct single articulation root is clear.
   - Enable an articulation root body or clear kinematic mode only when dynamic articulation is the intended behavior.
   - For PhysX variants, repair only schema opinions and relationships on existing colliders or rigid bodies; do not create collider geometry.
8. Rerun the same profile validation gate, or the narrowest available FET004 validation gate.
9. Summarize the stage as passed, failed, skipped, or blocked. Stop when FET004 passes, is correctly skipped as not applicable, or the next FET004 failure requires geometry, topology, joint intent, runtime simulation evidence, or an upstream conversion change.

## Examples

Example request:

```text
Repair FET004 multi-body physics failures without creating new geometry.
```

Expected result summary:

```text
staged_asset: repaired copy or output directory
validation: selected feature/profile gate and report path
remaining_failures: next failing requirement IDs, if any
```

## Repair Policy

Make automatic repairs only when the intended result is mechanical and locally verifiable:

- Add a missing rigid-body schema to an existing xformable part root that clearly represents a distinct physical body.
- Retarget a joint body relationship to an existing rigid body when the intended target is obvious from neighboring hierarchy, naming, or source metadata.
- Reduce a body relationship with multiple targets to one target only when the selected target is unambiguous.
- Add a fixed joint between two existing rigid bodies only when the asset already expresses a fixed connection through source metadata, robot topology, naming, or user instruction.
- Remove a nested articulation root when another ancestor or descendant is clearly the intended unique root.
- Set `physics:rigidBodyEnabled = true` or `physics:kinematicEnabled = false` on an articulation root body only when the asset is meant to simulate dynamically.

Block and report instead of guessing when:

- The USD has only one existing physical body candidate and no source data for a second body.
- Passing `RB.MB.001` would require creating, duplicating, splitting, or importing geometry.
- A joint type, joint axis, anchor frame, or body pairing is not clear from existing data.
- Multiple plausible articulation roots exist.
- PhysX collision requirements require new collider geometry or a collider redesign.
- The asset is a prop profile where FET004 is conditional and the prop is intentionally a single rigid body.

## Variant Guidance

For `FET004_BASE_NEUTRAL`, use standard OpenUSD `UsdPhysics` bodies, joints, and articulation roots. The core FET004 requirements are `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, and `RB.MB.001`.

For `FET004_BASE_PHYSX`, first satisfy the neutral FET004 dependency and the selected FET003 PhysX dependency. Then repair only selected PhysX collision requirements on existing colliders. Do not use robot-specific RB.COL.001 exemptions for a base PhysX prop profile.

For `FET004_ROBOT_PHYSX`, follow the robot PhysX manifest. This variant intentionally has different collision requirements from base PhysX and does not require RB.COL.001. Preserve robot link and joint semantics, and leave robot identity/schema issues to FET021, driven joint actuation to FET022, and articulation-root cardinality or PhysX collision-clearance issues to FET024 when those later gates are the active failure.

## Validation Handoff

Preserve reports under the staged output directory. If the Physical AI Skill Hub validation commands are available, use the same profile gate that exposed the failure:

```bash
uv run --python 3.12 validate-simready-profile <staged-usd> \
  --profile <profile> \
  --profile-version <version> \
  --foundation-root <simready-foundation-root> \
  --foundation-spec-root <simready-foundation-root>/nv_core/sr_specs/docs \
  --report <output-root>/simready-profile-after-fet004.json
```

Count this skill as successful when the selected FET004 variant passes or when FET004 is explicitly not applicable for the selected prop workflow. Report later feature failures as handoff work for their own skills.

## Limitations

- Do not silently mutate the source asset; work on the requested staged output.
- Do not hide later profile failures after the selected feature gate passes or fails.
- Do not invent geometry, metadata, or runtime behavior that conflicts with the asset intent.

## Troubleshooting

- Error: validation tooling is unavailable. Solution: run the narrowest available USD or static check and report the gap.
- Error: a repair would change asset intent. Solution: stop and ask for direction or stage the smallest reversible edit.
- Error: later profile gates still fail. Solution: report the next failing feature and hand off to the matching conformance skill.

## Resources

- `assets/openai.yaml` preserves optional UI metadata for clients that read skill display hints. It is not required for the workflow.
- `references/` contains detailed requirement notes; load only the files needed for the active validation failure.

## Summary Format

Report:

| Field | Meaning |
|---|---|
| `input_usd_path` | Original USD path. |
| `output_usd_path` | Latest staged/repaired USD path. |
| `profile` and `profile_version` | Validation target. |
| `fet004_variant` | Selected FET004 feature ID and version. |
| `applicability` | Applied, skipped as not applicable, failed, or blocked. |
| `rigid_body_roots` | Existing prims with `UsdPhysics.RigidBodyAPI` after repair. |
| `joint_prims` | Joint prims authored or repaired by this skill. |
| `articulation_roots` | Articulation root prims after repair. |
| `geometry_policy` | Confirmation that no new geometry was created, or why work was blocked. |
| `requirements_repaired` | Requirement IDs changed by this skill. |
| `requirements_blocked` | Requirement IDs that need geometry, topology, joint intent, or upstream conversion. |
| `validation_report` | Path to the rerun validation report. |
| `next_step` | Usually the next failing profile feature or a blocked FET004 requirement. |

Keep the user-facing summary short: whether FET004 applied, what body/joint/articulation opinions changed, that no geometry was created, which FET004 variant was validated, and the first validation gate that blocks progress.
