---
name: simready-foundation-conform-fet-007-nonvisual-materials
description: "Use for repairing SimReady nonvisual sensor material attributes on bound USD materials."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - materials
---


# SimReady Conform FET-007 Nonvisual Materials

## Purpose
Use this workflow skill when the selected profile, validation report, or user request targets `FET007_BASE_NEUTRAL` non-visual sensor material attributes. FET007 authors and repairs sensor-facing material classification on bound `UsdShade.Material` prims so radar, lidar, thermal, and related RTX sensor simulations can reason about surfaces beyond visible shader appearance.

This is a material-semantics repair skill, not a shader-generation skill. Work on a staged copy under the requested output directory, preserve existing visual material bindings, and stop at the first FET007 issue that needs material identity or user judgement.

FET007 is not currently used by the default prop robotics profiles in `profiles.toml`. When a profile does not include FET007, run this skill only when the user explicitly asks for non-visual sensor material conformance or supplies a profile/workflow that includes `FET007_BASE_NEUTRAL`.

## Prerequisites

Read the source-of-truth files named below before editing. Work on staged outputs where the skill requires them, and keep validation evidence with the result.

## Source of Truth

Before changing an asset, load the selected FET007 manifest and requirement docs:

- `nv_core/sr_specs/docs/features/FET_007_base_neutral-0.2.0-nonvisual_materials.json`
- `nv_core/sr_specs/docs/features/FET_007-nonvisual_materials.md`
- `nv_core/sr_specs/docs/capabilities/nonvisual_sensors/nonvisual_materials/capability-nonvisual_materials.md`
- `nv_core/sr_specs/docs/capabilities/nonvisual_sensors/nonvisual_materials/requirements.md`
- `nv_core/sr_specs/docs/capabilities/nonvisual_sensors/nonvisual_materials/validation.py`

Treat the selected JSON manifest as authoritative for the required IDs. If the markdown, manifest, validator, or report disagree on allowed values or requirement behavior, follow the current validation report and call out the mismatch in the stage summary.

For per-requirement repair details, read `references/fet007-requirements.md` when a FET007 validation report or inspection identifies matching failures.

## Inputs

Collect these before editing:

| Input | Requirement |
|---|---|
| `usd_asset` | Required `.usd`, `.usda`, `.usdc`, or unpacked USD-family asset to repair. |
| `output_root` | Required or inferred folder for staged assets and reports. |
| `simready_profile` | Profile being validated, if one includes FET007. |
| `profile_version` | Profile version, if supplied by the user or validation command. |
| `validation_report` | Preferred JSON or markdown report from the failing profile or feature validation gate. |
| `fet007_variant` | Selected feature ID and version, currently `FET007_BASE_NEUTRAL@0.2.0`. |
| `material_evidence` | Source DCC material metadata, visual material names, shader parameters, property reports, render review, or user-supplied material classifications. |
| `classification_policy` | User-approved defaults or mappings for unknown materials, coatings, and special attributes. |

## Instructions

Use this checklist when changing the repository:

1. Confirm the input asset exists and determine whether FET007 is actually selected by the profile or explicitly requested by the user.
2. Parse the validation report and filter to FET007/NVM failures. Do not repair visual shader, texture, rigid-body, physics-material, or grasp issues in this skill.
3. Load the selected FET007 manifest version and the requirement repair map.
4. Create a staged output folder under `output_root`; do not mutate the source unless the user explicitly asks for in-place repair.
5. Inspect the stage before editing:
   - default prim and composed payload/reference boundaries
   - renderable `UsdGeom.Gprim` and `UsdGeom.Subset` prims with computed purpose `default` or `render`
   - computed full-purpose material bindings for those prims
   - bound and unbound `UsdShade.Material` prims
   - existing `omni:simready:nonvisual:base`, `omni:simready:nonvisual:coating`, and `omni:simready:nonvisual:attributes`
   - time samples on those attributes
   - visual material evidence such as shader metallic, opacity, diffuse color, material names, texture names, and source DCC metadata
6. Decide the non-visual material classification before authoring:
   - Use explicit source or user-supplied material labels first.
   - Use strong visual-material evidence only when the mapping is obvious and allowed by the current validator.
   - Use user-approved defaults for generic classes such as `plastic`, `steel`, `rubber`, `wood`, `fabric`, or `clear_glass`.
   - Block when the real material is not representable by the allowed values, or when multiple classes are plausible.
7. Apply repairs in this order:
   - Remove, move, or bind orphaned non-visual material attributes only when the material-binding intent is clear.
   - Add or fix `omni:simready:nonvisual:base` from explicit material evidence.
   - Add or fix `omni:simready:nonvisual:coating`, defaulting to `none` only when no coating evidence exists and that policy is approved.
   - Add or fix `omni:simready:nonvisual:attributes`, using `["none"]` or an empty token array only when no special sensor attributes are intended by policy.
   - Remove time samples from non-visual attributes only after preserving one intended default value.
   - Re-check consistency with the visual material semantics.
8. Rerun the same validation gate when a profile includes FET007, or the narrowest available Foundation/OAV capability check for non-visual materials. If no executable FET007 gate is available, report the USD inspection results and the validation gap.
9. Summarize the stage as passed, failed, skipped, or blocked. Stop when FET007 passes or the next FET007 failure requires material identity, sensor-response policy, visual review, or source-material data.

## Examples

Example request:

```text
Repair FET007 nonvisual sensor material attributes on a USD asset.
```

Expected result summary:

```text
staged_asset: repaired copy or output directory
validation: selected feature/profile gate and report path
remaining_failures: next failing requirement IDs, if any
```

## Repair Policy

Make automatic repairs only when the intended result is mechanical and locally verifiable:

- Fix attribute type names to `token` or `token[]` when the value is already valid.
- Replace invalid token values with a clear approved mapping from source material evidence.
- Remove time samples and author a default value when one sampled value is clearly the intended static material label.
- Move non-visual attributes from an unbound duplicate material to the bound material only when the duplicate relationship is obvious.
- Remove non-visual attributes from a clearly orphaned scratch material only when that material is not referenced or bound.

Block and report instead of guessing when:

- A material has no reliable source classification.
- A visual material name or shader color is too generic to identify a sensor material class.
- The asset material is outside the current allowed FET007 value list.
- The validator and docs disagree and the repair would risk making sensor semantics less truthful.
- A material appears visually inconsistent with the proposed non-visual class.
- The staged asset has no bound visual materials and the user did not ask to create visual materials first.

## Classification Guidance

FET007 values are semantic labels, not visual decoration. Do not choose them just to satisfy the validator.

Use the current validator value list for pass/fail decisions. Notable current values include:

- Base examples: `aluminum`, `steel`, `oxidized_steel`, `iron`, `plastic`, `rubber`, `wood`, `fabric`, `leather`, `clear_glass`, `frosted_glass`, `concrete`, `brick`, `stone`, `water`, `snow`, `ice`, `calibration_lambertian`
- Coating values: `none`, `paint`, `clearcoat`, `paint_clearcoat`
- Attribute values: `none`, `emissive`, `retroreflective`, `single_sided`, `visually_transparent`

Common consistency checks:

- Metallic visual materials should map to a metal base such as `steel`, `aluminum`, `iron`, `brass`, or `bronze`.
- Transparent visual materials should usually use a glass-like base and include `visually_transparent`.
- Painted materials should use a base material plus `paint` or `paint_clearcoat`.
- Rubber-like dark flexible surfaces should use `rubber`, not generic `plastic`, when evidence supports it.
- Emissive visual materials should include `emissive`; road reflectors and similar objects may include `retroreflective`.

## Validation Handoff

Preserve reports under the staged output directory. If a selected profile includes FET007 and the Physical AI Skill Hub validation commands are available, use the same profile gate that exposed the failure:

```bash
uv run --python 3.12 validate-simready-profile <staged-usd> \
  --profile <profile> \
  --profile-version <version> \
  --foundation-root <simready-foundation-root> \
  --foundation-spec-root <simready-foundation-root>/nv_core/sr_specs/docs \
  --report <output-root>/simready-profile-after-fet007.json
```

If no selected profile includes FET007, do not mutate `profiles.toml` just to test the skill. Run the available non-visual materials capability validator directly if the local environment exposes it; otherwise report the deterministic USD inspection and note that profile validation cannot exercise FET007 until a profile selects it.

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
| `fet007_variant` | Selected FET007 feature ID and version. |
| `material_evidence` | Source used for non-visual classification. |
| `classified_materials` | Bound material prims and authored base/coating/attribute values. |
| `unbound_material_repairs` | Orphaned attribute fixes or bindings changed for NVM.004. |
| `time_sample_repairs` | Attributes changed for NVM.006. |
| `requirements_repaired` | Requirement IDs changed by this skill. |
| `requirements_blocked` | Requirement IDs that need material identity, source data, or user judgement. |
| `validation_report` | Path to the rerun validation or inspection report. |
| `next_step` | Usually run FET007-capable validation or collect missing material evidence. |

Keep the user-facing summary short: which materials were classified, what evidence justified the values, what validation could run, and what remains blocked.
