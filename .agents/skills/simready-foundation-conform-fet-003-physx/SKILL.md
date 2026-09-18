---
name: simready-foundation-conform-fet-003-physx
description: "Use for repairing exact FET_003_PHYSX SimReady conformance for rigid body physics (physx) conformance. Use when a profile, validation report, or user request names FET_003_PHYSX; default to version `0.4.0` unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - physx
---

# SimReady Conform FET_003_PHYSX

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_003_PHYSX`. It repairs or stages rigid body physics (physx) conformance without drifting into another runtime contract.

Default to `FET_003_PHYSX@0.4.0` when the user asks for this feature without a version. Use an older integer version only when the profile, validation report, or user explicitly pins it. If the report names a different `FET_###_RUNTIME` feature, switch to that feature's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_PHYSX-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_PHYSX-0.2.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_PHYSX-0.3.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_PHYSX-0.4.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_PHYSX.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, benchmarks, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | FET_003_STANDARD@0.1.0 | `COL.001` |
| `0.2.0` | None | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.006`, `RB.007`, `RB.009`, `RB.010`, `PHYSX.COL.001`, `PHYSX.COL.002` |
| `0.3.0` | None | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.007`, `RB.009`, `RB.010`, `PHYSX.COL.001`, `PHYSX.COL.002` |
| `0.4.0` | None | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.007`, `RB.009`, `RB.010`, `PHYSX.COL.001`, `PHYSX.COL.002` |

## Feature Adapter

When the input already conforms to the neutral base feature, prefer the deterministic feature adapter to author the runtime-specific data first (via the `workspace upgrade` command; see `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`), then repair only the residual requirements below.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/cip_specs/asset_handler_modules/neutral_to_physx` | `rigid_body_neutral_to_prop_physx` | `FET_003_STANDARD@0.1.0` -> `FET_003_PHYSX@0.1.0` | Mesh extents on all meshes. |

- The adapter runs on a staged output stage and never creates geometry; it only annotates existing prims. Ensure colliders/rigid bodies already exist.
- It reaches `FET_003_PHYSX@0.1.0` only. The default `@4` (and `@2`/`@3`) adds `RB.*` rigid-body and `PHYSX.COL.001`/`PHYSX.COL.002` requirements that the adapter does not author; repair those manually per the Workflow below.

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET_003_PHYSX` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET_003_PHYSX` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET_003_PHYSX` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair the selected PhysX rigid-body feature and use PhysX-only collider schema only when the manifest allows it.
- Keep multibody joint and articulation work in FET_004_PHYSX or related robot features.
- Record whether runtime or validator evidence was available for PhysX collider behavior.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_003_PHYSX@0.4.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
