---
name: simready-foundation-conform-fet-022-physx
description: "Use for repairing exact FET022_DrivenJoints.PhysX SimReady conformance for PhysX driven-joint conformance. Use when a profile, validation report, or user request names FET022_DrivenJoints.PhysX; default to `FET022_DrivenJoints.PhysX.0-2-0` unless a profile or report pins another version. Foundations 1 ID: FET_022_PHYSX."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - physx
---

# SimReady Conform FET022_DrivenJoints.PhysX

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

Use this exact feature skill when the selected profile, validation report, or user request names `FET022_DrivenJoints.PhysX`. It repairs or stages PhysX driven-joint conformance without drifting into another runtime contract.

Default to `FET022_DrivenJoints.PhysX.0-2-0` when the user asks for this feature without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET022_DrivenJoints.PhysX.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET022_DrivenJoints.PhysX.0-2-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET022_DrivenJoints.PhysX.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `FET022_DrivenJoints.PhysX.0-1-0` | FET004_Multibody.RobotPhysX.0-1-0 | `DJ.001`, `DJ.002`, `DJ.003`, `DJ.004`, `DJ.005`, `DJ.006`, `DJ.007`, `DJ.011` |
| `FET022_DrivenJoints.PhysX.0-2-0` | FET004_Multibody.PhysX.0-4-0 | `DJ.001`, `DJ.002`, `DJ.003`, `DJ.004`, `DJ.005`, `DJ.006`, `DJ.007`, `DJ.011` |

Version `FET022_DrivenJoints.PhysX.0-1-0` is retained for compatibility with historical or external
contracts that pin the deprecated `FET004_Multibody.RobotPhysX` feature. New profile
versions must select `FET022_DrivenJoints.PhysX.0-2-0` and its canonical
`FET004_Multibody.PhysX.0-4-0` dependency.

## PhysX Driven-Joint Authoring & Runtime Calibration

When conforming `Robot-Body` (and `Robot-Gripper`) assets to `FET022_DrivenJoints.PhysX.0-2-0` and its PhysX benchmark suite (`drive_gain_validation`, `effort_limit`, `full_range_sweep`, `ik_target_reach`, `jacobian_ik`, `mimic_joint`, `multi_joint_coordination`, `state_accuracy`, `velocity_limit`), apply these evidence-based procedures (any named robot models or joints below are illustrative examples only; all repair decisions must derive from the selected asset's topology, measured behavior, and source specifications):

- **Axis-specific `PhysicsJointStateAPI` placement and `RC.005`/`RC.006` layer hygiene (`DJ.001`, `DJ.002`, `DJ.003`):**
  - Every non-fixed joint (`PhysicsRevoluteJoint` -> `PhysicsJointStateAPI:angular`, `PhysicsPrismaticJoint` -> `PhysicsJointStateAPI:linear`) must have the axis-correct `PhysicsJointStateAPI:<axis>` applied with finite `state:<axis>:physics:position` and `state:<axis>:physics:velocity`.
  - Author `PhysicsJointStateAPI:<axis>` and `PhysicsDriveAPI:<axis>` (along with `state:<axis>:physics:*` and `drive:<axis>:physics:*`) in the shared physics layer (`payloads/Physics/physics.usda`), **not** in `payloads/robot.usda`, `payloads/base.usda`, or `payloads/instances.usda`, so `CAP000_Core.Isaac` (`RC.005`, `RC.006`) and `Disabled`-variant checks pass. If `payloads/robot.usda` carries a stale `PhysicsJointStateAPI:<axis>` opinion, remove it (`delete apiSchemas = ["PhysicsJointStateAPI:<axis>"]`) and move the schema into `physics.usda`.
  - When `runnables/physics/physx.usda` overrides `drive:<axis>:physics:*` or `state:<axis>:physics:*` on a joint `over`, ensure `PhysicsDriveAPI:<axis>` and `PhysicsJointStateAPI:<axis>` remain applied on the composed joint alongside `PhysxJointAPI`.
- **Finite, positive `drive:<axis>:physics:maxForce` (`DJ.001`):**
  - `DJ.001` requires `drive:<axis>:physics:maxForce` to be authored, finite, and strictly greater than `0` on every active drive.
  - Replace non-finite `inf` values (common in URDF conversions such as `comau/n-220-27`) with a finite positive limit (or the float32 maximum `3.4028235e38` when preserving an unbounded source rating), and replace `0` on passive joints that still carry `PhysicsDriveAPI` with a small positive floor such as `1e-7` (or the mechanism's passive force cap) while zeroing `stiffness = 0` and `damping = 0`.
  - Conversely, if a source conversion leaves an unrealistically huge `maxForce` (e.g. `60000`) on a lightweight gripper finger joint (`Denso/CobottaPro900`), reduce it to the physical actuator rating so step commands do not destabilize `velocity_limit` or finger contact.
- **Pose, `targetPosition`, and `state:<axis>:physics:position` consistency (`DJ.001`, `DJ.003`, `state_accuracy`, `effort_limit`):**
  - `DJ.001` requires `|drive:<axis>:physics:targetPosition - state:<axis>:physics:position| <= 1e-2` (and matching velocities), while `DJ.003` requires the relative transform between `physics:body0` (at `localPos0`, `localRot0`) and `physics:body1` (at `localPos1`, `localRot1`) in the composed stage to match `state:<axis>:physics:position` within `1e-4` translation and `1e-3` quaternion orientation (`1 - |q0 · q1|`).
  - **Do not clamp or shift `targetPosition`/`state` without updating link poses (or vice versa):**
    - If a joint's rest pose in `base.usda` is at `0 deg` (e.g. `Sawyer`, `UF850`, `xArm6`, `xArm7`, `Dofbot`), reset stale non-zero `targetPosition` values to `0` so they match `state = 0` and the composed link transforms.
    - If a joint's `physics:lowerLimit..upperLimit` range excludes `0 deg` (for example `[47, 313] deg` and `[19, 341] deg` on `Kinova/Jaco2` `joint_2`/`joint_3` or `[30, 330] deg` on `j2n7s300` `joint_2`/`joint_4`, or `[0, 170] deg` on `Unitree/Z1`), never set `targetPosition = 0` while leaving the range excluding `0`: an out-of-range starting pose immediately fails `effort_limit` and `DJ.003`. Either keep `targetPosition` and `state:<axis>:physics:position` at the in-range rest pose (`120 deg` / `90 deg`) and rotate the downstream link `xformOp:translate` / `xformOp:orient` transforms (and `localRot0`/`localPos0` if needed) to match that exact angle, or recenter the joint frame and limits around the rest pose (`Unitree/Z1`).
    - Preserve valid winding and rest coordinates when `targetPosition`, `state:<axis>:physics:position`, and link transforms are mutually consistent and within `[lowerLimit, upperLimit]`. Do **not** replace a valid `-360 deg` state/target on a finite-limited joint (such as `[-360, 360] deg`) with `0 deg` while leaving the limits unchanged merely to fit `state_accuracy` waypoint pacing: equal 3D orientation does not imply equal remaining travel relative to the mechanical stops (`[0, +720] deg` vs. `[-360, +360] deg`). Only convert a joint's coordinate origin or winding when source evidence establishes a conversion error in the coordinate convention itself — and when doing so, transform `lowerLimit`, `upperLimit`, `state:<axis>:physics:position`, `drive:<axis>:physics:targetPosition`, and any mimic couplings consistently together. If a short test waypoint budget saturates `physxJoint:maxJointVelocity` from a valid rest pose, diagnose the test pacing or initialization rather than altering the asset's rest configuration.
- **PhysX drive stiffness and damping balance (`DJ.006`, `drive_gain_validation`, `full_range_sweep`, `multi_joint_coordination`, `state_accuracy`):**
  - `DJ.006` enforces `0.0 <= drive:<axis>:physics:stiffness <= 1e6` (`1000000.0`).
  - **Always scale `damping` proportionally when capping `stiffness`:** When a source asset authors extreme penalty gains (`stiffness = 1e7..1e15`, `damping = 1e11..1e14`, as in `Kuka/KR210_L150`, `Kuka/LBR_iiwa`, `Flexiv/Rizon4`, `Kawasaki/RS*`, `Techman/TM12`), capping `drive:angular:physics:stiffness` to `1e6` (or `1000`) in `runnables/physics/physx.usda` while leaving `damping` at `1e11..1e14` produces an overdamped time constant $\tau = k_d / k_p \gg 1\,\text{s}$ (`1e8 s` on `KR210_L150`) that freezes the arm during `full_range_sweep`, `state_accuracy`, and `multi_joint_coordination`. Whenever stiffness is capped to satisfy `DJ.006`, reduce `drive:<axis>:physics:damping` in tandem so the damping-to-stiffness ratio $k_d / k_p$ stays physically responsive (typically $\tau = k_d / k_p \in [0.003, 0.2]\,\text{s}$, e.g. `stiffness = 1e6, damping = 3000` on `KR210_L150` or `stiffness = 1000, damping = 100` on `TM12`).
  - **Gravity torque vs. stiffness and source-derived `maxForce`:** On gravity-loaded shoulder/elbow/wrist joints (for example `OpenArm/openarm_bimanual` `joint1`, `RobotStudio/so101_new_calib` `shoulder_lift`/`elbow_flex`, or `Kinova/Jaco2` `joint_1..4`), if `full_range_sweep`, `drive_gain_validation`, or `multi_joint_coordination` (`1.0 deg` settling tolerance under gravity) sags short of target while actuator effort is not saturated, raise controller `drive:angular:physics:stiffness` (within `<= 1e6`) and tune `damping` to match the link inertia. Do not fabricate or inflate `drive:<axis>:physics:maxForce` or alter joint limits to pass a benchmark; only update `maxForce` when source specifications (URDF/MJCF/datasheet) establish that the authored USD force limit was mis-converted.
- **PhysX joint velocity limits and joint friction (`DJ.005`, `velocity_limit`, `full_range_sweep`):**
  - `DJ.005` requires every joint with `PhysxJointAPI` to author a finite, strictly positive `physxJoint:maxJointVelocity > 0` (replace `inf`, `0`, or negative values with the physical velocity ceiling in deg/s for revolute or m/s for prismatic joints, e.g. `FactoryFranka` `panda_joint7`).
  - Preserve source-authored `physxJoint:jointFriction`. Opposition to motion is normal physical friction behavior and does not by itself prove a conversion error; do **not** zero or reduce `physxJoint:jointFriction` merely because friction impedes PD tracking in `state_accuracy`, `full_range_sweep`, or `mimic_joint`. Require concrete evidence of a mistaken source conversion (such as a discrepancy against the source URDF/MJCF `<dynamics friction="..."/>` or manufacturer specification) before altering `physxJoint:jointFriction`; otherwise preserve the authored friction and diagnose controller authority (`stiffness`/`damping` within source `maxForce`), test pacing, or a runtime limitation.
- **PhysX mimic joints — revolute vs. prismatic follower rules and `naturalFrequency` (`DJ.004`, `DJ.006`, `DJ.007`, `mimic_joint`):**
  - **Revolute (and non-prismatic) mimic followers:** When a revolute joint carries `PhysxMimicJointAPI:<rotAxis>`, `DJ.004` and `DJ.006` require `drive:angular:physics:stiffness = 0.0` and `drive:angular:physics:damping = 0.0` so the PhysX mimic constraint owns the DOF without fighting a position drive. Also ensure `PhysxMimicJointAPI:<rotAxis>` is actually prepended in `apiSchemas` whenever `physxMimicJoint:<rotAxis>:*` attributes are authored (for example `PhysxMimicJointAPI:rotY` on `Fanuc/m900*` `P2`).
  - **Prismatic mimic followers (`DJ.004`, `DJ.006`, and `mimic_joint` motion ratio):** Because PhysX's `DJ.004`/`DJ.006` validator requires non-zero `drive:linear:physics:stiffness > 0` on a `PhysicsPrismaticJoint` follower with `PhysxMimicJointAPI`, authoring a large follower stiffness (such as `stiffness = 1000` holding `targetPosition = 0` on `FrankaRobotics/FrankaFR3` `fr3_finger_joint2`) creates a strong spring toward `0` that opposes `PhysxMimicJointAPI` when only the leader finger is commanded in `mimic_joint`. Author a minimal positive follower stiffness (`float drive:linear:physics:stiffness = 1` and `damping = 0` in `runnables/physics/physx.usda`) so `DJ.004` and `DJ.006` pass while `PhysxMimicJointAPI` drives the follower with a `~1.0` motion ratio.
  - **Completing `DJ.007` mimic attributes:** `DJ.007` requires a valid single `referenceJoint` target, finite non-zero `gearing`, finite `offset`, and finite resolved `dampingRatio` and `naturalFrequency` (plus compatible follower/leader joint limits under `follower = -gearing * reference - offset`, with neither joint having `physics:excludeFromArticulation = true`). Preserve authored zero or negative `naturalFrequency` and unauthored zero schema defaults: PhysX uses `naturalFrequency <= 0` for rigid coupling without compliance. Positive natural frequency and damping ratio select compliant coupling; non-positive damping also selects rigid coupling. Choose compliance from the mechanism's intended behavior; zero natural frequency needs no repair. Blocked and malformed values still require correction from source evidence.
- **Closed-loop 4-bar / parallel linkages in PhysX (`DJ.004`, `DJ.007`, `DJ.011`):**
  - `DJ.011` requires the non-excluded articulation subgraph (`physics:excludeFromArticulation = false`) to be cycle-free and have at most one joint per body pair; break every kinematic loop by setting `uniform bool physics:excludeFromArticulation = true` on one joint in the loop (and ensure no `PhysxMimicJointAPI` is applied to or references an excluded joint, per `DJ.007`).
  - On non-excluded passive linkage joints inside a closed loop (such as `P2_01` or `P2` on `Fanuc/m900*` and `Fanuc/m-2000_*` 4-bar linkages, or passive `Finger_02`/`Finger_03` linkage joints on `Yahboom/Dofbot`) that do not use `PhysxMimicJointAPI`, satisfy `DJ.004` (`PhysicsJointHasDriveOrMimicAPI`) and `DJ.001`/`DJ.006` by applying `PhysicsDriveAPI:angular` with **zero stiffness and zero damping** (`float drive:angular:physics:stiffness = 0`, `float drive:angular:physics:damping = 0`) and a finite positive `drive:angular:physics:maxForce > 0` (e.g. `1e-7` or the linkage rating). Never leave non-zero `stiffness` or `damping` on a passive loop joint: an active drive on a dependent loop coordinate fights the primary actuator (`J3` or `Finger_01`) and causes the benchmark to command incompatible targets across the loop.

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET022_DrivenJoints.PhysX` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET022_DrivenJoints.PhysX` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET022_DrivenJoints.PhysX` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair only the requirements listed by the selected `FET022_DrivenJoints.PhysX` manifest and its dependencies.
- Do not add schemas, metadata, or runtime behavior for a sibling runtime feature.
- Report missing runtime/tooling evidence as a validation limitation instead of claiming a pass.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `FET022_DrivenJoints.PhysX.0-2-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
