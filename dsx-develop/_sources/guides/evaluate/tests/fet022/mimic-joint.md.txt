# mimic_joint  (FET022 Driven Joints)

| Property     | Value                                                                         |
|--------------|-------------------------------------------------------------------------------|
| Test name    | mimic_joint                                                                   |
| Feature(s)   | `FET022_DrivenJoints.PhysX.0-1-0`, `FET022_DrivenJoints.PhysX.0-2-0`, `FET022_DrivenJoints.Isaac.0-1-0`, `FET022_DrivenJoints.Isaac.0-2-0` |
| Engine       | Kit / Isaac Sim (>=2024.2.0)                                                  |
| Test version | 1.1.11                                                                         |
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

Sweeps each reference joint and verifies that every mimic-follower joint moves by
the correct magnitude according to its declared gear ratio.

## Optional Motion Evidence

Each exercised mimic pair records separate reference and follower histories at
the existing every-ten-step readback points. The reference plot compares measured
position with its actual issued command; the follower plot shows its measured
position, displacement from the measured rest pose, expected incremental
displacement from the backend-normalized multiplier, and incremental error. For
PhysX, `follower + gearing * reference + offset = 0`, so the displacement
multiplier is `-gearing`; the constant offset cancels when subtracting the
measured rest pose. Incremental
error is diagnostic: the unchanged verdict uses the swept-motion magnitude ratio,
not a per-frame tracking-error gate.

Resolved angular joint coordinates use radians. Prismatic tensor units remain
`unknown_native` unless their conversion path is qualified; raw USD limits use
stage length. Legacy `_rad` metric names do not establish prismatic units.
The absolute residual is a raw-authored-offset numeric diagnostic, not a
runtime-calibrated physical offset error; angular offset conversion and mixed
reference/follower joint units must not be guessed. Times are pair-local nominal step-count
estimates, excluding rendering ticks. Capture markers associate successful images
with the preceding retained observation, not exact video timestamps. JSON/CSV and
plots are optional; recorder failures mark evidence partial without changing the
test result, and runners without the hooks retain ordinary execution.

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
page. No-applicable-pair cases still skip before control checks.

## Required Runtime State

Selected mimic gearing and offset reads are required too. A genuine absent or
`None` value retains its existing schema fallback; a supported query/conversion
error or non-finite value stops execution before the pair is measured. The
test does not substitute a default after a failed read, even if setup read
the property successfully earlier. This is an execution error, not an asset
response FAIL or a completed PASS.

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
volume proxy. `mimic_guard_reference` records the basis and qualification;
`mimic_guard_abort` retains a detected guard interruption when diagnostics
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

MIM requires a usable finite runtime reference sweep window. Correctly signed
infinities and the SDK's rounded float32-maximum unlimited sentinels are not
finite mechanical stops: they stop this procedure with an explicit execution/
coverage limitation before that pair receives commands, never an enormous
setpoint or an evaluated mimic-following asset FAIL. No local continuous-joint
range is fabricated. Valid finite pair goals and magnitude criteria are
unchanged; metrics from an earlier completed finite pair remain available if a
later window is unavailable. Locked, inverted or tiny intervals no wider than
the unchanged 1e-6-native-unit epsilon likewise stop as procedure limitations,
not fabricated tested-pair responses. This prerequisite is not a DJ.007 requirement
to replace valid continuous limits with invented finite stops.

A passing result confirms that tested, resolved mimic pairs in this sampled
PhysX response have a follower/reference swept-magnitude ratio within the
configured tolerance of the authored coefficient magnitude. It does not certify
direction, absolute offset, every possible load or universal constraint enforcement.

## What It Checks

The test discovers all joints that carry a `PhysxMimicJointAPI` schema. For each
such follower joint, it identifies the reference joint and sweeps the reference
joint across its inset test range. From sampled minimum/maximum positions across
the sweep, the test computes the ratio of the follower's span to the reference's span and
compares it against the absolute value of the authored gear ratio. A follower
fails if the magnitude ratio differs from `|gear|` by more than
`gear_ratio_tolerance` (default 0.10 in dimensionless ratio units, not necessarily
a 10-percent relative error).

PhysX discovery preserves the exact authored instance namespace and recognizes
the DJ.007 spellings `rotX`/`rotY`/`rotZ`, `transX`/`transY`/`transZ` and short
`X`/`Y`/`Z`. These are USD token values, not Python token attribute names
(`UsdPhysics.Tokens.z` is `"Z"`). A short axis is not a reason to rename an
asset's schema or discard its follower. This detection also supplies required
scene control ownership; recognizing a token does not establish solver support.

Reference relationships support direct and chained native USD forwarding. The
resolved target must be exactly one existing joint inside the detector's asset
search subtree, not an intermediary relationship property, non-joint prim or
same-named joint in another asset. Empty, cyclic, dangling, multiple or self
references provide no runnable pair. Native USD resolution errors remain
unresolved prerequisites; unexpected helper errors propagate as execution
errors. Required scene command ownership is separate from response-pair
qualification: active authored followers must map uniquely to runtime DOFs.
Missing/ambiguous active follower mappings or unexpected required ownership
queries stop execution; they are not evidence of independent coordinates.
Explicitly disabled joints are omitted before ownership/mapping.
Newton mimic opinions with an explicitly disabled composed enable flag do not
establish active ownership alone; an independently active co-authored PhysX
mimic API remains eligible. Missing/unauthored Newton enable flags retain their
existing default-enabled policy. No backend coefficient translation is inferred.
Raw API presence conservatively establishes command ownership only, not native
mimic equations or solver support. If authored followers exist but SDK, axis,
reference or mapping prerequisites leave no qualified response pair, execution
stops with an explicit coverage limitation, not a claim that mimic APIs are
absent or an asset-response FAIL. Unknown authored presence and missing
reference/pair mappings are execution gaps with NO VERDICT. Successfully
established absence of active applicable followers records
`no_active_mimic_followers` only after complete composition and an independent
raw authored coupling inspection establish absence.
An empty mapped selection cannot erase active authored followers whose physical
joints were omitted, including through external body-endpoint ownership.
Incomplete proof retains the original skip without a marker, reported as Could
not assess rather than evaluated asset FAIL or PASS.
The same resolved identity is used by the conservative one-leader gripper
topology hint. These checks do not qualify native solver support.

Direction mismatch (whether the follower moves in the same or opposite direction
as the reference) and rest-pose offset differences are recorded as diagnostic
warnings, not as failures. The original discovery skip is Not applicable only
when the separate positive absence proof succeeds. A response detector returning
no qualified pair does not, by itself, establish that no mimic API was authored.

## How It Works

Each pair uses its own triangular smoothstep command: inset lower to inset
upper and back toward lower over `sweep_seconds` (default 2 nominal seconds),
with at least 20 requested physics ticks for the complete sweep. Each leg uses
half of that fixed step window; there are no FRS endpoint-hold windows,
velocity-aware ramp extension or FRS execution budgets in this procedure.
Finite legal inset targets remain unchanged. A slow follower may therefore
need timing/setup investigation; an FRS pass does not qualify this pair's
response window. At the existing every-ten-step observation points, the
reference and follower positions are read from the articulation state.
The final ratio uses the observed span of each
joint, avoiding sensitivity to a constant rest-pose offset. It is not an
instantaneous per-frame ratio. The ratio is checked against `|gear_ratio|` with
the configured dimensionless tolerance.

The test operates on the articulation as authored, without modifying any joint
schemas. A pair whose reference is itself a mimic follower, passive or loop DOF
stops with an execution limitation: driving that dependent reference independently
is not qualified. Such chains are not silently omitted or reinterpreted.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Follower magnitude ratio error exceeds the configured tolerance | Inspect composed coupling, controller response, limits, importer/solver support and test setup; this does not identify a cause by itself |
| Test skipped | A healthy marker identifies positively qualified absence of active applicable authored followers. Without complete composition and independent raw authored coupling absence proof, the original unmarked skip is Could not assess; neither supplies response PASS or asset FAIL. |
| Presence or pair-mapping gap | Unknown authored presence or unresolved runtime DOF mappings leave NO VERDICT |
| Runtime coverage limitation | Known authored followers without a qualified response pair, a dependent reference, or an unusable finite sweep window prevents evaluated response; inspect prerequisites without assigning an asset defect |
| Direction mismatch warning (not failure) | Backend-normalized sampled direction comparison disagrees; inspect joint-axis conventions and runtime coupling before attributing an asset defect |

## How to Fix

Preserve the original evidence and inspect the composed `PhysxMimicJointAPI`
instance, reference target, raw gearing/offset and runtime DOF mapping. Compare
the selected runtime, controller, joint-axis conventions, limits and qualified
coordinate units before deciding whether there is an asset, setup or solver
defect. A ratio mismatch alone does not prove the gearing is wrong. Do not flip
gearing merely to match a direction warning: changing its sign changes the
physical constraint, not its appearance. Any justified repair/tuning is external
to Evaluate, not an automatic consequence of this result.

If the follower cannot reach the full excursion implied by the gear ratio, check
that the follower joint limits are wide enough to accommodate the range commanded
by the reference joint multiplied by the gear ratio.

## Expected Result

:::{note}
An expected-result still and video for this test are not captured yet. The expected result is described below.
:::

Ideally, the follower moves in proportion as the reference joint sweeps through
its range. A passing result confirms only that the measured swept-span magnitude
ratio meets the test's criterion; it does not establish proportional motion at
every observation. Asymmetric or lagging motion warrants investigation of the
commands, coupling, setup and solver, rather than establishing a coupling defect.

## Notes and Caveats

The test checks magnitude only. Direction and offset are reported as warnings
by the existing direction-agnostic verdict policy. Inspect the backend coefficient
convention and residual unit basis rather than assuming a direction or offset
warning proves either correct coupling or an authoring defect.

The existing skip receives an N/A marker only when complete composition and
independent raw authored inspection establish no active applicable mimic followers.
An unqualified empty mapped inventory retains an unmarked Could not assess
result. Disabled API opinions can remain present;
this is not a count of all raw schema tokens. Active authored followers with no
qualified response pair instead produce an explicit execution limitation.
A documented applicability skip supplies no response coverage and does not
indicate a defect.
