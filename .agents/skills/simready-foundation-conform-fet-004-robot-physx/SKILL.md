---
name: simready-foundation-conform-fet-004-robot-physx
description: "Use for compatibility repair of deprecated FET004_Multibody.RobotPhysX SimReady conformance. Use only when a historical or external profile, validation report, asset stamp, or user request explicitly names FET004_Multibody.RobotPhysX; never select it for a new profile version. Foundations 1 ID: FET_004_ROBOT_PHYSX."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - robot-physx
---

# SimReady Conform FET004_Multibody.RobotPhysX

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

Use this exact feature skill when the selected profile, validation report, or user request names `FET004_Multibody.RobotPhysX`. It repairs or stages simulate multi-body physics (robot physx) conformance without drifting into another runtime contract.

`FET004_Multibody.RobotPhysX` is deprecated. This skill exists only to preserve
compatibility with historical or external contracts and assets that explicitly
name the feature. Never select or recommend it for a new profile version; use
`FET003_RigidBody.PhysX.0-4-0` and `FET004_Multibody.PhysX.0-4-0` instead.

Default to `FET004_Multibody.RobotPhysX.0-4-0` when the user asks for this feature without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.RobotPhysX.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.RobotPhysX.0-2-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.RobotPhysX.0-3-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.RobotPhysX.0-4-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.RobotPhysX.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `FET004_Multibody.RobotPhysX.0-1-0` | None | `RB.COL.002`, `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.006`, `RB.007`, `RB.009`, `RB.010`, `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, `RB.MB.001`, `RB.011`, `RB.012` |
| `FET004_Multibody.RobotPhysX.0-2-0` | None | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.006`, `RB.007`, `RB.009`, `RB.010`, `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, `RB.MB.001`, `PHYSX.COL.001`, `PHYSX.COL.002`, `RB.011`, `RB.012` |
| `FET004_Multibody.RobotPhysX.0-3-0` | None | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.007`, `RB.009`, `RB.010`, `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, `RB.MB.001`, `PHYSX.COL.001`, `PHYSX.COL.002`, `RB.011`, `RB.012` |
| `FET004_Multibody.RobotPhysX.0-4-0` | None | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.007`, `RB.009`, `RB.010`, `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, `RB.MB.001`, `PHYSX.COL.001`, `PHYSX.COL.002`, `RB.011`, `RB.012` |

## Feature Adapter

When the input already conforms to the neutral base feature, prefer the deterministic feature adapter to author the runtime-specific data first (via the `workspace upgrade` command; see `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`), then repair only the residual requirements below.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_physx` | `rigid_body_neutral_to_robot_physx` | `FET003_RigidBody.0-1-0` -> `FET004_Multibody.RobotPhysX.0-2-0` | Mesh extents on all meshes. |

- The adapter runs on a staged output stage and never creates geometry, joints, or articulation topology; it only annotates existing prims.
- It only authors mesh extents (targeting `FET004_Multibody.RobotPhysX.0-2-0`). The robot `RB.*`, `JT.*`, `RB.MB.001`, and `PHYSX.COL.*` requirements — and the `FET004_Multibody.RobotPhysX.0-4-0` default — must be repaired manually per the Workflow below on existing robot link/joint topology.

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET004_Multibody.RobotPhysX` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET004_Multibody.RobotPhysX` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET004_Multibody.RobotPhysX` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Use this legacy robot PhysX feature only when the profile pins it or needs its robot-specific collider exemption.
- Preserve robot link and joint semantics; leave robot identity to `CAP021_RobotCore.*` and driven actuation to `FET022_DrivenJoints.*` / `CAP022_DrivenJoints.*`.
- For robot multibody topology repairs (ensuring a single non-nested `PhysicsArticulationRootAPI`, converting zero-range or unpinned root joints to `PhysicsFixedJoint`, moving the PhysX articulation root to `root_joint` when `body0 = </Robot>` causes base drift, removing invalid `PhysxMeshMergeCollisionAPI` applications from single-mesh colliders, repairing invalid link mass/inertia, and removing embedded scene ground planes), follow the detailed guidance in `simready-foundation-conform-fet-004-physx` (`FET004_Multibody.PhysX`) and `simready-foundation-conform-fet-003-physx` (`FET003_RigidBody.PhysX`).
- Do not create new geometry to satisfy this feature.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `FET004_Multibody.RobotPhysX.0-4-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
