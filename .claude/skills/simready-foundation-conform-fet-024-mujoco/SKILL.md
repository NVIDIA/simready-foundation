---
name: simready-foundation-conform-fet-024-mujoco
description: "Use for repairing exact CAP024_BaseArticulation.MuJoCo SimReady conformance for MuJoCo-compatible base articulation. Use when a profile, validation report, or user request names CAP024_BaseArticulation.MuJoCo; default to `CAP024_BaseArticulation.MuJoCo.0-1-0` unless pinned otherwise. Foundations 1 ID: FET_024_MUJOCO."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - mujoco
---

# SimReady Conform CAP024_BaseArticulation.MuJoCo

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

Use this exact capability skill when the selected profile, validation report, or user request names `CAP024_BaseArticulation.MuJoCo`. It repairs MuJoCo-compatible base articulation authoring without inventing MuJoCo-only articulation schemas.

Default to `CAP024_BaseArticulation.MuJoCo.0-1-0` when no version is specified.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP024_BaseArticulation.MuJoCo.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP024_BaseArticulation.MuJoCo.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP024_BaseArticulation.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/base_articulation/requirements/mujoco-standard-articulation-root.md`

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `CAP024_BaseArticulation.MuJoCo.0-1-0` | CAP024_BaseArticulation.0-1-0 | `MUJOCO.BA.001` |

## Workflow

1. Identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected manifest, feature markdown, dependency manifest, and failing requirement docs before editing.
3. Preserve the single `UsdPhysics.ArticulationRootAPI` contract.
4. Remove unsupported `MjcArticulationRootAPI` or `MjcArticulationRoot` authoring if present.
5. Do not author a `MjcArticulationRootAPI`; the official MuJoCo schema does not define one.
6. Rerun the narrowest available validation gate and report any missing MuJoCo runtime evidence.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `CAP024_BaseArticulation.MuJoCo.0-1-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact capability skill or runtime evidence needed. |
