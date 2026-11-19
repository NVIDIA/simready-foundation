---
name: simready-foundation-conform-fet-004-robot-mujoco
description: "Use for repairing exact CAP004_Multibody.RobotMuJoCo SimReady conformance for robot MuJoCo multibody physics, including MuJoCo collider requirements and robot joint topology. Use when a profile, validation report, or user request names CAP004_Multibody.RobotMuJoCo; default to `CAP004_Multibody.RobotMuJoCo.0-1-0` unless pinned otherwise. Foundations 1 ID: FET_004_ROBOT_MUJOCO."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - mujoco
---

# SimReady Conform CAP004_Multibody.RobotMuJoCo

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

Use this exact capability skill when the selected profile, validation report, or user request names `CAP004_Multibody.RobotMuJoCo`. It repairs robot-specific MuJoCo multibody conformance without creating new geometry.

Default to `CAP004_Multibody.RobotMuJoCo.0-1-0` when no version is specified.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP004_Multibody.RobotMuJoCo.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP004_Multibody.RobotMuJoCo.md`
- MuJoCo rigid-body requirement docs linked from `CAP003_RigidBody.MuJoCo.md` when collider failures are reported

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `CAP004_Multibody.RobotMuJoCo.0-1-0` | None | Robot rigid-body, joint, articulation, nested-body, and MuJoCo collider requirements listed in `CAP004_Multibody.RobotMuJoCo.0-1-0.json` |

## Feature Adapter

When the input already conforms to the neutral base feature, prefer the deterministic feature adapter to author the runtime-specific data first (via the `workspace upgrade` command; see `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`), then repair only the residual requirements below.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_mujoco` | `rigid_body_neutral_to_robot_mujoco` | `FET003_RigidBody.0-1-0` -> `CAP004_Multibody.RobotMuJoCo.0-1-0` | Mesh extents; `MjcCollisionAPI` (+`mjc:group`) / `MjcMeshCollisionAPI` with `physics:approximation = "convexHull"` on existing colliders. |

- The adapter runs on a staged output stage and never creates geometry, joints, or articulation topology; it only annotates existing colliders.
- The robot rigid-body, `JT.*`, articulation, and nested-body requirements require existing robot link/joint topology and must be repaired manually per the Workflow below.

## Workflow

1. Identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected manifest, feature markdown, and failing requirement docs before editing.
3. Create or use a staged output location unless the user explicitly asks for in-place edits.
4. Do not create geometry to pass this capability; use existing robot link geometry and hierarchy.
5. Preserve the robot link/joint topology and repair USD physics schemas, relationships, articulation APIs, masses, and MuJoCo collider schemas.
6. Use `MjcCollisionAPI` and MuJoCo mesh collision attributes only where required by the selected contract.
7. Rerun the narrowest available validation gate and report any missing MuJoCo runtime evidence.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `CAP004_Multibody.RobotMuJoCo.0-1-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact capability skill or runtime evidence needed. |
