---
name: simready-foundation-conform-fet-004-robot-mujoco
description: "Use for repairing exact FET_004_ROBOT_MUJOCO SimReady conformance for robot MuJoCo multibody physics, including MuJoCo collider requirements and robot joint topology. Use when a profile, validation report, or user request names FET_004_ROBOT_MUJOCO; default to version `0.1.0` unless pinned otherwise."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - mujoco
---

# SimReady Conform FET_004_ROBOT_MUJOCO

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_004_ROBOT_MUJOCO`. It repairs robot-specific MuJoCo multibody conformance without creating new geometry.

Default to `FET_004_ROBOT_MUJOCO@0.1.0` when no version is specified.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_ROBOT_MUJOCO-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_ROBOT_MUJOCO.md`
- MuJoCo rigid-body requirement docs linked from `FET_003_MUJOCO.md` when collider failures are reported

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | None | Robot rigid-body, joint, articulation, nested-body, and MuJoCo collider requirements listed in `FET_004_ROBOT_MUJOCO-0.1.0.json` |

## Feature Adapter

When the input already conforms to the neutral base feature, prefer the deterministic feature adapter to author the runtime-specific data first (via the `workspace upgrade` command; see `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`), then repair only the residual requirements below.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/cip_specs/asset_handler_modules/neutral_to_mujoco` | `rigid_body_neutral_to_robot_mujoco` | `FET_003_STANDARD@0.1.0` -> `FET_004_ROBOT_MUJOCO@0.1.0` | Mesh extents; `MjcCollisionAPI` (+`mjc:group`) / `MjcMeshCollisionAPI` with `physics:approximation = "convexHull"` on existing colliders. |

- The adapter runs on a staged output stage and never creates geometry, joints, or articulation topology; it only annotates existing colliders.
- The robot rigid-body, `JT.*`, articulation, and nested-body requirements require existing robot link/joint topology and must be repaired manually per the Workflow below.

## Workflow

1. Identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected manifest, feature markdown, and failing requirement docs before editing.
3. Create or use a staged output location unless the user explicitly asks for in-place edits.
4. Do not create geometry to pass this feature; use existing robot link geometry and hierarchy.
5. Preserve the robot link/joint topology and repair USD physics schemas, relationships, articulation APIs, masses, and MuJoCo collider schemas.
6. Use `MjcCollisionAPI` and MuJoCo mesh collision attributes only where required by the selected contract.
7. Rerun the narrowest available validation gate and report any missing MuJoCo runtime evidence.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_004_ROBOT_MUJOCO@0.1.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or runtime evidence needed. |
