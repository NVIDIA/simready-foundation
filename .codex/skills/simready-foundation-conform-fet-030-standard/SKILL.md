---
name: simready-foundation-conform-fet-030-standard
description: "Use for repairing exact CAP030_PackagingCore SimReady conformance for packaging core conformance. Use when a profile, validation report, or user request names CAP030_PackagingCore; default to `CAP030_PackagingCore.0-1-0` unless a profile or report pins another version. Foundations 1 ID: FET_030_STANDARD."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - standard
---

# SimReady Conform CAP030_PackagingCore

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

Use this exact capability skill when the selected profile, validation report, or user request names `CAP030_PackagingCore`. It repairs or stages packaging core conformance without drifting into another runtime contract.

Default to `CAP030_PackagingCore.0-1-0` when the user asks for this capability without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP030_PackagingCore.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP030_PackagingCore.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the capability markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `CAP030_PackagingCore.0-1-0` | None | `PKG.DEF.001`, `PKG.META.001`, `PKG.HASH.001`, `PKG.CONF.001`, `AA.001` |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `CAP030_PackagingCore` manifest and the capability markdown before editing.
3. Load requirement docs linked from the capability markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `CAP030_PackagingCore` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `CAP030_PackagingCore` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair only the requirements listed by the selected `CAP030_PackagingCore` manifest and its dependencies.
- Do not add schemas, metadata, or runtime behavior for a sibling runtime feature.
- Report missing runtime/tooling evidence as a validation limitation instead of claiming a pass.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `CAP030_PackagingCore.0-1-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact capability skill or user/runtime evidence needed. |
