---
name: simready-foundation-conform-fet-004-physx
description: "Use for repairing exact FET_004_PHYSX SimReady conformance for simulate multi-body physics (physx) conformance. Use when a profile, validation report, or user request names FET_004_PHYSX; default to version `0.4.0` unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - physx
---

# SimReady Conform FET_004_PHYSX

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_004_PHYSX`. It repairs or stages simulate multi-body physics (physx) conformance without drifting into another runtime contract.

Default to `FET_004_PHYSX@0.4.0` when the user asks for this feature without a version. Use an older integer version only when the profile, validation report, or user explicitly pins it. If the report names a different `FET_###_RUNTIME` feature, switch to that feature's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_PHYSX-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_PHYSX-0.2.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_PHYSX-0.3.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_PHYSX-0.4.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_PHYSX.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, benchmarks, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | FET_003_PHYSX@0.1.0, FET_004_STANDARD@0.1.0 | `COL.001` |
| `0.2.0` | FET_003_PHYSX@0.2.0, FET_004_STANDARD@0.1.0 | `PHYSX.COL.001`, `PHYSX.COL.002` |
| `0.3.0` | FET_003_PHYSX@0.3.0, FET_004_STANDARD@0.2.0 | `PHYSX.COL.001`, `PHYSX.COL.002` |
| `0.4.0` | FET_003_PHYSX@0.4.0 | `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, `RB.MB.001`, `RB.011`, `RB.012` |

## Feature Adapter

When the input already conforms to the neutral base feature, prefer the deterministic feature adapter to author the runtime-specific data first (via the `workspace upgrade` command; see `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`), then repair only the residual requirements below.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/cip_specs/asset_handler_modules/neutral_to_physx` | `collider_neutral_to_prop_physx` | `FET_004_STANDARD@0.1.0` -> `FET_004_PHYSX@0.1.0` | `physics:approximation = "sdf"` plus `PhysxCollisionAPI` / `PhysxSDFMeshCollisionAPI` / `UsdPhysics.MeshCollisionAPI` on existing colliders. |

- The adapter runs on a staged output stage and never creates geometry, joints, or articulation topology; it only annotates existing colliders.
- It reaches `FET_004_PHYSX@0.1.0` (`COL.001`) only. The default `@4` is the multibody contract (`JT.*`, `RB.MB.001`, `RB.011`, `RB.012`); those joints require existing topology and are not authored by the adapter. Repair them manually per the Workflow below.

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET_004_PHYSX` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET_004_PHYSX` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET_004_PHYSX` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair PhysX multibody requirements on existing rigid bodies, joints, articulations, and colliders.
- Do not create collider geometry; use only source/user-approved collider edits.
- Prefer FET_004_PHYSX@0.4.0 for new PhysX profile pins when the profile exposes it.
- **Runtime-variant packaging.** For an asset that exposes physics through variant sets (`FET_000_PHYSX` scaffolding), the PhysX collider annotations (`PhysxCollisionAPI`/`PhysxSDFMeshCollisionAPI` + `physics:approximation = "sdf"`) belong in the `runnables/physics/physx.usd` payload as `over`s on **every** collider — not on the neutral base. This skill repairs the joint/articulation topology on the neutral base (rigid bodies, `UsdPhysics` joints, exactly one `PhysicsArticulationRootAPI`, and no local `physics:approximation` on any collider); author the per-runtime collider deltas via `FET_000_PHYSX`.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_004_PHYSX@0.4.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
