---
name: simready-foundation-conform-fet-004-mujoco
description: "Use for repairing exact FET_004_MUJOCO SimReady conformance for MuJoCo multibody physics without creating geometry. Use when a profile, validation report, or user request names FET_004_MUJOCO; default to version `0.1.0` unless pinned otherwise."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - mujoco
---

# SimReady Conform FET_004_MUJOCO

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_004_MUJOCO`. It repairs or stages MuJoCo multibody conformance after the `FET_003_MUJOCO` rigid-body gate.

Default to `FET_004_MUJOCO@0.1.0` when no version is specified.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_MUJOCO-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_MUJOCO.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_MUJOCO-0.1.0.json`

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | FET_003_MUJOCO@0.1.0 | `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, `RB.MB.001`, `RB.011`, `RB.012` |

## Feature Adapter

When the input already conforms to the neutral base feature, prefer the deterministic feature adapter to author the runtime-specific data first (via the `workspace upgrade` command; see `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`), then repair only the residual requirements below.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/cip_specs/asset_handler_modules/neutral_to_mujoco` | `collider_neutral_to_prop_mujoco` | `FET_004_STANDARD@0.1.0` -> `FET_004_MUJOCO@0.1.0` | `MjcCollisionAPI` (+`mjc:group`) / `MjcMeshCollisionAPI` with `physics:approximation = "convexHull"` on existing colliders. |

- The adapter runs on a staged output stage and never creates geometry, joints, or articulation topology; it only annotates existing colliders.
- `FET_004_MUJOCO@0.1.0` is the multibody contract, so the adapter only covers MuJoCo collision data. The multibody requirements (`JT.*`, `RB.MB.001`, `RB.011`, `RB.012`) require existing joint/articulation topology and must be repaired manually per the Workflow below.

## Workflow

1. Identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected manifest, feature markdown, dependency manifest, and failing requirement docs before editing.
3. Create or use a staged output location unless the user explicitly asks for in-place edits.
4. Do not create geometry to pass this feature; use existing USD geometry and hierarchy.
5. Repair rigid-body nesting, mass placement, joints, and articulation topology only as required by the selected manifest.
6. Preserve `FET_003_MUJOCO` collider data.
7. Rerun the narrowest available validation gate and report any missing MuJoCo runtime evidence.

## Feature Guidance

- Repair MuJoCo multibody joint and articulation requirements on existing rigid bodies, joints, and articulations. Do not create geometry.
- **Runtime-variant packaging.** For an asset that exposes physics through variant sets (`FET_000_MUJOCO` scaffolding), the MuJoCo collider annotations (`MjcCollisionAPI`/`MjcMeshCollisionAPI` + `physics:approximation = "convexHull"` + `mjc:*`) belong in the `runnables/physics/mujoco.usd` payload as `over`s on **every** collider — not on the neutral base. This skill repairs the joint/articulation topology on the neutral base (rigid bodies, `UsdPhysics` joints, exactly one `PhysicsArticulationRootAPI`, and no local `physics:approximation` on any collider); author the per-runtime collider deltas via `FET_000_MUJOCO`.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_004_MUJOCO@0.1.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or runtime evidence needed. |
