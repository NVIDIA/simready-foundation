---
name: simready-foundation-conform-fet-028-mujoco
description: "Use for repairing exact CAP028_Gripper.MuJoCo SimReady conformance for MuJoCo gripper-site authoring with MjcSiteAPI. Use when a profile, validation report, or user request names CAP028_Gripper.MuJoCo; default to `CAP028_Gripper.MuJoCo.0-1-0` unless pinned otherwise. Foundations 1 ID: FET_028_MUJOCO."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - mujoco
---

# SimReady Conform CAP028_Gripper.MuJoCo

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

Use this exact capability skill when the selected profile, validation report, or user request names `CAP028_Gripper.MuJoCo`. It repairs Standard gripper-site data plus MuJoCo site API authoring.

Default to `CAP028_Gripper.MuJoCo.0-1-0` when no version is specified.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP028_Gripper.MuJoCo.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP028_Gripper.MuJoCo.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET028_Gripper.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP022_DrivenJoints.MuJoCo.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/physics_grippers/requirements/mujoco-gripper-site-api.md`

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `CAP028_Gripper.MuJoCo.0-1-0` | FET028_Gripper.0-1-0, CAP022_DrivenJoints.MuJoCo.0-1-0 | `MUJOCO.GR.001` |

## Workflow

1. Identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected manifest, feature markdown, dependency manifests, and failing requirement docs before editing.
3. Preserve Standard gripper-site socket, forward-axis, grip-line, and max-opening data.
4. Apply `MjcSiteAPI` to each MuJoCo gripper site and keep optional `mjc:group` valid.
5. Rerun the narrowest available validation gate and report any missing MuJoCo runtime evidence.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `CAP028_Gripper.MuJoCo.0-1-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact capability skill or runtime evidence needed. |
