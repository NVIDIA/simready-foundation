---
name: simready-foundation-conform-fet-006-materials
description: "Use for repairing SimReady material bindings, USDPreview or MDL shaders, texture paths, sizes, and color spaces."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - materials
---


# SimReady Conform FET-006 Materials

## Purpose
Use this workflow skill after Core, Minimal, physics, and grasp requirements are already in a reasonable state and the next profile validation gate is `FET006_BASE_MDL` or `FET006_BASE_USDPREVIEW`. It repairs material conformance on a staged USD asset while preserving visual intent, payload portability, and profile-specific material requirements.

This is an authoring and repair skill, not the final validator. Work on a staged copy under the requested output directory, rerun the same validation gate after each repair stage, and stop at the first remaining FET006 validation failure that needs material identity, visual design, texture replacement, or external material assets.

## Prerequisites

Read the source-of-truth files named below before editing. Work on staged outputs where the skill requires them, and keep validation evidence with the result.

## Source of Truth

Before changing an asset, load the exact FET006 manifest selected by the profile:

- `nv_core/sr_specs/docs/features/FET_006_base_mdl-0.1.0-mdl_materials.json`
- `nv_core/sr_specs/docs/features/FET_006_base_usdpreview-0.1.0-usdpreview_materials.json`
- `nv_core/sr_specs/docs/features/FET_006-materials.md`
- `nv_core/sr_specs/docs/capabilities/visualization/materials/requirements.md`
- `nv_core/sr_specs/docs/capabilities/visualization/materials/validation.py`

Treat the selected JSON manifest as authoritative for the required IDs. If the markdown, manifest, validator, or report disagree on a requirement ID, follow the validation report for the current gate and call out the mismatch in the stage summary.

For per-requirement repair details, read `references/fet006-requirements.md` when a FET006 validation report or inspection identifies matching failures.

## Inputs

Collect these before editing:

| Input | Requirement |
|---|---|
| `usd_asset` | Required `.usd`, `.usda`, `.usdc`, or unpacked USD-family asset to repair. |
| `output_root` | Required or inferred folder for staged assets and reports. |
| `simready_profile` | Profile being validated, such as `prop-robotics-neutral` or `prop-robotics-physx`. |
| `profile_version` | Profile version, if supplied by the user or validation command. |
| `validation_report` | Preferred JSON or markdown report from the failing profile or feature validation gate. |
| `fet006_variant` | Selected feature ID and version, such as `FET006_BASE_MDL@0.1.0` or `FET006_BASE_USDPREVIEW@0.1.0`. Infer from the profile when possible. |
| `material_source` | Existing materials, source DCC data, user-approved default material policy, or a material-assignment output. Do not invent material identity silently. |
| `texture_root` | Optional folder containing referenced texture assets that may need staging, inspection, or relative path repair. |
| `mdl_policy` | Whether existing MDL materials may be repaired, copied into the package, or replaced by a user-approved material. |

## Instructions

Use this checklist when changing the repository:

1. Confirm the input asset exists and that earlier gates needed by the selected profile are already staged. For a prop workflow, FET000, FET001, FET003, and FET005 should usually pass before FET006.
2. Parse the validation report and filter to FET006 failures. Do not repair unrelated later profile features in this skill.
3. Load the selected FET006 manifest version and the requirement repair map.
4. Create a staged output folder under `output_root`; do not mutate the source unless the user explicitly asks for in-place repair.
5. Inspect the stage before editing:
   - default prim, payload boundaries, references, sublayers, and relative asset anchors
   - renderable `UsdGeomGprim` prims with `purpose` set to default or render
   - existing `UsdShade.MaterialBindingAPI` relationships, inherited bindings, collection bindings, and bound material paths
   - `UsdShade.Material` and `UsdShade.Shader` prims, surface outputs, shader IDs, and implementation-source metadata
   - MDL source assets, material identifiers, local files, and package-relative paths
   - texture asset paths, dimensions when tooling is available, color-space metadata, and normal-map scale/bias settings
6. Decide the material strategy before authoring:
   - Prefer preserving and repairing existing valid materials.
   - Bind existing valid materials to unbound renderable geometry when the intended assignment is clear.
   - Create a simple USDPreviewSurface fallback only when the selected variant allows it and the user or workflow policy accepts a neutral default.
   - For MDL variants, do not fabricate an MDL material or material identity. Use existing MDL assets, a material-assignment output, or user-provided material data.
7. Apply repairs in this order:
   - Repair material binding scope and missing bindings before changing shader internals.
   - Repair USDPreviewSurface attribute types and token values when the intended value is mechanical.
   - Repair MDL schema fields and source asset paths when the source asset and material identifier are clear.
   - Repair shader input types and invalid numeric values only when conversion is lossless and semantically obvious.
   - Repair texture color-space metadata when the texture channel semantics are known.
   - Block instead of silently downscaling, replacing, or deleting oversized textures unless the user approved the visual change.
8. Rerun the same profile validation gate, or the narrowest available FET006 validation gate.
9. Summarize the stage as passed, failed, skipped, or blocked. Stop when FET006 passes or the next FET006 failure requires material identity, source texture edits, MDL libraries, visual judgement, or a material-assignment service.

## Examples

Example request:

```text
Repair FET006 material binding and shader failures on a USD asset.
```

Expected result summary:

```text
staged_asset: repaired copy or output directory
validation: selected feature/profile gate and report path
remaining_failures: next failing requirement IDs, if any
```

## Repair Policy

Make automatic repairs only when the intended result is mechanical and locally verifiable:

- Bind an already-authored material to unbound renderable geometry when hierarchy, naming, or an existing binding pattern makes the target material clear.
- Move or copy material definitions into the same payload scope as the binding when this preserves the composed appearance and fixes portability.
- Add or fix `UsdPreviewSurface` shader attributes only when the required type, token, or default value is unambiguous.
- Convert deprecated MDL schema fields to the current schema when the MDL file and material identifier are already present.
- Fix relative MDL or texture paths when the target file exists and the package anchor is clear.
- Set texture color-space metadata for known PBR channels such as albedo/base color, roughness, metallic, normal, opacity, displacement, or emission.
- Remove NaN or Inf shader input values only by replacing them with a documented source value or user-approved default.

Block and report instead of guessing when:

- The asset has no material source and the user did not request material prediction or default material assignment.
- Multiple materials could plausibly apply to the same geometry.
- The selected profile requires MDL and no valid MDL material or material-assignment output is available.
- Texture resizing, format conversion, or replacement would change visible appearance.
- Shader input type repair would require interpreting a custom shader without SDR or MDL specification data.
- A color-space repair is ambiguous because the texture channel semantics cannot be determined from shader wiring, naming, or source metadata.

## Variant Guidance

For `FET006_BASE_USDPREVIEW`, keep repairs in standard OpenUSD `UsdShade` and `UsdPreviewSurface` patterns. Every renderable GPrim must compute a material binding. `UsdPreviewSurface` attributes must use the expected USD types, token values, and non-time-sampled token opinions.

For `FET006_BASE_MDL`, preserve MDL materials when the profile selects them. Current docs and validators expect `info:implementationSource = "sourceAsset"`, `info:mdl:sourceAsset`, and `info:mdl:materialType`; current MDL input validation may also use `info:mdl:sourceAsset:subIdentifier` to query MDL parameter specs. If both are needed for the local validator and runtime, author them consistently from the same material identifier and note the validator/schema nuance in the report.

## Validation Handoff

Preserve reports under the staged output directory. If the Physical AI Skill Hub validation commands are available, use the same profile gate that exposed the failure:

```bash
uv run --python 3.12 validate-simready-profile <staged-usd> \
  --profile <profile> \
  --profile-version <version> \
  --foundation-root <simready-foundation-root> \
  --foundation-spec-root <simready-foundation-root>/nv_core/sr_specs/docs \
  --report <output-root>/simready-profile-after-fet006.json
```

Count this skill as successful when the selected FET006 variant passes, even if the full profile still fails on later features. Report those remaining failures as handoff work for their own skills.

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
| `fet006_variant` | Selected FET006 feature ID and version. |
| `material_strategy` | Existing material repair, user-approved default, material-assignment output, or blocked. |
| `bound_materials` | Renderable prims or scopes whose material bindings changed. |
| `shader_repairs` | USDPreviewSurface or MDL shader/schema fields changed. |
| `texture_repairs` | Texture paths, dimensions, or color-space metadata changed. |
| `requirements_repaired` | Requirement IDs changed by this skill. |
| `requirements_blocked` | Requirement IDs that need material identity, source assets, texture editing, or user judgement. |
| `validation_report` | Path to the rerun validation report. |
| `next_step` | Usually the next failing profile feature or a blocked FET006 requirement. |

Keep the user-facing summary short: what material data changed, which FET006 variant was validated, what still fails, and the first validation gate that blocks progress.
