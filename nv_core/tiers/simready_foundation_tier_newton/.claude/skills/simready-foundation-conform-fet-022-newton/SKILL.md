---
name: simready-foundation-conform-fet-022-newton
description: "Use for repairing exact FET022_DrivenJoints.Newton SimReady conformance for Newton driven-joint conformance. Use when a profile, validation report, or user request names FET022_DrivenJoints.Newton; default to `FET022_DrivenJoints.Newton.0-1-0` unless a profile or report pins another version. Foundations 1 ID: FET_022_NEWTON."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - newton
---

# SimReady Conform FET022_DrivenJoints.Newton

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET022_DrivenJoints.Newton`. It repairs or stages Newton driven-joint conformance without drifting into another runtime contract.

Default to `FET022_DrivenJoints.Newton.0-1-0` when the user asks for this feature without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/features/FET022_DrivenJoints.Newton.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/features/FET022_DrivenJoints.Newton.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

These are checkout-relative paths. In an installed workflow, resolve catalogs
through the selected tier descriptor rather than inventing a Core copy. Feature
pages use the assembled documentation site's logical links: shared requirements
such as `DJ.011` and robot profiles are Core-owned. Resolve a local linked rule
through its owning tier's descriptor/source root, or use the published site;
do not treat a missing Newton-relative file as a missing requirement.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `FET022_DrivenJoints.Newton.0-1-0` | FET004_Multibody.RobotNewton.0-1-0 | `DJ.011`, `NEWTON.DJ.001`, `NEWTON.DJ.002`, `NEWTON.DJ.003` |

## Newton Actuation Vocabulary

This feature uses the published Newton USD schemas (`newton-usd-schemas`) for joint tuning
and actuation. Author these on the Newton runtime layer only; keep the composed stage
strictly Newton (RV.011: no `Mjc*` / `Physx*` schemas or attributes).

- **Joint tuning — `NewtonJointAPI`** on each `UsdPhysics.Joint` (`NEWTON.DJ.002`):
  - `newton:armature`, `newton:damping`, `newton:friction` — finite and non-negative.
  - `newton:velocityLimit` — positive, or `inf` for no clamping.
  - `newton:limitStiffness`, `newton:limitDamping` — finite and non-negative, or the `-inf`
    sentinel that defers to the engine default (`limitStiffness` may also be `inf` for a hard
    limit). All values broadcast to every DOF; angular attributes use degrees. The bare
    `newton:*` attributes without the applied API are also accepted.
- **Actuation** (`NEWTON.DJ.001`) — each non-fixed articulation joint must be actuated in at least
  one of three ways (unless `physics:excludeFromArticulation = true`): a `PhysicsDriveAPI:<axis>`,
  a `NewtonActuator` that targets it, **or** a `NewtonMimicAPI` coupling to a leader joint. A mimic
  follower is actuated indirectly through the coupling, so it needs **no** drive or actuator of its
  own. Preserve valid standard `PhysicsDriveAPI` and `PhysicsJointStateAPI` data
  in Newton-only and multi-runtime compositions, valid Newton-actuator control,
  and valid indirect mimic actuation permitted by the selected requirement.
  Inspect redundant controllers for demonstrated conflicting commands before
  proposing a change. Replacing an actuation representation requires a separately
  authorized repair or conversion derived from the source mechanism; conformance
  work repairs only demonstrated violations in the existing representation.
  - **`NewtonActuator`** (typed prim): `rel newton:targets` -> a `PhysicsRevoluteJoint` or
    `PhysicsPrismaticJoint` (first target honored). Actuators use radians.
  - Apply exactly one control law: `NewtonPDControlAPI` (`newton:kp`, `newton:kd`,
    `newton:constEffort`), `NewtonPIDControlAPI` (adds `newton:ki`, `newton:integralMax`), or
    `NewtonNeuralControlAPI` (`newton:modelPath`).
  - Optional clamps: `NewtonMaxEffortClampingAPI` (`newton:maxEffort`),
    `NewtonDCMotorClampingAPI` (`newton:maxMotorEffort`, `newton:saturationEffort`,
    `newton:velocityLimit`), `NewtonPositionBasedClampingAPI` (`newton:lookupPositions`,
    `newton:lookupEfforts`). Optional `NewtonActuatorDelayAPI` (`newton:delaySteps`, integer >= 0).
  - Authored gains/clamps must be finite and non-negative; `newton:constEffort` finite.
- Do not guess actuator gains. Derive them from the source robot's servo/drive parameters
  (for example, map MuJoCo servo gains to `newton:kp`/`newton:kd` and neutral
  `maxForce` to `newton:maxEffort`).
- **Mimic (coupled) joints — `NewtonMimicAPI`** on the follower `UsdPhysics.Joint`
  (`NEWTON.DJ.003`): author `rel newton:mimicJoint` pointing at exactly one leader joint (never
  the follower itself), with finite `newton:mimicCoef0` (offset) and `newton:mimicCoef1` (scale)
  enforcing `joint0 = coef0 + coef1 * joint1`; `newton:mimicEnabled` is a boolean. Apply only on
  single-DOF joints — a parallel-jaw gripper's second finger typically mimics the first with
  `coef1 = 1.0` (or `-1.0` to reverse). Do not invent a mimic relationship: only author it when
  the source mechanism is actually coupled.
- **Keep intended coupling and physical parameters.** An enabled, valid
  `NewtonMimicAPI` follower needs no placeholder drive or second actuator to
  satisfy `NEWTON.DJ.001`. Redundant active controllers can fight the coupling;
  inspect their actual commands and measured travel before proposing a repair.
  A sphere escaping does not establish that a one-leader mechanism is wrong.
  Preserve source mechanical ownership; do not split a coupling or borrow gains,
  effort, friction or armature from another robot to obtain PASS. Armature is
  inertia-related tuning, not a requirement for a nonzero value on every joint;
  derive any justified change from this mechanism's evidence or report the
  missing physical data.
- **Zero residual raw drive gains on mimic followers.** Newton's USD importer
  (`import_usd.py`) inspects raw `drive:<axis>:physics:stiffness` and
  `drive:<axis>:physics:damping` attributes on every joint even when
  `PhysicsDriveAPI:<axis>` is omitted from `apiSchemas`. If a `NewtonMimicAPI`
  follower joint (`newton:mimicEnabled = true`) inherits non-zero raw
  `drive:<axis>:physics:stiffness` or `damping` from the neutral layer, Newton
  creates an active `JointTargetMode.POSITION` actuator holding
  `targetPosition = 0` that fights the mimic constraint and stalls the leader.
  In `runnables/physics/newton.usda`, explicitly author
  `float drive:<axis>:physics:stiffness = 0` and
  `float drive:<axis>:physics:damping = 0` on mimic follower joints that carry
  neutral drive gains.
- **Calibrate closed-loop controller gains separately from passive joint mechanics (`newton:damping`, `newton:friction`, `newton:armature`) and physical actuator ratings (`maxForce`, `velocityLimit`, limits).**
  - **Passive mechanical joint attributes vs. closed-loop controller laws**:
    1. In `NewtonJointAPI` (`NEWTON.DJ.002`) and `import_usd.py`, `newton:damping` (`model.joint_damping` $\to$ MuJoCo `dof_damping` in `qfrc_passive`) defines **always-active passive mechanical viscous drag**, not a closed-loop PD controller gain. Altering `newton:damping` changes coasting, free fall, and backdriving behavior even when the actuator is disabled or uncommanded. Preserve or source/measure passive mechanical properties (`newton:damping`, `newton:friction`, `newton:armature`) from the source robot specification (URDF/MJCF `<dynamics damping="..." friction="..."/>`, manufacturer datasheets, or measured passive joint mechanics) rather than inventing passive losses from `maxForce / velocityLimit` to fit benchmark velocity peaks.
    2. In Newton's MuJoCo-Warp solver (`solver_mujoco.py`), `model.joint_velocity_limit` (`newton:velocityLimit`) is imported and read by `RobotHandle.get_joint_velocity_limits()`, but is **not** enforced as a hard solver velocity cap during simulation, and `jnt_actfrcrange = (-maxForce, +maxForce)` clamps total actuator effort:
       $$f_{\text{act}} = \operatorname{clip}\!\big(k_p(q_{\text{des}} - q) - k_d\dot{q},\; -\text{maxForce},\; +\text{maxForce}\big).$$
       Meanwhile, implicit velocity integration adds $+dt(k_{d,\text{rad}} + b_{\text{rad}})$ to the effective mass matrix $M_{\text{impl}} = M + dt(k_{d,\text{rad}} + b_{\text{rad}})$.
  - **Evidence-based controller calibration in `runnables/physics/newton.usda`** (all named models/joints below are illustrative examples only; repair decisions must derive from the selected asset's topology, measured behavior, and source specifications):
    - Preserve the asset's authored `newton:velocityLimit`, passive mechanical parameters (`newton:damping`, `newton:friction`, `newton:armature`), and source-derived `drive:<axis>:physics:maxForce` ratings (never delete or fabricate actuator ratings, passive drag, or joint ranges to pass a test).
    - Calibrate the supported closed-loop controller gains (`drive:<axis>:physics:stiffness` and `drive:<axis>:physics:damping` on `PhysicsDriveAPI`, or `newton:kp` / `newton:kd` on `NewtonPDControlAPI` / `NewtonPIDControlAPI`) so the closed-loop time constant $\tau = (k_{d,\text{rad}} + b_{\text{rad}}) / k_{p,\text{rad}}$ tracks smoothstep ramps in `state_accuracy_newton` and `full_range_sweep_newton` without overdamped lag while keeping $(k_{p,\text{rad}} / (k_{d,\text{rad}} + b_{\text{rad}})) < 2/\Delta t$ for explicit-position / implicit-velocity numerical stability.
    - Do **not** hide a missing solver hard-velocity-cap enforcement in `velocity_limit_newton` by inventing or inflating passive `newton:damping` (or reducing `maxForce`); if a joint with valid source-derived passive mechanics and controller gains exceeds `newton:velocityLimit` under a full-range step command because `SolverMuJoCo` does not enforce `model.joint_velocity_limit` and clamps actuator damping inside `jnt_actfrcrange`, preserve the physical parameters and report the runtime/solver velocity-clamping limitation.
    - **Gravity-sag stiffness calibration (`full_range_sweep_newton`, `multi_joint_coordination_newton`, and `jacobian_ik_newton` holds)**:
      Unlike `state_accuracy_newton` (which runs at `gravity = 0.0` with a `5.0 deg` tolerance), `full_range_sweep_newton`, `multi_joint_coordination_newton`, and `jacobian_ik_newton` run under full Earth gravity ($9.81\,\text{m/s}^2$). At static equilibrium ($\dot{q} = 0$), gravity sag is $|\Delta q_{\text{grav}}| = |\tau_g(q)| / k_{p,\text{rad}}$ (assuming $\tau_{\max} > |\tau_g(q)|$), which also accumulates into Cartesian end-effector deflection $\|\Delta x_{\text{EE}}\| \approx \sum_i \|J_{v,i}(q^*)\|\,|\tau_{g,i}|/k_{p,i,\text{rad}}$. On gravity-loaded shoulder/elbow/wrist joints where static gravity droop exceeds the measured goal tolerances while effort is below `maxForce`, tune controller `drive:<axis>:physics:stiffness` and `drive:<axis>:physics:damping` in tandem so static droop stays within tolerance without destabilizing step or ramp tracking.
  - **Distinguishing controller tuning (`stiffness`, `damping`, `kp`, `kd`) from passive mechanics (`newton:damping`, `newton:friction`, `newton:armature`) and physical actuator capacity (`maxForce`, `velocityLimit`, limits)**:
    - Closed-loop controller gains (`drive:<axis>:physics:stiffness`, `drive:<axis>:physics:damping`, `newton:kp`, `newton:kd`) tune the servo control law; `newton:damping`, `newton:friction`, and `newton:armature` represent passive mechanical joint properties; and `drive:<axis>:physics:maxForce`, `newton:velocityLimit`, and `physics:lowerLimit` / `upperLimit` represent physical hardware ratings.
    - Do **not** fabricate or inflate `maxForce`, invent passive `newton:damping`, or alter joint limits merely to satisfy a benchmark probe (such as `effort_limit_newton`'s external `10 N` disturbance on a low-force mechanism, `velocity_limit_newton` step peaks, or `full_range_sweep_newton` on a joint whose physical torque rating is smaller than gravity torque $\tau_g$).
    - Only modify `drive:<axis>:physics:maxForce`, `newton:damping`, or `newton:friction` when source specifications (URDF/MJCF actuator `effort`/`forcerange`, joint `<dynamics>`, or manufacturer datasheets) establish that the neutral USD value was mis-converted — for example, replacing an unauthored float32 sentinel (`3.4028235e38`) or a converter placeholder (`1000`–`60000` N on a small gripper finger) with the source hardware rating, or restoring a documented source actuator torque limit. When a mechanism's genuine source actuator rating or passive mechanics cannot support a test's external probe load, gravity torque, or step command, preserve the source values and report the physical or runtime limitation.
- **Verify consistency of `targetPosition`, `state:<axis>:physics:position`, and link rest transforms (`DJ.001`, `DJ.003`), and preserve valid authored rest poses and winding.**
  1. Newton's `ModelBuilder.JointDofConfig` checks whether `drive:<axis>:physics:targetPosition` lies within `[lowerLimit, upperLimit]`, and `NewtonStage` initializes `state_0.joint_q` from link world poses via `newton.eval_ik(...)`.
  2. When an asset has a genuine authoring defect — such as `targetPosition` disagreeing with `state:<axis>:physics:position` (`DJ.001`), `targetPosition` or link transforms falling outside `[lowerLimit, upperLimit]` (e.g. a converter writing `targetPosition = 0.0` on a joint whose limits exclude `0`), or `state:<axis>:physics:position` disagreeing with the composed `body0`/`body1` link pose (`DJ.003`) — repair `targetPosition`, `state:<axis>:physics:position`, and (only when the USD link transforms disagree with the source rest configuration) the child link transforms so they match the source mechanism's valid in-bounds rest pose.
  3. **Do not rewrite a valid authored rest pose or limited-joint winding merely to shorten travel to a benchmark waypoint.** If an asset's `targetPosition`, `state:<axis>:physics:position`, and link transforms are mutually consistent and within `[lowerLimit, upperLimit]`, preserve that rest pose and winding (for example, do not replace a valid `-360 deg` state/target on a finite `[-360, 360] deg` joint with `0 deg` while leaving the limits unchanged, as that alters the remaining legal travel relative to the mechanical stops from `[0, 720] deg` to `[-360, 360] deg`). If the coordinate convention itself requires conversion from source evidence, transform `lowerLimit`, `upperLimit`, states, targets, and couplings consistently together; if a test's fixed initial ramp duration (`state_accuracy_newton`'s `0.5 s` ramp to `center`) saturates `newton:velocityLimit` from a valid rest pose, diagnose the test ramp pacing or initialization rather than altering the asset's default pose.
  4. When iteratively tuning `newton.usda` across driven-joint tests, never overwrite or strip valid existing `targetPosition`, `state:<axis>:physics:position`, `physics:lowerLimit`, `physics:upperLimit`, `physics:jointEnabled`, or link `xformOp` opinions, and always re-verify all driven-joint tests together.
- **Exclude the loop-closing joint on 4-bar / parallel linkages (`DJ.011`) and zero residual drives on dependent linkage/gripper joints.**
  - Newton requires every joint inside the articulation tree
    (`physics:excludeFromArticulation = false`) to be directed from parent
    (`physics:body0`) to child (`physics:body1`) away from the articulation root;
    traversing an articulation joint backwards raises
    `ValueError: Reversed joints are not supported`. In a closed kinematic loop
    (for example `J2_link -(P1)-> P1_link -(P2)-> P2_link -(P2_01)-> J3_link`),
    author `uniform bool physics:excludeFromArticulation = true` on the
    loop-closure joint (`P2_01`) and `false` on the root-side chain joints (`P1`,
    `P2`) in `runnables/physics/newton.usda`.
  - In `jacobian_ik_newton`, `control_ownership()` and `detect_loop_joints()`
    exclude passive joints (`_joint_is_passive()`), `NewtonMimicAPI` followers, and
    passive loop-only branch joints from the independent IK DOFs (`locked_indices`).
    When a 4-bar linkage or coupled multi-DOF gripper has dependent joints that
    inherit non-zero `drive:<axis>:physics:stiffness` / `damping` from
    `payloads/Physics/physics.usda` (holding `targetPosition = 0`), explicitly zero
    `float drive:<axis>:physics:stiffness = 0` and
    `float drive:<axis>:physics:damping = 0` on those dependent joints in
    `runnables/physics/newton.usda` so residual zero-target springs do not fight
    the mechanism or cause passive loop joints to be treated as independent active
    DOFs. Only author `NewtonMimicAPI` when the source mechanism establishes an
    actual affine coupling relationship; do not add affine mimic constraints to a
    general nonlinear closed-loop linkage.
- **Preserve unbounded continuous revolute joints (`±inf`); do not invent position limits to avoid `SweepBudgetExceeded`.**
  - Continuous revolute joints (such as unbounded wrist roll or base rotation joints) legitimately omit `physics:lowerLimit` and `physics:upperLimit` (`±inf`).
  - Never invent finite position limits (such as `[-360, +360] deg`) on a continuous joint to prevent `jacobian_ik_newton` solver windup or `SweepBudgetExceeded`: adding artificial limits converts a continuous mechanism into a limited one and causes range-based tests (`full_range_sweep_newton`, `multi_joint_coordination_newton`) to test fabricated bounds. Only author finite limits when the source robot specification (URDF/MJCF/datasheet) defines a finite joint range that was omitted in conversion; otherwise preserve the unbounded joint and diagnose/report any solver winding or playback-budget limitation.

## Runtime Verification Boundary

Use real `simready-validate` for the selected static gate and real
`simready-evaluate` with the exact selected manifest's
`simready.foundation.tier_newton.runtime_tests:<name>` bindings for dynamic
verification, including applicable dependency coverage. Inspect installed
providers, selected runtime/variant and source or wheel provenance first; use
the matching Evaluate `run-tests` and `diagnose-failures` skills where available.
Do not substitute a look-alike test or change framework code, bindings or
thresholds as part of asset repair. Such maintenance requires separate authority.

Current published `gripper_close_lift_cube` and `gripper_close_lift_sphere` are
Core's PhysX-only `FET028_Gripper.Isaac.0-1-0` coverage, not Newton grasp
acceptance. This Newton driven-joint contract does not supply a Newton close/lift
test. Report that coverage gap instead of enabling an experiment or using a
PhysX PASS to certify Newton. An FET004 movement probe likewise does not replace
authored-control FET022 coverage or prove grasp retention.

Missing/nonfinite required observations, failed initialization or a wrong
backend leave execution incomplete; an applicability skip supplies no response
PASS. A finite measured FAIL establishes only the tested response, not an asset
defect or the cause. Diagnose setup, mapping, controller/importer and actual
asset evidence before making a source-derived, authorized repair.

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET022_DrivenJoints.Newton` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET022_DrivenJoints.Newton` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET022_DrivenJoints.Newton` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair only the requirements listed by the selected `FET022_DrivenJoints.Newton` manifest and its dependencies.
- Repair joint tuning and the existing standard-drive, Newton-actuator or indirect
  mimic actuation only where the selected requirements demonstrate a violation.
  Keep the Newton layer free of `Mjc*` / `Physx*` joint or actuator schemas.
- Preserve valid indirect mimic actuation and the mechanism's independently
  controlled coordinates. Repair only a demonstrated violation; missing runtime
  coverage is not a reason to redesign jaws or add tuning values.
- Do not add schemas, metadata, or runtime behavior for a sibling runtime feature.
- Report missing runtime/tooling evidence as a validation limitation instead of claiming a pass.

## Samples

- `sample_content/common_assets/robots_general/Robotiq/2F-85/simready_usd/runnables/physics/newton.usda`
  — inspect this sample's composed actuator, coupling and collision opinions as
  examples only. Its topology and numerical tuning are not transferable repair
  defaults and its presence does not prove current native runtime acceptance.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `FET022_DrivenJoints.Newton.0-1-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
