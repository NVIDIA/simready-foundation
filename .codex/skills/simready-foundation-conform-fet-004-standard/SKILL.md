---
name: simready-foundation-conform-fet-004-standard
description: "Use for repairing exact FET_004_STANDARD SimReady conformance for simulate multi-body physics conformance. Use when a profile, validation report, or user request names FET_004_STANDARD; default to version `0.2.0` unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - standard
---

# SimReady Conform FET_004_STANDARD

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_004_STANDARD`. It repairs or stages simulate multi-body physics conformance without drifting into another runtime contract.

Default to `FET_004_STANDARD@0.2.0` when the user asks for this feature without a version. Use an older integer version only when the profile, validation report, or user explicitly pins it. If the report names a different `FET_###_RUNTIME` feature, switch to that feature's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_STANDARD-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_STANDARD-0.2.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_STANDARD.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, benchmarks, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | FET_003_STANDARD@0.1.0 | `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, `RB.MB.001` |
| `0.2.0` | FET_003_STANDARD@0.2.0 | `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, `RB.MB.001` |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET_004_STANDARD` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET_004_STANDARD` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET_004_STANDARD` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair standard OpenUSD multibody joint, articulation, and rigid-body requirements without creating new geometry.
- Apply this feature only when the asset has multiple intended rigid bodies, joints, articulation intent, or source multibody structure.
- Skip as not applicable for single-rigid-body props when the selected profile marks FET_004 conditional.
- **Runtime-variant packaging.** When the asset exposes physics through runtime variant sets, the neutral base owns the runtime-agnostic multibody topology only: rigid bodies, `UsdPhysics` joints, exactly one `PhysicsArticulationRootAPI`, and **no** local `physics:approximation` on any collider. Per-runtime collider (and, for Newton, material) annotations are layered into the `runnables/physics/<stem>.usd` payloads via the `FET_000_PHYSX`/`FET_000_NEWTON`/`FET_000_MUJOCO` skills — never authored on the base.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_004_STANDARD@0.2.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
