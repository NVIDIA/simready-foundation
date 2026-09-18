---
name: simready-foundation-conform-fet-022-newton
description: "Use for repairing exact FET_022_NEWTON SimReady conformance for Newton driven-joint conformance. Use when a profile, validation report, or user request names FET_022_NEWTON; default to version `0.1.0` unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - newton
---

# SimReady Conform FET_022_NEWTON

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_022_NEWTON`. It repairs or stages Newton driven-joint conformance without drifting into another runtime contract.

Default to `FET_022_NEWTON@0.1.0` when the user asks for this feature without a version. Use an older integer version only when the profile, validation report, or user explicitly pins it. If the report names a different `FET_###_RUNTIME` feature, switch to that feature's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_022_NEWTON-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_022_NEWTON.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, benchmarks, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | FET_004_ROBOT_NEWTON@0.1.0 | `DJ.011`, `NEWTON.DJ.001`, `NEWTON.DJ.002`, `NEWTON.DJ.003` |

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
- **Actuation** (`NEWTON.DJ.001`) — each non-fixed articulation joint must be actuated in exactly
  one of three ways (unless `physics:excludeFromArticulation = true`): a `PhysicsDriveAPI:<axis>`,
  a `NewtonActuator` that targets it, **or** a `NewtonMimicAPI` coupling to a leader joint. A mimic
  follower is actuated indirectly through the coupling, so it needs **no** drive or actuator of its
  own. In an isolated Newton runtime layer, give each joint exactly one actuation source to avoid
  double-driving. The usual pattern removes the neutral `PhysicsDriveAPI:angular` (and
  `PhysicsJointStateAPI:angular`) in the Newton runnable and drives the leaders via `NewtonActuator`.
  Keep the standard `PhysicsDriveAPI` only when the same joint must serve multiple runtimes in one
  composition.
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
- **Mimic followers carry no drive (avoid the hollow pass).** As of `NEWTON.DJ.001`, a
  `NewtonMimicAPI` follower is a valid actuation form on its own: the coupling ties the follower's
  DOF to its leader, so the follower needs **no** `PhysicsDriveAPI` or `NewtonActuator`. Author the
  mimic coupling and leave the follower **drive-less** — this is the clean, non-hollow pattern. Do
  **not** add an inert placeholder drive (older assets did this before the rule accepted mimic
  followers; it is now unnecessary), and never add an **active or damped** follower drive: a
  non-zero-stiffness/damping follower drive with a fixed target fights the leader through the
  coupling and can pin the whole mechanism — it passes static `NEWTON.DJ.*` validation but the
  leader barely moves in simulation (a hollow pass). Drive only the **leader** joint(s), via a
  `NewtonActuator` (preferred) or a `PhysicsDriveAPI` with gains strong enough for the Newton
  solver; runtime-neutral gains tuned for PhysX are usually far too soft. Verify real travel with
  runtime evidence (for example `simready-benchmark` `joint_movement`) before trusting the pass —
  a wide driven-joint tolerance can otherwise mask a near-zero leader motion.
- **Armature for stability on tightly-coupled loops.** On closely-packed, mimic-coupled
  mechanisms (parallel-jaw grippers, four-bar finger linkages) the Newton solver is prone to
  instability. Authoring `newton:armature` (via `NewtonJointAPI`, `NEWTON.DJ.002`) augments each
  DOF's rotational inertia and markedly stabilizes the solver across the coupled loop without
  changing the observed travel. Derive values from the source robot's Newton reference where one
  exists;   the Newton team's tuned `robotiq_2f85` reference uses roughly `newton:armature = 0.005`
  on the driven leader joint and `0.001` on the mimic followers as a sound starting point. Keep
  every value finite and non-negative.

## Parallel-Jaw Gripper Grasp (Newton)

A parallel-jaw gripper (for example the Robotiq 2F-85) that must actually **hold** an object in a
grasp-and-lift test (`FET_028`) needs more than a statically-valid driven-joint graph. Patterns
that pass `NEWTON.DJ.*` but drop the object in simulation, and their fixes:

- **Drive both jaw leaders, symmetrically and gently.** Driving one jaw leader and letting the
  opposite jaw only *mimic* it makes the following jaw go slack on off-center or spherical objects,
  which then squirt/roll out. Instead give **each** jaw leader its own matched `NewtonActuator`
  (same `newton:kp`/`newton:kd`) and split the linkage so each jaw's passive followers mimic *that
  jaw's* leader. Keep the effort **gentle** (the 2F-85 uses `newton:maxEffort ≈ 2.5` per jaw) so
  the close conforms to the object instead of slamming/ejecting it.
- **Give the pads a real, RV.011-clean contact surface.** A `purpose = "guide"` box collider is
  skipped by the benchmark's grip geometry (it computes bounds over `default`/`render` purposes)
  and by Newton, so the fingers have nothing to grip with. Instead reuse the actual rubber-pad
  mesh: in the Newton layer de-instance the fingertip pad mesh, `delete` its `Physx*CollisionAPI`
  schemas, and `prepend` `NewtonCollisionAPI` + `NewtonMeshCollisionAPI` (convex hull) bound to a
  high-friction `NewtonMaterialAPI` (see `FET_003_NEWTON`). This keeps the composition RV.011-clean
  (no leaked PhysX collision) while giving a large flat contact patch. If you must keep a separate
  proxy collider hidden from render, use `visibility = "invisible"` with default purpose, never
  `purpose = "guide"`.
- The `FET_028` grasp behavior is proven by runtime evidence (`simready-benchmark`
  `gripper_close_lift_{cube,sphere}`), not static validation; report it as a runtime check.

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET_022_NEWTON` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET_022_NEWTON` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET_022_NEWTON` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair only the requirements listed by the selected `FET_022_NEWTON` manifest and its dependencies.
- Author `NewtonJointAPI` tuning and `NewtonActuator` actuation per the vocabulary above; do
  not apply `Mjc*` / `Physx*` joint or actuator schemas on the Newton layer.
- On coupled (mimic) mechanisms, leave the followers **drive-less** — the `NewtonMimicAPI` coupling
  satisfies `NEWTON.DJ.001` — and tune only the leader(s). Do not author inert placeholder drives,
  and never add an active follower drive: it passes static validation but resists the leader and
  pins the mechanism in simulation.
- For parallel-jaw grippers that must hold an object, drive **both** jaw leaders with matched gentle
  `NewtonActuator`s and give the pads a real RV.011-clean mesh collider (see "Parallel-Jaw Gripper
  Grasp" above); a single-jaw drive or a `purpose = "guide"` collider passes validation but drops
  the object in the grasp benchmark.
- On tightly-coupled loops, author `newton:armature` (finite, non-negative) on every articulation
  joint for Newton solver stability — for example `~0.005` on the driven leader and `~0.001` on
  mimic followers — sourced from the robot's Newton reference where one exists.
- Do not add schemas, metadata, or runtime behavior for a sibling runtime feature.
- Report missing runtime/tooling evidence as a validation limitation instead of claiming a pass.

## Samples

- `sample_content/common_assets/robots_general/Robotiq/2F-85/simready_usd/runnables/physics/newton.usda`
  — parallel-jaw gripper: two gentle `NewtonActuator`s driving both jaw leaders, drive-less
  `NewtonMimicAPI` followers split per jaw, `newton:armature` on the leaders, and RV.011-clean pad
  contact (de-instanced fingertip mesh with `NewtonMeshCollisionAPI` bound to a high-friction
  `NewtonMaterialAPI`).

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_022_NEWTON@0.1.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
