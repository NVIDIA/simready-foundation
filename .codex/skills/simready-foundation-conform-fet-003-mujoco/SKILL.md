---
name: simready-foundation-conform-fet-003-mujoco
description: "Use for repairing exact FET_003_MUJOCO SimReady conformance for MuJoCo rigid-body physics, including MjcCollisionAPI and MjcMeshCollisionAPI. Use when a profile, validation report, or user request names FET_003_MUJOCO; default to version `0.1.0` unless pinned otherwise."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - mujoco
---

# SimReady Conform FET_003_MUJOCO

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_003_MUJOCO`. It repairs or stages MuJoCo rigid-body and collider conformance without drifting into PhysX or Newton-only requirements. A `UsdPhysics.Scene` with `MjcSceneAPI` is a scenario-level concern and is not required for a single asset.

Default to `FET_003_MUJOCO@0.1.0` when no version is specified.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_MUJOCO-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_MUJOCO.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_rigid_bodies/requirements/mujoco-collider-api.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_rigid_bodies/requirements/mujoco-mesh-collision-api.md`

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | None | `RB.COL.001`, `RB.COL.002`, `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.007`, `RB.009`, `RB.010`, `MUJOCO.COL.001`, `MUJOCO.COL.002` |

## Feature Adapter

When the input already conforms to the neutral base feature, prefer the deterministic feature adapter to author the runtime-specific data first (via the `workspace upgrade` command; see `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`), then repair only the residual requirements below.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/cip_specs/asset_handler_modules/neutral_to_mujoco` | `rigid_body_neutral_to_prop_mujoco` | `FET_003_STANDARD@0.1.0` -> `FET_003_MUJOCO@0.1.0` | Mesh extents; `MjcCollisionAPI` (+`mjc:group`) and `MjcMeshCollisionAPI` with `physics:approximation = "convexHull"`, `mjc:inertia`, `mjc:maxhullvert` on existing colliders. Satisfies `MUJOCO.COL.001`/`MUJOCO.COL.002`. |

- The adapter runs on a staged output stage and never creates geometry; it only annotates existing colliders.
- If the base `RB.*` rigid-body data is missing, or `convexHull` is not the correct approximation for a given collider, repair that manually per the Workflow below.

## Workflow

1. Identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected manifest, feature markdown, and failing requirement docs before editing.
3. Create or use a staged output location unless the user explicitly asks for in-place edits.
4. Preserve standard `UsdPhysics` rigid-body, mass, and collider authoring.
5. Add or repair `MjcCollisionAPI` on active collision shapes.
6. Use `physics:approximation = "convexHull"` for MuJoCo mesh collision geoms.
7. Keep authored MuJoCo numeric, token, and array attributes valid.
8. Rerun the narrowest available validation gate and report any missing MuJoCo runtime evidence.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_003_MUJOCO@0.1.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or runtime evidence needed. |
