# drive_gain_validation  (FET022 Driven Joints)

| Property     | Value                                                                         |
|--------------|-------------------------------------------------------------------------------|
| Test name    | drive_gain_validation                                                         |
| Feature(s)   | `FET022_DrivenJoints.PhysX.0-1-0`, `FET022_DrivenJoints.PhysX.0-2-0`, `FET022_DrivenJoints.Isaac.0-1-0`, `FET022_DrivenJoints.Isaac.0-2-0` |
| Engine       | Kit / Isaac Sim (>=2024.2.0)                                                  |
| Test version | 1.1.9                                                                         |
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

Commands each driven joint through a step input and evaluates the step-response
quality by measuring overshoot, settling time, and velocity sign changes.

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
and can mark diagnostic evidence partial. Eligible-joint goals, finite response
criteria, timing and configured failure policies are unchanged; command
ownership now leaves dependent/passive control buffers untouched.

## Spatial Safety Observation

The safety guard compares required finite live articulation geometry with a
frozen setup reach reference derived from owned body geometry, joint-anchor
offsets and bounded prismatic travel, when that topology can be qualified.
The configured volume-margin factor is applied as its cube root to this span;
ordinary bending from a slender initial pose is not judged against that pose's
small volume. Unsupported topology retains an explicitly unqualified initial
volume proxy. `dgv_guard_reference` records the basis and qualification;
`dgv_guard_abort` retains a detected guard interruption when diagnostics
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

By default (`step_fatal = false`), response exceedances are warnings: overall
PASS can include every sampled joint outside thresholds. Inspect response counts,
warnings and saved policy. With `step_fatal = true`, configured sampled response
criteria must pass. Neither policy proves continuous stability, identifies a
cause, or establishes safe drive gains across loads.

The spatial safety guard is separate from the joint response `ok` calculation.
Its trip leaves execution incomplete irrespective of `step_fatal`; it is not
a nonfatal response warning or evaluated gain-quality failure.

If a computed legal step is smaller than the existing 1e-6-native-coordinate
epsilon, the procedure records `evaluated: false` and an explicit reason,
with null response fields and no PASS/FAIL response claim. The row is excluded
from the tested, passed and failed response counts. `dgv_joints_eligible`
describes the selected candidates; `dgv_joints_tested` counts observed response
windows, and `dgv_joints_not_evaluated` identifies omitted candidates. A mixed
run warns about omitted coverage. If no legal step is observable despite
selected candidates, execution stops with NO VERDICT; no drive response was measured.

## What It Checks

The test commands each non-passive, non-mimic-follower joint to step by
`step_magnitude_deg` (default 30 degrees, converted to radians) from its current
position, choosing a legal direction or a shorter endpoint step when the range
is too narrow. The comparison uses imported runtime stops. This angular
configuration is also numerically applied to linear coordinates; it does not
establish a calibrated prismatic step distance.

`test_duration_seconds` (default 5.0 s) controls the observation window, with at
least 20 requested ticks. The window can stop early after 24 consecutive
observations below `settled_velocity_threshold` (default 0.05 native units/s).
`max_settling_seconds` (default 5.0 s) is a separate response acceptance
threshold, not an automatic extension of that window. Three metrics are evaluated:

- Overshoot: the peak position error beyond the target, as a percentage of the
  step magnitude. The threshold is `max_overshoot_pct` (default 50 percent).
- Settling: whether the joint position remains within `settling_tolerance`
  (default 5 percent of step magnitude) before `max_settling_seconds` elapses.
- Oscillations: the number of velocity sign changes during the settling window.
  The threshold is `max_oscillations` (default 20 sign changes).

By default, all three metrics are reported as warnings. Failures are only
promoted to a hard test failure when `step_fatal` is set to `true` in the test
configuration.

## How It Works

Each joint is stepped individually after restoring the captured default state
when available. The drive command is sent and position/velocity are sampled on
every requested simulation tick of the observed window. The peak position is
used to compute overshoot, and velocity signs determine the oscillation count.
Settling is the beginning of the final uninterrupted sampled tail inside the
target band; it does not prove continuous or indefinite stability. Before the
next joint, its iteration performs the same default-state restoration; there is
no separate final return-to-start command after the last measured joint.

The test uses the drive gains already authored on the asset. It does not modify
stiffness, damping, or maxForce values during execution.

It attaches no carrier fixture. Authored base constraints and gravity setup
remain relevant; a qualified standalone gripper can receive a temporary world
pin. A fixed robot base is not guaranteed for every asset.

## Failure Cases

| Observed symptom | Checks before assigning a cause |
|---|---|
| Overshoot above the configured threshold (warning by default) | Compare the actual step, live response, imported controls, limits and coupling; damping is not isolated by this observation |
| No accepted settling tail within the threshold (warning by default) | Check the completed observation window, runtime units, imported controls, loads and base setup before diagnosing stiffness or effort |
| Velocity sign-change count above the threshold (warning by default) | Inspect sampled positions/velocities, control mapping, constraints and runtime behavior; the count does not establish a cause |

## How to Fix

Compare step commands and position/velocity traces with imported controls/limits,
coupling, units, variant, base/gravity setup and solver support. Overshoot,
non-settling and sign changes do not isolate a gain problem from setup/importer/
asset effects. Preserve original criteria and evidence. Do not prescribe generic
gain multipliers, raise ratings or disable fatal policy merely to pass.
Evidence-backed repair or tuning belongs outside Evaluate.

## Expected Result

![drive_gain_validation expected result](../_images/drive-gain-validation.png)

[Result video](../../../../../../../../sr_specs/docs/_static/videos/drive-gain-validation.mp4)

Each joint steps by approximately 30 degrees, overshoots slightly, and then
settles to the target position within a few seconds. The motion looks like a
lightly damped step response: a rapid rise, a small overshoot peak, and a smooth
decay to the final position. Sustained oscillation or failure to reach the target
requires setup/importer/asset triage; an overall pass may still include those
warnings and does not identify gain tuning as the cause.

## Notes and Caveats

Optional `dgv_joint_NNN` histories retain per-joint command, position, velocity
and tracking error from the existing readbacks. Revolute coordinates use radians
and radians/s; unqualified prismatic and unresolved coordinates remain
`unknown_native`, with stage scale recorded as context. The clock is nominal
observation-step
time, not wall time or an exact rendered frame clock. Successful captures are
associated with preceding observations; the ticks do not support exact video
seeking. Missing diagnostic evidence leaves the original criteria unchanged.

By default, all three metrics are warnings, not hard failures. This design allows
the test to report gain-quality information on assets whose specification does not
mandate a specific step-response standard. Authors who require strict gain
compliance can set `step_fatal: true` in the test configuration to promote
warnings to failures.

The test reports response criteria without auto-tuning or prescribing optimal
gains. A failed response alone does not identify its cause.
