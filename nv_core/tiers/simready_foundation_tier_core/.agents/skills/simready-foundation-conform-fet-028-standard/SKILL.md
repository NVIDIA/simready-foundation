---
name: simready-foundation-conform-fet-028-standard
description: "Use for repairing exact FET028_Gripper SimReady conformance for standard gripper-site conformance. Use when a profile, validation report, or user request names FET028_Gripper; default to `FET028_Gripper.0-1-0` unless a profile or report pins another version. Foundations 1 ID: FET_028_STANDARD."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - standard
---

# SimReady Conform FET028_Gripper

## OpenUSD Competence

Running this conform skill is expert USD authoring. Reason from the OpenUSD /
Pixar USD spec rather than pattern-matching a validator message: composition
arcs and LIVRPS strength ordering, value resolution and list editing
(prepend, append, explicit, delete), the `def`/`over`/`class`
specifiers, native instancing and model hierarchy, stage units and up-axis,
and the `UsdGeom`, `UsdShade`, and `UsdPhysics` schemas. Make the exact native
edit on the correct prim, arc, and layer, derive values from the asset's real
geometry and composition, then reopen the composed stage to confirm the
opinion resolves as intended before claiming the gate passes. Never fabricate
data to satisfy a validator token. The repository-root `AGENTS.md`
"Master-Level OpenUSD Competence for Conform Work" section is the full
statement.

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET028_Gripper`. It repairs or stages standard gripper-site conformance without drifting into another runtime contract.

Default to `FET028_Gripper.0-1-0` when the user asks for this feature without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET028_Gripper.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET028_Gripper.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `FET028_Gripper.0-1-0` | None | `GR.001`, `GR.002`, `GR.003`, `GR.004` |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET028_Gripper` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET028_Gripper` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET028_Gripper` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair only the requirements listed by the selected `FET028_Gripper` manifest and its dependencies.
- Do not add schemas, metadata, or runtime behavior for a sibling runtime feature.
- Report missing runtime/tooling evidence as a validation limitation instead of claiming a pass.
- Measure maximum opening in meters, but guide geometry and translations in
  stage units, accounting for composed parent and matrix-encoded scale. GR.003
  grip-line tube geometry is not automatically the opposing-pad width or jaw
  gap; retain the frame, jaw pose and measurement basis.
- Preserve contract-valid matrix transforms and fixed-joint/sibling-body
  articulation layouts. A runtime provider losing scale or resolving the API
  prim instead of the physical body is a setup defect, not permission to bake
  geometry, move the root API or tune drives during asset repair. Use the
  installed Evaluate `diagnose-failures` / `asset-repair-report` skills for
  ordered setup checks and evidence, without replacing the real validators.
- Rerun the selected static gate on the final composed asset. Runtime evidence
  for a different source revision cannot qualify a metadata or guide repair.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `FET028_Gripper.0-1-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
