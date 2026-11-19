---
name: simready-foundation-conform-fet-006-mdl
description: "Use for repairing exact FET006_Materials.MDL SimReady conformance for MDL material conformance. Use when a profile, validation report, or user request names FET006_Materials.MDL; default to `FET006_Materials.MDL.0-1-0` unless a profile or report pins another version. Foundations 1 ID: FET_006_MDL."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - mdl
---

# SimReady Conform FET006_Materials.MDL

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

Use this exact feature skill when the selected profile, validation report, or user request names `FET006_Materials.MDL`. It repairs or stages MDL material conformance without drifting into another runtime contract.

Default to `FET006_Materials.MDL.0-1-0` when the user asks for this feature without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET006_Materials.MDL.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET006_Materials.MDL.0-3-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET006_Materials.MDL.0-2-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET006_Materials.MDL.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `FET006_Materials.MDL.0-1-0` | None | `VM.BIND.002`, `VM.MAT.001`, `VM.MDL.001`, `VM.TEX.001`, `VM.TEX.002` |
| `FET006_Materials.MDL.0-2-0` | None | `com.nvidia.usd.VM.BIND.001`, `VM.BIND.002`, `VM.MAT.001`, `VM.MDL.001`, `com.nvidia.usd.VM.MDL.002`, `VM.MDL.003`, `VM.TEX.001`, `VM.TEX.005` |
| `FET006_Materials.MDL.0-3-0` | None | `com.nvidia.usd.VM.BIND.001`, `VM.BIND.002`, `VM.MDL.001`, `com.nvidia.usd.VM.MDL.002`, `VM.MDL.003`, `VM.TEX.001`, `VM.TEX.005` |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET006_Materials.MDL` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET006_Materials.MDL` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET006_Materials.MDL` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair only the requirements listed by the selected `FET006_Materials.MDL` manifest and its dependencies.
- Do not add schemas, metadata, or runtime behavior for a sibling runtime feature.
- Report missing runtime/tooling evidence as a validation limitation instead of claiming a pass.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `FET006_Materials.MDL.0-1-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
