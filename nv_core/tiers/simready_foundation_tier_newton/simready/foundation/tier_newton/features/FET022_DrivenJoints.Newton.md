# Feature: `FET022_DrivenJoints.Newton`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET022_DrivenJoints.Newton` |
| Runtime                 | `Newton` |
| Proprietary Techs       | `Newton` |
| Versions                | `0-1-0` |

## Description

Defines the Newton driven-joint contract. Actuation may be authored either with standard
`UsdPhysics.DriveAPI` drives or with the published Newton actuator schemas
(`NewtonActuator` + a control-law API), and Newton joint tuning is expressed with
`NewtonJointAPI` (or the equivalent `newton:*` resolver attributes) instead of PhysX joint
APIs. Coupled (mimic) joints are expressed with `NewtonMimicAPI`.

### Newton Authoring Notes

Editorial guidance (does not change the requirement IDs above):

- **Joint tuning** uses `NewtonJointAPI` on the `UsdPhysics.Joint`: `newton:armature`,
  `newton:damping`, `newton:friction` (all non-negative), `newton:velocityLimit`
  (positive or `inf`), and the `newton:limitStiffness` / `newton:limitDamping` limit spring
  (non-negative, or the `-inf` sentinel that defers to the engine default). Values broadcast
  uniformly to every DOF; angular attributes use degrees.
- **Actuators** are `NewtonActuator` prims that target a `PhysicsRevoluteJoint` or
  `PhysicsPrismaticJoint` via `rel newton:targets`. Each actuator applies exactly one control
  law — `NewtonPDControlAPI` (`newton:kp`, `newton:kd`, `newton:constEffort`),
  `NewtonPIDControlAPI` (adds `newton:ki`, `newton:integralMax`), or
  `NewtonNeuralControlAPI` — plus optional clamps (`NewtonMaxEffortClampingAPI` `newton:maxEffort`,
  `NewtonDCMotorClampingAPI`, `NewtonPositionBasedClampingAPI`) and an optional
  `NewtonActuatorDelayAPI` (`newton:delaySteps`). Actuators use radians.
- A joint counts as actuated for `NEWTON.DJ.001` when it has a `PhysicsDriveAPI:<axis>`,
  is targeted by a `NewtonActuator`, **or** has an enabled valid `NewtonMimicAPI`
  coupling to a leader. A mimic follower needs no independent drive/actuator.
  Standard drives are valid in Newton-only and multi-runtime compositions.
  Preserve valid drives, joint-state data, Newton-actuator control and indirect
  mimic actuation permitted by the selected requirement. Inspect redundant
  controllers for demonstrated conflicting commands before proposing a change.
  Replacing an actuation representation requires a separately authorized repair
  or conversion derived from the source mechanism; conformance work repairs only
  demonstrated violations in the existing representation.
- **Mimic (coupled) joints** use `NewtonMimicAPI` on the follower `UsdPhysics.Joint`
  (`NEWTON.DJ.003`): author `rel newton:mimicJoint` pointing at one leader joint (not the
  follower itself), with finite `newton:mimicCoef0` / `newton:mimicCoef1` enforcing
  `joint0 = coef0 + coef1 * joint1`. Apply only on single-DOF joints; typical use is a
  parallel-jaw gripper where one finger tracks the other. Because Newton's USD importer
  reads raw `drive:<axis>:physics:stiffness` and `damping` attributes even when
  `PhysicsDriveAPI:<axis>` is not in `apiSchemas`, ensure mimic follower joints do not
  retain non-zero neutral `stiffness` or `damping` values (author `0` in the Newton
  runtime layer when needed) so an implicit position drive at `targetPosition = 0` does
  not fight the mimic coupling.
- **Closed-loop controller calibration, passive joint mechanics, and rest targets under Newton** (illustrative examples only; all repairs must derive from the selected asset's topology, measured behavior, and source specifications):
  - In `NewtonJointAPI` (`NEWTON.DJ.002`), `newton:damping` (`model.joint_damping` $\to$ MuJoCo `dof_damping` in `qfrc_passive`) defines **always-active passive mechanical viscous drag**, not a closed-loop PD controller gain. Altering `newton:damping` changes coasting and backdriving behavior even with the actuator disabled. Preserve or source/measure passive mechanical joint properties (`newton:damping`, `newton:friction`, `newton:armature`) from the source specification (`<dynamics>`, datasheet, or measured passive mechanics).
  - Newton's MuJoCo-Warp solver (`solver_mujoco.py`) does not enforce `model.joint_velocity_limit`
    (`newton:velocityLimit`) as a hard solver velocity cap and clamps total actuator effort
    $f_{\text{act}} = \operatorname{clip}(k_p(q_{\text{des}} - q) - k_d\dot{q}, -\text{maxForce}, +\text{maxForce})$
    via `jnt_actfrcrange`, while adding $+dt(k_{d,\text{rad}} + b_{\text{rad}})$ to the implicit mass
    matrix $M_{\text{impl}} = M + dt(k_{d,\text{rad}} + b_{\text{rad}})$.
  - Calibrate supported closed-loop controller gains (`drive:<axis>:physics:stiffness` and
    `drive:<axis>:physics:damping` on `PhysicsDriveAPI`, or `newton:kp` / `newton:kd` on
    `NewtonPDControlAPI` / `NewtonPIDControlAPI`) separately from passive mechanical properties.
    On gravity-loaded joints where static gravity sag $|\tau_g(q)| / k_{p,\text{rad}}$ exceeds goal
    tolerances in `full_range_sweep_newton`, `multi_joint_coordination_newton`, or `jacobian_ik_newton`
    while effort is within `maxForce`, tune controller `stiffness` and `damping` in tandem (keeping
    $k_{p,\text{rad}} / (k_{d,\text{rad}} + b_{\text{rad}}) < 2/\Delta t$ for numerical stability).
    Do not hide a hard-velocity-cap limitation in `velocity_limit_newton` by inventing or inflating
    passive `newton:damping`; if a joint with valid source-derived passive mechanics and controller
    gains exceeds `newton:velocityLimit` under a full-range step command because the solver does not
    enforce hard velocity clamping, preserve the physical parameters and report the solver limitation.
  - **Distinguish controller tuning from passive mechanics and physical actuator capacity**: Do not
    fabricate or inflate `drive:<axis>:physics:maxForce`, invent passive `newton:damping`, or alter
    joint limits to pass a benchmark probe (`effort_limit_newton`, `velocity_limit_newton`, or
    `full_range_sweep_newton`). Only modify `maxForce`, `newton:damping`, or `newton:friction` when
    source specifications (URDF/MJCF actuator ratings, joint `<dynamics>`, or manufacturer datasheets)
    establish that the neutral USD value was mis-converted (such as an unauthored `3.4028235e38`
    sentinel or an inflated placeholder on a small gripper finger). When a mechanism's genuine source
    rating cannot support a test's external load or gravity torque, preserve the source rating and
    report the limitation.
  - On 4-bar parallel linkages (`J2_link -(P1)-> P1_link -(P2)-> P2_link -(P2_01)-> J3_link`,
    with `P2_01` having `physics:excludeFromArticulation = 1`) and on attached multi-DOF coupled grippers,
    zero `drive:<axis>:physics:stiffness = 0` and `damping = 0` on dependent/follower joints in
    `runnables/physics/newton.usda` so residual `targetPosition = 0` drives do not fight the mechanism
    and `control_ownership()` / `detect_loop_joints()` excludes passive closed-loop and follower DOFs
    during `jacobian_ik_newton`. Only author `NewtonMimicAPI` when the source mechanism establishes an
    actual affine coupling relationship; do not add affine mimic constraints to a general nonlinear
    closed-loop linkage.
  - **Preserve continuous revolute joints (`±inf`)**: Never invent finite `physics:lowerLimit` /
    `physics:upperLimit` (such as `[-360, +360] deg`) on a continuous joint to avoid `jacobian_ik_newton`
    `SweepBudgetExceeded`. Only author finite limits when source robot specifications define a finite range
    that was omitted during conversion; otherwise preserve the unbounded joint and diagnose/report any
    solver winding or playback-budget limitation.
  - **Preserve valid authored rest poses and winding**: Ensure `drive:<axis>:physics:targetPosition`,
    `state:<axis>:physics:position`, and link rest transforms are mutually consistent (`DJ.001`, `DJ.003`)
    and inside `[lowerLimit, upperLimit]`. Repair `targetPosition`, `state:<axis>:physics:position`, or
    link transforms only when evidence establishes an authoring mismatch against the source mechanism (such
    as `targetPosition = 0` on a joint whose limits exclude `0`). Do not rewrite a valid authored rest pose
    or replace a valid limited-joint winding (such as `-360 deg` on a `[-360, 360] deg` joint while leaving
    limits unchanged) merely to shorten travel to a benchmark's initial waypoint (`state_accuracy_newton`'s
    `0.5 s` ramp to `center`); if the coordinate convention itself requires conversion from source evidence,
    transform limits, states, targets, and couplings consistently together, or diagnose ramp pacing /
    initialization instead. When updating `runnables/physics/newton.usda`, preserve all valid authored joint
    and link opinions and re-verify all driven-joint tests together.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_004_ROBOT_NEWTON_0_1_0["FET004_Multibody.RobotNewton\n0-1-0"]
    FET_022_NEWTON_0_1_0["FET022_DrivenJoints.Newton\n0-1-0"]
    FET_022_NEWTON_0_1_0 --> FET_004_ROBOT_NEWTON_0_1_0

    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies Newton driven-joint requirements.
 - SimReady Evaluate runs `state_accuracy_newton` with the Newton engine to command
  driven joints and verify Newton joint-state readback against each target.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot-body.md): optional in `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`; required in `4.0.0`
- [Robot-Gripper](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot-gripper.md): optional in `2.1.0`, `2.2.0`, `3.0.0`; required in `4.0.0`

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET004_Multibody.RobotNewton.0-1-0` |

#### Requirement List

* Capability: [Physics Bodies/Physics Driven Joints](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/physics_driven_joints/capability-physics_driven_joints.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `DJ.011` | [DJ.011](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/physics_driven_joints/requirements/no-articulation-loops.md) |
| `NEWTON.DJ.001` | [NEWTON.DJ.001](../rules_and_reqs/physics_bodies/physics_driven_joints/requirements/newton-joint-drive-api.md) |
| `NEWTON.DJ.002` | [NEWTON.DJ.002](../rules_and_reqs/physics_bodies/physics_driven_joints/requirements/newton-joint-attributes.md) |
| `NEWTON.DJ.003` | [NEWTON.DJ.003](../rules_and_reqs/physics_bodies/physics_driven_joints/requirements/newton-mimic-api.md) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies Newton driven-joint requirements.
 - `state_accuracy_newton` runs in the Newton engine and verifies position-command
  tracking plus joint-state reporting for every eligible driven joint.

## Samples

- `sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usd`

## Evaluates

 - [`state_accuracy_newton`](../runtime_tests/docs/runtime-tests.md) (Kit / Isaac Sim Newton experience)

## Adapters

- `skill:simready-foundation-conform-fet-022-newton` (as declared by the versioned JSON manifest).
