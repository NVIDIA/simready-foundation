---
name: simready-foundation-conform-fet-021-robot-core
description: "Use for repairing SimReady robot core layout, thumbnails, robot schema, relationships, and root joint pinning."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - robotics
---


# SimReady Conform FET-021 Robot Core

## Purpose
Use this workflow skill when the selected profile, validation report, or user request targets `FET021_ROBOT_CORE_RUNNABLE` or `FET021_ROBOT_CORE_ISAAC`. FET021 repairs robot identity, folder/package layout, robot schema metadata, and root-joint pinning expectations for robot-body profiles.

This is a robot-core repair skill, not a full robot physics authoring skill. Work on a staged copy under the requested output directory, preserve existing articulation and joint semantics, and stop at the first FET021 issue that needs robot type, link/joint topology, physics-layer restructuring, thumbnail imagery, or Isaac schema availability.

## Prerequisites

Read the source-of-truth files named below before editing. Work on staged outputs where the skill requires them, and keep validation evidence with the result.

## Source of Truth

Before changing an asset, load the exact FET021 manifest selected by the profile:

- `nv_core/sr_specs/docs/features/FET_021_robot_core_runnable_0.2.0.json`
- `nv_core/sr_specs/docs/features/FET_021-robot_core_isaac-0.2.0.json`
- `nv_core/sr_specs/docs/features/FET_021-robot_core_isaac-0.1.0.json`
- `nv_core/sr_specs/docs/features/FET_021-robot_core.md`
- `nv_core/sr_specs/docs/capabilities/isaac_sim/robot_core/requirements.md`
- `nv_core/sr_specs/docs/capabilities/isaac_sim/robot_core/validation.py`

Treat the selected JSON manifest as authoritative for the required IDs. If the markdown, manifest, validator, or report disagree on a requirement ID or allowed value, follow the validation report for the current gate and call out the mismatch in the stage summary.

For per-requirement repair details, read `references/fet021-requirements.md` when a FET021 validation report or inspection identifies matching failures.

## Inputs

Collect these before editing:

| Input | Requirement |
|---|---|
| `usd_asset` | Required robot `.usd`, `.usda`, `.usdc`, or unpacked USD-family asset to repair. |
| `output_root` | Required or inferred folder for staged assets and reports. |
| `simready_profile` | Robot profile being validated, usually `Robot-Body-Runnable` or `Robot-Body-Isaac`. |
| `profile_version` | Profile version, if supplied by the user or validation command. |
| `validation_report` | Preferred JSON or markdown report from the failing profile or feature validation gate. |
| `fet021_variant` | Selected feature ID and version, such as `FET021_ROBOT_CORE_RUNNABLE@0.2.0` or `FET021_ROBOT_CORE_ISAAC@0.2.0`. |
| `robot_type` | Required before repairing RC.008 or RC.009. Must be a valid schema value and must not be `Default`. |
| `link_and_joint_roots` | Existing robot link and joint prims or source topology used to populate robot relationships. |
| `physics_layer_policy` | Existing `_physics.usd` layer path or user-approved staging strategy for moving physics opinions. |
| `thumbnail_source` | Existing or generated representative thumbnail when RC.004 is in scope. |

## Instructions

Use this checklist when changing the repository:

1. Confirm the input asset exists and determine whether the selected profile uses the runnable or Isaac FET021 variant.
2. Parse the validation report and filter to FET021/RC failures. Do not repair driven joints, articulation root, collider approximation, or Isaac composition failures in this skill unless the RC failure directly depends on them.
3. Load the selected FET021 manifest version and the requirement repair map.
4. Create a staged output folder under `output_root`; do not mutate the source unless the user explicitly asks for in-place repair.
5. Inspect the stage before editing:
   - root layer path and robot folder layout
   - default prim, robot root prim, model metadata, and stage units
   - applied `IsaacRobotAPI` or equivalent Isaac robot schema token on the default prim
   - `isaac:namespace`, `isaac:robotType`, `isaac:physics:robotLinks`, and `isaac:physics:robotJoints`
   - all `UsdPhysics.Joint` prims, their body targets, and whether body targets have `RigidBodyAPI`
   - layer stack, sublayers, references, payloads, and where physics schemas and `physics:*` attributes are authored
   - thumbnail folder and expected thumbnail names
6. Apply repairs in this order:
   - Stage into a compliant robot folder/name layout when RC.003 fails.
   - Remove or isolate unexpected root-folder files only in the staged copy when RC.001 fails.
   - Add or copy thumbnail files when RC.004 is selected and a representative source image is available.
   - Repair robot schema metadata and relationships when link and joint prims are unambiguous.
   - Repair `isaac:robotType` only from explicit source data or user approval.
   - Repair root-joint pinning only after robot type and root joint order are confirmed.
   - Move physics attributes and schemas into `_physics.usd` only when the layer split can be performed without changing composed physics behavior.
7. Rerun the same profile validation gate, or the narrowest available FET021 validation gate.
8. Summarize the stage as passed, failed, skipped, or blocked. Stop when FET021 passes or the next FET021 failure requires robot topology, robot type, layer restructuring, thumbnail generation, or Isaac schema tooling.

## Examples

Example request:

```text
Repair FET021 robot core failures on a Robot-Body-Runnable USD asset.
```

Expected result summary:

```text
staged_asset: repaired copy or output directory
validation: selected feature/profile gate and report path
remaining_failures: next failing requirement IDs, if any
```

## Repair Policy

Make automatic repairs only when the intended result is mechanical and locally verifiable:

- Stage `Manufacturer/robot/robot.usd` or `Manufacturer/robot/version/robot.usd` style output when folder/file naming is the only issue.
- Create a clean staged folder containing only the interface layer and referenced subfolders; never delete source files outside the staged output.
- Copy an existing representative thumbnail into `.thumbs/256x256/` when RC.004 is selected.
- Populate `isaac:physics:robotLinks` and `isaac:physics:robotJoints` from existing unambiguous rigid body links and joint prims.
- Apply or repair robot schema metadata only when the Isaac robot schema is available or the asset already uses the exact schema pattern.
- Remove time/session/override opinions only by moving them to the appropriate source layer in the staged copy.

Block and report instead of guessing when:

- The robot type is unknown or could be more than one allowed value.
- The root joint order is ambiguous.
- Link or joint prims are missing, duplicated, or not already authored by earlier robot physics features.
- Moving physics schemas or attributes across layers would alter composition strength, variants, references, or payload behavior.
- Isaac robot schemas are unavailable in the local USD environment and no reliable existing schema token is present.
- A thumbnail must be generated but no renderable robot view or screenshot source is available.

## Variant Guidance

For `FET021_ROBOT_CORE_RUNNABLE@0.2.0`, the manifest requires `RC.003`, `RC.007`, `RC.008`, and `RC.009`. Do not add Isaac-only packaging requirements such as clean folder, thumbnail, or physics source-layer checks unless validation reports them separately.

For `FET021_ROBOT_CORE_ISAAC@0.2.0`, the manifest requires `RC.001`, `RC.003`, `RC.004`, `RC.005`, `RC.006`, `RC.007`, `RC.008`, and `RC.009`. Isaac repair should preserve modular composition and keep physics opinions in the `_physics.usd` layer expected by the validator.

For `FET021_ROBOT_CORE_ISAAC@0.1.0`, the manifest does not include `RC.008` or `RC.009`. Do not author robot type or root-joint pinning solely for that older feature version unless the user requests an upgrade or another selected feature requires it.

## Validation Handoff

Preserve reports under the staged output directory. If the Physical AI Skill Hub validation commands are available, use the same profile gate that exposed the failure:

```bash
uv run --python 3.12 validate-simready-profile <staged-usd> \
  --profile <profile> \
  --profile-version <version> \
  --foundation-root <simready-foundation-root> \
  --foundation-spec-root <simready-foundation-root>/nv_core/sr_specs/docs \
  --report <output-root>/simready-profile-after-fet021.json
```

Count this skill as successful when the selected FET021 variant passes, even if the full Robot-Body profile still fails on driven joints, articulation, or Isaac composition. Report those remaining failures as handoff work for their own features.

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
| `fet021_variant` | Selected FET021 feature ID and version. |
| `robot_root` | Default prim and robot root prim. |
| `robot_type` | Authored or confirmed `isaac:robotType`. |
| `robot_links` | Relationship targets after repair. |
| `robot_joints` | Relationship targets after repair and chosen root joint. |
| `layer_repairs` | Physics attributes or schemas moved to `_physics.usd`. |
| `package_repairs` | Folder, naming, clean-folder, or thumbnail changes. |
| `requirements_repaired` | Requirement IDs changed by this skill. |
| `requirements_blocked` | Requirement IDs that need robot type, topology, thumbnail, or layer intent. |
| `validation_report` | Path to the rerun validation report. |
| `next_step` | Usually the next failing Robot-Body feature or a blocked FET021 requirement. |

Keep the user-facing summary short: what robot-core data changed, which FET021 variant was validated, what still fails, and the first validation gate that blocks progress.
