---
name: simready-foundation-conform-fet-000-isaac
description: "Use for repairing exact FET_000_ISAAC SimReady conformance: Isaac packaging Core (clean folder, thumbnail, physics attribute/schema source layer). Use when a profile, validation report, or user request names FET_000_ISAAC; default to version `0.1.0`."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - isaac
    - core
---

# SimReady Conform FET_000_ISAAC

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_000_ISAAC`. It repairs or stages Isaac packaging Core on top of neutral Core, without drifting into robot identity or another runtime contract.

`FET_000_ISAAC` adds Isaac package cleanliness, thumbnail, and physics-layer placement expectations to an asset that already satisfies neutral Core (`FET_000_STANDARD@0.1.0`). Robot naming, schema, type, and root-joint policy belong to `FET_021_ISAAC`.

Default to `FET_000_ISAAC@0.1.0` when the user asks for this feature without a version. If the report names a different `FET_000_<RUNTIME>` feature, switch to that feature's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_000_ISAAC-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_000_ISAAC.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_000_STANDARD-0.1.0.json` (dependency)
- Requirement docs under `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/isaac_sim/robot_core/requirements/`:
  - `clean-folder.md` (RC.001)
  - `thumbnail-exist.md` (RC.004)
  - `verify-robot-physics-attribute-source-layer.md` (RC.005)
  - `verify-robot-physics-schema-source-layer.md` (RC.006)

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | FET_000_STANDARD@0.1.0 | `RC.001`, `RC.004`, `RC.005`, `RC.006` |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version.
2. Ensure the neutral Core gate (`FET_000_STANDARD@0.1.0`) is in shape first; if Core fails, hand off to `simready-foundation-conform-fet-000-standard` before this skill.
3. Load the `FET_000_ISAAC` manifest, the feature markdown, and the RC.001/004/005/006 requirement docs.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only `RC.001`, `RC.004`, `RC.005`, and `RC.006`. Do not rewrite robot identity (`RC.003`, `RC.007`-`RC.009`).
6. Rerun the same profile gate or the narrowest available feature/capability validation gate.
7. Summarize the selected version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Keep only the interface asset and required subfolders at the package root; remove stray sibling files.
- Place the thumbnail at `.thumbs/256x256/<asset-filename>.png` next to the validated root asset.
- Author `physics:` attributes and Physics/PhysX schemas in the physics source layer, not the base layer.
- For robot identity failures, hand off to `simready-foundation-conform-fet-021-isaac`.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_000_ISAAC@0.1.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
