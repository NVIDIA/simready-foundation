---
name: simready-foundation-conform-fet-021-isaac
description: "Use for repairing exact FET_021_ISAAC SimReady conformance for robot-core identity. Use when a profile, validation report, or user request names FET_021_ISAAC; default to version `0.3.0` unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - isaac
---

# SimReady Conform FET_021_ISAAC

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_021_ISAAC`. It repairs or stages robot-core identity conformance without drifting into Isaac packaging or another runtime contract.

Default to `FET_021_ISAAC@0.3.0` when the user asks for this feature without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different `FET_###_RUNTIME` feature, switch to that feature's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_021_ISAAC-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_021_ISAAC-0.2.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_021_ISAAC-0.3.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_021_ISAAC.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, benchmarks, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | None | `RC.001`, `RC.003`, `RC.004`, `RC.005`, `RC.006`, `RC.007` |
| `0.2.0` | None | `RC.001`, `RC.003`, `RC.004`, `RC.005`, `RC.006`, `RC.007`, `RC.008`, `RC.009` |
| `0.3.0` | None | `RC.003`, `RC.007`, `RC.008`, `RC.009` |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET_021_ISAAC` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET_021_ISAAC` manifest.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET_021_ISAAC` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- For `0.3.0`, repair robot naming, RobotAPI/schema relationships, robot type, and root-joint pinning only.
- For `0.1.0`/`0.2.0`, also repair packaging requirements listed on those manifests, or hand packaging failures to `simready-foundation-conform-fet-000-isaac` when the selected profile uses the split.
- Do not invent robot topology; only repair schema/relationships against existing links and joints.
- Record missing Isaac schema/runtime availability (`usd.schema.isaac`) instead of claiming runtime validation passed.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_021_ISAAC@0.3.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
