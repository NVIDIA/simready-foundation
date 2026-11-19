# FET028 Gripper

Tests in this family verify that a gripper asset can close on a test object, lift it, shake it, and release it cleanly.

## Overview

Runtime site discovery requires active `BasisCurves` children for both the
forward axis and grip line. It prefers `gripper_forward_axis` and
`gripper_grip_line`, with active `forward_axis` and `grip_line` children accepted
as legacy reader aliases. An inactive preferred child is skipped when resolving
an active alias. A site without an active required curve is excluded from the
trial; its inactive geometry cannot establish a grasp result. Inactive sites
and ancestor subtrees are also excluded by USD traversal.

Independent hand discovery maps each selected active leader's USD identity to
its unique native index, including full-path and axis-suffixed names. Original
native names remain the identities for trial remapping and sparse commands.
Missing or ambiguous active leaders and failed required gain queries stop
setup; they cannot produce a supported partial hand. Valid zero-gain passive
links and coupled followers retain geometry without independent commands.
The selected non-closure tree is oriented from a qualified physical root or the
existing complete cooked parent-tree contract, never body0/body1 ordering or
the first native link. Reversed/mixed endpoints retain the same leader chains
and distal follower/passive geometry. An unavailable/ambiguous root, incomplete
cooked tree or foreign parent edge remains a setup limitation; this is not
universal support for every legal USD layout or every SDK metadata shape.

This family exercises the gripper itself rather than an object being grasped. The test spawns a standard synthetic test object on the ground plane, opens the gripper, descends a Z-axis gantry onto the object, closes the gripper on the object, lifts it 20 cm using the gantry, shakes the gantry to perturb the grip, and then opens the gripper to verify the object is released. The gantry is a test-owned prismatic carrier attached to the gripper base by a fixed joint, so a fixed-base gripper is still fully exercised through all stages.

Two test objects serve as complementary configured trials. The sphere uses 50 percent and the cube 85 percent of the resolved maximum payload by default. That payload comes from positive `gripper_maxPayload` metadata (kilograms; legacy `custom:maxPayload` is a reader fallback), otherwise from a jaw-opening heuristic; the heuristic is not a rated capability. Opening metadata prefers `gripper_maxOpening` (metres; legacy `custom:maxOpening` accepted). The synthetic shapes and their contact geometry do not measure the gripper's contact forces or establish suitability for a real-world payload-rated workflow. Effective size, mass and controls can be overridden by supported configuration and are recorded in `gripper_trial_controls`.

The published Isaac contracts run on PhysX and cover resolvable parallel-jaw and centric mimic grippers as well as independent-finger hands. A conventional mimic jaw exposes one shared driven leader. The guarded internal Newton-native jaw helper requires explicit actuator targets and distinct joint-graph branches; it is not published Newton close/lift coverage. Independent fingers can contain free joints and locally coupled follower chains with finite signed/asymmetric gearing. Joint traversal retains follower, passive and fixed geometry while commands remain leader-only. Invalid metadata, ambiguous ownership or geometry, and incomplete live readback are execution limitations.

Missing-site and unsupported-topology branches retain unmarked legacy skips.
The report shows Could not assess for these checks, not Not applicable; their
diagnostic messages establish neither measured grasp PASS nor asset FAIL.
They do not add N/A markers or expand supported test topology.

The test does not require robot-specific prim, joint, actuator, or collider
names. It discovers the gripper site from its schemas and relationships,
resolves fingertip links through the joint graph, and observes geometry owned
by those rigid bodies, excluding nested rigid bodies and non-colliding guide
annotations. These bounds are placement/aperture proxies, not measured contact
surfaces. Its temporary lift
carrier uses a unique test-owned joint identity so an asset may use common DOF
names such as `joint_z` without being filtered or commanded accidentally.

## What a Passing Family Means

Implementation 1.4.6 includes the corrected lower-is-open handling with bounded
sparse probes and live owned-geometry observations. It infers each leader's
polarity independently, and uses collective planar spread for centric fingers.
GR.003 remains the tube axis/contact-pad width, not a jaw-endpoint declaration.
Independent fingers use stepped observations rather than state teleportation;
positioning DOFs retain prior commands. Leaders return toward their measured
initial pose before prior controller commands are restored. This is not an exact
dynamic-state rollback, and no gains, source assets or verdict thresholds change.
Ambiguous observations or incomplete restoration stop the trial; they are not
proof of an asset defect. Compare runs using their recorded test version.

The free probe and existing standoff move temporarily suspend collision only on
explicitly tracked test-owned supports. Prior collision opinions are restored
before the pickup floor is enabled and the object is spawned, and restoration is
attempted on errors/cancellation. Asset colliders, walls, controls and probe
timing are unchanged. A failed restoration is a setup error. Bounded
`detect_probe_evidence_<DOF>` metrics retain failed commands/achieved positions,
live world/base-relative geometry and aperture tolerances before mapping guards;
optional `gripper_probe_joint_<zero-padded-DOF>` histories separate probe/restore.
Later shape trials append `_trial_002`, `_trial_003`, etc. to both identities,
with explicit shape/trial metadata. These measurements are geometry proxies,
not contact telemetry. The grasp video begins after silent mapping/standoff;
the final exported scene may represent reset/cleanup, not the failed probe.

Prior commands must be available as a complete controller-target buffer. Isaac
builds without a direct target getter use the public applied-action snapshot;
actual joint positions are never substituted for missing commands. Mapping,
restoration, required-floor setup, and misrouted-backend errors stop execution
as runtime/setup errors rather than asset FAIL. Core close/lift has no published
Newton binding.
Procedure 1.4.9 validates every raw active selected coupling before accepting
either the existing jaw classifier or an independent-hand mapping, including
couplings omitted by the response detector. References must remain within the
selected articulation, with finite coefficients, acyclic unique ownership and
unambiguous native leader identities. Independent hands require at least two
physical finger branches with distinct resolved distal tips. Every follower must
belong to its ultimate leader's physical branch; visible followers remain absent
from finger chains and sparse control specs. Each leader's live polarity is
measured at its own branch tip. Unknown/unsafe mappings are setup/runtime errors,
not applicability skips or asset failures. Topology success is not a grasp PASS;
official cube and sphere runs remain separate.
Required open/close position readbacks must also be finite and unambiguous;
missing state cannot satisfy reachability or blockage proxies. A non-finite
carrier lift, or a test-owned gantry lift below the existing minimum, likewise
stops as a setup error before evaluating asset retention. Missing/non-finite
required test-object poses also stop as setup errors; optional pad-separation
diagnostics remain null when geometry is unavailable. Finite reachability,
retention thresholds and configured control trajectories are unchanged.

Carrier topology restoration requires a successful physics stop. If the backend
cannot stop, the harness leaves the disposable stage's topology and controller
bindings untouched, does not restart simulation, and reports a setup/teardown
error for the runner to retry or retire. Failed attachment preserves its original
failure or cancellation and annotates any rollback failure. Optional carrier
state/effort traces may be unavailable (not zero) or omitted; ordinary
trace-only telemetry/formatting/logging failures do not change the existing
commands, simulation steps, or verdict criteria. The required live carrier
motion checks remain independent of these traces. Cancellation and failures of
required control/state operations still propagate.

A pass means the configured simulation satisfied the close/retention proxies, carrier-follow, shake, and release criteria for that synthetic object and resolved payload. It does not establish measured physical contact, contact force, pad friction, a rated payload, or real-world pick-and-place suitability. A failed trial is likewise not an automatic asset-defect diagnosis: check placement, grasp depth, reopening, carrier motion, payload resolution, and backend setup before attributing a cause. Each test is registered independently; the framework marks the feature FAIL if either test fails, regardless of the other test's outcome.

The published `FET028_Gripper.Isaac.0-1-0` bindings run on PhysX. Internal legacy Newton helpers do not provide a published Newton gripper contract or Newton gripper coverage. The motion histories are optional sampled diagnostics; unavailable contact-force readbacks remain null. Successful captures are associated with the latest retained observation, not with an exact encoded-video timestamp or frame index. Closing fractions preserve the signed open-to-close range, report held/unavailable DOFs as null, and are not verdict inputs.

## Configured hand trials and optional contacts

The default cube/sphere sizes, payload fractions and grasp verdict thresholds
remain unchanged. [Hand trial controls](fet028/hand-trial-controls.md) allow
explicit, validated positioning/closure targets, delayed finger motion and
approach/placement experiments without changing the source asset. Empty
controls preserve the default procedure. Results record effective object
dimensions, mass, targets and delays under `gripper_trial_controls`; the report
shows them below the video. A configured pass covers that trial only, not an
unrun shape or complete static/runtime qualification.

Fixed-joint-root fingertip discovery uses the verified loaded asset and selected
connected articulation, not the API joint's empty subtree. Carrier attachment
frames preserve the intended rotated pose; old tensor views are not queried
while physics is being rebuilt. Invalid required selected state stops before
capture. Optional trace/contact failures remain separate from required control,
restoration and verdict measurements.

`diagnostic_native_contact_pairs` is disabled by default. When enabled on a
compatible PhysX Engine Kit, it collects bounded object–hand contact summaries
with phase and nullable timeline time. Raw native units remain explicitly
unqualified; peak per-point impulse is not force, actuator effort or total pair
impulse. Missing diagnostics are unknown, not zero. Collection adds no commands,
captures or physics steps, changes no verdict thresholds, and does not disable
self-collision or tune source drives. See the controls page for cleanup and
interpretation limits.

## Tests

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [gripper_close_lift_sphere](fet028/gripper-close-lift-sphere.md)
  - By default, closes on a sphere at 50 percent of its resolved maximum payload and evaluates the configured close, lift, shake and release proxies.
  - `FET028_Gripper.Isaac.0-1-0` (PhysX)
* - [gripper_close_lift_cube](fet028/gripper-close-lift-cube.md)
  - By default, closes on a cube at 85 percent of its resolved maximum payload and evaluates the configured close, lift, shake and release proxies.
  - `FET028_Gripper.Isaac.0-1-0` (PhysX)
:::

## Relationship to the Feature

This family validates the runtime behavior described by
[FET028 Gripper](../../features/FET028_Gripper.Isaac.md).

```{toctree}
:maxdepth: 1
:hidden:

gripper_close_lift_sphere <fet028/gripper-close-lift-sphere>
gripper_close_lift_cube <fet028/gripper-close-lift-cube>
Configured hand trials <fet028/hand-trial-controls>
```
