# gripper_close_lift_sphere  (FET028 Gripper)

| Property     | Value                                         |
|--------------|-----------------------------------------------|
| Test name    | gripper_close_lift_sphere                     |
| Feature(s)   | `FET028_Gripper.Isaac.0-1-0`                          |
| Engine       | Kit / Isaac Sim (PhysX; >=2024.2.0)           |
| Test version | 1.4.9                                         |
| Wall-clock timeout | 600 seconds |

## Summary

By default, the gripper closes on a sphere whose diameter is 70 percent of its maximum jaw opening, at 50 percent of the resolved maximum payload, then attempts a 20 cm gantry lift, a 2-second sinusoidal shake, and release. Opening and payload metadata prefer `gripper_maxOpening` and `gripper_maxPayload`; the reader also accepts legacy `custom:maxOpening` and `custom:maxPayload`. If no usable positive payload is resolved, an opening-based heuristic supplies the maximum; it is not necessarily a rated capability.

## What Pass Guarantees

A pass means this configured synthetic-sphere simulation satisfied the close/retention proxies, carrier-follow, shake, and release criteria. It does not directly measure contact force, holding torque, or pad friction, and it does not certify a rated payload or real-world pick-and-place suitability. Review the resolved payload and setup together with the sampled evidence.

## What It Checks

The test confirms that the gripper:

- discovers a valid gripper site with a positive maximum jaw opening,
- attaches to a test-owned Z-axis gantry through the gripper base rigid body,
- drives every resolved jaw leader to its open limit and verifies that the commanded leaders reach the open position,
- descends toward the sphere using an object-motion contact proxy before closing,
- satisfies the close stall/engagement proxy (not a measured collision-contact check),
- retains the sphere laterally within one object diameter of its spawn XY position after the close,
- lifts the sphere at least 10 cm with the gantry and confirms the sphere follows the carrier upward within 5 cm vertical error and 5 cm horizontal drift,
- holds the sphere through 2 s of sinusoidal Z-axis perturbation with the object staying above 2 cm and slipping less than 3 cm relative to the gripper, and
- releases the sphere when commanded: the sphere falls at least 5 cm after the open command.

The published Isaac contract runs on PhysX and covers resolvable parallel-jaw and centric mimic grippers as well as independent-finger hands. Internal legacy Newton jaw helpers are not a published Newton gripper contract. Mechanisms without compatible position-driven branches retain an unmarked skip reported as Could not assess; unsafe or unresolved active coupling stops execution with a mapping/setup error.

Missing-site skips are also unmarked and reported as Could not assess.
Neither skip supplies positive N/A evidence, measured grasp PASS or asset FAIL.

## How It Works

The test runs the following stages in order. Numeric values below describe the
registered defaults; supported configuration can change the trial. Inspect
`gripper_trial_controls` for the effective dimensions, mass, targets and controls.

1. **Site discovery.** The test uses the first discovered valid gripper site and resolves maximum opening from preferred `gripper_maxOpening` (metres), with `custom:maxOpening` as a legacy fallback. The current orientation/mapping helper requires a rigid-body ancestor of the site, preferring one with rigid-body descendants and otherwise the closest ancestor. This is a provider mapping constraint, not an additional GR.001 authoring requirement. The physical carrier attachment root is resolved separately within the verified loaded asset; it need not be that ancestor or the articulation API prim.

The numeric reader tries the canonical field first and reaches the legacy alias
only when the preferred field returns no value (missing, empty or non-finite).
Once a finite value is found it takes precedence: a nonpositive canonical
opening fails the opening gate rather than borrowing a conflicting positive
legacy value. Malformed values can raise setup errors. Do not author conflicting
aliases to manipulate the trial.

2. **Topology check.** All joint types, including fixed and closed-loop extensions, contribute geometry candidates on distinct physical branches. The rest-pose pair is only a provisional hint; live geometry selects distal pads. GR.003 is the tube axis/contact-pad width, not a pad-to-pad opening segment. The guarded internal Newton-native two-leader helper still requires explicit actuator targets and separate joint-graph branches; it is not a published Newton close/lift contract.

3. **Payload resolution.** The default sphere mass is `0.5 * resolved_max_payload_kg`. A positive `gripper_maxPayload` supplies that maximum, with `custom:maxPayload` accepted as a legacy fallback. If no usable positive value is resolved, the maximum is estimated at 50 kg/m of maximum opening and clamped between 0.1 kg and 50 kg before applying the fraction. A warning identifies the heuristic. `tested_mass_kg_override` can explicitly replace the trial mass and is recorded as an override, not an authored rating.

4. **Gantry attachment and free-probe setup.** The test attaches a prismatic Z-axis carrier by a fixed joint to the unambiguous physical articulation root body, not arbitrarily to the site ancestor or API prim. A world-joint API can resolve a sibling body; competing roots/anchors stop setup rather than guessing. Default parallel/centric approach points toward world negative Z; independent hands retain their authored frame unless a supported control overrides it. Collision on explicitly tracked test-owned supports is temporarily suspended; asset colliders and walls are untouched. No pickup object exists during mapping.

5. **Measured endpoint mapping.** Each selected jaw leader is gently ramped to inset lower and upper probes using existing authored drives and the configured bounded probe steps. One live transform snapshot at each endpoint locates owned distal geometry, excluding nested rigid bodies and non-colliding guide annotations. Wider planar pad separation (or collective centric spread) determines open; an authored rest target, curve length, or joint name never determines polarity. Multiple leaders are mapped independently and can use opposite conventions. Independent fingers likewise use stepped live geometry, including reversed closure; radial-invariant positioning DOFs retain their prior commands. Observations are normalized to the live gripper-base frame so carrier translation/rotation does not masquerade as finger closure. The probe returns leaders toward their measured initial pose, then restores only their prior controller commands through sparse writes, without teleporting followers, changing gains, or overwriting the carrier. This is bounded command restoration, not an exact dynamic-state rollback. Angular readbacks are radians; unresolved Core prismatic tensor scale remains `unknown_native`.

Missing prior commands, partial/stale/non-finite live geometry, insignificant
motion, equally plausible pads or incomplete restoration stop the trial with
an explicit mapping/setup diagnostic. Geometry apertures are proxies, not
measured collision contacts. Physical-metre aperture metrics include the stage
scale; runtime joint coordinates retain their separately recorded units.

6. **Standoff, support restoration, spawn and open.** With test-owned support collision still suspended, the existing gantry move positions the gripper at its size-based standoff. The test restores those prior collision opinions, enables the required pickup floor, then spawns a synthetic sphere below the resolved grasp center and configured placement offsets. By default its diameter is `0.7 * gripper_maxOpening` (radius half that diameter), its mass is 50 percent of the resolved maximum payload, and static/dynamic friction are 2.0. The effective size fraction and any direct-mass override are recorded. The sphere settles briefly. Actual open commands must reach their selected targets within `5 * open_position_tolerance` (default 0.025), unchanged from the existing test. Support restoration is also attempted on errors and cancellation; an incomplete restoration is a setup error, never an asset verdict.

7. **Descent and contact proxy.** The gantry descends while holding the gripper open, using at least the configured minimum chunk count (default 12) and increasing it as needed to respect `descent_contact_max_step_m` (default 5 mm). When the sphere shifts by more than 3 mm, the descent stops and the gripper backs off 10 percent of the maximum opening before closing. Object motion is a proxy, not a measured contact point or force.

8. **Close.** The test drives the resolved grasp DOFs toward their close targets using the asset's authored drive parameters. Engagement followed by a stall short of the closed target is the test's grasp proxy; it does not prove the pads contact the sphere. DOFs held at the same open and closed target are excluded from this inference.

9. **Grip gate.** The test requires the stall/engagement proxy and sphere retention within one object diameter of its spawn XY position. If either condition fails, the test reports a failed configured trial without proceeding to lift; placement, grasp depth, incomplete reopening, and backend setup must be checked before blaming the asset.

10. **Lift.** The gantry raises the gripper 20 cm over 1 s. Pass criteria: the sphere's vertical deviation from the expected position is less than 5 cm and horizontal drift is less than 5 cm. Vertical motion during close is reported as a pre-load diagnostic because a hand may seat or lift the sphere while establishing contact; the subsequent carrier-follow, shake, and release phases determine whether the grasp is valid. The gantry must lift at least 10 cm; a shorter lift is an internal harness error, not an asset fault.

11. **Shake.** The gantry oscillates sinusoidally along Z at 2 Hz, 2 cm amplitude, for 2 s. The sphere must stay above 2 cm and slip less than 3 cm relative to the gripper throughout.

12. **Release.** The test drives every resolved jaw leader back to its open position. The sphere must fall at least 5 cm after the open command.

## Failure Cases

| Symptom | Checks before attributing a cause |
|---|---|
| Test skipped: no gripper site found | The existing unmarked skip is Could not assess, not Not applicable. Inspect the provider's discovery diagnostic and selected contract without inferring asset FAIL or PASS. |
| Test skipped: no compatible position-driven finger topology | The existing unmarked skip is Could not assess, not Not applicable; inspect the emitted topology diagnostic. No grasp response was measured. |
| Runtime/setup error: unresolved or unsafe coupled topology | Raw active selected coupling coverage, local references, finite coefficients, unique leader ownership and distinct physical tips are required before mapping; unresolved coupling is an execution limitation, not an applicability skip or asset FAIL |
| Runtime/setup error: ambiguous or invalid mapping/readback | Duplicate physics-link names, a stale tensor view, non-finite live transforms or ambiguous pad motion prevent safe endpoint mapping; this is not proof of an asset defect |
| Runtime/setup error: required ground or backend unavailable | A usable collision floor is required; the published Core test requires PhysX and has no Newton binding |
| Runtime/setup error: required joint/object state or carrier lift unavailable | Open/close readbacks must be finite and correctly indexed; required test-object poses must be available and finite; the test-owned gantry must produce the existing minimum lift before asset retention can be evaluated |
| Precheck failure: invalid maximum opening | No usable positive opening was resolved from the preferred `gripper_maxOpening` or accepted legacy reader alias; inspect the composed site metadata and selected contract |
| Precheck failure: no resolvable rigid-body attachment | The provider could not resolve its carrier attachment from the site's current ancestor/mapping path; this does not itself establish a GR.001 marker violation or missing body schema |
| Open command did not reach the open position | Check resolved leader mappings, authored limits, runtime units, initial pose, command timing, and drive response; this observation does not isolate the cause |
| Grasp center at or below the sphere | Inspect generated object placement, carrier frame, grasp-center mapping and available descent first; the source gripper need not point down or have a universal floor elevation |
| Close/retention proxy gate failed | Check reopening, target mapping, grasp depth, placement and object motion; a false proxy is not proof that the fingers reached a closed limit or that contact never occurred |
| Lift failed: sphere did not follow the carrier | Check the resolved authored/heuristic payload, carrier lift, placement, engagement and proxy readbacks before investigating materials or drive parameters. A gantry lift below 10 cm is a harness error. |
| Shake failed: sphere dropped or slipped | Check setup, payload resolution, carrier trajectory, engagement and motion readbacks; insufficient holding force or friction is only a possible cause |
| Release failed: sphere did not fall | Check open targets, leader mappings, readbacks and the release window before attributing the result to limits or drives |
| Physics view returns None after the open command | Internal harness error, not an asset fault. The Isaac physics view was not initialized before the open command returned. File a bug against the core tier's FET028 runtime tests. |
| Gantry lifted less than 10 cm | Internal harness error, not an asset fault. The test-owned Z-axis carrier failed to produce a meaningful lift. Refer to the gantry lift note in How It Works. |

## How to Fix

If the site is not found or maximum opening is invalid, inspect the selected
contract, composed gripper-site schema, marker identity and measured opening.
The canonical field is `gripper_maxOpening`, in metres; `custom:maxOpening` is
only a legacy reader fallback, not permission to add conflicting metadata.
Use the real mechanism's opening rather than a generic industrial range, and
rerun the actual static gate after any justified authoring correction. Missing
runtime discovery alone does not establish which property or topology is wrong.

If the carrier attachment cannot be resolved, preserve the marker's authored local frame and source topology. Inspect the composed layout/variant, physical base body, loader/importer mapping and runtime support. GR.001 does not itself require a rigid-body ancestor. A provider mapping limitation can need a test fix rather than reparenting the marker or adding body/mass APIs to decorators; establish the cause before changing the asset.

If the open command does not reach its target, inspect the recorded per-leader achieved coordinates and geometry apertures, finite joint limits, runtime units, initial pose and motion window. Mapping ambiguity or incomplete readback is a test/setup limitation, not proof of bad asset authoring. Do not swap limits, rewrite GR.003 metadata or increase drive force merely to satisfy the harness.

If the close/retention gate fails, first verify complete reopening, object placement, grasp depth, leader mapping and the configured engagement tolerance. The stall proxy may fail despite partial contact, or pass for a different obstruction. Use the videos and histories to distinguish those cases before changing the asset.

If lift or shake fails, check the actual carrier motion, payload source, grasp placement and proxy readbacks first. A heuristic payload may overestimate capability. Only after setup is established should drive parameters and collision materials be compared with the mechanism's specifications; no universal stiffness, effort, or friction coefficient follows from this failure.

If the release fails, check that the open drive parameters and joint limits allow every commanded leader to return to its open position. A locked, reversed, or uncoordinated leader will prevent the gripper from re-opening.

## Expected Result

:::{note}
An expected-result still and video for this test are not captured yet. The expected result is described below.
:::

In the default trial, an orange sphere rests on the floor below the gripper. The gripper opens, the gantry descends, the gripper closes on the sphere, the gantry lifts 20 cm, the gantry shakes for approximately 2 s, and the gripper opens again. A passing configured result meets the observed carrier-follow, shake and post-opening fall criteria. Overrides can change placement and controls, and a failure clip can end before all stages complete; video alone does not measure contact or holding force.

## Notes and Caveats

See [Hand trial controls](hand-trial-controls.md) for opt-in signed joint
targets, held positioning joints, closing delays, approach/placement controls
and optional native contact summaries. The report's **Recorded grasp trial controls**
uses provider-recorded effective dimensions, mass and targets; this description
states defaults. Configured trial passes do not qualify default controls or
unrun shapes. Fixture handling and diagnostics do not alter source assets,
published feature bindings or the existing grasp verdict thresholds.

The carrier resolves the articulation API prim, connected physical root body,
and bounded asset transform separately. A fixed world joint carrying
`PhysicsArticulationRootAPI` is supported even when its rigid-body links are
siblings. Approach prediction uses that physical body's pivot, so mapping,
standoff travel, and object spawn stay aligned with a site on an offset link.
Temporary carrier root ownership, world-pin suspension, and approach
rotation belong only to the disposable test stage; detach or failed attachment
restores the original controller path and authored opinions after a successful
physics stop. If stopping fails, topology restoration, controller rebinding and
timeline restart are blocked; the runner must retry teardown or retire the stage.
The original attachment error/cancellation is preserved with rollback notes;
detach reports an error. Optional carrier state/effort traces can be unavailable
or omitted when trace-only getters, formatting or logging fail, without changing
commands or simulation steps. Required live carrier motion checks remain
independent, and required-operation failures and cancellation are not suppressed.
Ambiguous topology
or incomplete restoration is a setup error, not evidence of an asset defect.
Do not remove an asset's valid world pin or relocate its API to work around
such an error. Test 1.4.6 includes this fixture handling and current prerequisite diagnostics without changing the
published feature requirements or the grasp pass thresholds.
Version 1.4.7 also protects the first required error/cancellation from failures
in secondary note lookup, formatting or delivery, including SDK exceptions
without `add_note`; it does not change the grasp criteria.

Bounded failed-probe metrics `detect_probe_evidence_<DOF>` retain prior commands,
original/achieved positions, inset endpoint commands, live world/base-relative
pad bounds, aperture changes/tolerances and omission counts. Optional
`gripper_probe_joint_<zero-padded-DOF>` histories distinguish probe and restore;
later trials append `_trial_002`, `_trial_003`, etc., with shape/trial metadata.
Interrupted mapping is partial evidence, not a completed grasp. The grasp video
starts after silent mapping/standoff; an exported reset/cleanup scene is not
proof of probe-time contact. Review the numeric evidence first when mapping fails.

The default sphere payload is 50 percent of the resolved maximum payload; the cube uses 85 percent. These are configured synthetic trials, not measurements of a mechanical rating or physical contact patches.

Closing-fraction diagnostics use the signed open-to-close range, so a decreasing target range remains meaningful and overshoot is not clamped. Held DOFs, missing readbacks and non-finite values are null, not zero; only measured fractions enter the diagnostic mean. These fractions do not affect pass/fail.

Successful still/video captures are associated with the latest retained motion observation. Graph ticks are capture associations, not exact encoded-frame indices or timestamps, and can be coalesced when multiple captures share an observation. Gripper histories use the Kit timeline clock where available, not a measured solver-step clock. Missing contact-force channels remain null and do not prove zero force. Hooks remain optional for older runners and do not add simulation steps or captures.

If no usable declared payload is resolved, compare the heuristic with the
mechanism's specification before interpreting the trial. A justified metadata
repair should use canonical `gripper_maxPayload` in kilograms; the reader accepts
`custom:maxPayload` only for legacy compatibility. Do not fabricate a rating or
add conflicting aliases merely to avoid the warning or obtain a pass. The
report distinguishes authored, heuristic and explicit trial-mass sources.

Version 1.4.9 supports independent leader-owned finger chains, including mixed
free/mimic fingers and finite signed/asymmetric gearing. Raw active selected
couplings are validated before accepting either a jaw or hand mapping. Each
independent leader is probed against its own branch's distal tip; follower and
passive links contribute geometry but never become commanded finger controls.
Duplicate ownership, cycles, foreign/unresolved references, missing or ambiguous
tips and ambiguous closure stop execution. Held positioning controls remain
readable and every required branch must retain a closing leader.

Parallel-jaw, centric, and independent-finger grippers retain the existing pass
thresholds. Missing-site and unsupported position-driven-topology skips remain
unmarked/Could not assess; they do not establish Not applicable. Unsafe or
unresolved active coupling is a
mapping/setup error. Topology discovery alone does not qualify a grasp; cube and
sphere require separate official native runs with this procedure version.

The internal legacy Newton two-leader classifier remains guarded by explicit actuator ownership, symmetric follower groups, and distinct joint-graph branches. Live mapping determines each leader polarity separately. These guards do not provide published Newton close/lift coverage; the Isaac binding remains on PhysX.

The test does not override the gripper's finger-pad physics materials. Authored materials participate in the configured backend simulation, but the failure proxies do not establish low friction as the cause or automatically justify changing the asset.
