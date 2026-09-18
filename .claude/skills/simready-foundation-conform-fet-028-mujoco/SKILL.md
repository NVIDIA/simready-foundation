---
name: simready-foundation-conform-fet-028-mujoco
description: "Use for repairing exact FET_028_MUJOCO SimReady conformance for MuJoCo gripper-site authoring with MjcSiteAPI. Use when a profile, validation report, or user request names FET_028_MUJOCO; default to version 1 unless pinned otherwise."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - mujoco
---

# SimReady Conform FET_028_MUJOCO

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_028_MUJOCO`. It repairs Standard gripper-site data plus MuJoCo site API authoring.

Default to `FET_028_MUJOCO@1` when no version is specified.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/sr_specs/docs/features/FET_028_MUJOCO-0.1.0.json`
- `nv_core/sr_specs/docs/features/FET_028_MUJOCO.md`
- `nv_core/sr_specs/docs/features/FET_028_STANDARD-0.1.0.json`
- `nv_core/sr_specs/docs/features/FET_022_MUJOCO-1.json`
- `nv_core/sr_specs/docs/capabilities/physics_bodies/physics_grippers/requirements/mujoco-gripper-site-api.md`

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `1` | FET_028_STANDARD@1, FET_022_MUJOCO@1 | `MUJOCO.GR.001` |

## Workflow

1. Identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected manifest, feature markdown, dependency manifests, and failing requirement docs before editing.
3. Preserve Standard gripper-site socket, forward-axis, grip-line, and max-opening data.
4. Apply `MjcSiteAPI` to each MuJoCo gripper site and keep optional `mjc:group` valid.
5. Rerun the narrowest available validation gate and report any missing MuJoCo runtime evidence.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_028_MUJOCO@1`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or runtime evidence needed. |
