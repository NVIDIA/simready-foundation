---
name: simready-foundation-conform-fet-005-simulate-grasp-physics
description: "Use for vision-guided SimReady grasp repair, grasp_identifier curves, and physics-material triage."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - grasp
---


# SimReady Conform FET-005 Simulate Grasp Physics

## Purpose
Use this workflow skill after Core, Minimal, and rigid-body requirements are already in a reasonable state and the next profile validation gate is `FET005_BASE_NEUTRAL`. It adds or repairs a USD grasp vector line that tells a robotic gripper where to grasp the asset.

This is a visual-semantic authoring skill, not a bounding-box shortcut. The grasp line must be chosen from visual evidence of the asset shape and intended grasp behavior, then authored deterministically as a `UsdGeom.BasisCurves` prim.

## Capability Gate

This skill requires a vision-capable agent or model. Before authoring, replacing,
or invoking any script that creates a grasp line, confirm that the current agent
can inspect visual evidence directly, such as renders, screenshots, viewport
captures, or generated mesh previews.

If the current agent cannot use vision, stop immediately. Do not add or repair a
grasp line from bounds, text metadata, file names, validator failures, or user
descriptions alone. Tell the user that FET005 grasp-line repair requires a
vision-capable model/agent and ask them to rerun this skill with vision enabled.

If the current agent can use vision and visual evidence is available, the agent
is expected to choose explicit local-space grasp points from that evidence. Do
not skip authoring merely because the user did not pre-supply points. User
approval is only required when the visual evidence, coordinate mapping, gripper
constraints, or grasp intent remain genuinely ambiguous after inspection.

## Prerequisites

Read the source-of-truth files named below before editing. Work on staged outputs where the skill requires them, and keep validation evidence with the result. This grasp workflow also requires a vision-capable agent or rendered visual evidence.

## Source of Truth

Before changing an asset, load the selected FET005 manifest and requirement docs:

- `nv_core/sr_specs/docs/features/FET_005_base_neutral-0.1.0-simulate_grasp_physics.json`
- `nv_core/sr_specs/docs/features/FET_005-simulate_grasp_physics.md`
- `nv_core/sr_specs/docs/capabilities/physics_bodies/physics_graspable/requirements/graspable-vector-line.md`
- `nv_core/sr_specs/docs/capabilities/physics_bodies/physics_graspable/validation.py`

The current manifest lists `PMT.001` and `GSP.001`. The current FET005 prose and graspable validator focus on `GSP.001`: at least one `BasisCurves` prim under the default prim, named with the `grasp_identifier` prefix, with at least two points. If validation reports `PMT.001`, read `references/fet005-requirements.md` and handle physics-material binding separately from grasp-line placement.

## Inputs

Collect these before editing:

| Input | Requirement |
|---|---|
| `usd_asset` | Required `.usd`, `.usda`, or `.usdc` asset to repair. |
| `output_root` | Required or inferred folder for staged assets and reports. |
| `simready_profile` | Profile being validated, such as `prop-robotics-neutral`. |
| `profile_version` | Profile version, if supplied by the user or validation command. |
| `validation_report` | Preferred JSON or markdown report from the failing profile or feature validation gate. |
| `visual_evidence` | Required renders, screenshots, viewport captures, or generated previews from enough angles to identify the graspable region. |
| `source_visual_asset` | Optional source USD/CAD/mesh used only for visual evidence when the staged SimReady USD has no renderable geometry. |
| `gripper_context` | Optional gripper type, jaw width, approach constraints, and regions to prefer or avoid. |
| `grasp_points` | Final two or more local-space USD points for the grasp line, chosen after visual review. |

## Instructions

Use this checklist when changing the repository:

1. Confirm the input asset exists and that earlier gates needed by the selected profile are already staged. For a prop workflow, FET000 and FET001 should pass; FET003 should usually pass before FET005 because grasping assumes a physical prop.
2. Parse the validation report and filter to `FET005_BASE_NEUTRAL`. If `GSP.001` already passes, do not add duplicate grasp lines.
3. Inspect existing grasp vector prims under the default prim:
   - type is `BasisCurves`
   - name starts with `grasp_identifier`
   - `points` has at least two points
   - curve is under the asset default prim
4. Generate or collect visual evidence before choosing points. Prefer real renders from `render-usd`, Kit, Omniverse viewport screenshots, or existing preview images when available. If no renderer is available, use `assets/scripts/render_grasp_preview.py` to generate a four-panel point-cloud PNG with top, front, side, and isometric views. If the staged USD opens but has no renderable mesh triangles, use the nearest source visual asset from conversion context or the asset fixture/source tree, then record that fallback explicitly. If the current agent cannot inspect the generated or collected images with vision, write a first-class `BLOCKED` report and stop.
5. Use visual reasoning to choose a grasp region:
   - Prefer stable, rigid, central body geometry with enough contact area for opposing gripper fingers.
   - Avoid handles, holes, voids, thin rims, fragile appendages, decorative parts, sharp protrusions, and table-contact bottoms unless the user or asset semantics explicitly say those are intended.
   - For handled containers, prefer the main body or sidewall region, not the handle, unless a handle grasp is explicitly requested.
   - For box-like props, prefer a line across two broad opposing side faces with clearance.
   - For cylindrical props, prefer a diameter across the main body at a stable height, avoiding top and bottom edges.
   - For tools, use the designed grip handle only when it is the intended robotic grasp region.
6. Convert the selected visual grasp into USD local-space points. The line should intersect the graspable geometry and represent the gripper contact/closing axis or agreed runtime convention. If the visual source and staged USD use different units, root transforms, or meter-normalization scales, convert points into the authoring parent's local space and record the conversion note. If the coordinate mapping is uncertain, inspect bounds, xform ops, layer scale, and default-prim transforms before authoring. If explicit points still cannot be chosen, write a `BLOCKED` report with the visual evidence path, the reason points could not be selected, and the exact inputs needed to continue.
7. Stage a copy under `output_root`; do not mutate the source unless the user explicitly asks for in-place repair.
8. Author or replace one `BasisCurves` prim named `grasp_identifier_##` under the default prim, with:
   - `type = "linear"`
   - `curveVertexCounts = [point_count]`
   - `points = [...]`
   - a small display width
   - `purpose = "guide"`
   - visible display color for review
9. Render or inspect the repaired asset again. Confirm the line is visible, intersects the intended region, and is not accidentally placed through an avoided region. When possible, save overlay images or a small decision JSON beside the staged output.
10. Rerun the same profile validation gate, or the narrowest available FET005 validation gate. Stop when FET005 passes or when the remaining FET005 issue requires user or runtime-gripper judgement. If the full profile still fails on another feature, report the first remaining failing gate separately from the FET005 result.

## Authoring Script

Use `assets/scripts/render_grasp_preview.py` to create visual evidence when a renderer or viewport is not available. This script uses USD mesh points and pure-Python PNG output, so it does not require PIL, matplotlib, Kit, or a display server:

```bash
uv run --python 3.12 python <skill-dir>/assets/scripts/render_grasp_preview.py <input-usd> \
  --output <output-root>/grasp-preview.png \
  --report <output-root>/grasp-preview.json
```

After choosing explicit points, rerun the preview with the proposed line overlaid and inspect it before authoring:

```bash
uv run --python 3.12 python <skill-dir>/assets/scripts/render_grasp_preview.py <input-usd> \
  --output <output-root>/grasp-preview-overlay.png \
  --point=-0.010,-0.032,0.050 \
  --point=-0.010,0.032,0.050 \
  --report <output-root>/grasp-preview-overlay.json
```

The preview helper is evidence generation only. It does not choose the grasp
region and does not replace vision review.

Use `assets/scripts/author_grasp_line.py` for deterministic USD authoring after the vision decision has produced explicit points. Prefer `uv run --python 3.12 python` or `python3`; do not assume `python` exists or points to Python 3.10+ on Linux:

```bash
uv run --python 3.12 python <skill-dir>/assets/scripts/author_grasp_line.py <input-usd> \
  --output <staged-output-usd> \
  --parent-prim /<defaultPrim> \
  --name grasp_identifier_01 \
  --point=x0,y0,z0 \
  --point=x1,y1,z1 \
  --source-visual-asset <source-visual-usd-or-mesh> \
  --visual-evidence <render-or-screenshot> \
  --rationale "why this grasp region was selected" \
  --coordinate-note "how source-space points map to authored local points" \
  --report <output-root>/author-grasp-line.json \
  --markdown-report <output-root>/author-grasp-line.md
```

When repair is blocked before explicit points are available, use the same script
to produce a distinguishable `BLOCKED` report instead of a failed repair report:

```bash
uv run --python 3.12 python <skill-dir>/assets/scripts/author_grasp_line.py <input-usd> \
  --output <staged-output-usd> \
  --visual-evidence <render-or-screenshot> \
  --blocked-reason "Vision-capable agent could not choose two unambiguous local-space grasp points from the available evidence." \
  --report <output-root>/author-grasp-line.json \
  --markdown-report <output-root>/author-grasp-line.md
```

If the Physical AI Skill Hub CLI is available, `author-grasp-vectors` can also author explicit points. Do not rely on its bounding-box heuristic unless visual review confirms the generated line is semantically correct for the asset.

The script only authors explicit points. It does not choose the grasp region, render evidence, or infer scale. Use the optional evidence and rationale flags so the report preserves the human/vision decision that led to those points. If no points are supplied, the script returns `BLOCKED` with `requirements_blocked = ["GSP.001"]`; workflow summaries must preserve that status instead of converting it to `FAIL`.

## Vision Policy

Do not use this skill to author a grasp line unless the current agent can inspect
the visual evidence directly. A non-vision agent must report `blocked` for
`GSP.001` repair and should not call `assets/scripts/author_grasp_line.py`.

Do not place the final line from a bounding box alone when the asset has meaningful shape, openings, handles, or multiple plausible grasp regions. A bounding-box line is acceptable only for simple primitives or after render review confirms it intersects the intended graspable body.

If there is no way to see the asset, block and request visual evidence or a specific user-approved grasp region. Passing `GSP.001` with an arbitrary line is not a useful SimReady repair.

If there is a way to see the asset and the current model is vision-capable, make
the repair actionable: inspect the image, choose two or more explicit points,
author the curve, then rerun validation. A statement such as "visual evidence
existed but no user-approved points were supplied" is not sufficient unless the
asset has unresolved ambiguity that the report names precisely.

## Examples

Example request:

```text
Use a vision-capable model to add a FET005 grasp line to a coffee mug USD asset.
```

Expected result summary:

```text
staged_asset: repaired copy or output directory
validation: selected feature/profile gate and report path
remaining_failures: next failing requirement IDs, if any
```

## Validation Handoff

Preserve reports under the staged output directory. If the Physical AI Skill Hub validation commands are available, use:

```bash
uv run --python 3.12 validate-simready-profile <staged-usd> \
  --profile <profile> \
  --profile-version <version> \
  --foundation-root <simready-foundation-root> \
  --foundation-spec-root <simready-foundation-root>/nv_core/sr_specs/docs \
  --report <output-root>/simready-profile-after-fet005.json
```

Count this skill as successful when `FET005_BASE_NEUTRAL` passes, even if the full profile still fails on unrelated features. If `PMT.001` fails, report it as a physics-material binding issue and do not hide it by only adding a grasp line.

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
- `assets/scripts/` contains the deterministic preview and authoring helpers for this skill.
- `references/` contains detailed requirement notes; load only the files needed for the active validation failure.

## Available Scripts

| Script | Purpose | Arguments |
|---|---|---|
| `assets/scripts/render_grasp_preview.py` | Render point-cloud visual evidence and optional line overlays. | `<input-usd>`, `--output`, optional `--point`, optional `--report` |
| `assets/scripts/author_grasp_line.py` | Author explicit vision-selected points as a `grasp_identifier` BasisCurves prim or write a `BLOCKED` report. | `<input-usd>`, `--output` or `--in-place`, `--point`, `--visual-evidence`, `--rationale`, `--coordinate-note`, report paths |

## Summary Format

Report:

| Field | Meaning |
|---|---|
| `input_usd_path` | Original USD path. |
| `output_usd_path` | Latest staged/repaired USD path. |
| `profile` and `profile_version` | Validation target. |
| `fet005_version` | Selected `FET005_BASE_NEUTRAL` manifest version. |
| `visual_evidence` | Renders/screenshots inspected. |
| `grasp_vector_path` | Authored or repaired `BasisCurves` prim. |
| `grasp_points` | Final local-space points. |
| `grasp_rationale` | Why this region is graspable and what was avoided. |
| `status` | `PASS`, `BLOCKED`, or `FAIL`. Preserve `BLOCKED` separately from validation failures. |
| `requirements_repaired` | Requirement IDs changed by this skill. |
| `requirements_blocked` | Requirement IDs that need visual, gripper, material, or runtime-test judgement. |
| `blocked_reasons` and `needed_inputs` | Required when no grasp line is authored. |
| `validation_report` | Path to the rerun validation report. |
| `next_step` | Usually rerun the selected full profile or address the next failing feature. |

Keep the user-facing summary short: what visual evidence was used, where the grasp line was placed, why that region was chosen, and what validation reported.
