---
name: simready-foundation-conform-fet-023-robot-materials
description: "Use for repairing SimReady robot material organization under the top-level Looks scope."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - robotics
---


# SimReady Conform FET-023 Robot Materials

## Purpose
Use this workflow skill when the selected profile, validation report, or user request targets `FET023_ROBOT_MATERIALS`. FET023 repairs robot material organization for Isaac Sim by centralizing material definitions as direct children of the top-level `Looks` scope and eliminating nested material prims.

This is a material-organization repair skill, not a material-authoring skill. It should preserve existing materials, shader networks, texture paths, and visual appearance while changing where material prims live and what geometry bindings target.

FET023 is not currently used by the default Robot-Body profiles in `profiles.toml`. When a profile does not include FET023, run this skill only when the user explicitly asks for robot material organization conformance or supplies a profile/workflow that includes `FET023_ROBOT_MATERIALS`.

## Prerequisites

Read the source-of-truth files named below before editing. Work on staged outputs where the skill requires them, and keep validation evidence with the result.

## Source of Truth

Before changing an asset, load the selected FET023 manifest and requirement docs:

- `nv_core/sr_specs/docs/features/FET_023-robot_materials-0.1.0.json`
- `nv_core/sr_specs/docs/features/FET_023-robot_materials.md`
- `nv_core/sr_specs/docs/capabilities/isaac_sim/robot_materials/requirements.md`
- `nv_core/sr_specs/docs/capabilities/isaac_sim/robot_materials/validation.py`

Treat the selected JSON manifest as authoritative for the required IDs. If the markdown, manifest, validator, or report disagree on behavior, follow the validation report for the current gate and call out the mismatch in the stage summary.

For per-requirement repair details, read `references/fet023-requirements.md` when a FET023 validation report or inspection identifies matching failures.

## Inputs

Collect these before editing:

| Input | Requirement |
|---|---|
| `usd_asset` | Required robot `.usd`, `.usda`, `.usdc`, or unpacked USD-family asset to repair. |
| `output_root` | Required or inferred folder for staged assets and reports. |
| `simready_profile` | Profile being validated, if one includes FET023. |
| `profile_version` | Profile version, if supplied by the user or validation command. |
| `validation_report` | Preferred JSON or markdown report from the failing profile or feature validation gate. |
| `fet023_variant` | Selected feature ID and version, currently `FET023_ROBOT_MATERIALS@0.1.0`. |
| `material_move_policy` | Whether material prims may be moved within the staged asset, copied with redirects, or blocked for user review. |

## Instructions

Use this checklist when changing the repository:

1. Confirm the input asset exists and determine whether FET023 is selected by the profile or explicitly requested by the user.
2. Parse the validation report and filter to FET023/RM failures. Do not repair shader schema, texture properties, material semantics, robot core, or physics issues in this skill.
3. Load the selected FET023 manifest version and the requirement repair map.
4. Create a staged output folder under `output_root`; do not mutate the source unless the user explicitly asks for in-place repair.
5. Inspect the stage before editing:
   - default prim and expected top-level `/<defaultPrim>/Looks` scope
   - all composed `UsdShade.Material` prim paths under the default prim
   - material prims that are children or descendants of other material prims
   - material prims outside `/<defaultPrim>/Looks`
   - direct children of `/<defaultPrim>/Looks`
   - all material binding relationships, collection bindings, and shader connections that target material or shader paths inside material subtrees
   - layer stack and authored layer for each material prim, binding, and connection that may need rewriting
6. Plan moves before editing:
   - Choose one canonical target path per material under `/<defaultPrim>/Looks/<MaterialName>`.
   - Preserve the whole material subtree, including child shaders and supporting scopes.
   - Resolve name collisions deterministically, for example by appending `_01`, `_02`, or a sanitized source-scope suffix.
   - Build an old-path to new-path map for every moved material and every descendant prim.
7. Apply repairs in this order:
   - Create `/<defaultPrim>/Looks` as a `Scope` if it does not exist.
   - Move or copy material subtrees into direct children of `Looks`.
   - Flatten nested materials by moving each nested material subtree to its own direct child of `Looks`.
   - Update material binding relationships to target the moved material paths.
   - Update shader connections and relationship targets that point inside moved material subtrees.
   - Remove old local material prims only after all references to them are updated and the new material paths compose correctly.
8. Rerun the same validation gate when a profile includes FET023, or the narrowest available RobotMaterials validator. If no executable FET023 gate is available, report the deterministic USD inspection results and the validation gap.
9. Summarize the stage as passed, failed, skipped, or blocked. Stop when FET023 passes or the next FET023 failure requires cross-layer material moves, referenced asset edits, or material identity decisions outside this skill.

## Examples

Example request:

```text
Repair FET023 robot material organization failures by flattening materials under Looks.
```

Expected result summary:

```text
staged_asset: repaired copy or output directory
validation: selected feature/profile gate and report path
remaining_failures: next failing requirement IDs, if any
```

## Repair Policy

Make automatic repairs only when the intended result is mechanical and locally verifiable:

- Create the top-level `Looks` scope under the default prim.
- Move locally-authored material prim subtrees under `/<defaultPrim>/Looks`.
- Flatten nested material prims by preserving each nested material as a separate direct child of `Looks`.
- Update direct and collection material bindings that target moved materials.
- Update connection targets inside moved material subtrees when absolute paths changed.
- Preserve existing shader attributes, texture asset paths, non-visual material attributes, physics material data, and custom metadata.

Block and report instead of guessing when:

- A material prim is authored in a referenced or payloaded asset that should not be edited from the current package.
- Moving a material would cross composition boundaries, variants, or layers in a way that changes strength or asset ownership.
- Two materials collide by name and there is no stable way to preserve both without changing external bindings.
- The material subtree contains authored relationships or connections whose target rewrite is ambiguous.
- A material binding points to a missing material or an invalid path; hand off to FET006 or material assignment if material creation is needed.

## Validation Handoff

Preserve reports under the staged output directory. If a selected profile includes FET023 and the Physical AI Skill Hub validation commands are available, use the same profile gate that exposed the failure:

```bash
uv run --python 3.12 validate-simready-profile <staged-usd> \
  --profile <profile> \
  --profile-version <version> \
  --foundation-root <simready-foundation-root> \
  --foundation-spec-root <simready-foundation-root>/nv_core/sr_specs/docs \
  --report <output-root>/simready-profile-after-fet023.json
```

If no selected profile includes FET023, do not mutate `profiles.toml` just to test the skill. Run the available RobotMaterials capability validator directly if the local environment exposes it; otherwise report the USD inspection results and note that profile validation cannot exercise FET023 until a profile selects it.

Count this skill as successful when `FET023_ROBOT_MATERIALS` passes or when inspection proves there are no nested materials and every local material under the default prim is a direct child of `/<defaultPrim>/Looks`.

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
| `profile` and `profile_version` | Validation target, if any. |
| `fet023_variant` | Selected FET023 feature ID and version. |
| `looks_scope` | Top-level Looks scope path. |
| `materials_moved` | Old material paths mapped to new material paths. |
| `bindings_updated` | Material binding relationships retargeted. |
| `connections_updated` | Shader connections or relationships retargeted. |
| `requirements_repaired` | Requirement IDs changed by this skill. |
| `requirements_blocked` | Requirement IDs that need cross-layer edits, external asset ownership, or material creation. |
| `validation_report` | Path to the rerun validation or inspection report. |
| `next_step` | Usually run FET023-capable validation or hand off to FET006/material assignment if material definitions are missing. |

Keep the user-facing summary short: which material paths moved, how bindings were preserved, what validation could run, and what remains blocked.
