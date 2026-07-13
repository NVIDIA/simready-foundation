---
name: simready-foundation-conform-fet-001-minimal
description: "Use for repairing SimReady Minimal assets: units, upAxis, defaultPrim, hierarchy, mesh quality, extents, and origin placement."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - minimal
---


# SimReady Conform FET-001 Minimal

## Purpose
Use this workflow skill after FET000_CORE passes and the next profile validation gate is `FET001_BASE_NEUTRAL`. It brings an existing USD asset toward the Minimal/Base Neutral feature contract while preserving visual scale, hierarchy intent, and source traceability.

This is an authoring and repair skill, not the final validator. Work on a staged copy under the requested output directory, rerun the same validation gate after each repair stage, and stop at the first remaining failing FET001 validation gate.

## Prerequisites

Read the source-of-truth files named below before editing. Work on staged outputs where the skill requires them, and keep validation evidence with the result.

## Source of Truth

Before changing an asset, load the exact FET001 manifest selected by the profile:

- `nv_core/sr_specs/docs/features/FET_001_base_neutral-0.1.0-minimal.json`
- `nv_core/sr_specs/docs/features/FET_001_base_neutral-1.0.0-minimal.json`
- `nv_core/sr_specs/docs/features/FET_001-minimal.md`

Some profiles select `FET001_BASE_NEUTRAL@0.1.0`, while newer profiles may select `1.0.0`. Treat the JSON manifest requirement list as authoritative for the selected profile/version.

For per-requirement repair details, read `references/fet001-requirements.md` when a FET001 validation report or inspection identifies matching failures.

## Inputs

Collect these before editing:

| Input | Requirement |
|---|---|
| `usd_asset` | Required `.usd`, `.usda`, `.usdc`, or unpacked USD-family asset to repair. |
| `output_root` | Required or inferred folder for staged assets and reports. |
| `simready_profile` | Profile being validated, such as `Prop-Robotics-Neutral`. |
| `profile_version` | Profile version, if supplied by the user or validation command. |
| `validation_report` | Preferred JSON or markdown report from the failing profile/feature validation gate. |
| `source_asset` | Original CAD, DCC, URDF, MJCF, or conversion input path, used for provenance. |
| `physical_size_policy` | Whether to preserve physical size. Default to preserve size. |

## Instructions

Use this checklist when changing the repository:

1. Confirm the input asset exists and that FET000_CORE is already passing on the same staged asset. If Core still fails, hand back to `simready-foundation-conform-fet-000-core` first.
2. Parse the validation report and filter to `FET001_BASE_NEUTRAL` failures. Do not repair later profile features in this skill.
3. Load the selected FET001 manifest version and the requirement repair map.
4. Create a staged output folder under `output_root`; do not mutate the source unless the user explicitly asks for in-place repair.
5. Run or inspect minimum USD metadata: stage openability, default prim, root prims, `upAxis`, `metersPerUnit`, composed bounds, mesh/geometry counts, authored references, and used layers.
6. Apply deterministic fixes in this order:
   - Atomic asset/file fixes for `AA.001` and `AA.002`.
   - Hierarchy fixes for `HI.001`, `HI.003`, and `HI.004`.
   - Unit and orientation fixes for `UN.001`, `UN.002`, `UN.006`, and `UN.007`.
   - Minimal visual geometry fixes for `VG.001` or `VG.MESH.001`.
   - Mesh quality fixes for `VG.002`, `VG.014`, `VG.027`, `VG.028`, and `VG.029`.
   - Origin placement fixes for `VG.025` only when the asset placement convention is clear.
7. Rerun the same profile validation gate, or the narrowest available FET001 validation gate.
8. Summarize the stage as passed, failed, skipped, or blocked. Stop when FET001 passes or the next FET001 failure requires upstream conversion, source geometry, or user intent.

## Unit Repair Policy

Treat `UN.007` with extra care. Setting `metersPerUnit = 1.0` without adjusting authored coordinates can change the apparent physical size of an asset.

Default policy:

- Preserve physical size.
- Record the original `metersPerUnit`, composed bounds, default prim, and root transforms before editing.
- If the asset uses millimeters, such as `metersPerUnit = 0.001`, normalize to meter units by scaling authored linear data by `0.001` or by applying an equivalent root-scale normalization in the same staged USD file.
- Recompute authored extents after any geometry-space rescale.
- Validate that the composed bounds in meters are unchanged within a small tolerance.

Prefer these approaches in order:

| Strategy | Use When | Notes |
|---|---|---|
| Re-export from converter with meter units | Conversion options are available and reliable. | Best long-term fix because geometry, metadata, and derived data are generated consistently. |
| Rescale staged USD data | All relevant layers are local and editable. | Multiply points, translate ops, extents, and other linear authored values by `old_meters_per_unit / 1.0`, then set stage `metersPerUnit = 1.0`. |
| Apply root-scale normalization in the same staged USD | The asset root has no existing authored xform ops and the selected FET001 version does not reject a root scale. | Set stage `metersPerUnit = 1.0` and add a root scale op equal to `old_meters_per_unit / 1.0`. This strategy is useful for millimeter- or centimeter-authored converter output when a root scale is acceptable. |
| Create a meter-unit wrapper | The package/validator contract allows a local USD payload reference without violating Core or atomic-asset rules. | Verify `FET000_CORE` and `AA.001` immediately. Current validators may reject extra USD files under `simready_usd` (`NP.005`) or `../payloads/...` references as outside the asset root (`AA.001`). |
| Metadata-only change | The coordinates are already in meters, or the user accepts a physical size change. | Report this explicitly because it can make the asset too large or too small. |

For any asset with `metersPerUnit = 0.001`, a size-preserving single-file repair can set `metersPerUnit = 1.0` and author root op `xformOp:scale:meter_normalization = (0.001, 0.001, 0.001)`, assuming the root transform is otherwise safe to modify.

## Examples

Example request:

```text
Repair FET001_BASE_NEUTRAL minimal stage failures on a staged USD asset.
```

Expected result summary:

```text
staged_asset: repaired copy or output directory
validation: selected feature/profile gate and report path
remaining_failures: next failing requirement IDs, if any
```

## Repair Policy

Make automatic repairs only when the result is mechanical and locally verifiable:

- Set missing `upAxis` to `Z` when the asset is already visually Z-up or when the selected profile requires Z-up.
- Set `defaultPrim` to the single root prim when there is exactly one valid root.
- Wrap multiple roots under a new Xform only when all asset content can be moved or referenced without breaking paths.
- Convert search paths to anchored relative paths only after the dependency is inside the staged asset root.
- Author extents using USD-computed bounds for local editable meshes.
- Normalize or generate mesh normals only when the intended smoothing can be inferred or the converter already produced enough topology to compute them deterministically.
- If adding a root-scale normalization, check for existing root xform ops first. If the root already has meaningful transform ops, preserve order and semantics or use data-space rescaling instead.

Block and report instead of guessing when:

- The feature failure comes from missing or non-mesh geometry that requires upstream conversion.
- Unsupported file types require lossy texture/audio/geometry conversion.
- Winding, normal direction, or origin placement cannot be inferred from local geometry.
- Rescaling would require editing external layers that are not staged with the asset.
- A unit wrapper or payload layout causes `FET000_CORE` or `AA.001` to regress.

## Validation Handoff

Preserve reports under the staged output directory. If the Physical AI Skill Hub validation commands are available, use:

```bash
uv run --python 3.12 validate-usd-minimum <staged-usd> \
  --report <output-root>/minimum-usd-after-fet001.json

uv run --python 3.12 validate-simready-profile <staged-usd> \
  --profile <profile> \
  --profile-version <version> \
  --foundation-root <simready-foundation-root> \
  --foundation-spec-root <simready-foundation-root>/nv_core/sr_specs/docs \
  --report <output-root>/simready-profile-after-fet001.json
```

Count this skill as successful when `FET001_BASE_NEUTRAL` passes, even if the full profile still fails on later features such as rigid bodies, multibody physics, or grasp vectors. Report those remaining failures as handoff work for their own skills.

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
| `fet001_version` | Selected `FET001_BASE_NEUTRAL` manifest version. |
| `requirements_repaired` | Requirement IDs changed by this skill. |
| `requirements_blocked` | Requirement IDs that need user intent or upstream conversion. |
| `scale_preserved` | Whether composed physical bounds were preserved after unit repair. |
| `validation_report` | Path to the rerun validation report. |
| `next_step` | Usually the next failing profile feature. |

Keep the user-facing summary short: what was fixed, whether the asset scale was preserved, what FET001 result validation reported, and the first remaining validation gate.
