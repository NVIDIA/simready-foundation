---
name: simready-foundation-conform-fet-022-mujoco
description: "Use for repairing exact FET_022_MUJOCO SimReady conformance for MuJoCo driven-joint conformance. Use when a profile, validation report, or user request names FET_022_MUJOCO; default to version `0.1.0` unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - mujoco
---

# SimReady Conform FET_022_MUJOCO

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_022_MUJOCO`. It repairs or stages MuJoCo driven-joint conformance without drifting into another runtime contract.

Default to `FET_022_MUJOCO@0.1.0` when the user asks for this feature without a version. Use an older integer version only when the profile, validation report, or user explicitly pins it. If the report names a different `FET_###_RUNTIME` feature, switch to that feature's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_022_MUJOCO-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_022_MUJOCO.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_driven_joints/requirements/mujoco-joint-api.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_driven_joints/requirements/mujoco-actuator-targets.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, benchmarks, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | FET_004_ROBOT_MUJOCO@0.1.0 | `DJ.011`, `MUJOCO.DJ.001`, `MUJOCO.DJ.002` |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET_022_MUJOCO` manifest, feature markdown, and MuJoCo requirement docs before editing.
3. Create or use a staged output location unless the user explicitly asks for in-place edits.
4. Repair only the requirements listed by the selected `FET_022_MUJOCO` manifest and its dependencies.
5. Preserve existing USD joint topology, body relationships, and authored limits unless a reported validation failure requires a narrow correction.
6. Apply `MjcJointAPI` to non-fixed articulation joints that belong to the MuJoCo driven-joint contract.
7. Author or repair MuJoCo joint tuning attributes only on USD physics joint prims. Keep `mjc:armature` finite and non-negative.
8. Author or repair `MjcActuator` prims so each actuator has exactly one `mjc:target` relationship to a valid `MjcJointAPI` joint.
9. Keep authored actuator ranges finite and ordered, and keep authored gain and bias parameter arrays numeric.
10. Rerun the same profile gate or the narrowest available feature/capability validation gate. If MuJoCo runtime evidence is unavailable, report that limitation instead of claiming a runtime pass.
11. Summarize the selected `FET_022_MUJOCO` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair only the requirements listed by the selected `FET_022_MUJOCO` manifest and its dependencies.
- Do not add schemas, metadata, or runtime behavior for a sibling runtime feature.
- Do not delete standard `UsdPhysics` joint topology or MuJoCo robot multibody data when repairing the current version; `FET_022_MUJOCO@0.1.0` depends on `FET_004_ROBOT_MUJOCO@0.1.0`.
- Do not delete `PhysicsDriveAPI` or joint-state schemas unless the selected validation report or user request explicitly asks for a MuJoCo-only overlay. When both standard drives and MuJoCo actuators are present, preserve authored data and report the ambiguity.
- Report missing MuJoCo runtime/tooling evidence as a validation limitation instead of claiming a runtime pass.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_022_MUJOCO@0.1.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
