---
name: simready-foundation-conform-fet-004-robot-newton
description: "Use for repairing exact FET004_Multibody.RobotNewton SimReady conformance for simulate multi-body physics (robot newton) conformance. Use when a profile, validation report, or user request names FET004_Multibody.RobotNewton; default to `FET004_Multibody.RobotNewton.0-1-0` unless a profile or report pins another version. Foundations 1 ID: FET_004_ROBOT_NEWTON."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - robot-newton
---

# SimReady Conform FET004_Multibody.RobotNewton

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET004_Multibody.RobotNewton`. It repairs or stages simulate multi-body physics (robot newton) conformance without drifting into another runtime contract.

Default to `FET004_Multibody.RobotNewton.0-1-0` when the user asks for this feature without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/features/FET004_Multibody.RobotNewton.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/features/FET004_Multibody.RobotNewton.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `FET004_Multibody.RobotNewton.0-1-0` | None | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.007`, `RB.009`, `RB.010`, `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, `RB.MB.001`, `NEWTON.COL.001`, `NEWTON.COL.002`, `NEWTON.MAS.001`, `NEWTON.MAT.001`, `RB.011`, `RB.012` |

## Feature Adapter

When the input already conforms to the neutral base feature, prefer the deterministic feature adapter to author the runtime-specific data first (via the `workspace upgrade` command; see `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`), then repair only the residual requirements below.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_newton` | `rigid_body_neutral_to_robot_newton` | `FET003_RigidBody.0-1-0` -> `FET004_Multibody.RobotNewton.0-1-0` | Mesh extents; `NewtonCollisionAPI` + `NewtonMeshCollisionAPI` and `newton:contactGap = 0` on existing colliders; `NewtonMaterialAPI` + default friction tuning on bound physics materials. Satisfies `NEWTON.COL.001`/`NEWTON.COL.002`/`NEWTON.MAT.001`. |

- The adapter runs on a staged output stage and never creates geometry, joints, or articulation topology; it only annotates existing prims.
- The robot `RB.*`, `JT.*`, `RB.MB.001`, `RB.011`, and `RB.012` requirements require existing robot link/joint topology and must be repaired manually per the Workflow below. Strict Newton isolation: no `Mjc*`/`Physx*` data or `physics:approximation = "sdf"`.

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET004_Multibody.RobotNewton` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET004_Multibody.RobotNewton` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET004_Multibody.RobotNewton` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Use this robot Newton feature only when the profile pins it or needs its robot-specific collider exemption.
- Preserve robot link and joint semantics; leave robot identity to `CAP021_RobotCore.*` and driven actuation to `FET022_DrivenJoints.*` / `CAP022_DrivenJoints.*`.
- Newton collider tuning (`NewtonCollisionAPI` / `NewtonMeshCollisionAPI` /
  `NewtonSDFCollisionAPI`, `newton:contactGap`, `newton:maxHullVertices`) mirrors the
  `FET003_RigidBody.Newton` collider requirements. Hydroelastic contact
  (`newton:hydroelasticEnabled` bool + positive `newton:hydroelasticStiffness`) is Newton-only and,
  when enabled, needs an authored SDF source (`newton:sdfMaxResolution` / `newton:sdfTargetVoxelSize`)
  unless the mesh has an attached `mesh.sdf`.
- Newton mass override (`NewtonMassAPI`, `NEWTON.MAS.001`) on link `Xformable`s is optional:
  `newton:inertia` empty or 6 finite elements with non-negative diagonal, `newton:massModel`
  `solid`/`shell`, `newton:shellThickness` finite `> 0` (or `-inf` sentinel). Derive inertia from
  source data; do not invent it. See `FET003_RigidBody.Newton` for the full attribute list.
- `NewtonMaterialAPI` (`NEWTON.MAT.001`) applies on physics `Material` prims bound to robot
  colliders. Aligned with the `UsdPhysicsMaterialAPI` convention (`PMT.001`), validation checks
  **placement only**: the schema must sit on a `UsdShade.Material` that also carries
  `PhysicsMaterialAPI`. The `newton:*` tuning values (`torsionalFriction`, `rollingFriction`,
  `contact*`) are trusted, not value-checked. See `FET003_RigidBody.Newton` for the full material
  attribute list.
- Newton joint tuning (`NewtonJointAPI` / `newton:armature`), actuation (`PhysicsDriveAPI` or
  `NewtonActuator` + control law), and articulation-root self-collision
  (`NewtonArticulationRootAPI` / `newton:selfCollisionEnabled`) belong to
  `FET022_DrivenJoints.Newton` and `CAP024_BaseArticulation.Newton`; author them there when the robot profile pins those
  features.
- **Single enabled fixed base joint to world (and preserving internal fixed joints to rigid-body children).** Newton's USD importer resolves any joint `physics:body0` target that is not an enabled `PhysicsRigidBodyAPI` prim (for example a plain `/Robot` or `/Robot/world` `Xform`) to the world (`parent = -1`). When a neutral physics layer carries both an original fixed root joint and a synthetic `__fixed_base_joint` (added for `JT.ART.004`), both resolve to `(parent = -1, child = base_link)` and Newton fails at import with `Cannot merge joint ... of type FixedJoint into a D6 joint`. In `runnables/physics/newton.usda`, disable the redundant fixed base joint (`bool physics:jointEnabled = 0`) so exactly one enabled fixed joint anchors `base_link`. Conversely, do **not** disable an internal `PhysicsFixedJoint` (such as an auxiliary fingertip or tool-frame joint) whose child prim carries `PhysicsRigidBodyAPI` inside the `PhysicsArticulationRootAPI` subtree unless that child rigid body is also disabled, because an unjointed rigid body inside the articulation root causes Newton to compile two articulations under the same root path (`AssertionError: self.count == 1` in `SingleArticulation.initialize()`).
- **Directed parent-to-child joint topology (`ValueError: Reversed joints are not supported`).** Newton requires every joint included in the articulation (`physics:excludeFromArticulation = false`) to be directed from parent (`physics:body0`) to child (`physics:body1`) away from the articulation root:
  - If a serial joint has `physics:body0` targeting the child link and `physics:body1` targeting the parent link, swap `physics:body0` <-> `physics:body1`, `physics:localPos0` <-> `physics:localPos1`, and `physics:localRot0` <-> `physics:localRot1` in `runnables/physics/newton.usda`, **and apply the corresponding signed-coordinate conversion** ($q' = -q$ when keeping the same `physics:axis`): negate and swap asymmetric joint limits (`lowerLimit' = -upperLimit`, `upperLimit' = -lowerLimit`), negate non-zero `state:<axis>:physics:position`, `state:<axis>:physics:velocity`, `drive:<axis>:physics:targetPosition`, `drive:<axis>:physics:targetVelocity`, and signed `NewtonActuator` `newton:constEffort`, reverse and negate `newton:lookupPositions` (`[-p for p in reversed(lookupPositions)]`, e.g. `[-1, 0, 2]` -> `[-2, 0, 1]`) while reversing `newton:lookupEfforts` (`list(reversed(lookupEfforts))`, e.g. `[10, 20, 30]` -> `[30, 20, 10]`, preserving non-negative effort capacity magnitudes and sorted position order), and flip the sign of `newton:mimicCoef0` / `newton:mimicCoef1` on any `NewtonMimicAPI` relationship where the reversed joint is the follower (or negate `newton:mimicCoef1` on any follower that references the reversed joint as leader) so the physical mechanism's travel and coupling direction are preserved.
  - In closed-loop / 4-bar linkages (`DJ.011`, such as `J2_link -(P1)-> P1_link -(P2)-> P2_link -(P2_01)-> J3_link`), set `uniform bool physics:excludeFromArticulation = true` on the loop-closing joint (`P2_01`) and `false` on the root-side chain joints (`P1`, `P2`) so topological traversal never crosses an articulation joint backwards.
- **Mesh collider approximation and diagnosing self-collision contact behavior on multi-mesh robot links.**
  - In Newton, `uniform token physics:approximation = "convexDecomposition"` invokes CoACD MCTS decomposition at stage load time. On dense robot link sub-meshes where CoACD exceeds runtime budgets, override `uniform token physics:approximation = "convexHull"` in `runnables/physics/newton.usda` when convex hulls preserve link clearance.
  - When a robot link contains multiple overlapping collision sub-meshes (such as motor housings, brackets, and jaw sub-parts) and `physics:approximation` is left unset (`"none"` triangle mesh), sweeping joints can generate excessive intra-link or adjacent-link contacts that overflow MuJoCo-Warp's `nconmax = 1000` buffer (`Number of Newton contacts exceeded MJWarp limit (1000)`). Prefer authoring `prepend apiSchemas = ["NewtonCollisionAPI", "NewtonMeshCollisionAPI", "PhysicsMeshCollisionAPI"]` with `uniform token physics:approximation = "convexHull"` on the link collision meshes and adding missing `physics:filteredPairs` between legitimately overlapping adjacent links. Only set `bool newton:selfCollisionEnabled = 0` on the `NewtonArticulationRootAPI` prim when source evidence (such as the source URDF/MJCF or neutral asset disabling self-collisions) establishes that articulation-wide self-collision is unintended; do not disable intended self-collision merely to make a test pass or work around an engine contact-budget limitation.
- Strict Newton isolation (RV.011): no `Mjc*` / `Physx*` data or `physics:approximation = "sdf"`.
- Do not create new geometry to satisfy this feature.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `FET004_Multibody.RobotNewton.0-1-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
