---
name: simready-foundation-conform-fet-024-mujoco
description: "Use for repairing exact FET_024_MUJOCO SimReady conformance for MuJoCo-compatible base articulation. Use when a profile, validation report, or user request names FET_024_MUJOCO; default to version `0.1.0` unless pinned otherwise."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - mujoco
---

# SimReady Conform FET_024_MUJOCO

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_024_MUJOCO`. It repairs MuJoCo-compatible base articulation authoring without inventing MuJoCo-only articulation schemas.

Default to `FET_024_MUJOCO@0.1.0` when no version is specified.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_024_MUJOCO-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_024_MUJOCO.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_024_STANDARD-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/base_articulation/requirements/mujoco-standard-articulation-root.md`

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | FET_024_STANDARD@0.1.0 | `MUJOCO.BA.001` |

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
| `feature` | Exact feature ID and version, for example `FET_024_MUJOCO@0.1.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or runtime evidence needed. |
