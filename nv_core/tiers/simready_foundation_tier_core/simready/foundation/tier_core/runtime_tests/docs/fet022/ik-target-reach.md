# ik_target_reach  (FET022 Driven Joints)

| Property     | Value                                                                         |
|--------------|-------------------------------------------------------------------------------|
| Test name    | ik_target_reach                                                               |
| Feature(s)   | `FET022_DrivenJoints.PhysX.0-1-0`, `FET022_DrivenJoints.PhysX.0-2-0`, `FET022_DrivenJoints.Isaac.0-1-0`, `FET022_DrivenJoints.Isaac.0-2-0` |
| Engine       | Kit / Isaac Sim (>=2024.2.0)                                                  |
| Test version | 1.2.9                                                                         |
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

Generates a Fibonacci-sphere distribution of end-effector targets, solves them
with the Lula IK solver, commands the articulation to each solution, and verifies
the configured sampled success fraction using final live EE position error.
Target generation requires a finite robot-base world position and nonempty,
finite asset bounds with positive horizontal extent. Missing measurements
stop execution without an asset verdict; no synthetic base or reach is used.

## Optional Motion Evidence

Each solved target records bounded per-joint playback histories comparing actual
issued commands with articulation position readbacks and their signed difference.
Only independently commanded solver-subset coordinates have target/error
channels. Passive, mimic-follower, loop and other uncommanded coordinates record
position only.
The target-local nominal step clock covers interpolation and reached-target hold;
solver computation, teleport/reset windows and rendering ticks are explicitly
excluded. Revolute readbacks use radians; unqualified prismatic tensor units
remain `unknown_native`. Metadata records stage scale and unit basis without
guessing a linear tensor conversion.
These joint-response plots diagnose drive behavior; they are not the
end-effector position-error verdict or proof of orientation accuracy.

Sampling is independent of video enablement. Successful captures associate with
the preceding retained observation rather than claiming exact video timing.
Optional playback readback or recording failures mark histories partial and
retain null measurements. Required joint/kinematics and live end-effector
position measurements must be usable; unavailable or invalid state is a
setup/runtime error. Runners without the hooks retain ordinary execution.

## Required Runtime State

Missing, non-finite or wrong-shaped runtime state needed by control or the
verdict stops the test as a setup/runtime error, not conformance PASS or an
evaluated asset-response FAIL. Optional extra motion readbacks remain nullable
and can mark diagnostic evidence partial. Response criteria and timing are
unchanged. Setup probes now synchronize position and drive targets and zero
velocity; failure to establish that configuration is a runtime error.
Native solver exceptions, malformed solver status, action construction or
hold-command failures, and unavailable end-effector error calculations remain
execution errors. They cannot count as correctly rejected out-of-reach targets.
An explicit, well-formed solver rejection retains its sampled diagnostic
meaning; it is not proof of global unreachability. Precomputation still restores
the reference configuration when such an error propagates.

## Spatial Safety Observation

The safety guard compares required finite live articulation geometry with a
frozen setup reach reference derived from owned body geometry, joint-anchor
offsets and bounded prismatic travel, when that topology can be qualified.
The configured volume-margin factor is applied as its cube root to this span;
ordinary bending from a slender initial pose is not judged against that pose's
small volume. Unsupported topology retains an explicitly unqualified initial
volume proxy. `ik_guard_reference` records the basis and qualification;
`ik_guard_abort` retains a detected guard interruption when diagnostics
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

A pass meets the configured sampled position-success fraction (default 0.50),
not every target. Failed samples remain visible. It does not certify the full
workspace, descriptor pairing or final live orientation: Lula orientation
tolerance is a solver input, not an observed playback orientation criterion.

## What It Checks

`num_reachable_targets` (default 5) receive a geometric in-reach sampling label,
not proof of actual workspace reachability. Accepted Lula solutions are played
back and target success uses final live EE position error with
`position_tolerance` (default 0.02 m). The configured minimum fraction is
`min_success_rate` (default 0.50). `orientation_tolerance` (default 0.25 rad)
is supplied to Lula; playback does not independently check live orientation.

Proven standalone grippers skip with `standalone_gripper` applicability
evidence. A missing compatible Lula descriptor leaves execution incomplete
with NO VERDICT. The
gripper validation receipts alone do not imply a standalone gripper. An arm
with an attached gripper remains applicable when it has independent arm DOFs.
Authored gripper classification or gripper signals plus at most one independent
native DOF establish the standalone case; unknown topology does not establish it.
Before scene setup can infer an unauthored gripper type and pin its base, it
requires positive gripper signals plus qualified one-leader authored topology.
Weak or passive arm joints still count in that conservative setup inspection.
Scene setup records `robot_type_authored` and `robot_type_source` in
`scene_info` and logs the classification source; an inferred type still needs
the native independent-DOF applicability check.

## How It Works

The test uses the Isaac Sim `motion_generation` extension to instantiate the Lula
IK solver. The Lula solver requires a robot descriptor (a YAML file paired with a
URDF) to be registered for the asset. Missing descriptors, required EE poses
or generated targets are setup/input errors with NO VERDICT.

Robot-name inference uses complete identifier tokens rather than substrings:
UR3/UR3e, UR5/UR5e and UR10/UR10e remain distinct, FR3 is recognized and Panda
aliases Franka. An explicit `lula_robot_name` still takes precedence. A token
match is a descriptor lookup hint, not proof that the descriptor fits the asset.
Indexed Lula actions are expanded into the full live joint configuration;
the expansion is calculation context, not permission to command every DOF.
The public descriptor subset and each validated action's joint indices bound
probe, target, velocity and playback writes. Passive, mimic-follower and loop
coordinates are excluded; their controller buffers are left untouched.
The native Lula solver reads its native articulation subset and creates an
action, but does not apply it directly in this phase. The local sparse facade
intercepts only the phase's later writes; it does not claim to intercept any
external/direct native controller calls. Repeated, noninteger, out-of-range or malformed
indices and nonfinite/wrong-shaped solutions are runtime errors, not failed
reachability measurements. The reference configuration is restored after
precomputation on success, error and cancellation; a cleanup failure retains
the original error rather than replacing it with an asset verdict.

Core requires PhysX and uses public indexed APIs. When required coordinates
cannot remain uncommanded, execution stops with a setup limitation rather than
an asset failure or a silent full-vector fallback. No-exclusion behavior remains
unchanged. Newton's separately owned provider has its own implementation and
backend qualification; this page does not establish its sparse-control support.
Native qualification and a matching robot rerun remain necessary for either
provider. The target generator, Lula solver and acceptance thresholds are not
changed by this control correction.

Fibonacci-sphere sampling distributes targets uniformly over the surface of a sphere with a radius scaled to the robot's reach estimate. Targets are pre-classified as reachable or out-of-reach geometrically: `num_reachable_targets` targets are placed at radius fractions within the estimated workspace (default 0.5, 0.7, and 0.9 of the robot's reach), and a small number of out-of-reach targets are placed beyond it. All targets are then passed to the solver, and the test tracks which targets were geometrically classified as reachable when computing the pass rate.

### Playback Timing

Lula playback retains its own duration policy, separate from the velocity-aware
FRS and coordination ramps. Available speed hints estimate the largest
command-distance/speed ratio, scaled by `motion_velocity_scale` (default 1.0)
and bounded by `motion_min_seconds` / `motion_max_seconds` (both default 1.5).
The configured `motion_seconds` fallback is 4.0 seconds when no usable estimate
can be constructed. A missing speed array can first use
`motion_velocity_fallback` (default 2.0 native coordinates/s); this is a configured
estimate, not an observed rating or calibrated prismatic speed. These are
provider timing choices, not proof that a slow joint has enough time to reach
its solution or that interpolation respects a
physical velocity or acceleration cap.

Absent or unusable optional authored speeds can use the existing fallback.
Errors querying supported selected authored velocity properties propagate from
input gathering; they cannot be replaced by a native ceiling or timing fallback.

Smoothstep playback issues a command on each requested physics tick.
`motion_update_hz` (default 60 Hz) controls command refresh only in the
reached-target hold loop. `settle_seconds_after_apply` supplies the post-playback hold
(default 0.25 nominal seconds) only after the reached-target condition is
observed. Captures/render work are separate from the
nominal observation clock; `capture_fps` (default 8) is the encoded clip rate,
not the simulation frequency. Preserve the actual motion/hold configuration
when interpreting a solver success followed by a live-position miss. This
procedure's registered whole-test ceiling is 1200 wall seconds; a synchronous
Lula call can still exceed the outer runner deadline or liveness allowance before
the host terminates the session; the local phase cannot interrupt that call.

## Failure Cases

| Symptom | Checks before attributing a cause |
|---|---|
| No in-reach targets found | Target-generation configuration, bounds/reach heuristic, base transform, selected descriptor and live pose source; no workspace defect is established |
| Pass rate below configured minimum (default 50 percent) | Separate solver/playback failures; compare descriptor/TCP, DOF mapping, imported controls/limits, units, coupling, runtime support and playback budget |
| Test skipped | Confirm marked standalone-gripper applicability; a skip supplies no target-tracking evidence |
| Setup/input error | Inspect compatible Lula configuration, required EE pose and generated targets; execution supplies NO VERDICT |

## How to Fix

Separate solver failures, unavailable prerequisites and playback position-error
failures. Inspect descriptor/URDF/TCP, selected variant, DOF mapping, imported
controls/limits, actual commands/readbacks, coupling, units, base/gravity setup
and runtime support before identifying an asset defect. Authored USD revolute
limits use degrees and linear limits use stage units; runtime angular coordinates
use radians and linear tensor units require qualification.

Preserve the original asset, plan and traces. Do not widen limits, raise ratings,
rewrite gains or relax criteria merely to force a pass. Evidence-backed repair
or tuning is external to Evaluate.

## Expected Result

![ik_target_reach expected result](../_images/ik-target-reach.png)

[Result video](../../../../../../../../sr_specs/docs/_static/videos/ik-target-reach.mp4)

The robot attempts sampled targets and plays back accepted solutions. Inspect
per-target status and live position error with video and joint traces. A pass
can contain failed targets and does not certify final live orientation.

## Notes and Caveats

This test applies to arm-like Cartesian kinematic chains, not standalone
grippers. It also requires a Lula robot descriptor. Without a descriptor,
execution supplies NO VERDICT. Descriptor resolution uses the installed Lula `policy_map` and selected
robot name, or explicit `lula_yaml_path`/`lula_urdf_path` configuration with
`lula_robot_name` as needed. Generic SimReady asset metadata alone does not
register a descriptor. Verify that the selected YAML/URDF represents this actual
mechanism, rather than retagging a different robot to force a policy match.

This test is distinct from the jacobian_ik test. The jacobian_ik test uses an
in-house damped-least-squares Jacobian solver that does not require a Lula
descriptor and samples targets differently. Refer to the
[jacobian_ik](jacobian-ik.md) doc for details.
