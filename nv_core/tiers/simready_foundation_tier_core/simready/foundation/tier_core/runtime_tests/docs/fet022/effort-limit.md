# effort_limit  (FET022 Driven Joints)

| Property     | Value                                                                         |
|--------------|-------------------------------------------------------------------------------|
| Test name    | effort_limit                                                                  |
| Feature(s)   | `FET022_DrivenJoints.PhysX.0-1-0`, `FET022_DrivenJoints.PhysX.0-2-0`, `FET022_DrivenJoints.Isaac.0-1-0`, `FET022_DrivenJoints.Isaac.0-2-0` |
| Engine       | Kit / Isaac Sim (>=2024.2.0)                                                  |
| Test version | 1.2.0                                                                         |
| Wall-clock timeout | 1200 seconds |

## Nominal Initial Settling

Before measuring the response, the phase requests complete `ctx.step_one()`
ticks for the configured initial settling interval, rounded up from
`settle_seconds * physics_fps`. Zero settling is allowed; FPS must be finite
and positive, and settling seconds finite and nonnegative. Invalid timing
configuration or failed ticks remain execution errors, not asset verdicts.
This is nominal requested tick time, not measured solver or wall-clock time;
render/capture work is separate. The processing-only `ctx.physics_steps()`
helper is not used to establish this interval.

## Summary

Applies an external force at each testable joint's live child-body center of
mass in 12 world directions
and checks for finite runtime position-range overrun. A separate spatial
safety guard interrupts incomplete execution when its observation trips.
Missing or non-finite required COM or position readback is a setup/runtime error, not
an evaluated asset response failure.
The COM read requires the child's exact USD path in the existing cooked
articulation tensor view's single link-path row, aligned with its live body
pose and COM tensors. Missing, inconsistent, or nonunique cooked link paths
are execution limitations that stop before force submission. A leaf body
name or USD rigid-body ownership alone does not identify a tensor row.

Probe setup first binds the native coordinate to one enabled, non-excluded
joint in the selected physical articulation. Exact cooked DOF paths, when
available, and supported path/axis aliases identify the joint. Forwarded joint
endpoints resolve to their owning rigid bodies. The downstream child follows
qualified rooted topology, independent of body0/body1 ordering; a container
root without an unambiguous world pin needs complete cooked parent metadata.
Disabled shadows, foreign joints, ambiguous topology and detached/rebound
views are required setup errors. Ownership is resolved at probe setup; live
transform and COM tensors are still read afresh on every force tick.

## Optional Motion Evidence

An optional `eff_joint_NNN` history records the existing position readback and
the three components of the world-frame external force actually issued on the
child body. Force channels are in newtons; they are not measured joint torque,
actuator effort, or a measurement of the authored effort ceiling. Joint metadata
identifies radians for revolute position. Prismatic tensor scaling is
unqualified and remains `unknown_native`, as does unresolved identity;
stage meters-per-unit is recorded as context without a guessed conversion.
Raw USD body/bounding-box distances remain stage lengths.
`force_point_x/y/z` record the observed live world COM used at retained force
samples in native articulation world coordinates. The bounded
`eff_force_point_observation` diagnostic records the latest body, direction,
basis and nullable COM coordinates; null means the required point was
unavailable. These coordinates are not contact measurements. Their
stage-to-meter conversion is unqualified, so they are not labelled meters.
Metadata also records the tested child body, finite `runtime_lower` /
`runtime_upper` position limits, their `runtime_limit_source`, and the
break-tolerance configuration. These limits are the actual
`RobotHandle.get_joint_position_limits()` readback in native joint coordinates,
not raw authored USD limits. Older unreleased histories labelled the same
values `authored_lower` / `authored_upper`; do not reinterpret them as USD
degrees or apply another unit conversion.

Force-direction phases share a cumulative per-joint clock estimated from
observed probe steps and configured `physics_fps`; reset, setup, and
capture/render ticks are excluded. A capture references the preceding retained
observation, not an exact solver/video timestamp. Up to 4096 samples are
retained per history, normally every fourth sample plus phase changes.
Ordinary observer/metric publication failures leave force application and local
verdict calculation unchanged. A producer's `None` capture/encode result omits
that media; unknown engine errors, unsafe evidence paths, cancellation and
required force cleanup still stop execution. Live COM is a required tensor readback on every force
tick; a missing or malformed point stops the current joint as incomplete while
retaining previously completed joint results and motion samples. No extra
physics steps are added. Evidence does not by itself establish an actuator's
torque rating.

When a later direction cannot complete after an earlier direction evaluated a
range overrun, `eff_incomplete_joint_evidence` retains the evaluated direction
and reason as partial evidence. The interrupted joint is not counted among
`eff_joints_tested`, `eff_joints_passed` or `eff_joints_failed`.

## Spatial Safety Observation

The safety guard compares required finite live articulation geometry with a
frozen setup reach reference derived from owned body geometry, joint-anchor
offsets and bounded prismatic travel, when that topology can be qualified.
The configured volume-margin factor is applied as its cube root to this span;
ordinary bending from a slender initial pose is not judged against that pose's
small volume. Unsupported topology retains an explicitly unqualified initial
volume proxy. `eff_guard_reference` records the basis and qualification;
`eff_guard_abort` retains a detected guard interruption when diagnostics
are available. Raw initial-box metrics remain observations, not the qualified
reach reference.

A guard trip interrupts execution as a runtime/setup error with incomplete
response coverage, not an evaluated joint/target failure or an asset-defect
diagnosis. Required geometry errors also propagate; optional diagnostic
persistence cannot disable the guard or replace its original cause. Inspect
completed observations/timing records where supplied, rather than assuming
all planned motion ran. No extra physics steps or acceptance tolerances are
introduced; native qualification of the reported asset remains separate.

## What Pass Guarantees

A passing result confirms that the observed probe windows did not overrun the
tested runtime position ranges beyond the configured allowance, with no
spatial safety interruption. Required position observations must remain finite
and available. Motion within the full allowed position range
can still pass. This test does not measure actuator torque, prove holding of a
commanded pose, or establish enforcement of `driveMaxForce`/an effort rating.
The force magnitude and direction window are test inputs, not certified loads.
Passive, mimic-follower and identified loop joints are excluded from the force
candidate set. A remaining joint is eligible with a finite runtime position
range wider than 1e-6 native coordinates or a positive finite effort-limit
readback. For an effort-only candidate without a finite range, the positional
overrun gate cannot establish
range containment; the sampled geometry guard remains separate. Such a PASS
does not turn an absent range or the effort input into measured effort compliance.

## What It Checks

The test commands all joints to a stable configuration and then, for each joint,
applies a `force_magnitude_newtons` (default 10.0 N) force at that joint's
child-body center of mass in each of 12 evenly distributed world directions in
sequence. The COM is recomputed from the cooked articulation's live link pose
and link-local COM offset before every force submission.
The lookup requires a unique exact cooked link path from the articulation
tensor view; leaf names and USD rigid-body ownership cannot substitute for
it. Numeric-suffixed cooked body names are accepted when exact paths identify
the rows. The supported cooked path layout has one articulation row with one
path per body name; missing or other layouts are not qualified.
Link and COM quaternions must be finite and
have norm above float32 unit-scale machine epsilon before normalization.
After each force application, the test checks the selected joint's position against its
runtime-imported limits plus `break_tolerance` (default 0.10, that is, 10
percent of that joint's runtime position range). A finite selected-joint
observation that exceeds this threshold is counted as failed. A separate
sampled bounding-box guard covers the whole articulation; this does not
independently establish range containment of every coupled joint during that
force block.
When `stop_on_first_break` is true (default), the test stops further force
directions for the current failed joint; subsequent eligible joints still run.

The total test duration is distributed across all 12 force directions within
`test_duration_seconds` (default 2.0 s).

## How It Works

The robot is held in its configured pose using the drive stiffness and damping
values already authored on the asset. The external force is applied as a
continuous world-frame force at the joint's live child-body COM, re-applied every
physics tick through `IPhysxSimulation.apply_force_at_pos`. The simulation runs for each
direction segment, and joint positions are sampled on its existing probe steps.
The selected joint fails if its finite position exceeds its runtime-imported limits by more than `break_tolerance` times its joint range. Other coupled joints are not independently range-checked during that block; whole-articulation bounding-box growth is a separate guard.

The test does not modify the drive gains or the mass properties of the
articulation. It uses the asset as authored.

## Failure Cases

| Observed symptom | Checks before attributing a cause |
|---|---|
| Runtime range overrun | Actual readings, imported limits/controls, units and force leverage |
| Missing or non-finite required readback (setup/runtime error) | Initialization, view/body mapping and importer/API support; no evaluated asset response is available |
| Bounding-box growth | Geometry, transforms, constraints and base/gravity setup; growth alone does not establish an asset defect |

Completed per-joint outcomes are published in `eff_joint_results` and the
`eff_joints_*` aggregates. A required-operation interruption anywhere in a
joint probe preserves the original error and attempts independent best-effort
publication of earlier completed joints and `eff_incomplete_joint_evidence`.
The interrupted joint's observed `broke_directions` and `broke_reasons` are
partial evidence, never a completed pass/fail or aggregate count. Optional
observer, capture, metric, logging and cleanup failures do not replace the
primary required-operation error. Inspect the available native payload; failed
publication is unavailable evidence, not guaranteed persistence. The legacy
`min_break_force_newtons` field stays null: the procedure performs no refinement
probes and cannot establish a minimum breaking force or a measured lower bound.
`commanded_force_at_failure_newtons` records only the configured force magnitude
actually issued when a criterion failed, not physical breakage or actuator
effort. After a criterion failure, `bisection_enabled` emits an
unsupported-refinement warning; the retained bisection configuration keys do
not cause extra probes or steps.

A missing required PhysX force interface, unmapped or ambiguously mapped child
body, unavailable/malformed live link pose or COM offset, failed force
submission, or missing/non-finite required position readback is a
setup/runtime error. A meaningful range-containment verdict needs the planned
force application and usable observations.

## How to Fix

Distinguish evaluated range overrun from incomplete spatial-safety observation
or readback/setup errors. Inspect
force/body mapping, leverage, imported controls/limits, units, base/gravity setup
and solver support before assigning an asset defect. These criteria do not measure
physical breakage or actuator-effort enforcement.

World-frame body force in N cannot be compared directly with actuator torque in
N*m. Do not raise ratings, widen limits or reduce the load merely to pass. Preserve
the original asset, plan and trajectory. Repair/tuning is external to Evaluate.

## Expected Result

![effort_limit expected result](../_images/effort-limit.png)

[Result video](../../../../../../../../sr_specs/docs/_static/videos/effort-limit.mp4)

World-frame forces are applied at each joint's live child-body COM from multiple
directions under the recorded gravity and base-constraint setup. This test does
not attach a carrier fixture: authored world constraints remain in effect, and
qualified standalone grippers may receive a temporary world pin. Inspect
`scene_info.pinned_to_world`; a fixed base is not guaranteed for every robot.
The existing visualization
may show an arrow; it is not a measured contact force. Some joint movement is
permitted by the unchanged positional-range criterion. Use the video and
recorded positions to review behavior, not as proof of an actuator effort rating.

## Notes and Caveats

The 12 force directions are evenly distributed on the unit sphere. Not all
directions produce equal torque at every joint. A force through the child-body
COM can still have a nonzero moment about a joint anchor offset from that COM;
the moment depends on the live anchor-to-COM lever arm and force direction.

The test does not check torque values directly. Its failure criterion concerns
position-range containment and a sampled instability canary, not compliance
with a particular commanded pose or an actuator torque/force envelope.
