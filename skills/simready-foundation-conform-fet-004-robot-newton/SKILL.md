---
name: simready-foundation-conform-fet-004-robot-newton
description: "Use for repairing exact FET_004_ROBOT_NEWTON SimReady conformance for simulate multi-body physics (robot newton) conformance. Use when a profile, validation report, or user request names FET_004_ROBOT_NEWTON; default to version `0.1.0` unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - robot-newton
---

# SimReady Conform FET_004_ROBOT_NEWTON

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_004_ROBOT_NEWTON`. It repairs or stages simulate multi-body physics (robot newton) conformance without drifting into another runtime contract.

Default to `FET_004_ROBOT_NEWTON@0.1.0` when the user asks for this feature without a version. Use an older integer version only when the profile, validation report, or user explicitly pins it. If the report names a different `FET_###_RUNTIME` feature, switch to that feature's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_ROBOT_NEWTON-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_004_ROBOT_NEWTON.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, benchmarks, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | None | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.007`, `RB.009`, `RB.010`, `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, `RB.MB.001`, `NEWTON.COL.001`, `NEWTON.COL.002`, `NEWTON.MAS.001`, `NEWTON.MAT.001`, `RB.011`, `RB.012` |

## Feature Adapter

When the input already conforms to the neutral base feature, prefer the deterministic feature adapter to author the runtime-specific data first (via the `workspace upgrade` command; see `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`), then repair only the residual requirements below.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/cip_specs/asset_handler_modules/neutral_to_newton` | `rigid_body_neutral_to_robot_newton` | `FET_003_STANDARD@0.1.0` -> `FET_004_ROBOT_NEWTON@0.1.0` | Mesh extents; `NewtonCollisionAPI` + `NewtonMeshCollisionAPI` and `newton:contactGap = 0` on existing colliders; `NewtonMaterialAPI` + default friction tuning on bound physics materials. Satisfies `NEWTON.COL.001`/`NEWTON.COL.002`/`NEWTON.MAT.001`. |

- The adapter runs on a staged output stage and never creates geometry, joints, or articulation topology; it only annotates existing prims.
- The robot `RB.*`, `JT.*`, `RB.MB.001`, `RB.011`, and `RB.012` requirements require existing robot link/joint topology and must be repaired manually per the Workflow below. Strict Newton isolation: no `Mjc*`/`Physx*` data or `physics:approximation = "sdf"`.

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET_004_ROBOT_NEWTON` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET_004_ROBOT_NEWTON` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET_004_ROBOT_NEWTON` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Use this robot Newton feature only when the profile pins it or needs its robot-specific collider exemption.
- Preserve robot link and joint semantics; leave robot identity to FET_021_* and driven actuation to FET_022_*.
- Newton collider tuning (`NewtonCollisionAPI` / `NewtonMeshCollisionAPI` /
  `NewtonSDFCollisionAPI`, `newton:contactGap`, `newton:maxHullVertices`) mirrors the
  `FET_003_NEWTON` collider requirements. Hydroelastic contact
  (`newton:hydroelasticEnabled` bool + positive `newton:hydroelasticStiffness`) is Newton-only and,
  when enabled, needs an authored SDF source (`newton:sdfMaxResolution` / `newton:sdfTargetVoxelSize`)
  unless the mesh has an attached `mesh.sdf`.
- Newton mass override (`NewtonMassAPI`, `NEWTON.MAS.001`) on link `Xformable`s is optional:
  `newton:inertia` empty or 6 finite elements with non-negative diagonal, `newton:massModel`
  `solid`/`shell`, `newton:shellThickness` finite `> 0` (or `-inf` sentinel). Derive inertia from
  source data; do not invent it. See `FET_003_NEWTON` for the full attribute list.
- `NewtonMaterialAPI` (`NEWTON.MAT.001`) applies on physics `Material` prims bound to robot
  colliders. Aligned with the `UsdPhysicsMaterialAPI` convention (`PMT.001`), validation checks
  **placement only**: the schema must sit on a `UsdShade.Material` that also carries
  `PhysicsMaterialAPI`. The `newton:*` tuning values (`torsionalFriction`, `rollingFriction`,
  `contact*`) are trusted, not value-checked. See `FET_003_NEWTON` for the full material
  attribute list.
- Newton joint tuning (`NewtonJointAPI` / `newton:armature`), actuation (`PhysicsDriveAPI` or
  `NewtonActuator` + control law), and articulation-root self-collision
  (`NewtonArticulationRootAPI` / `newton:selfCollisionEnabled`) belong to
  `FET_022_NEWTON` and `FET_024_NEWTON`; author them there when the robot profile pins those
  features.
- Strict Newton isolation (RV.011): no `Mjc*` / `Physx*` data or `physics:approximation = "sdf"`.
- Do not create new geometry to satisfy this feature.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_004_ROBOT_NEWTON@0.1.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
