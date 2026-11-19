---
name: simready-foundation-conform-fet-004-physx
description: "Use for repairing exact FET004_Multibody.PhysX SimReady conformance for simulate multi-body physics (physx) conformance. Use when a profile, validation report, or user request names FET004_Multibody.PhysX; default to `FET004_Multibody.PhysX.0-4-0` unless a profile or report pins another version. Foundations 1 ID: FET_004_PHYSX."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - physx
---

# SimReady Conform FET004_Multibody.PhysX

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

Use this exact feature skill when the selected profile, validation report, or user request names `FET004_Multibody.PhysX`. It repairs or stages simulate multi-body physics (physx) conformance without drifting into another runtime contract.

Default to `FET004_Multibody.PhysX.0-4-0` when the user asks for this feature without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.PhysX.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.PhysX.0-2-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.PhysX.0-3-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.PhysX.0-4-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.PhysX.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `FET004_Multibody.PhysX.0-1-0` | FET003_RigidBody.PhysX.0-1-0, FET004_Multibody.0-1-0 | `COL.001` |
| `FET004_Multibody.PhysX.0-2-0` | FET003_RigidBody.PhysX.0-2-0, FET004_Multibody.0-1-0 | `PHYSX.COL.001`, `PHYSX.COL.002` |
| `FET004_Multibody.PhysX.0-3-0` | FET003_RigidBody.PhysX.0-3-0, FET004_Multibody.0-2-0 | `PHYSX.COL.001`, `PHYSX.COL.002` |
| `FET004_Multibody.PhysX.0-4-0` | FET003_RigidBody.PhysX.0-4-0 | `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, `RB.MB.001`, `RB.011`, `RB.012` |

## Feature Adapter

When the input already conforms to the neutral base feature, prefer the deterministic feature adapter to author the runtime-specific data first (via the `workspace upgrade` command; see `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`), then repair only the residual requirements below.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_physx` | `collider_neutral_to_prop_physx` | `FET004_Multibody.0-1-0` -> `FET004_Multibody.PhysX.0-1-0` | `physics:approximation = "sdf"` plus `PhysxCollisionAPI` / `PhysxSDFMeshCollisionAPI` / `UsdPhysics.MeshCollisionAPI` on existing colliders. |

- The adapter runs on a staged output stage and never creates geometry, joints, or articulation topology; it only annotates existing colliders.
- It reaches `FET004_Multibody.PhysX.0-1-0` (`COL.001`) only. The default `FET004_Multibody.PhysX.0-4-0` is the multibody contract (`JT.*`, `RB.MB.001`, `RB.011`, `RB.012`); those joints require existing topology and are not authored by the adapter. Repair them manually per the Workflow below.

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET004_Multibody.PhysX` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET004_Multibody.PhysX` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET004_Multibody.PhysX` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair PhysX multibody requirements on existing rigid bodies, joints, articulations, and colliders.
- Do not create collider geometry; use only source/user-approved collider edits.
- Prefer FET004_Multibody.PhysX.0-4-0 for new PhysX profile pins when the profile exposes it.
- **Runtime-variant packaging.** For an asset that exposes physics through variant sets (`CAP000_Core.PhysX` scaffolding), the PhysX collider annotations (`PhysxCollisionAPI`/`PhysxSDFMeshCollisionAPI` + `physics:approximation = "sdf"`) belong in the `runnables/physics/physx.usd` payload as `over`s on **every** collider — not on the neutral base. This skill repairs the joint/articulation topology on the neutral base (rigid bodies, `UsdPhysics` joints, exactly one `PhysicsArticulationRootAPI`, and no local `physics:approximation` on any collider); author the per-runtime collider deltas via `CAP000_Core.PhysX`.
- **Robot-Body multibody topology, fixed-base articulation roots, and `joint_movement` repairs:**
  - **Single non-nested articulation root (`JT.ART.002`, `JT.ART.004`, `BA.001`):** An articulated robot or arm+gripper assembly must have exactly one `PhysicsArticulationRootAPI` in the composed stage. When a manipulator includes an attached gripper sub-assembly (such as `Ufactory/xarm6` or `xarm7`), remove `PhysicsArticulationRootAPI` from the nested gripper's `root_joint` (`def PhysicsFixedJoint "root_joint"` connecting the wrist link to `gripper_base_link`) while keeping the `PhysicsFixedJoint` itself so the gripper is welded into the arm's single articulation.
  - **Fixed-base anchoring in PhysX (`JT.ART.004`, `RC.009`, and base drift prevention):** Fixed-base manipulators must be anchored to the world via a `PhysicsFixedJoint` (`root_joint` / `rootJoint` / `world2base`) where one body target is the world (empty) or a non-rigid-body root Xform (such as `/Robot` or `/Robot/world` without `PhysicsRigidBodyAPI`) and the other target is `base_link` (which carries an enabled `PhysicsRigidBodyAPI` and `PhysicsMassAPI`). If the root joint was converted as a zero-range `PhysicsRevoluteJoint` (`lowerLimit = 0`, `upperLimit = 0`, as on `I2RT/yam` `dof_joint0`) or a generic `PhysicsJoint` with `body0 = base_link` and no `body1` (`FrankaPanda` `rootJoint`), convert it to `PhysicsFixedJoint` anchoring `base_link` and remove any drive/joint-state APIs from it. Furthermore, if placing `PhysicsArticulationRootAPI` on `base_link` while `root_joint` has `body0 = /Robot` (non-rigid defaultPrim) causes PhysX to treat the articulation as `fixed_base = false` with base drift (`Addverb/Syncro5`), move `PhysicsArticulationRootAPI` and `PhysxArticulationAPI` onto the fixed `root_joint` in `runnables/physics/physx.usda` (removing `PhysicsArticulationRootAPI` from `base_link` in the PhysX override) so PhysX compiles a true fixed-base articulation.
  - **Valid rigid-body mass and inertia (`RB.007`, `RB.008`, `RB.011`, `RB.012`):** Every enabled `PhysicsRigidBodyAPI` link must have positive `physics:mass` (on the link or its owned colliders), normalized `physics:principalAxes` (when authored), and `physics:diagonalInertia` satisfying the triangle inequality ($I_1 + I_2 \ge I_3$, etc.). Repair near-zero or invalid inertia tensors (`FrankaPanda`) and zero-mass links (`Mecademic/meca500` `link_6`, `ur30` `base_link`, `Syncro5` `base_link`) in `payloads/Physics/physics.usda`.
  - **Remove embedded scene ground planes (`RB.MB.001`):** Robot assets must not ship an embedded `GroundPlane` / `CollisionPlane` collider inside the asset hierarchy (`Fanuc/r2000ic_190u`); remove stray ground-plane prims and their physics overrides from `base.usda`, `physics.usda`, and the root layer.
  - **Non-empty visual/geometry bounds on articulated links for `joint_movement`:** The `joint_movement` benchmark measures link displacement using the child link's geometry bounding box. When a terminal or intermediate robot link (such as `J4_link` on 4-DOF SCARA arms) has no visual or collision geometry of its own (empty bounds), verify whether the source package omitted the link geometry arc; if the source link genuinely has no geometry, report the empty-bounds measurement limitation rather than inventing placeholder geometry.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `FET004_Multibody.PhysX.0-4-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
