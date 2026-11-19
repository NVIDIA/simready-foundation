---
name: simready-foundation-conform-fet-021-isaac
description: "Use for repairing exact CAP021_RobotCore.Isaac SimReady conformance for robot-core identity. Use when a profile, validation report, or user request names CAP021_RobotCore.Isaac; default to `CAP021_RobotCore.Isaac.0-3-0` unless a profile or report pins another version. Foundations 1 ID: FET_021_ISAAC."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - isaac
---

# SimReady Conform CAP021_RobotCore.Isaac

## OpenUSD Competence

Running this conform skill is expert USD authoring. Reason from the OpenUSD /
Pixar USD spec rather than pattern-matching a validator message: composition
arcs and LIVRPS strength ordering, value resolution and list editing
(prepend, append, explicit, delete), the `def`/`over`/`class`
specifiers, native instancing and model hierarchy, stage units and up-axis,
and the `UsdGeom`, `UsdShade`, and `UsdPhysics` schemas. Make the exact native
edit on the correct prim, arc, and layer, derive values from the asset's real
geometry and composition, then reopen the composed stage to confirm the
opinion resolves as intended before claiming the gate passes. Never fabricate
data to satisfy a validator token. The repository-root `AGENTS.md`
"Master-Level OpenUSD Competence for Conform Work" section is the full
statement.

## Purpose

Use this exact capability skill when the selected profile, validation report, or user request names `CAP021_RobotCore.Isaac`. It repairs or stages robot-core identity conformance without drifting into Isaac packaging or another runtime contract.

Default to `CAP021_RobotCore.Isaac.0-3-0` when the user asks for this capability without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP021_RobotCore.Isaac.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP021_RobotCore.Isaac.0-2-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP021_RobotCore.Isaac.0-3-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP021_RobotCore.Isaac.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the capability markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `CAP021_RobotCore.Isaac.0-1-0` | None | `RC.001`, `RC.003`, `RC.004`, `RC.005`, `RC.006`, `RC.007` |
| `CAP021_RobotCore.Isaac.0-2-0` | None | `RC.001`, `RC.003`, `RC.004`, `RC.005`, `RC.006`, `RC.007`, `RC.008`, `RC.009` |
| `CAP021_RobotCore.Isaac.0-3-0` | None | `RC.003`, `RC.007`, `RC.008`, `RC.009` |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `CAP021_RobotCore.Isaac` manifest and the capability markdown before editing.
3. Load requirement docs linked from the capability markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `CAP021_RobotCore.Isaac` manifest.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `CAP021_RobotCore.Isaac` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- For `CAP021_RobotCore.Isaac.0-3-0`, repair robot naming, RobotAPI/schema relationships, robot type, and root-joint pinning only.
- **Pinned root joint ordering in `isaac:physics:robotJoints` (`RC.009`):** `RootJointPinned` (`RC.009`) inspects **only the first target** (`GetTargets()[0]`) of `rel isaac:physics:robotJoints` on the `defaultPrim`. For `isaac:robotType = "Manipulator"` or `"End Effector"`, that first target must be a valid `UsdPhysics.Joint` (`PhysicsFixedJoint`) where at least one of `physics:body0` or `physics:body1` is either empty (world) or a prim without `PhysicsRigidBodyAPI`.
  - If the fixed base joint (`root_joint`, `rootJoint`, `world2base`, `joint_w`) is listed later in `isaac:physics:robotJoints` (after `joint1..jointN`, as occurred on `Addverb/Syncro5`, `FrankaPanda`, `RethinkRobotics/Sawyer`, `Techman/TM12`, `Ufactory/xarm6`, `xarm7`, `Unitree/Z1`), reorder `prepend rel isaac:physics:robotJoints` in `payloads/robot.usda` so the pinned root joint is **first**.
  - If the asset lacks a fixed base joint (or has a nested gripper `root_joint` listed before the arm's world anchor), author a `PhysicsFixedJoint` anchoring `base_link` to the world/root Xform in `payloads/Physics/physics.usda` and place it first in `prepend rel isaac:physics:robotJoints` in `payloads/robot.usda`.
- **Canonical entrypoint naming (`RC.003`):** `RobotNaming` (`RC.003`) requires the root USD filename stem to match either its immediate parent directory (`<Manufacturer>/<robot>/<robot>.usd`) or its grandparent directory (`<Manufacturer>/<robot>/<version>/<robot>.usd`, case-insensitive). When a converted robot package lives under `simready_usd/` with a variant suffix in the filename (such as `Yaskawa/Motoman_Next/NEX10/simready_usd/NEX10_C00.usda` or `NHC12_A00.usda`), rename the entrypoint (and its `.thumbs/256x256/<name>.usda.png` thumbnail) to match the `<robot>` folder name (`NEX10.usda`, `NHC12.usda`).
- For `CAP021_RobotCore.Isaac.0-1-0`/`CAP021_RobotCore.Isaac.0-2-0`, also repair packaging requirements listed on those manifests, or hand packaging failures to `simready-foundation-conform-fet-000-isaac` when the selected profile uses the split.
- Do not invent robot topology; only repair schema/relationships against existing links and joints.
- Record missing Isaac schema/runtime availability (`usd.schema.isaac`) instead of claiming runtime validation passed.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `CAP021_RobotCore.Isaac.0-3-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact capability skill or user/runtime evidence needed. |
