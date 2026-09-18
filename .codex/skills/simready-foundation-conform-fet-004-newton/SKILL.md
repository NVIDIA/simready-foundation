---
name: simready-foundation-conform-fet-004-newton
description: "Use for repairing exact FET_004_NEWTON SimReady conformance for simulate multi-body physics (newton) conformance. Use when a profile, validation report, or user request names FET_004_NEWTON. FET_004_NEWTON has a single published version, 1."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - newton
---

# SimReady Conform FET_004_NEWTON

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_004_NEWTON`. It repairs or stages simulate multi-body physics (newton) conformance without drifting into another runtime contract.

`FET_004_NEWTON` has a single published version, `0.1.0`; use `FET_004_NEWTON@0.1.0`. If the report names a different `FET_###_RUNTIME` feature, switch to that feature's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_NEWTON-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_NEWTON.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, benchmarks, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | FET_003_NEWTON@0.1.0 | `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, `RB.MB.001`, `RB.011`, `RB.012` |

Newton collider requirements (`NEWTON.COL.001`, `NEWTON.COL.002`) and the Newton rigid-body base come from the `FET_003_NEWTON@0.1.0` dependency.

## Feature Adapter

When the input already conforms to the neutral base feature, prefer the deterministic feature adapter to author the runtime-specific data first (via the `workspace upgrade` command; see `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`), then repair only the residual requirements below.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/cip_specs/asset_handler_modules/neutral_to_newton` | `collider_neutral_to_prop_newton` | `FET_004_STANDARD@0.1.0` -> `FET_004_NEWTON@0.1.0` | `NewtonCollisionAPI` + `NewtonMeshCollisionAPI` and `newton:contactGap = 0` on existing colliders. |

- The adapter runs on a staged output stage and never creates geometry, joints, or articulation topology; it only annotates existing colliders.
- `FET_004_NEWTON@0.1.0` is the multibody contract, so the adapter only covers the Newton collision annotation. The multibody requirements (`JT.*`, `RB.MB.001`, `RB.011`, `RB.012`) require existing joint/articulation topology and must be repaired manually per the Workflow below. Strict Newton isolation: no `Mjc*`/`Physx*` data or `physics:approximation = "sdf"`.

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET_004_NEWTON` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET_004_NEWTON` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET_004_NEWTON` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair Newton multibody joint and articulation requirements on existing rigid bodies, joints, and articulations. Do not create geometry.
- Newton collider conformance (`NEWTON.COL.001`/`NEWTON.COL.002`, choosing NewtonMeshCollisionAPI or NewtonSDFCollisionAPI per collider without applying both on the same prim) is owned by the `FET_003_NEWTON@0.1.0` dependency; repair it there.
- Do not use robot-specific collider exemptions unless the selected feature is FET_004_ROBOT_NEWTON.
- **Runtime-variant packaging.** For an asset that exposes physics through variant sets (`FET_000_NEWTON` scaffolding), the Newton collider annotations (`NewtonCollisionAPI`/`NewtonMeshCollisionAPI` + `newton:contactGap`) and `NewtonMaterialAPI` material tuning belong in the `runnables/physics/newton.usd` payload as `over`s on **every** collider and bound material — not on the neutral base. This skill repairs the joint/articulation topology on the neutral base (rigid bodies, `UsdPhysics` joints, exactly one `PhysicsArticulationRootAPI`, and no local `physics:approximation` on any collider); author the per-runtime collider/material deltas via `FET_000_NEWTON`.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_004_NEWTON@0.1.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
