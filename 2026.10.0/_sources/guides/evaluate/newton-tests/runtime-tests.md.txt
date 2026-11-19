# Newton Runtime Tests and Motion Evidence

This guide describes the independently owned Newton Evaluate implementation
shipped in `simready-foundation-tier-newton`. Its canonical provider is
`simready.foundation.tier_newton.runtime_tests`, which is also its Python import
package. The former flat name remains a provider alias, not an import shim.
Preserve the provider, `_newton`
test name, test version, feature ID and engine when comparing results.

Install the optional execution dependencies with Python 3.12:

```bash
python -m pip install "simready-foundation-tier-newton[evaluate]"
```

This does not select a Newton engine or install a configured Isaac Sim runtime.
The current Newton `evaluate` extra requires `simready.evaluate[kit]>=2026.9.0rc2,<2026.11` and
`simready.evaluate.engine-kit>=2026.9.0rc3,<2026.11` for strict
complete live geometry and required-cleanup worker retirement. The Newton-owned
setup independently verifies composed room-floor collision and visibility before
physics, so older supported Kit implementations receive the same fixture checks.
These declared bounds admit compatible prerelease and stable updates within
this API generation. Install
the tier extra to apply both compatible requirements; an older Kit wheel cannot
provide this suite's required measurement and cleanup contracts.
Configure the Evaluate Kit engine to use Newton and inspect the saved plan.
The entry points reject an active-backend mismatch before running the procedure.
A scene-initialization failure is an incomplete execution, not proof that an
asset failed its behavioral criterion. Compare the actual installed importer,
schema and solver capabilities before classifying a result as an asset defect.

## Shared Engine Lifecycle and Failure Diagnostics

The drop and multibody procedures initialize Newton, inspect readiness, stop,
then start their evaluated motion. Current Evaluate `PhysicsHandle.stop()`
checks the stop and commits its public timeline state without adding a physics
tick. Newton's queued backend STOP callback can lag that public state. An
already-sufficient contact-capacity check performs no solver write and allows
that lag; an actual capacity change still requires qualified backend stopped
state. A paused, playing or otherwise unqualified public timeline cannot restart.
Stop/commit alone does not establish that every backend callback has drained.

The deferred MuJoCo-Warp contact-capacity request is applied before native play
when the fresh physics scene has a qualified selected solver. The existing
default remains `newton_nconmax=1000`, preserving larger configured values.
Configuration acknowledgment is not compiled-capacity or contact evidence.
Observed contact overflow invalidates the attempt; inspect its bounded
fresh-session recovery and retained logs instead of accepting a behavioral
PASS/FAIL from a simulation that dropped contacts.

Original execution exceptions retain bounded `caused by` or `while handling`
type/message chains where available. Abbreviated/unavailable-message and
cycle/depth markers mean the explanation is partial; they do not identify an
asset defect. Older outer-only errors cannot be reconstructed from absent
logs. Preserve their evidence before a separately authorized rerun.
Required observation/restoration errors preserve their original cause,
including cancellation. Secondary diagnostic note lookup, formatting or
delivery is best-effort and cannot replace that cause; SDK exceptions without
`add_note` remain supported. This does not relax any measurement gate.
Required drop/slope cleanup attempts remaining safe restoration, preserves
the first execution or cleanup cause and retires uncertain native context,
including cancellation. A cleanup-only stop request propagates; a later retry
does not qualify reuse of that native process.

For the public runtime API, use SimReady Evaluate's published **Kit Plugin →
API → PhysicsHandle** and **Kit Plugin Concepts** pages for the matching
installed version. Locate its bundled **diagnose-failures** skill with
`simready-evaluate --skills-path` for error ownership and recovery procedures.
These shared engine notes do not change the Newton-owned acceptance criteria
below or authorize asset tuning, extra probe motion or native-array edits.

## Wall-clock execution allowances

Motion-test wall-clock safety allowances are doubled, including the internal
FRS, coordination and Jacobian-IK wall guards. This does not change physics
FPS, velocity-aware ramp calculations, simulation-step budgets, settling
windows, targets, tolerances or pass criteria. Explicit configuration values
remain literal wall seconds; they are not multiplied again. The independent
Kit output-inactivity watchdog is unchanged. A wall deadline is total elapsed
execution time, not time since the last progress message.

Generate a fresh plan after rebuilding/installing the tier: saved plans keep
their recorded procedure versions, deadlines and configuration overrides.

| Test | Whole-test wall limit (seconds) |
|---|---:|
| `ground_drop_newton` | 600 |
| `ground_stability_newton` | 600 |
| `slope_drop_newton` | 600 |
| `joint_movement_newton` | 600 |
| `drive_gain_validation_newton` | 600 |
| `effort_limit_newton` | 1200 |
| `full_range_sweep_newton` | 14400 |
| `ik_target_reach_newton` | 1200 |
| `jacobian_ik_newton` | 2400 |
| `mimic_joint_newton` | 600 |
| `multi_joint_coordination_newton` | 3600 |
| `state_accuracy_newton` | 600 |
| `velocity_limit_newton` | 600 |

State accuracy completes every configured smoothstep ramp before its endpoint
hold. Only the hold may stop early after consecutive settled samples; entering
a coarse response band cannot leave an intermediate command active. Newton's
locally owned ramp/hold budgets, legal waypoint selection and configured
response tolerances are unchanged.

FRS defaults to 3360 internal wall seconds beneath its 14400-second outer
ceiling; coordination defaults to 3360 beneath 3600; Jacobian IK search
defaults to a maximum of 1800 beneath 2400. FRS and coordination still reserve
at least 60 seconds beneath the outer ceiling for remaining work. The FET004
batched-drive wall watchdog is 240 seconds. Startup and asset-loading watchdogs
are not motion execution allowances and are unchanged.

## Spatial Safety Observations

Native fixed-tendon affine position controls require finite authored
coefficients, mimic offsets/scales, gains and biases with matching vector
lengths. Control ranges must be ordered; absent or outward unbounded
`-inf`/`+inf` endpoints remain allowed. NaN, reversed/inward-infinite ranges,
malformed requested targets and nonfinite derived control values are setup/
command errors, not failed asset-response measurements. The entire requested
tendon group, actual compiled mappings and native/solver float-buffer
representability are preflighted before staging native or legacy position targets.
Native control/solver buffer updates use detached validated copies so a later
invalid conversion or mapping cannot partially mutate an earlier control.
This validates the test's command boundary; it does not repair the authored
actuator or establish native response/contact correctness.
Finite zero-gain/disabled or non-position actuators retain their existing
discovery exclusion; an explicitly requested affine conversion still requires
a nonzero position gain. No disabled actuator is enabled or retuned here.

Newton FRS, STA, VEL, EFF, DGV, MIM, MJC, IK and JIK freeze a locally owned
setup reach reference from connected body geometry, joint-anchor offsets and
bounded prismatic travel, where topology is qualified. Required live geometry
is compared against that span with the configured volume-margin factor's
cube root. Ordinary bending from a slender pose is not judged solely against
the narrow starting box volume. Unsupported topology retains an explicitly
unqualified initial-volume proxy; the original raw box metrics remain available.
Phase-owned `frs`, `sta`, `vel`, `eff`, `dgv`, `mimic`, `mjc`, `ik`
and `jik` `_guard_reference` / `_guard_abort` records identify qualification,
basis and any detected safety interruption, when diagnostic persistence succeeds.

A guard trip leaves incomplete execution, not measured joint non-convergence,
range/speed failure or an asset diagnosis. Missing required live geometry
also propagates; optional recording cannot disable the safety check or replace
its original cause. Inspect completed observations/timing where available,
not only planned work. These setup geometry proxies do not establish native
contacts. Locally owned commands, tick counts, defaults and response criteria
remain unchanged; host regressions are not native Newton asset qualification.

## Ownership and Coverage

Newton owns the FET003 drop procedures, FET004 multibody probe, and nine FET022
robot procedures, including defaults, scene setup, actuator/tensor access and
verdict policy. Placement and diagnostic-message helpers are owned locally
by Newton; no Core runtime-test module is imported. The neutral overlay API
remains available for future declared reuse. Core's similarly named PhysX
pages are not Newton policy.
Published feature bindings remain unchanged by this ownership split.

`ground_stability_newton` is now an independently enabled settling procedure.
Ground-drop PASS alone does not supply its required feature coverage. Published
provider/test bindings are unchanged; create a fresh plan to adopt this inventory.

Newton close/lift gripper contracts are not introduced. Core's published Isaac
sphere/cube gripper contracts remain unchanged and route to PhysX. Running
Newton driven-joint tests on a gripper-shaped articulation does not certify
Newton grasp/lift behavior. A Newton gripper contract and independently owned
implementation need separate versioning and adoption.

Selected physical joint paths are resolved before native-name mapping for
passive ownership, velocity hints, raw mimic discovery and diagnostic metadata.
Disconnected foreign articulations, including reversed-endpoint body/container
roots with repeated joint names, cannot supply selected gains or limits.
Ambiguous ownership is an execution/setup limitation (or unknown optional
metadata), never a traversal-order choice. This boundary imposes no gripper
topology prerequisite on ordinary passive/velocity queries. Zero-gain drive
schemas alone do not grant independent command ownership.

### Registered Test Versions

Use these exact registered names with the canonical Newton provider. The test
version identifies the procedure and observable evidence, not a new published
feature-contract version.

| Registered test name | Test version | Registration source |
|---|---|---|
| `ground_drop_newton` | `4.0.2` | `fet003_physics/ground_drop.py` |
| `slope_drop_newton` | `3.3.6` | `fet003_physics/slope_drop.py` |
| `ground_stability_newton` | `3.0.2` | `fet003_physics/ground_stability.py` |
| `joint_movement_newton` | `2.2.5` | `fet004_multibody/joint_movement.py` |
| `full_range_sweep_newton` | `1.5.7` | `fet022_driven_joints/full_range_sweep.py` |
| `state_accuracy_newton` | `1.2.10` | `fet022_driven_joints/state_accuracy.py` |
| `velocity_limit_newton` | `1.1.12` | `fet022_driven_joints/velocity_limit.py` |
| `effort_limit_newton` | `1.1.10` | `fet022_driven_joints/effort_limit.py` |
| `drive_gain_validation_newton` | `1.1.10` | `fet022_driven_joints/drive_gain_validation.py` |
| `mimic_joint_newton` | `1.1.12` | `fet022_driven_joints/mimic_joint.py` |
| `multi_joint_coordination_newton` | `1.2.6` | `fet022_driven_joints/multi_joint_coordination.py` |
| `ik_target_reach_newton` | `1.2.10` | `fet022_driven_joints/ik_target_reach.py` |
| `jacobian_ik_newton` | `1.4.12` | `fet022_driven_joints/jacobian_ik.py` |

Registration paths are relative to `simready.foundation.tier_newton.runtime_tests`. Exact
defaults are declared by each local decorator and, for FET022, its corresponding
`articulation_phases` module's `get_defaults()`. Inspect the saved execution
plan for the configuration actually used; documentation is not an override.

FET022 initial settling now requests complete `ctx.step_one()` ticks, rounding
up the nominal `settle_seconds * physics_fps` interval. Zero settling is
allowed; FPS must be finite and positive and settling seconds finite and
nonnegative. Invalid timing configuration or a failed tick remains an execution
error. This does not measure elapsed solver or wall-clock time. The
processing-only `ctx.physics_steps()` helper cannot establish that interval on
an already paused Newton timeline and is no longer used for these initial
settles. Full-range sweep uses its own complete-tick budget.

STA, VEL, DGV, MIM and MJC now exclude declared passive, mimic-follower and
loop coordinates from target/state/velocity writes, not just from verdict
selection. Other independent DOFs retain their existing starting hold targets.
Genuine indexed dispatch is required when such exclusions exist: the current
Newton adapter stops with an explicit capability/execution error before
excitation because its sparse control path is not natively qualified. With
no exclusions, its legacy full-vector behavior remains unchanged. Applicability
skips precede that control guard. A MIM reference that is itself dependent,
passive or loop-constrained is an explicit execution limitation, not silently
omitted coverage or an independently commanded mimic-chain coordinate.

Scene ownership uses raw authored mimic APIs independently of the response
detector's optional schema SDK, axis and reference resolution. Explicitly
disabled joints and this provider's existing disabled Newton-mimic/equality
precedence do not become active mimic ownership. Unexpected required ownership
query errors and unmapped or ambiguous active authored followers
stop scene setup; they never clear exclusions and invent uncoupled coverage.
Successful truly no-mimic detection remains empty. Authored ownership does not
qualify native mimic equations or support. When authored followers exist but no
response pair can be qualified, MIM stops with an execution/coverage limitation;
it does not claim missing APIs or evaluate an asset-response FAIL.

MIM likewise rejects literal infinite or rounded SDK float32-maximum unlimited
reference windows before issuing commands for that pair. It invents no finite
continuous-joint excursion; this is an execution/coverage limitation, not an
evaluated mimic-following asset FAIL. Already completed finite-pair metrics
remain visible; valid finite goals/criteria are unchanged. Locked, inverted or
tiny intervals no wider than the unchanged 1e-6-native-unit epsilon likewise
stop as procedure limitations, not fabricated tested-pair responses.

Required loop
discovery scans the verified loaded asset subtree, including instance proxies,
never a partial body branch or an unrelated room/asset. Native qualification of
indexed Newton control and real-robot response remains pending.

The IK Target Reach and Jacobian IK applicability guards treat gripper receipts
as signals, not proof that the whole articulation is a standalone gripper. An arm
with an attached gripper remains applicable when independent arm DOFs exist.
Authored gripper classification or gripper signals with at most one independent
motion DOF (excluding passive, mimic-follower and loop joints) establish the
standalone case. Unknown or ambiguous topology does not justify that skip.
Before scene setup infers an unauthored gripper type and pins its base, positive
gripper signals must also have qualified one-leader authored joint topology.
Weak/passive arm joints still count during this conservative setup inspection.
Scene setup exposes `robot_type_authored` and `robot_type_source` in
`scene_info` and logs that source. Inferred gripper types still require the
native independent-DOF check rather than automatically suppressing IK.

Full-range-sweep and effort-limit history context `runtime_lower` / `runtime_upper` identifies
the actual `RobotHandle.get_joint_position_limits()` readback in native joint
coordinates, not raw authored USD limits. Its `runtime_limit_source` records
that distinction. Older unreleased histories labelled the same runtime values
`authored_lower` / `authored_upper`; those keys do not justify treating the
values as USD degrees or applying another unit conversion.

Full-range-sweep destinations always stay inside the imported legal limit
interval. Its precise default `max_sweep_range` is `math.tau` (a full turn in
radians for revolute joints); the cap uses native joint coordinates, not USD
degree-valued limits. Genuinely wider ranges use a zero-centered cap shifted
entirely inside the legal interval. A one-part-per-million relative tolerance
at the cap boundary preserves full-turn float32 imports and saved plans using
the legacy `2*3.14159` cap. A `[-90, +270]` degree-equivalent imported range with
10 percent margins therefore commands `[-54, +234]` degree-equivalent extrema,
not `[-144, +144]`. Finite non-positive caps disable capping. Parameter
construction for a selected joint rejects invalid/reversed or non-finite limits,
non-finite caps, and margins outside `[0, 0.5)` as setup/configuration errors
before sweep commands, not evaluated asset-response failures. Initial selection
still excludes missing or non-finite limits and ranges no wider than `1e-3`
native joint units; no eligible joints retains the established skip policy.
Newton owns this implementation and its existing
bounded final-convergence policy independently of Core.

FRS excludes mimic followers from independently selected sweeps, but the
one-joint command API does not establish independently indexed native dispatch.
Isaac's legacy Newton action boundary reconstructs a finite full target vector,
preserving existing targets and seeding uninitialized entries from measured
positions. Coupled followers can therefore appear in that submitted vector.
Inspect the actual backend dispatch and coupling response before diagnosing
an attached-gripper failure; this procedure does not claim follower-free
native control, and synthetic pacing tests do not qualify that native path.

FRS checks verdict configuration before settling or commands. Rest and
zero-return tolerances must be finite nonnegative real numbers, and the
bounding-box explosion ratio finite and positive; NaN, infinity and
boolean/string coercions are configuration errors, not asset verdicts.
Exact zero tolerances remain valid.
Policy flags `rest_check_enabled` and `rest_check_fatal` must be actual
booleans; null, zero and empty strings cannot silently suppress endpoint
checks. Explicit `false` preserves the intentionally diagnostic policy,
not the default conformance guarantee. The final convergence allowance
`newton_zero_max_settling_seconds` must be finite and nonnegative, and
`newton_zero_consecutive_frames` a finite positive whole-number value
(integer-valued `6.0` is valid). Invalid counts are not silently clamped or
truncated. Sweep margin/cap checks also precede motion; finite non-positive
caps still disable capping.

### Newton Full-Range-Sweep Timing

Version 1.5.1 retains the destinations, evaluated hold tolerances, and bounded
final convergence, while pacing each ramp from its native travel and an optional
usable speed hint. Its minimum remains 1 / max(0.1, `sweep_speed_scale`)
(1.25 simulation seconds by default). A known-speed ramp additionally budgets
profile peak derivative times max(planned distance, distance from current
required position) divided by speed times min(1, `sweep_speed_scale`), plus
`sweep_settling_allowance_seconds` (default 0.25). Peak factors are 1 for
linear/unknown, 1.5 for smoothstep, 1.875 for smootherstep, and 2 for trapezoidal.
Derived ticks round up. The allowance is configured response time, not measured
acceleration; the existing evaluated 0.15-second hold remains distinct.

Each ramp begins at the required live observed position rather than the previous
requested endpoint, preventing a stale-target jump after an endpoint miss.
Timing rows retain `requested_start` and `observed_start` separately. Imported
legal destinations and hold criteria remain unchanged. Commands stay within the
runtime stops; an out-of-range start requiring an unpaceable first legal command
under a qualified speed hint is a setup/timing error before commands, not an
asset FAIL. With no hint, the fallback is not a speed guarantee.

The smaller usable native/qualified authored input supplies the timing hint.
A native distance/native speed ratio uses seconds even for unknown linear
scales. USD fallback requires a unique joint and the actually loaded/installed
qualified Newton 1.2.1 importer: explicit `physxJoint:maxJointVelocity`
angular degrees/second converts once to radians/second, while its prismatic
input retains stage distance/second. Other/unknown Newton versions do not
qualify this authored fallback. DC-motor `newton:velocityLimit` saturation
and PhysX performance-envelope parameters are not substituted as Newton joint
timing ceilings. This does not claim imported speed caps are solver-enforced.
Absent, zero, negative, nonfinite, malformed optional inputs and the narrowly
rounded float32-max unlimited sentinel retain the bounded fallback; a present
getter's exception and required position-readback errors propagate.

The defaults cap a ramp at 60 simulation seconds and completed nominal sweep
time at 600 seconds, including initial settle, ramps, holds, and final
convergence. Initial settle advances real `step_one` ticks with heartbeats.
The monotonic wall guard is 3360 seconds including setup/steps/captures;
registered `max_duration` is 14400 wall seconds. The default guard stays 3360;
a longer CPU run explicitly configures `max_sweep_wall_seconds` at most 14340,
leaving at least 60 seconds beneath the bounded outer deadline. Regenerate the
execution plan to adopt the new procedure version/registration; older saved
plans can retain their older outer timeout. An insufficient complete-window budget or
exhaustion raises an execution/configuration error, without shortening a ramp
or creating an evaluated asset FAIL.

At 240 physics ticks/second and 30 rendered frames/second, one simulation second
can require about eight wall seconds before capture overhead. Encoded video FPS
does not set timing; capture/render/retry ticks stay excluded from nominal
simulation and history clocks. Bounded `frs_segment_timing` records preserve
hint provenance and durations, with omission counts beyond 192 records.
All timing helpers and policy remain locally owned; focused synthetic tests do
not establish native Newton or asset runtime qualification.

Version 1.5.2 additionally records bounded `frs_execution_timing` snapshots,
including acknowledged `completed_nominal_ticks`, active joint/segment,
elapsed/setup wall time and budget stop reasons. The existing
`frs_completed_nominal_simulation_seconds` is retained on ordinary errors
and cancellation. `wall_budget`, `simulation_budget`, and `segment_budget`
mean incomplete execution, not an evaluated asset FAIL; native process death
may prevent a final snapshot.

Fixed `costs` buckets time existing stepping, captures, bounds, camera,
optional motion, commands and encoding calls with monotonic wall time.
They include waits/rendering and failed call attempts, not native solver CPU
time. Overall `observed_service_seconds_per_nominal_tick` also includes
unbucketed required readbacks, progress logging and other phase work.
`planned_nominal_ticks_estimate` reuses required post-settle position/limit
snapshots and resolved hints without new native queries; it includes the
configured upper final-convergence allowance. Early convergence and missed
earlier endpoints can change actual ticks. More than 1024 selected joints or
an unavailable calculation omits that estimate with omission context.
`estimated_remaining_wall_seconds` and `estimated_budget_insufficient`
are advisory, neither verdict inputs nor an automatic budget extension.
Recording failures warn/omit optional evidence while preserving the original
operation error/cancellation. No targets, physics/capture cadence, native
query counts or evaluated response criteria change.

## Recorded Observations

Watch the video first; use charts and downloadable JSON/CSV to investigate
the measured criterion. Diagnostic hooks observe existing commands/readbacks;
they do not add physics steps, change controls or decide pass/fail.

### Test-Owned Drop Fixtures and Criteria

Ground drop, ground stability and slope drop use the selected asset variant and required live AABB
geometry; authored initial bounds are placement context, not later stability
evidence. Their default `floor_margin=0.1` is a stage-length proximity/overlap
allowance, not a measured collider contact offset or floating-point error bound.
Ground drop `4.0.0`, ground stability `3.0.0` and slope `3.3.3` qualify finite real/non-boolean configuration
before scene mutation. Physics/capture rates are positive integer-valued
numbers, settle frames are nonnegative integer-valued numbers and load timeout
is positive. Lengths, tolerances, durations and friction are nonnegative; floor
level and slope angle are signed finite. Slope's actual derived observation
gates are also validated before stepping. Supported zero settings retain their
existing comparator policy; invalid configuration is incomplete execution,
not a completed asset-response verdict. Defaults and valid response criteria
are unchanged except for the explicit drop/stability separation described here.
Ground drop requires crossing `floor_level + floor_margin` from above and staying
above `floor_level - floor_margin` after that crossing. Settling remains diagnostic
for early stopping, but does not decide this drop verdict. Excessive overlap fails
at its first qualifying observation. Ground stability independently requires a
complete sampled center/corner rest window after proximity and before the deadline.
Its hold is positive and needs at least two samples. Every hold-window sample
must remain inside the existing floor-
proximity/allowed-overlap band. A flat midair window after an earlier proximity
crossing cannot qualify rest; return to the band requires a fresh full eligible hold.
Low-variation graph curves do not independently establish this floor prerequisite.
Defaults retain a 0.02-stage-
length tolerance, 2-second nominal hold, 8-second post-proximity deadline and
10-second hard nominal budget. Required complete-window/overlap opportunity must
fit that budget; early budget exhaustion is incomplete execution, not measured
non-settling. Rest/deadline acceptance freezes before the 0.5-second recording
tail; later settling cannot turn a missed deadline into PASS. Overlap checks
remain active through that tail and may still invalidate the result. Older combined drop
versions required rest in their drop verdict; preserve that version distinction.
`penetration_check_seconds=1` delays rest evaluation; it does not require a
sustained one-second penetration before failing.
Both flat-floor procedures now author and verify a typed physics-purpose
material binding with unchanged static/dynamic friction 0.5/0.4 and restitution
0. An older untyped or ineffective binding is not assumed solver-equivalent.
This fixture correction does not edit asset materials or qualify native contacts.

Slope drop's generated ramp is configured by Evaluate's `RoomHandle.add_slope`.
It authors a typed `UsdShade.Material` with `UsdPhysics.MaterialAPI` and binds
it to the collision geometry for the `physics` purpose after the display
material. Static friction uses `slope_friction` (default 0.5), dynamic friction
is 0.8 times that value, and restitution is zero. These are fixture properties,
not repairs to the asset. Authoring/binding alone does not establish the native
solver's effective contacts; inspect the composed fixture and installed adapter
before blaming asset friction or collider authoring.

Slope proximity, ramp overlap and separation use the AABB's signed-distance
interval from the analytic plane. After proximity, signed downhill center
displacement must reach `horizontal_movement_threshold` (default 0.01 stage
units). The default post-displacement window is 3 nominal simulation seconds,
not 0.5. The complete AABB lying too far below the ramp while fully over it,
excessive floor overlap after downhill detection, or confirmed separation can
fail. Separation needs consecutive samples for `separation_confirmation_seconds`
(default 0.1); only an exit beyond the downhill edge with sufficient positive
downhill displacement exempts it. Uphill exits remain checked. A valid finite-
ramp exit or a sampled PASS does not prove continuous collision contact.
PASS requires the complete configured post-displacement window before the hard
nominal budget ends. Late displacement without enough remaining observations
is incomplete execution (ERROR), not PASS or an asset-response FAIL; observed
motion/overlap/separation failures retain priority. Explicit zero post-window
settings complete on the detection observation. Required/observed post-window
steps and completion are recorded, without adding simulation steps or changing
the configured cap. Slope version `3.3.5` also uses Newton's locally owned
qualified flat-floor material helper: typed material, static/dynamic friction
0.5/0.4, restitution 0, acknowledged writes and effective physics binding.
Unverified fixture state is a setup error, not an asset friction defect. This
does not import Core procedures or certify native contact behavior.
Slope version `3.3.6` requests a near-terminal illustrative render after
the measured slope, separation or floor guard fires. Renderer ticks can advance
the physics scene, so the image has no exact measurement timestamp. Optional
terminal media failure leaves the measured physics result intact and records
a warning. Unsafe evidence paths remain execution errors. Proxy verdicts and
configured thresholds are unchanged.

| Procedure | Evidence and interpretation |
|---|---|
| Ground drop | Runtime world-aligned bounding-box center and lowest Z, proximity/overlap thresholds, and fall/proximity/diagnostic-rest phases. Proximity is an AABB threshold crossing, not a measured collision. Drop PASS does not guarantee settling. |
| Ground stability | The same locally owned flat-floor fixture, with an independent complete sampled rest window and deadline. Maximum center distances and AABB-corner coordinate variations are relative to the latest sample in the hold window; both must meet the tolerance. Null window channels mean the hold is incomplete, not zero motion. These are not velocity thresholds or continuous stability proof. Required stability FAIL or missing coverage still affects the feature. |
| Slope drop | AABB ramp-plane distance interval, center Y and displacement from the initial center, with contact/exit phases. These are geometry proxies, not contact forces. Leaving the downhill edge of a finite ramp can be valid; an uphill launch is not automatically exempt from separation checks. |
| Joint movement | Rotation change in the connected parent's frame; relative translation mapped through the frozen reference-parent linear transform into reference-world stage units. Explicit world connections use the world frame. Required live Fabric body poses and complete reference geometry must be available. These are body-motion proxies, not joint-coordinate or contact measurements. Test-owned tensor drives or balanced forces retain their existing excitation; aggregate PASS needs one evaluated joint above its unchanged threshold. |
| Full-range sweep | Per-joint position, actual intermediate command, segment destination and command-minus-position error across inset upper/lower and zero/rest ramps/holds. Configurable margins and range caps mean these are not exact authored endpoint commands. |
| State accuracy | Position/velocity, actual smoothstep command, final goal and their distinct errors across ramp/settling windows. Each complete paced ramp commands its exact endpoint before the hold; an interrupted ramp retains its last actually issued intermediate command. The position criterion uses final required readback at each waypoint; velocity/consistency observations are diagnostic, not independent state calibration. |
| Velocity limit | Signed velocity, position command, resolved comparison ceiling and tolerance ceiling. The verdict evaluates absolute velocity; it excludes the first five observations when more than ten are collected and can stop after consecutive near-zero observations. See the limitation below. |
| Effort limit | Position and issued world-frame external body-force components in N. Force commands are not measured contact forces or joint actuator torque. The criterion checks finite range overrun, not exact pose holding or maximum-effort enforcement. Spatial-guard interruptions and missing/non-finite required position readbacks leave execution incomplete, not an evaluated asset-response failure. |
| Drive-gain validation | Existing joint position/velocity, issued step target and position error during the response window. Observing a response does not authorize automatic gain tuning. |
| Mimic joint | Reference/follower positions, the reference command, expected follower displacement and mimic error. Native Newton uses `follower = coef0 + coef1 * reference`; the supported PhysX compatibility import uses `follower = -offset - gearing * reference`. Constant offsets cancel in displacement from the measured rest pose. These diagnostics do not change the magnitude-ratio verdict. |
| Multi-joint coordination | Per-joint commanded/observed positions and errors during coordinated playback and holds. Goals and intermediate commands stay within each selected joint's qualified range, including endpoint floating-point roundoff; unselected independent coordinates retain measured starting hold targets, not guaranteed fixed observed positions. Dependent coordinates remain uncommanded and may move. Floating command construction avoids integer-goal truncation and float32 assignment past a float64 stop without extra readbacks. Velocity-aware shared ramps change the planned tick windows while retaining the post-ramp hold, target factors, margins and remembered individual band-entry criterion; they do not establish simultaneous final convergence. See the timing policy below. Skipped prerequisites do not fabricate motion histories. |
| IK target reach / Jacobian IK | Per-joint issued commands, observed positions and errors during dynamic target playback/holds. A kinematic solution or reset is not itself proof of dynamic target tracking. |

### Qualified Joint-Movement Observations

Optional motion arrows use default-time composed-USD bounding-box centers,
not live Fabric poses. A fresh cache does not guarantee USD follows the
simulated body; missing/stale centers can omit or misrepresent arrows.
Verdicts and recorded motion histories independently use the required Newton
Fabric body-transform tracker, not this visualization proxy. Static fallback
arrows depict attempted excitation rather than demonstrated movement.

The legacy `jm_joint_<name>_pct_of_travel` diagnostic divides rounded
relative-body motion by the chosen authored endpoint magnitude and caps at
100%; it is not native joint-coordinate travel or completion from a nonzero
starting coordinate. Its companion `jm_joint_<name>_pct_of_travel_basis` is
`capped_relative_body_motion_over_authored_endpoint_magnitude`. Legacy numeric
values and the aggregate movement criterion remain unchanged. Rotation and
translation movement thresholds must be finite nonnegative real numbers,
excluding booleans; malformed configuration stops before scene mutation.
The existing greater-than-or-equal comparison allows an explicit zero
threshold to accept zero motion; this is not proof of movement. Defaults
remain positive.

Newton's scalar joint probes require complete finite native joint positions
and usable native limit intervals before dispatch. A directional stop is an
absolute upper/lower coordinate, not travel added to a nonzero initial pose;
every interpolated target is clipped to the native interval. Required limits
or position-readback failures leave execution incomplete, not a zero-start
substitute or an asset no-motion verdict. Correctly mapped native limits are
not inferred from stage meters-per-unit. The locally owned direction policy,
existing ramp/ticks and aggregate motion threshold remain unchanged.

Tensor-drive setup also requires a complete finite real one-dimensional joint
position snapshot matching the native DOF count. Supported tensor buffers are
detached and moved to the host without discarding their dtype before inspection.
Missing/short/wrong-shaped, boolean, string, object, complex or non-finite state
and getter/conversion errors stop as execution errors before ramp commands.
No coordinate is filled with zero or replaced by an intended target. Existing
no-DOF/no-applicable-joint prerequisite skips retain their policy.

The local Newton tracker requires current Fabric body poses for the connected
child and every named parent. The optional native helper returning no matrix
is an execution error, never permission to read an authored rest pose as
motion. An explicit world connection has no parent readback. Missing, non-finite
or singular required transforms cannot become zero rotation/translation or a
world-frame substitute. Rotation extraction separates scale and qualifies a
proper orthonormal basis; unqualified decomposition is an error, not no motion.

Translation excludes common parent rigid motion and maps the relative delta
through the frozen reference-parent linear transform, including its scale,
into reference-world stage units. The unchanged 2-percent normalization needs
a finite positive diagonal from complete live default/render/proxy geometry.
Missing required live bounds leave execution incomplete; tiny positive bounds
remain valid without an arbitrary minimum-size cutoff. Stopped spherical-anchor
placement and pre-physics temporary limit sizing use explicitly authored setup
queries, not evaluated motion observations or recovery from missing Fabric.
Tensor drives, balanced spherical forces, legal targets and any-joint-moved
acceptance retain their Newton-owned procedure.

Temporary scalar-drive setup snapshots exact local attribute/API opinions
before mutation, including absence and inherited values, and qualifies required
float32 writes/readbacks. Stiffness, damping and the force ceiling must be
nonnegative. Invalid or unrepresentable nonzero commands are setup errors;
valid zero gains and explicit positive-infinity unlimited force retain their meaning.
Partial activation rolls back captured opinions without flattening inheritance.
Restoration requires a successful physics stop before DriveAPI/property edits;
an unqualified stop leaves that graph untouched and retires the native process.
Changed owned opinions are checked before undo, concurrent conflicts are
preserved and reported, and safe retries recognize already-original fields.
Newly created empty over specs are pruned only while they remain overs;
concurrently authored definitions/classes and other non-owned fields survive.
A later successful retry does not clear required-failure/retirement provenance.
These checks qualify authored fixture state, not the solver's effective drive.

Unique authored joint names retain their public identity. Colliding leaf names
or metric-sanitized names receive stable path-based evidence aliases; original
names and full joint/body paths remain in results. Native DOF lookup still uses
authored names, not evidence aliases. Duplicate SDK names or distinct USD
joints resolving to one native coordinate stop with the existing unsupported
mapping outcome before commands; they do not establish an asset defect.

Compatible `translation_m`/`bbox_diag_m` fields remain rounded stage lengths,
not automatically metres. Native `jm_joint_<name>_translation_stage_units`
and `jm_joint_<name>_bbox_diagonal_stage_units` metrics, plus the per-joint event,
retain exact raw values and `stage_length` units. The paired numerator and
reference diagonal come from the trial with the greatest exact normalized
translation, labelled `translation_evidence_basis`; they are not independent
maxima from different windows. Translation basis is `frozen_reference_world`,
and `bbox_purposes` records default/render/proxy. Missing observed tracker
evidence stays null. Host math/readback regressions do not qualify unavailable
Inspire, Syncro5, Cobotta or other native robot assets.

Read the aggregate together with its evaluated subset. State accuracy and
velocity limit fail on any evaluated joint violation; mimic fails on any
evaluated pair's magnitude-ratio violation. Prerequisite/excluded joints or
pairs have no measured coverage. FET004 instead retains its any-one-joint
movement rule. DGV's default warning policy, IK's sampled fractions and MJC's
remembered individual band entries do not imply every response passed or all
joints converged simultaneously. EFF's default two-second observation budget
is shared across its twelve directions for each tested joint, not two seconds
per direction; early criterion failure can leave later directions unrun.

Resolved revolute tensor values use radians and radians/s. Prismatic values
use stage length and stage length/s only when the installed or already loaded
Newton SDK is the qualified version 1.2.1. Other or unavailable versions remain
`unknown_native`, even with resolved joint identity; unresolved identities also
remain unknown. Metadata records the unit basis and package-version source.
Raw USD body/bounding-box distances use stage length regardless of tensor
qualification. Recorded stage meters-per-unit, where available, provides
context; stage length is not automatically metres. The current Evaluate Kit
adapter normalizes its execution stage to meters-per-unit 1.0, independently
of the source asset's authored scale. Proxy
thresholds and source labels must not be reinterpreted as measured contacts.

The prismatic unit basis is qualified against the Newton 1.2.1 importer and
Isaac Newton tensor path: raw USD prismatic limits/drive values pass to
`add_joint_prismatic` without metres-per-unit rescaling, and readbacks expose
`joint_q`/`joint_qd` directly. Do not extend that conclusion to another backend
or importer without checking its conversion path. Runs on angular robots alone
cannot qualify generic prismatic scaling.

Mimic coefficients and joint coordinate types must be checked before interpreting
scaling across unlike joint units. The absolute-equation residual retains the
raw numeric authored offset after backend sign normalization and is labelled as
an unqualified-unit diagnostic, not a confirmed physical offset error. Newton
USD schemas 0.2.0 document angular `mimicCoef0` in degrees, but the inspected
Newton 1.2.1 importer passes its numeric value directly into the mimic constraint.
The inspected Kit Newton 1.5.0 importer instead converts angular
`newton:mimicCoef0` degrees to radians; deprecated `mjc:coef0` stays raw radians.
These version-/attribute-specific differences do not affect zero-offset samples.
The retained raw numeric absolute residual is not calibrated physical error for
either importer. Do not guess conversions or infer importer equivalence.
Legacy mimic metric names ending in `_rad` remain for compatibility; motion
metadata supplies the actual qualified or unknown joint-coordinate unit.

Newton's local diagnostic guidance does not prescribe PhysX schema repairs or
automatic gain/tolerance changes. Inspect the composed NewtonMimic binding or
the compatibility binding actually imported, enable state, coefficient convention,
DOF mapping, units and installed solver support before attributing an asset
defect. A direction warning is not permission to flip a coefficient sign:
that changes physical coupling, not cosmetics.

Mimic applicability follows the inspected Newton 1.2.1 importer: an authored
`newton:mimicEnabled = false` disables that native coupling without falling
back to a PhysX compatibility mimic on the same joint. `MjcEqualityJointAPI`
takes precedence over native/compatibility mimic coupling. Disabled or
overridden bindings are not active mimic-test obligations; inspect the saved
plan and selected runtime variant rather than adding a coupling to force coverage.

The PhysX compatibility detector preserves the authored instance namespace for
`rotX`/`rotY`/`rotZ`, `transX`/`transY`/`transZ` and short `X`/`Y`/`Z`.
USD token values differ from Python attribute names (`UsdPhysics.Tokens.z`
is `"Z"`); a short spelling must not be treated as absent coupling. Discovery
alone does not qualify Newton import or solver support, and does not alter the
native/equality precedence above.

Selected native/compatibility gearing and offset queries are required. Genuine
absent or `None` values keep the existing schema fallback; supported query or
conversion errors propagate unchanged, and non-finite coefficients are execution
errors before measurement. A successful setup read does not authorize a default
after a later read fails. The magnitude equation, ratio tolerance, native/equality
precedence and physical asset data are unchanged.

Native `newton:mimicJoint` and supported PhysX `referenceJoint` relationships
resolve direct or chained targets through native USD forwarding. Exactly one
existing joint must resolve inside the detector's asset search subtree; an
intermediary property, outside same-named joint, non-joint, empty/dangling/cyclic
chain, multiple targets or self-reference cannot provide a runnable pair.
Native USD resolution errors remain unresolved prerequisites, while unexpected
helper errors propagate as execution errors. Missing runtime DOF mappings leave
execution incomplete with NO VERDICT. The conservative one-leader gripper topology
hint consumes the same resolved identity. Synthetic discovery/entry-point
coverage does not establish native Newton importer or solver support.

## Coordination Timing and Velocity Application

### Applicability and incomplete execution

When positive inspection proof succeeds, the existing clean skips for a
standalone gripper, fewer than two independent MJC motion coordinates,
no active applicable mimic followers, no independent VEL coordinates, a
qualified world-anchored falling/sliding trial, or no movable FET004 joints
record `assessment_applicability`. The metric contains
`status: not_applicable`, a stable `reason_code` and the actual `reason`;
it is published through `ctx.add_metric`, never by mutating a metrics copy.
Absence-based evidence requires a complete concrete composition of the full
owned asset, with its full subtree included in the population mask, and the
producer's actual inspected dependencies. Unloaded, undefined or
abstract owned content and failed inventory queries leave applicability unknown.
Any stage composition error also conservatively withholds proof; it does not
attribute an outside-asset error to the asset or create asset FAIL.
Owned composition includes sibling controller subtrees and instance proxies;
complete composition does not establish that a legacy non-proxy detector
inspected proxy controls. Cached passive or
standalone classifications from partial discovery cannot qualify N/A. When
publishing VEL/MJC/IK/JIK count or standalone markers, fresh read-only control
discovery must agree with the cached passive/follower/loop exclusion union.
A newly loaded ordinary controller subtree can invalidate cached exclusions
even without instance proxies. Disagreement or query failure withholds the
marker without changing the original skip, commands or load state. When
qualifying the marker, the actual actuator/mobility reads used by passive and
loop discovery must succeed: exception-to-empty fallbacks cannot prove absence
even if cached and fresh exclusions agree. This strict proof mode does not
change historical discovery eligibility. When
that inspection is unqualified, the marker is withheld while the original skip
remains unmarked and the test remains Could not assess. This qualification does
not change load state, physical eligibility, commands or response criteria.
World-anchor evidence requires every enabled owned rigid-body component to be
connected to a qualified fixed world/static anchor. Fixed, revolute and spherical
constraints can supply graph edges; prismatic edges require qualified finite
travel. A disconnected free body, unsupported/free constraint, animated
eligibility or breakable essential connection cannot establish this proof.
The Newton provider conservatively accepts only constant positive infinity or
exact float32 maximum (`3.4028234663852886e38`) for both breaking thresholds.
The inspected Newton 1.5 USD importer and joint builder do not propagate
breaking thresholds; this policy accepts the conventional effectively-unbreakable
export sentinel while retaining the guard on other finite authored strengths.
It does not claim Newton implements PhysX's breaking behavior. Animated,
blocked or invalid thresholds remain unqualified, as does the adjacent lower
float32 value. Source data and the historical skip remain unchanged; N/A is
not a measured falling/sliding PASS.
The resolved endpoints and each
rigid-body ownership ancestor must be qualified, including external sources;
an unloaded dynamic ancestor cannot prove a static frame. Missing, masked,
unloaded, undefined, abstract or unresolved required dependencies withhold the
marker without loading content or changing the legacy precheck. Disabled or
unrelated historical anchor skips retain their behavior and remain unmarked
with NO VERDICT.
Mimic absence additionally requires an independent raw active authored coupling
absence inspection. An empty mapped selection cannot excuse authored followers
omitted through external body-endpoint ownership.
Unqualified proof keeps the original skip unmarked/Could not assess; known
response-pair or required mapping errors retain their separate execution path.
Missing required input, safe ranges for otherwise applicable coordination,
Lula descriptors, stage/live endpoint mapping, solver construction, generated
targets, mimic pair mapping or runtime probe support leaves execution
incomplete with NO VERDICT. A marker does not override an error or failure.
Unmarked legacy or ambiguous coverage skips also supply NO VERDICT.

### Newton Multi-Joint Coordination Timing

Version 1.2.0 retains legal targets, exclusions and the independent remembered
band-entry criterion. Each iteration derives travel from required live starting
positions and uses one shared smoothstep ramp long enough for the slowest
qualified joint. The duration is the greater of `motion_seconds` (default 2)
and `1.5 * abs(goal - start) / (speed * coordination_speed_scale)` plus
`coordination_settling_allowance_seconds`, maximized across qualified joints.
Defaults are speed scale 0.8 and allowance 0.25 seconds; complete ticks round
up. This is a response allowance, not a measured acceleration model.

The original post-ramp opportunity remains: default `max_settling_seconds=8`
minus `motion_seconds=2` gives a 6-second hold. A 4.75-second shared ramp thus
receives 10.75 seconds total, subject to the unchanged early band-entry exit.
The historical minimum of 60 total ticks remains. A configured total window
shorter than the configured base ramp is rejected before physics work.

The Newton-owned resolver uses the native hint and qualified Newton 1.2.1
compatibility input described for FRS; it does not reinterpret a DC-motor
`newton:velocityLimit` as a joint cap. Unavailable/malformed optional hints
use a recorded motion-floor fallback; a present getter exception is an
execution error. Per-joint timing metrics retain hint source, travel and
estimated command peak, and each iteration records shared ramp/hold/total.
Pacing is not proof of physical hard-cap or acceleration enforcement.
The actual first clipped legal command is checked against each qualified
speed allowance. A far out-of-range live start that cannot fit this first
command becomes a setup/timing error before commands, not an asset FAIL;
tiny clipping within the allowance is retained. Timing rows expose
`initial_command_clipped` and `estimated_initial_command_step_speed`, while
absent hints still provide no pacing guarantee. Interrupted execution retains
planned timing and completed nominal ticks.
Read `mjc_timing_iterations` with the position/error histories;
`mjc_timing_iterations_omitted` and per-record `joints_omitted` describe
bounded diagnostic omissions, not missing commands or zero displacement.

Default `max_coordination_ramp_seconds=60`,
`max_coordination_simulation_seconds=600` and
`max_coordination_wall_seconds=3360` bound execution; the wrapper allows 3600
seconds. Initial settling and complete iteration windows must fit the nominal
budget before commands, and only completed requested ticks count as nominal
time. Captures/setup consume wall time separately. An exhausted budget is an
execution error, not an asset FAIL or a silently shortened ramp.

### Velocity-Limit Application Evidence

The Newton velocity-cap boundary accepts positive finite requested values and
treats NaN slots only as omission markers. Before a full-row native write it
preserves omitted coordinates from complete live native readback, including
existing zero caps and SDK defaults, or stops before writing when preservation
is unavailable. No fallback cap is invented. Original request shape/type,
infinity, nonpositive requested caps and float32 overflow/underflow are checked
before submission. Available readback must exactly match the complete submitted
float32 row. With no getter, a fully specified safe request can only receive a
setter acknowledgement, recorded in helper detail; omissions cannot be preserved.

Selected physical revolute joint identity qualifies native rad/s inputs for
rejection of the SDK float32-maximum degree/s default converted to radians/s,
including float32 rounding. Authored ratings, linear coordinates and unknown
units do not lose a value merely because it matches that converted number.
The same classification feeds full-range sweep, coordination and JIK timing;
their configured fallback duration applies when no meaningful hint remains.
Native defaults preserved as state are separate from mechanical comparison
ratings. These timing changes do not relax response criteria or execution budgets.

The actual Newton VEL phase still rejects explicit coupled/passive indexed
control when its adapter cannot qualify sparse commands. Omitted joints with
ineligible travel can reach the cap writer and use the preservation policy
above; this does not enable coupled control or prove solver enforcement.

`vel_velocity_limit_application` records `reported_success`, `not_applied` or
`unknown` from the application helper, also retained in motion metadata.
False/unknown outcomes warn. A helper success does not demonstrate physical
hard-cap enforcement; `vel_velocity_limit_enforcement` remains `not_verified`.
A present helper exception stops execution rather than becoming a PASS.
The deliberate fast position-step test retains its sampled-speed criterion,
startup exclusion and early near-zero stop; it is not a target-arrival test.
These setup observations do not make Newton's unsupported hard-cap behavior
an asset defect or justify changing authored limits.

Version 1.1.6 requires a meaningful positive finite comparison ceiling and a
finite nonempty bounded position range for the existing opposite-range target.
Rounded float32-maximum SDK unlimited sentinels are not physical speed caps or
position stops; raw authored sentinel inputs are rejected before conversion.
A valid supported authored ceiling can replace an unlimited native input while
retaining its source label. Reversed, locked, one-sided or unbounded ranges are
visible prerequisite omissions, not invented excursions or huge setpoints. If
no eligible joint remains despite independent coordinates, VEL leaves execution
incomplete with NO VERDICT. No independent coordinates yields a marked
applicability skip. Mixed eligibility covers only the tested subset. Floating command
construction preserves finite eligible fractional targets; the sampled-speed
criterion, startup exclusion and early near-zero stop remain unchanged.

VEL accepts a supported authored hint only for a uniquely resolved composed
revolute/prismatic joint and its matching angular/linear envelope instance.
Ambiguous basenames, including matches without a ceiling, cannot select an
arbitrary rating; mismatched axes cannot provide a converted comparison.
A meaningful native ceiling remains available independently.
`vel_joints_not_evaluated` counts ineligible nonexcluded joints;
`vel_joint_eligibility_omissions` retains up to 64 names/reasons and
`vel_joint_eligibility_omissions_truncated` discloses truncated diagnostics.
A bounded warning identifies that coverage is limited to the eligible subset.

VEL and IKR input gathering preserve optional schema absence and unusable-value
fallbacks. Errors querying a supported selected authored velocity property
propagate unchanged, with its qualified property path noted best-effort. A
failed schema, attribute, presence or value query cannot supply a native
comparison ceiling or timing fallback. This does not add Newton initialization
cap enforcement or qualify performance-envelope hints for the separate JIK,
FRS and coordination timing readers.

Host `test_authored_velocity_query_errors.py` regressions exercise real USD,
the installed legacy schema, actual VEL eligibility and IKR gathering with
bounded adapters. They establish required-read propagation and preserved
optional-input policy, not native speed-cap enforcement or asset PASS.

## Diagnostic Criteria and Triage

Robot phases validate their verdict-critical configuration before their
evaluated motion: finite real tolerances/thresholds with valid domains,
whole-number sample counts and boolean policy flags. Invalid numeric
coercions, NaN/infinity and malformed counts are configuration errors, not
asset verdicts or legitimate applicability skips. Valid exact-zero tolerances
remain supported where the criterion permits them. This is phase-owned
validation, not a blanket schema for other test packs or unused compatibility
keys.

For Lula and Jacobian IK, solver exceptions or malformed success flags, action/hold
command failures, and unavailable required end-effector error calculations are
execution errors, never correctly rejected out-of-reach targets. A well-formed
explicit solver rejection retains the existing sampled diagnostic criterion;
it does not prove global unreachability. Reference-state restoration remains
required when precomputation exits with an error.
Failed physics ticks, solver arithmetic errors and malformed Jacobian solver
results are execution errors, not measured nonconvergence.

Missing, non-finite, wrong-shaped or non-real-numeric joint/Cartesian state
(boolean, string, object or complex data) required by control
or the verdict stops execution as a setup/runtime error. It cannot prove
conformance PASS or an evaluated asset-response FAIL, including when response
exceedances are configured as nonfatal warnings. Optional extra motion
readbacks remain nullable/partial. Finite solver nonconvergence and response
criteria retain their existing policies; no commands or steps are added.

Newton runtime geometry canaries require complete finite live bounds, not the
authored rest-pose AABB. Geometry is selected from the verified loaded asset
subtree independently of a fixed-joint-leaf
articulation root; joint/actuator discovery never scans room/probe content.
Each eligible default/render/proxy boundable follows
its nearest enabled rigid body's live Fabric transform; independently moving
nested bodies own their geometry, and static geometry retains its authored
world transform. Missing required body poses or malformed geometry are
setup/runtime errors, not zero/partial bounds or measured stability. These
visual geometry proxies do not measure cooked colliders or collision contacts.
Explicit authored bounds remain appropriate for setup/reach heuristics and
the drop procedures' initial pre-pump placement context, not subsequent
runtime evidence. The optional camera's best-effort fallback is separate.

IK target reach meets a sampled success fraction (default 0.50) using final live
EE position error; orientation tolerance is a Lula solver input, not a live
orientation check. JIK defaults to a 0.40 fraction using final live position plus
solver orientation error. Neither pass certifies all targets, workspace,
descriptor pairing or final live orientation. Failed targets remain visible.
IK target generation requires a finite robot-base world position and nonempty,
finite asset bounds with positive horizontal extent; missing measurements stop
execution without an asset verdict or a synthetic target center/reach.

Newton-owned JIK excludes passive, resolved mimic-follower and loop DOFs from
independent sampling, Jacobian columns and all probe/target/velocity writes.
Lula similarly retains its public descriptor subset and action indices without
independently commanding coupled or unrelated coordinates. Those coordinates
record measured position only, not invented independent target/error channels.
The legacy Newton adapter expands sparse targets into full vectors and is not
qualified to leave excluded DOFs uncommanded. Therefore coupled/subset IK/JIK
requiring sparse writes stops with an explicit unsupported-control setup error
before those probes; it does not issue a full-vector fallback or blame the
asset. Complete live state is still required. No-exclusion Newton behavior
remains unchanged, and synthetic controllers do not establish native support.

For independently commanded DOFs, JIK requires observed runtime joint limits.
A present limit getter that raises, returns malformed shapes or invalid data
cannot fall back to invented infinities. An absent accessor needs supported
real `dof_properties` limit fields instead. Explicit correctly signed unlimited
values retain their meaning. Excluded, unwritten DOFs may keep unknown bounds;
that is not permission to command them or claim their coverage. These native
readback requirements are independent of Core's procedure/default ownership.

JIK keeps the same targets, limits, tolerances and live playback gate. After
explicit finite solver nonconvergence only it tries up to four deterministic,
deduplicated independent-coordinate seeds: previous success, current state,
the first failed solve's finite best configuration, and home. It never reuses
the generating FK answer as a shortcut. Each attempt retains the configured
`max_solver_iterations` (150 by default), with at most four times that configured
count per target (600 with defaults); errors, malformed results, failed propagation and cancellation stop
immediately. Bounded `jik_seed_attempts` diagnostics disclose seed/error/
iteration records and omissions. Newton's locally owned
`max_search_wall_seconds` is a finite positive real allowance, default 1800 with
an explicit maximum of 1800 seconds. Invalid booleans, strings and nonfinite
values are rejected before scene setup. It starts at phase entry, covers initial
settling, FK target sampling and all solver attempts, and is checked before/after
existing ticks, progress boundaries and completed solves without adding ticks.
All seven default targets retain up to 4,200 total solver iterations, including
the diagnostic negative-target searches. Targets, tolerances and the success
fraction do not change. The budget never extends automatically with machine speed.

The locally registered whole-test ceiling is 2,400 seconds. Search using its full
allowance leaves at most 600 seconds gross for prior scene setup, playback,
media and cleanup; prior setup has already used some of that allowance.
Slow machines are not guaranteed to finish. Local checks cannot forcibly
interrupt blocked synchronous native work; the runner's outer deadline still
applies. Exhaustion remains incomplete execution, not an asset FAIL or evidence
of correctly rejected diagnostic targets. An operation's actual error or
cancellation takes precedence over a late deadline, with required reference
restoration still attempted.

Optional `jik_search_timing` records wall allowance/elapsed time,
requested/completed search ticks, started/completed solver attempts, completed
iterations, bounded last progress and stop reason. These are whole-operation
service measurements, not native solver CPU time or physics/video timestamps.
Incomplete attempts have no invented completed iteration count. Optional
recording failure cannot change a valid result or mask the first execution
failure. Native robot qualification remains pending.
Generate a fresh plan with this provider version; replaying an older saved
plan can retain its earlier whole-test duration metadata.

JIK's retained `out_of_reach_factor` and `hemisphere_only` keys are inactive.
Its extra diagnostic targets use the fixed 1.4 multiplier on the maximum
sampled base-to-endpoint distance and always fold their direction into the
upper hemisphere, regardless of those overrides. This radial heuristic does not prove global
unreachability; inspect the actual target records.

The Newton-owned target/probe corrections keep finite native limits, including
one-sided stops. Only signed infinity or the narrowly rounded SDK float32-max
sentinel counts as unbounded; genuinely large finite limits are not silently
replaced. Local +/- pi fallback excursions require an unambiguous composed
revolute joint. Unbounded prismatic/unknown joints are visibly omitted from MJC
or held at home for FK samples; no angular range or linear unit is guessed.

Angular classification for JIK and coordination resolves selected physical joint
identity, including exact paths and supported native axis aliases; separately
rooted same-name joints cannot supply its type. This preserves the existing
bounded excursion, sampler, seeds and solver/search policy. Missing/ambiguous
identity does not authorize an angular excursion. The tier-owned
`tests/runtime_tests/unit/test_angular_identity_consumer.py` executes the original
applicability block and FK generator with real USD and host propagation adapters,
comparing complete target/probe arrays to a leaf-name control. It is not a full
native solver or asset-acceptance test.
The FK exclusion is not a frozen-DOF guarantee: nonlocked DOFs can still
participate in finite-difference probes, the native-coordinate solver and
solution playback under their reported limits.
Excluding loop DOFs from independent commands does not remove the requirement
for complete finite native-to-legacy state during initial-state checks, probes
and restoration. If the native SDK omits a legacy loop coordinate, that state
is unavailable: affected procedures report a setup/runtime error and remain
unqualified for that asset/SDK path. Do not fill missing state from authored
USD, zeros or stale motor targets, or interpret this as an evaluated asset FAIL.
Without any unlocked safely bounded sampling DOF, JIK reports insufficient
coverage before FK/solve, even for a one-target configuration; home-only
samples cannot certify workspace exercise. Too few distinct live target
positions retains the existing response criterion but does not establish
stale readback as its cause.
MJC retains its ever-entered-tolerance criterion and records final readback/error
separately without extra observations. Its velocity-aware shared timing is
described above. State-accuracy targets use the legal
position nearest zero and adaptive native-unit margins; clamped offsets can
coincide and do not guarantee two distinct excursions.
Its legacy `position_tolerance_deg` and `max_step_deg` inputs are numerically
converted with `math.radians` and used in native position coordinates. That is
the retained procedure policy, not independent prismatic-unit calibration or
proof that a linear comparison is an angle. Inspect the resolved coordinate
units and sampled values before interpreting those legacy parameter names.

State accuracy alone overrides scene gravity to zero: it measures configured
command tracking, not gravity compensation. Each waypoint has a minimum
`newton_min_motion_seconds` ramp (default 0.5 seconds) and a settling budget of
`max(30, int(0.5 * physics_fps))` ticks. At the default 240 Hz, five complete
windows can total 5 nominal seconds despite `test_duration_seconds = 3`;
that configuration input is not a strict whole-sequence deadline. Every bounded
smoothstep ramp completes and commands its exact final waypoint; it does not
truncate or jump to the endpoint when readback enters a coarse goal band.
Only the following hold can end early after consecutive settled samples.
The unchanged criterion compares the final required readback with the commanded
waypoint goal, including supported tight or zero tolerances. Failed/cancelled
ramps stop with their original cause and retain the actual last command in
partial motion evidence.

### Velocity-aware JIK playback

Newton retains its resolved 1.25 s minimum interpolation and 1.0 s hold,
independently of Core's defaults. Its local USD hint qualification remains
Newton 1.2.1 / schemas 0.2.0 as described below.

Playback schedules the complete accepted move from its live starting pose using
the slowest independently commanded coordinate's usable velocity hint and profile
peak speed. The existing local segment policy is exposed and consumed:
`sweep_speed_scale=0.8`, `sweep_settling_allowance_seconds=0.25`,
`max_sweep_segment_seconds=60.0`. Missing/invalid optional ceilings retain the
configured minimum; present getter failures and invalid required positions remain
errors. Runtime distance/velocity share coordinates; selected USD angular hints
convert degrees/s to radians/s. Linear USD hints retain the owning tier's existing
qualification, never a guessed conversion. Excluded passive/follower/loop/held
coordinates neither pace the segment nor acquire independent commands.
Per-target `scheduled_interpolation_frames` and `scheduled_interpolation_seconds`
describe nominal scheduled ticks, not measured elapsed simulation or wall time.
The integer frame count is retained without a seconds round-trip truncation.
Any required target-playback failure or cancellation, including initial/subsequent
position reads, commands, ticks, holds, final EE readback and an over-budget
segment, attempts to preserve earlier `jik_per_target` rows and independently
publish `jik_playback_completion=incomplete` with the interrupted target index.
No verdict is invented for the interrupted target. Optional recording, cleanup
and metric failures cannot replace the primary required cause; publication is
best effort, not guaranteed persistence. A budget error never truncates motion
into an asset FAIL.
Search, targets, pass criteria and outer/search deadlines are unchanged.
This pacing-only procedure does not implement passive projection, global paused
timeline search or arbitrary probe overrides. A search failure before playback
is not fixed or proven fixed by extending the dynamic window. A combined
experimental pass without ablation and final native qualification cannot
attribute the cause or qualify a build.

### Separate mimic, drive-response and Lula timing

The full-range-sweep and multi-joint timing policies do not apply to every
articulation procedure. Newton MIM retains its own `sweep_seconds` window
(default 2 seconds, at least 20 ticks): a triangular low-to-high-to-low
trajectory uses smoothstep on each leg. It samples reference/follower state
every tenth observation tick, and does not add FRS velocity-aware travel ramps,
post-target holds or adaptive wall budgets. Magnitude and direction evidence
must be interpreted within that sampled, fixed-duration window.

DGV's `test_duration_seconds` is an observation budget (default 5 seconds,
at least 20 ticks), distinct from its `max_settling_seconds` acceptance limit
(also default 5 seconds). The observation loop can end after 24 consecutive
samples below the default `settled_velocity_threshold = 0.05` in native
velocity units; that stop condition alone does not establish arrival at the
goal. Settling time is the start of the final uninterrupted sampled in-band
tail, using `settling_tolerance` (default 0.05) times step magnitude. The
legacy degree-labelled 30-degree step is converted numerically with
`math.radians` and then bounded in native joint coordinates, including for
prismatic joints; it is not a separately qualified linear-excursion policy.
If the legal step is smaller than the existing 1e-6 native-unit epsilon, the
procedure omits that response observation, recording `evaluated: false`, an
explicit reason, `ok: null` and null response fields. The row does not enter
tested, passed or failed response counts. `dgv_joints_eligible` identifies
selected candidates; `dgv_joints_tested` counts observed response windows and
`dgv_joints_not_evaluated` records omitted candidates. Mixed runs warn about
missing coverage; a run with no observable legal excitation leaves execution
incomplete with NO VERDICT. Spatial safety interruptions do not enter a joint's
response `ok` calculation: they leave execution incomplete regardless of
`step_fatal`. Per-joint default-state resets isolate later probes; there is no
separate final return-to-start observation after the last joint. The default
warning-only response policy is described below.

Lula IK has separate playback timing, not FRS/MJC adaptive pacing. It estimates
joint travel time from available positive finite velocity hints, or uses
`motion_velocity_fallback` (default 2 native units per second) when the hint
array is unavailable. A usable estimate is multiplied by
`motion_velocity_scale` (default 1) and clamped to `motion_min_seconds` and
`motion_max_seconds` (both default 1.5 seconds). Without a usable estimate, it
returns `motion_seconds` (default 4 seconds) instead. The 1.5-second cap does
not guarantee compliance with a slow joint's speed or acceleration limit or
successful arrival. Smoothstep interpolation dispatches a command each nominal
physics tick; `motion_update_hz` (default 60 Hz) controls reached-target hold
refresh only. Only a reached target gets the additional
`settle_seconds_after_apply` hold (default 0.25 seconds). The default 8 fps
encoded clip is not the 240 Hz configured observation rate. The registered
1200-second outer timeout still applies to this procedure.

Lula selection matches complete model identifiers (including the Panda alias),
not UR3 inside UR30. Indexed arm solutions preserve uncommanded DOFs and reject
invalid/nonfinite indices or state. Teleports and Jacobian probes synchronize
position, matching motor targets and zero velocity through the Newton backend
adapter; dispatch/readback errors surface honestly. Probe restoration retains
the original failure/cancellation. Clipped finite differences use the actual
displacement, not a nominal epsilon, and do not change tolerances or drives.

Jacobian endpoint discovery prefers a bounded connected acyclic articulation tree's
unique deepest non-finger chain, not unordered robot-link metadata. Ambiguous
arms, unexcluded cycles, disconnected graphs or endpoints outside the loaded asset do not
authorize a guessed TCP. Explicit `physics:excludeFromArticulation = true`
closures are validated but omitted from tree edges; both body endpoints must
still belong to that tree. Unexcluded cycles and malformed or disconnected
constraints remain unresolved. This topology handling does not qualify Newton's
native control of loop-owned coordinates. Optional `ee_link_path` selects an existing absolute
prim path within the loaded asset; an invalid explicit path does not fall back
to another identity. This controls discovery only: an unexposed TCP/flange
marker resolves to the nearest exposed rigid-body ancestor without transforming
the marker offset. Logs and `jik_ee_link` identify that actually measured link;
the run does not establish exact TCP-offset motion or orientation. This
heuristic and synthetic unit coverage are not native
Newton runtime qualification or proof of a universally correct tool frame.

DGV exceedances are warnings by default (`step_fatal = false`), so overall PASS
can include zero successful response checks. Inspect counts and policy. EFF
'break' labels mean the finite range-overrun criterion, not
physical breakage. Per-joint outcomes are persisted in `eff_joint_results`.
`min_break_force_newtons` remains null because no refinement probes establish a
minimum force or measured lower bound. `commanded_force_at_failure_newtons`
records only the configured force magnitude actually issued when the criterion
failed, not joint actuator effort. After a criterion failure, `bisection_enabled`
warns that refinement is unsupported; its retained configuration keys add no
probes or steps. An unavailable required force interface, unmapped required
child body, failed force submission, or missing/non-finite required position
readback is a setup/runtime error, not an evaluated asset failure.
A native DOF resolves to its unique selected enabled, non-excluded USD joint,
using qualified exact cooked paths or supported native path/axis aliases.
Forwarded endpoint/subprim targets resolve to owning rigid bodies. The actual
downstream body follows rooted selected physical topology, not endpoint order
or the first cooked link. Scene setup records the exact successful world-pin
path and owned body for grippers, including a temporary fixture pin outside the
asset. Effort procedure 1.1.10 requalifies that receipt against live enabled,
constant, non-breakable world-pin endpoints and selected/cooked body membership;
an available native fixed-base flag must corroborate it. Removed, rebound,
foreign, incomplete or contradictory pins leave execution unassessed. It does
not scan arbitrary external pins, change source data, or certify native effort
response from the setup receipt alone. A container-rooted view without an
authored root body or a qualified setup pin needs qualified cooked parent
metadata. Unresolved, ambiguous, foreign or
detached identities are errors. Force submission uses the exact cooked body path,
not a potentially duplicate display name; force placement and magnitude math
are unchanged. The whole EFF required-probe boundary (submission, ticks,
readback, bounds, reset and required force cleanup) attempts independent
publication of completed joint evidence and evaluated partial directions.
It never counts an interrupted joint as tested/passed or masks its primary
cause/cancellation with secondary diagnostics. Completed aggregates publish
before encoding, so required encoder failures do not erase evaluated records.

The FET004 spherical recording rerun requires the same force-view, mass and
finite child-body transforms as its exploratory probe. Procedure `2.2.5`
preserves an unavailable recording observation as an execution error, even if
the earlier probe moved. It stops physics and attempts the local state reset
before raising; an exposed cleanup failure retires the worker and preserves
the recording error as the first cause. Required full scene teardown remains
the framework's responsibility; this does not prove native state restoration.
This changes neither the force ramp nor the aggregate movement criterion and
does not turn missing recording evidence into an asset failure or a PASS.

EFF procedure 1.1.9 initializes current-joint evidence before its first progress
callback. Cancellation, process exit or unsafe evidence at that boundary retains
the exact primary cause and an empty current break/direction list, while completed
earlier joint records remain separate. An interruption before body mapping
submits no current force and performs no current-body force cleanup. Publication
is best effort when a secondary metric sink also fails; missing diagnostics do
not qualify completion or native force delivery.

For both EFF and JIK, ordinary observer/camera/metric delivery failures are
optional, not required engine-health failures. The producer's existing `None`
result omits recoverable media. Unknown capture/encode errors, unsafe evidence
paths, required cleanup, user cancellation and process exit propagate. JIK's
final fields publish independently without changing its local aggregate/gate.

Present selected drive gain queries must return finite nonnegative real values;
query failures and invalid values retain their cause as required setup/readback
errors, including through loop eligibility discovery. Unapplied drives and valid
default/explicit zero gains remain passive. This does not retune or enable drives.

Inspect variant, descriptor/TCP, DOF/body mapping, imported controls/limits,
coupling, units, base/gravity setup and actual runtime support before assigning
an asset defect. Authored USD angular limits are degrees and linear limits stage
units; linear tensor units need qualification. Do not add PhysX schemas, invent
frames/limits, prescribe generic gains or relax criteria merely to pass.
Evidence-backed repair/tuning is external to Evaluate.

## Time, Captures and Partial Evidence

Time is estimated from observed physics steps and configured `physics_fps`,
not measured wall-clock time or a complete solver timeline. Setup, warmup,
resets and capture/render ticks are excluded. Related ramp/hold segments use
one cumulative per-history clock; distinct joint/trial histories are separate
windows and must not be concatenated as one continuous recording.

Histories are bounded, normally retaining every fourth observation plus phase
changes, with at most 4096 retained samples per history. The runner also bounds
the total history count. Missing observations remain null/partial, not zero or
an interpolated measurement. Optional readback/recording failures warn without
changing required test readbacks or verdicts. Old runners without the motion API
continue to execute without these artifacts.

After a successful capture, a marker associates it with the preceding retained
observation. Multiple captures following the same observation are coalesced;
at most 512 associations are retained. Markers do not identify the exact instant
shown by a rendered image or encoded video frame: capture warmup/retries can
advance the scene, and encoding can omit or repeat images. Do not infer video
seeking or exact 240 Hz/15-30 fps alignment from those markers.

Reports expose relative JSON/CSV artifacts and completion/partial context.
Inspect stop reasons, missing channels, truncation and omitted remote artifacts
before interpreting a flat trace as stability or a missing plot as success.
Sparse diagnostic plots do not replace the procedure's evaluated observations.

## Qualified Newton Velocity Limitation

The currently qualified local evidence is Newton **1.2.1** with Newton USD
schemas **0.2.0** in Isaac Sim **6.0.1.0**. Recheck another installed version.
Recorded `velocity_limit_provenance` separates these qualified versions from
the actual package versions returned by the worker; unavailable metadata stays
unknown.

In that Newton importer, `_src/usd/schemas.py` maps joint `velocity_limit`
from the compatibility attribute `physxJoint:maxJointVelocity`, and
`_src/utils/import_usd.py` converts angular USD degrees/s to radians/s.
Prismatic compatibility inputs remain stage-distance/s. The test retains its
existing runtime-DOF and USD comparison inputs; a PhysX performance-envelope
fallback is not proof of Newton importer support or hard-cap enforcement.
Newton 1.2.1's `solvers.py` feature table lists `joint_velocity_limit` as
unsupported. Importing a ceiling and observing one passing response do not
establish a universal enforced hard speed cap.

In schema 0.2.0's `generatedSchema.usda`,
`NewtonDCMotorClampingAPI`'s `newton:velocityLimit` is a no-load effort-speed
saturation parameter on an actuator, in radians/s or distance/s. It is not a
hard joint-speed cap. Do not substitute it for a joint comparison ceiling or
apply the compatibility attribute's degrees-to-radians conversion to it.
A similarly named bare joint attribute is not mapped by the qualified importer.

A missing comparison ceiling is insufficient evidence, not an automatic asset
defect. A measured exceedance fails the existing response criterion but does
not establish its cause. First verify the selected variant, units, actual
importer, actuator controls, returned limits and solver enforcement. Do not add
PhysX schemas, raise ratings, loosen tolerance or rewrite gains merely to force
a pass. Report engine/test limitations separately from reproducible asset
defects. Any justified repair or tuning happens outside Evaluate, preserving
the original asset and evidence.
