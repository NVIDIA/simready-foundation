# state_accuracy  (FET022 Driven Joints)

| Property     | Value                                                                         |
|--------------|-------------------------------------------------------------------------------|
| Test name    | state_accuracy                                                                |
| Feature(s)   | `FET022_DrivenJoints.PhysX.0-1-0`, `FET022_DrivenJoints.PhysX.0-2-0`, `FET022_DrivenJoints.Isaac.0-1-0`, `FET022_DrivenJoints.Isaac.0-2-0` |
| Engine       | Kit / Isaac Sim (>=2024.2.0)                                                  |
| Test version | 1.2.9                                                                         |
| Wall-clock timeout | 600 seconds |

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

Commands each driven joint through a five-waypoint sequence and verifies that the
reported joint position matches the commanded position within tolerance at each
waypoint.

## Optional Motion Evidence

An optional `sta_joint_NNN` history records the existing position and velocity
readbacks, the actual smoothstep command (`target`), the final waypoint
(`final_goal`), and both command and final-goal errors. A ramp command is not
labelled as the final goal. Each bounded ramp completes its full smoothstep
command sequence and sends its endpoint before settling, even when readbacks
enter a coarse goal band sooner. The hold records that actual last command;
recording sends no commands or ticks. Each waypoint has separate ramp/settle
phases in one cumulative per-joint clock.

Joint metadata identifies radians/radians-per-second for revolute joints.
Prismatic tensor scaling is unqualified and remains `unknown_native`, with
stage meters-per-unit recorded as context; unresolved identity also stays
unknown. Raw USD body/bounding-box distances remain stage lengths.
Time is estimated from observed physics steps and
configured `physics_fps`, excluding capture/render and setup ticks. A capture
references the preceding retained observation rather than an exact video-frame
timestamp. Up to 4096 samples are retained per history, normally every fourth
sample plus phase changes. Diagnostic recording failures mark evidence partial
and warn without changing finite response criteria. Unavailable or invalid
required verdict readbacks stop as setup/runtime errors. Older runners without
the motion API execute normally.

## Independent Control Ownership

Declared mimic followers, passive coordinates and identified loop joints receive
no independent position, target or velocity writes, including restoration where
used. Their live motion remains determined by authored coupling/dynamics.
Other independent coordinates retain the existing starting hold targets;
eligibility, target selection and response criteria are unchanged. Sparse
commands must use a genuine indexed runtime API: an unqualified backend stops
with a setup/capability error before excitation, never an asset-response FAIL.
Core requires the selected PhysX engine for this procedure. Newton's separately
owned implementation and backend qualification are not established by this
page. No-applicable-joint cases still skip before control checks.

## Required Runtime State

Missing, non-finite or wrong-shaped runtime state needed by control or the
verdict stops the test as a setup/runtime error, not conformance PASS or an
evaluated asset-response FAIL. Optional extra motion readbacks remain nullable
and can mark diagnostic evidence partial. Position criteria and timing are
unchanged; all five waypoints are now kept inside valid reported joint limits.

## Spatial Safety Observation

The safety guard compares required finite live articulation geometry with a
frozen setup reach reference derived from owned body geometry, joint-anchor
offsets and bounded prismatic travel, when that topology can be qualified.
The configured volume-margin factor is applied as its cube root to this span;
ordinary bending from a slender initial pose is not judged against that pose's
small volume. Unsupported topology retains an explicitly unqualified initial
volume proxy. `sta_guard_reference` records the basis and qualification;
`sta_guard_abort` retains a detected guard interruption when diagnostics
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

A passing result confirms that sampled position readbacks satisfy the existing
waypoint criterion after the bounded smoothstep ramp has commanded its final
goal. Only the following hold may end early on consecutive settled samples;
the ramp does not truncate or jump to its endpoint. Consult actual command and
final-goal channels separately. It does not provide
an independent calibration of joint-state reporting or rule out noise and
tracking errors between those samples.

## What It Checks

The test commands each non-passive, non-mimic-follower joint through five
waypoints: a zero-derived center clamped to the legal interior, a positive step,
back to center, a negative step, and back to center again. The step size is the smaller of `max_step_deg` (default
15 degrees) and `step_range_fraction` (default 10 percent) of the full joint
range. `test_duration_seconds` (default 3.0 s) budgets the five-waypoint motion
sequence, not a separate three-second settle for each waypoint or a strict
whole-sequence deadline. The per-waypoint settle budget is half a nominal
second (at least 30 ticks), and each ramp retains a minimum of 30 ticks after
deducting those holds from the configured sequence window. At the default
240 Hz this permits 750 nominal ticks (3.125 seconds) before hold early exits,
excluding initial setup and capture/render work. The eventual readback is
compared against the final goal. A joint
fails if the position error at any waypoint exceeds `position_tolerance_deg`
(default 5 degrees for angular evaluation). This legacy angular configuration
does not establish a calibrated linear-joint distance tolerance. The test skips when no
testable joints are found.

## How It Works

Joints are tested in isolation. For each joint, the drive is commanded to each
of the five waypoints in sequence. The test waits for the settling duration at
each waypoint and then samples the current joint position from the articulation
state. The absolute position error is computed and compared to the tolerance.
If any waypoint error exceeds the tolerance, the joint is counted as failed, and
the test fails.

Core owns this PhysX/Isaac implementation and retains its existing scene setup
and timing. This wrapper explicitly requests zero gravity: it measures command
tracking, not gravity compensation. Authored world constraints remain in effect;
a qualified standalone gripper can receive the shared setup's temporary world
pin, but this procedure does not attach a carrier or guarantee a fixed base for
every articulation. It commands and reads back the asset's authored drives without
rewriting their gains. Newton owns a separate implementation and its own scene
setup; see the Newton tier's
source guide
`nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/runtime_tests/docs/runtime-tests.md`
for its behavior and diagnostic caveats.

## Failure Cases

| Symptom | Checks before assigning a cause |
|---|---|
| Position error exceeds the configured criterion | Compare actual command and final goal, selected variant, readback units, drive/axis mapping, gravity and settling setup |
| Error only on one direction | Check limit clipping, center/goal assumptions and imported coupling before changing authored offsets |
| Error grows with each waypoint | Inspect sampled commands/readbacks and phase timing; drift alone does not identify an unsafe gain value |

## How to Fix

Preserve the original asset and run. Match the exact provider/test/version,
selected variant, actual commands and final goals to the raw motion evidence.
Verify authored versus runtime units, drive/state API mappings, limits, coupling,
mass/inertia and solver/test setup before calling this an asset defect.

Only repair a demonstrated contract violation. A test assumption about center,
timing or linear units can instead require a provider issue. Retuning belongs
outside Evaluate; do not paste generic gains, change ratings or relax tolerance
solely to force a pass.

## Expected Result

![state_accuracy expected result](../_images/state-accuracy.png)

[Result video](../../../../../../../../sr_specs/docs/_static/videos/state-accuracy.mp4)

Each joint visits five waypoints in sequence: the legal center, a positive
directional target, center again, a negative directional target, and center again.
Clipping can make a directional target coincide with center for an offset range.
The video and graphs show the observed response. Drift, oscillation or failure
to reach a final goal warrants investigation; it does not by itself identify
drive stiffness or damping as the cause.

## Notes and Caveats

The test skips when no eligible joints remain after passive, mimic-follower,
loop and runtime-range selection. A skip supplies no measured response coverage.

The waypoint sequence is designed to exercise both the positive and negative
direction of the drive and to confirm that the joint returns reproducibly to the
center goal. The center is the nearest legal interior point to zero, not the
asset's authored home. The interior margin is the smaller of 0.05 native units
and 10 percent of the reported range, so narrow ranges are not inverted. When
zero lies outside the range, one directional step can coincide with center;
the sequence does not guarantee two distinct excursions. Nonfinite, inverted
or native ranges narrower than 0.01 are not selected; this is a procedure
eligibility threshold, not a universal authored travel requirement. Never expand
authored limits to fit a zero-centered test assumption.

The corresponding Newton FET022 tests are maintained by the Newton tier. Their
implementation and controls are separate from Core's PhysX/Isaac code; this page
describes only the Core test listed in the metadata table above.
