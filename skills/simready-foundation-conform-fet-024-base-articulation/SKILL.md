---
name: simready-foundation-conform-fet-024-base-articulation
description: "Use for repairing SimReady base articulation roots and PhysX collision-clearance evidence."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - robotics
---


# SimReady Conform FET-024 Base Articulation

## Purpose
Use this workflow skill when the selected profile, validation report, or user request targets `FET024_BASE_ARTICULATION_NEUTRAL` or `FET024_BASE_ARTICULATION_PHYSX`. FET024 repairs the base articulation contract for robot-body assets: exactly one articulation root for the articulated mechanism, plus PhysX collision-clearance checks for the PhysX variant.

This is a base-articulation repair skill, not a full robot topology, driven-joint, or collision-generation skill. Work on a staged copy under the requested output directory, preserve composed joint/body behavior, and stop at the first FET024 issue that needs robot topology, root-joint intent, collider redesign, or a PhysX runtime contact check.

## Prerequisites

Read the source-of-truth files named below before editing. Work on staged outputs where the skill requires them, and keep validation evidence with the result.

## Source of Truth

Before changing an asset, load the exact FET024 manifest selected by the profile:

- `nv_core/sr_specs/docs/features/FET_024-base_articulation_neutral-0.1.0.json`
- `nv_core/sr_specs/docs/features/FET_024-base_articulation_physx-0.1.0.json`
- `nv_core/sr_specs/docs/features/FET_024-base_articulation.md`
- `nv_core/sr_specs/docs/capabilities/physics_bodies/base_articulation/requirements.md`
- `nv_core/sr_specs/docs/capabilities/physics_bodies/base_articulation/validation.py`

Treat the selected JSON manifest as authoritative for the required IDs. If the markdown, manifest, validator, or report disagree on a requirement ID or behavior, follow the validation report for the current gate and call out the mismatch in the stage summary.

For per-requirement repair details, read `references/fet024-requirements.md` when a FET024 validation report or inspection identifies matching failures.

## Inputs

Collect these before editing:

| Input | Requirement |
|---|---|
| `usd_asset` | Required robot `.usd`, `.usda`, `.usdc`, or unpacked USD-family asset to repair. |
| `output_root` | Required or inferred folder for staged assets and reports. |
| `simready_profile` | Robot profile being validated, such as `Robot-Body-Neutral`, `Robot-Body-Runnable`, or `Robot-Body-Isaac`. |
| `profile_version` | Profile version, if supplied by the user or validation command. |
| `validation_report` | Preferred JSON or markdown report from the failing profile or feature validation gate. |
| `fet024_variant` | Selected feature ID and version, such as `FET024_BASE_ARTICULATION_NEUTRAL@0.1.0` or `FET024_BASE_ARTICULATION_PHYSX@0.1.0`. |
| `articulation_root_policy` | Intended articulation root: robot root, root body, root joint, or user/source-approved target prim. |
| `joint_topology` | Existing body and joint graph used to identify the articulation and adjacency. |
| `collision_clearance_policy` | User-approved strategy for resolving non-adjacent collision overlap, if BA.002 fails. |
| `physx_runtime` | Whether PhysX schemas/runtime contact checks are available for BA.002 validation. |

## Instructions

Use this checklist when changing the repository:

1. Confirm the input asset exists and determine whether the selected profile uses the neutral or PhysX FET024 variant.
2. Parse the validation report and filter to FET024/BA failures. Do not repair driven-joint APIs, mimic joints, joint limits, robot core schema, or broad multibody topology issues in this skill unless they directly block the FET024 root decision.
3. Load the selected FET024 manifest version and the requirement repair map.
4. Create a staged output folder under `output_root`; do not mutate the source unless the user explicitly asks for in-place repair.
5. Inspect the stage before editing:
   - default prim, robot root, and model hierarchy
   - existing `UsdPhysics.ArticulationRootAPI` applications and authored layers
   - all rigid body prims, static or kinematic body flags, and root body candidates
   - all `UsdPhysics.Joint` prims, `physics:body0`, `physics:body1`, and root joint candidates
   - whether the selected robot type or FET021 root-joint policy implies fixed-base or floating-base behavior
   - PhysX joint APIs, collision mesh APIs, and reported contact/collision pairs for the PhysX variant
6. Decide the articulation root before authoring:
   - Use a source- or user-approved articulation root when provided.
   - For a fixed-base manipulator or end effector, the root joint or robot root may be the correct articulation anchor depending on the authored USD pattern.
   - For a floating or mobile robot, the root body is usually the correct articulation root.
   - If the profile authoring guide requires the default robot root and that root clearly owns the whole articulation, use the default prim.
   - Block when more than one root candidate is plausible.
7. Apply repairs in this order:
   - Remove extra `ArticulationRootAPI` opinions only when the intended single root is clear.
   - Apply `UsdPhysics.ArticulationRootAPI` to the chosen root prim in the correct physics/source layer.
   - Preserve FET021 robot root and robot joint relationship order; do not reorder joints unless needed to identify a documented root joint.
   - For the PhysX variant, inspect any reported non-adjacent collider pairs and adjacency from PhysX joints.
   - Resolve BA.002 only with an approved collider strategy, such as simplified collision geometry, collider clearance adjustment, or excluding a non-critical loop outside the articulation through the appropriate joint feature.
8. Rerun the same profile validation gate, or the narrowest available FET024 validation gate. For PhysX BA.002, record whether PhysX runtime contact reporting was actually available.
9. Summarize the stage as passed, failed, skipped, or blocked. Stop when FET024 passes or the next FET024 failure requires root intent, topology repair, collider redesign, or missing PhysX runtime validation.

## Examples

Example request:

```text
Repair FET024 base articulation root placement failures on a robot USD asset.
```

Expected result summary:

```text
staged_asset: repaired copy or output directory
validation: selected feature/profile gate and report path
remaining_failures: next failing requirement IDs, if any
```

## Repair Policy

Make automatic repairs only when the intended result is mechanical and locally verifiable:

- Apply `UsdPhysics.ArticulationRootAPI` when exactly one articulation root candidate is clear from the robot root, root body, root joint, or source metadata.
- Remove duplicate articulation roots only when they plainly duplicate the same mechanism and one canonical root is known.
- Move the articulation root API opinion to the correct staged physics/source layer when doing so preserves the composed API and satisfies source-layer policy.
- Report BA.002 collision pairs and adjacency evidence when the validator or runtime supplies them.

Block and report instead of guessing when:

- There are multiple disconnected articulated mechanisms.
- The asset has joints but no clear root body or root joint.
- Root placement conflicts with FET021 robot type or root-joint pinning.
- Fixing BA.002 would require moving visual geometry, changing joint transforms, or changing default robot pose.
- Collision meshes must be regenerated or simplified and no collider strategy is approved.
- PhysX schemas or contact simulation are unavailable for a PhysX BA.002 check.

## Variant Guidance

For `FET024_BASE_ARTICULATION_NEUTRAL@0.1.0`, the manifest requires `BA.001`: the stage must have exactly one `UsdPhysics.ArticulationRootAPI` application for the articulated asset.

For `FET024_BASE_ARTICULATION_PHYSX@0.1.0`, the manifest depends on the neutral FET024 variant and adds `BA.002`: non-adjacent collision meshes in the articulation hierarchy must not clash at the default pose. Do not treat a PhysX BA.002 pass as meaningful unless the environment can run the needed PhysX contact or validator check; if the current checker cannot produce collision pairs, record the limitation.

## Validation Handoff

Preserve reports under the staged output directory. If the Physical AI Skill Hub validation commands are available, use the same profile gate that exposed the failure:

```bash
uv run --python 3.12 validate-simready-profile <staged-usd> \
  --profile <profile> \
  --profile-version <version> \
  --foundation-root <simready-foundation-root> \
  --foundation-spec-root <simready-foundation-root>/nv_core/sr_specs/docs \
  --report <output-root>/simready-profile-after-fet024.json
```

Count this skill as successful when the selected FET024 variant passes, even if the full Robot-Body profile still fails on driven joints, robot core, or Isaac composition. Report those remaining failures as handoff work for their own features.

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
| `fet024_variant` | Selected FET024 feature ID and version. |
| `articulation_root` | Chosen prim with `UsdPhysics.ArticulationRootAPI`. |
| `root_selection_evidence` | Why this prim is the correct articulation root. |
| `removed_roots` | Extra articulation roots removed or left blocked. |
| `collision_pairs` | Non-adjacent collider pairs reported for BA.002. |
| `collision_repairs` | Collider clearance, approximation, or policy changes made. |
| `requirements_repaired` | Requirement IDs changed by this skill. |
| `requirements_blocked` | Requirement IDs that need root intent, topology, collider strategy, or PhysX runtime validation. |
| `validation_report` | Path to the rerun validation report. |
| `next_step` | Usually the next failing Robot-Body feature or a blocked FET024 requirement. |

Keep the user-facing summary short: what articulation root changed, whether PhysX collision clearance was checked, what still fails, and the first validation gate that blocks progress.
