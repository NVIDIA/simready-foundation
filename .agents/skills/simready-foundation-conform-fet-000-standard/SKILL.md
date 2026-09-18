---
name: simready-foundation-conform-fet-000-standard
description: "Use for repairing FET_000_STANDARD@0.1.0 Core failures: asset file naming, directory layout, metadata location, relative and resolvable paths, SimReady metadata, and undefined prims."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - core
---


# SimReady Conform FET_000_STANDARD

## Purpose
Use this workflow skill to bring an existing USD asset into conformance with the `FET_000_STANDARD@0.1.0` Core feature contract, then hand the repaired copy back to profile validation.

`FET_000_STANDARD@0.1.0` is the baseline Standard/OpenUSD Core feature. It verifies that an asset has portable file naming, directory layout, path handling, metadata location, resolvable asset paths, required SimReady metadata, and no unsafe undefined prims before higher-level visual, material, physics, robot, or runtime-specific features are applied.

This skill is not the final validator and should not silently mutate source assets. It stages a repaired USD-family asset under the requested output directory, applies deterministic fixes only where safe, and stops when a validation gate still fails or a manual decision is required.

## Prerequisites

Read the source-of-truth files named below before editing. Work on staged outputs where the skill requires them, and keep validation evidence with the result.

## Source of Truth

Before changing an asset, load the exact `FET_000_STANDARD` manifest selected by the profile. In this repo, start with the canonical version:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_000_STANDARD-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_000_STANDARD.md`

This version has no feature dependencies. Its authoritative requirement list is:

- `NP.002`
- `NP.003`
- `NP.004`
- `NP.005`
- `NP.006`
- `NP.007`
- `NP.008`
- `SR.001`
- `HI.010`

If the selected profile names a newer `FET_000_STANDARD` version, use that manifest instead. Treat the JSON requirement list as authoritative when markdown and JSON disagree.

`FET_000_STANDARD` is the neutral Core feature and does not require physics
runtime variants. Runtime physics variant scaffolding (the `RV.*` Runtime
Variants requirements) lives in the separate runtime Core features
`FET_000_PHYSX`, `FET_000_NEWTON`, and `FET_000_MUJOCO`; repair those with their
own runtime-specific handling, not this Standard skill.

Because those runtime features layer runtime payloads on top of this neutral
base, keep the base **runtime-agnostic**: it carries only neutral
`UsdPhysics`/`physics:*` data and geometry (no `Physx*`/`Newton*`/`Mjc*`
schemas or `physx*:`/`newton:*`/`mjc:*` attributes), and it must not pin
`physics:approximation` to a runtime-specific value — never `sdf` on the base.
Leave `physics:approximation` unauthored on the neutral base so each runtime
payload can set its own value (a local base opinion outranks the payload arc in
LIVRPS and would leak into every runtime selection). See
`nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/runtime_variants/runtime-physics-isolation-matrix.md`.

For per-requirement repair details, read `references/fet-000-standard-requirements.md` only when a `FET_000_STANDARD@0.1.0` validation report or inspection identifies matching failures.

## Inputs

Collect these before editing:

| Input | Requirement |
|---|---|
| `usd_asset` | Required `.usd`, `.usda`, `.usdc`, or unpacked USD-family asset to repair. |
| `output_root` | Required or inferred folder for staged assets and reports. |
| `simready_profile` | Profile being validated, such as `Prop-Robotics-Neutral`, `Prop-Robotics-Physx`, or `Robotics-Prop`. |
| `profile_version` | Profile version, if supplied by the user or validation command. |
| `validation_report` | Preferred JSON or markdown report from the failing profile/feature validation gate. |
| `source_asset` | Original CAD, DCC, URDF, MJCF, or conversion input path, used for provenance metadata. |
| `asset_name` and `asset_type` | Use explicit user values when provided; otherwise infer conservative defaults from the asset path and profile. |

## Instructions

Use this checklist when changing the repository:

1. Confirm the input asset exists and record the original path.
2. Parse the validation report when available. If no report exists, run the same profile or feature validation gate first when the local tooling is available.
3. Filter to `FET_000_STANDARD@0.1.0` failures and the requirement IDs listed in the canonical manifest. Do not repair unrelated feature failures in this skill.
4. Create a staged output folder under `output_root`, using safe lowercase path components.
5. Copy or export the input asset into the staged folder. Do not overwrite the source asset unless the user explicitly asks for in-place repair.
6. Apply fixes in this order:
   - Path and layout fixes for `NP.002`, `NP.003`, `NP.004`, and `NP.005`.
   - Metadata fixes for `NP.006` and `SR.001`. If the only Core failure is `NP.006` and the Physical AI Skill Hub commands are available, prefer `apply-simready-foundation-metadata` over hand-editing.
   - Composition and asset path fixes for `NP.007` and `NP.008`.
   - Undefined prim cleanup for `HI.010` only when the affected over can be safely resolved or removed.
7. Rerun the same validation gate that failed, or the narrowest available `FET_000_STANDARD@0.1.0` validation gate.
8. Summarize the stage as passed, failed, skipped, or blocked. Stop at the first remaining failing validation gate unless the user asks for best-effort continuation.

## Examples

Example request:

```text
Repair FET_000_STANDARD@0.1.0 failures on a USD asset, including Core metadata and naming/path issues.
```

Expected result summary:

```text
staged_asset: repaired copy or output directory
validation: selected feature/profile gate and report path
remaining_failures: next failing requirement IDs, if any
```

## Repair Policy

Make automatic repairs only when the intended result is mechanical and portable:

- Rename copied files and folders to satisfy the Core naming and path rules.
- Place the main USD file at `asset_root/<intermediate>/<asset_file>.usd*` when repairing `NP.005`.
- Author `customLayerData` required by `SR.001`, including `SimReady_Metadata`, `asset_name`, `asset_type`, `source_file`, and `usd_date_generated`.
- Create or repair a same-directory sidecar JSON only when that is the chosen `NP.006` metadata strategy.
- Rewrite absolute asset paths to relative paths only when the referenced file exists and is inside the staged asset root, or when it is safe to copy/package the dependency into the staged asset root.

Block and report instead of guessing when:

- A required dependency cannot be found.
- A path points outside the asset package and copying it would change ownership or licensing assumptions.
- An undefined prim might be a legitimate composition override after a missing reference is restored.
- Metadata values would require domain knowledge the user did not provide.
- Repairing one requirement would invalidate a higher-priority profile requirement.

## Metadata Defaults

When explicit values are unavailable, use conservative defaults:

| Field | Default |
|---|---|
| `asset_name` | Safe stem of the staged USD asset or asset root folder. |
| `asset_type` | `robot` for robot profiles, `prop` for prop profiles, otherwise `asset`. |
| `source_file` | `source_asset` when supplied; otherwise the original input asset path. |
| `usd_date_generated` | Current date in `YYYY-MM-DD` format at repair time. |
| `SimReady_Metadata` | Empty dictionary unless a profile-specific authoring step supplies values. |

Prefer `SimReady_Metadata` with that exact capitalization because current validators check that key in root layer `customLayerData`.

## Tested Metadata Repair

For a converted CAD asset that fails `FET_000_STANDARD@0.1.0` only on `NP.006`, this command shape has been forward-tested:

```bash
uv run --python 3.12 apply-simready-foundation-metadata <usd-asset> \
  --output-dir <output-root>/<asset-name>/simready_usd \
  --profile <profile> \
  --profile-version <version> \
  --source-asset <source-asset> \
  --pipeline-step convert-cad-to-usd \
  --report <output-root>/apply-simready-foundation-metadata.json \
  --markdown-report <output-root>/apply-simready-foundation-metadata.md
```

Expected repair outputs:

- A staged copy of the USD asset under `<asset-name>/simready_usd/`.
- Root layer `customLayerData['SimReady_Metadata']`.
- A same-directory sidecar JSON file.

After rerunning profile validation, count this skill as successful when `FET_000_STANDARD@0.1.0` passes, even if the full profile still fails on non-Core features such as units, rigid bodies, multibody physics, or grasp vectors. Report those remaining feature failures as handoff work for their own skills.

## Validation Handoff

Preserve reports under the staged output directory. If the Physical AI Skill Hub validation commands are available, the normal handoff is:

```bash
uv run --python 3.12 validate-simready-profile <staged-usd> \
  --profile <profile> \
  --profile-version <version> \
  --report <output-root>/validation/fet-000-standard-after-repair.json
```

If those commands are not available, use the SimReady Foundations validator entrypoint configured in this checkout or inspect the relevant requirement validators directly. Always say which validation path was used.

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
| `requirements_repaired` | Requirement IDs changed by this skill. |
| `requirements_blocked` | Requirement IDs that need user or upstream data. |
| `validation_report` | Path to the rerun validation report. |
| `next_step` | Usually rerun the full selected profile validation. |

Keep the user-facing summary short: what was fixed, what still fails, and the first validation gate that blocks progress.
