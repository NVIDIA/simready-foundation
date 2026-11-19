# FET022 Driven Joints

Sampled runtime evidence for driven-joint response under configured test policies.

## Overview

Core owns the PhysX procedures selected by the PhysX and Isaac driven-joint
contracts. These tests exercise selected ranges, commands, velocity responses,
external-force responses, mimic relationships and sampled IK targets. Coverage
and pass criteria differ by test and configuration; this is not exhaustive
joint-authoring or controllability certification.

Newton procedures are separately owned by `simready-foundation-tier-newton`.
See [Newton Runtime Tests](../../../../../../simready_foundation_tier_newton/simready/foundation/tier_newton/runtime_tests/docs/runtime-tests.md) for that tier's
procedures, installation and backend limitations. Core does not execute Newton
procedures and a separate Newton gripper close/lift contract is absent.

## What a Passing Family Means

A passing executed test meets only its configured observed criteria. Inspect
skips, warnings, per-joint/per-target results and the saved configuration: drive
gain exceedances are nonfatal by default; coordination remembers independent
goal-band entries; IK can pass a configured fraction of sampled targets; and
the effort probe neither enforces authored effort ceilings nor measures a
minimum break force. Static validation and runtime results remain distinct.

Positive N/A requires complete proof over the actual inspected sources for the
particular procedure, not only a complete owned subtree or cached exclusions.
VEL, MJC, IK and JIK recheck passive/follower/loop exclusions from the current
USD composition before publishing their count/standalone N/A markers. The fresh
union must agree with cached exclusions; disagreement or an unavailable query
withholds the marker without changing the original skip, commands or load state.
The actual actuator/mobility reads used by passive and loop discovery must
succeed; an exception-to-empty fallback cannot prove absence even if both
exclusion sets agree. Strict source qualification applies only to this marker
proof, not to historical discovery eligibility.
Mimic absence also checks raw active authored coupling independently of an empty
mapped selection; joint mapping omissions cannot erase that authoring.
Unqualified legacy skips remain unmarked and reported as Could not
assess, supplying neither measured response PASS nor asset FAIL.

Unavailable, non-finite or malformed state required by control/verdict is a
setup/runtime error, not evidence of conformance or an evaluated asset-response
failure. Optional motion telemetry may be partial without changing valid test
criteria. A family pass does not prove arbitrary trajectories, complete
workspace reachability, safety, or realistic performance under other loads.

Runtime explosion canaries measure complete finite live geometry under the
verified loaded asset, independently of an articulation root placed on a leaf
fixed joint. Missing body poses or malformed/empty required geometry are
setup/runtime errors, not fabricated zero bounds. Legitimate zero-thickness
geometry is not treated as missing state; an unqualified legacy volume
fallback retains its degenerate-volume policy. These bounds are
visual geometry proxies, not cooked collider or contact measurements. Explicit
`authored=True` bounds are used only by the static reach/setup heuristic.
Joint/actuator discovery uses the same verified asset subtree, preserving the
actual articulation/controller identity and root policy without scanning
test-owned room or probe content. The current `evaluate` extra requires both
Evaluate[kit] `>=2026.9.0rc2,<2026.11` and engine-kit `>=2026.9.0rc3,<2026.11` for this API and
required cleanup. These bounds admit compatible prerelease and stable updates
within this API generation; install the tier extra to apply its declared requirements.
The tier verifies composed room-floor suppression before physics independently
of newer Kit bug fixes; unsuccessful setup cannot become a joint-motion verdict.

Selected physical joint paths are resolved before native-name mapping for
passive ownership, velocity hints, raw mimic discovery and diagnostic metadata.
Disconnected foreign articulations, including reversed-endpoint body/container
roots with repeated joint names, cannot supply selected gains or limits.
Ambiguous ownership is an execution/setup limitation (or unknown optional
metadata), never a traversal-order choice. This boundary imposes no gripper
topology prerequisite on ordinary passive/velocity queries. Zero-gain drive
schemas alone do not grant independent command ownership.

Continuous-joint angular classification for JIK and coordination uses that same
selected identity, including exact paths and supported native axis aliases.
It does not widen bounds or change the existing local excursion, target sampler,
seeds, or solver/search policy. Missing/ambiguous joint names do not authorize an
angular excursion.

Required authored velocity-cap initialization must be acknowledged. Where a
readback accessor exists, complete correctly shaped finite requested-coordinate
evidence is required; rejection or unavailable verification is setup failure,
not initialized success. Getter-less supported adapters provide acknowledgement
only, not verified native enforcement. Unauthored-coordinate policy is unchanged.
Cleanup failure preserves the first cause and retires an uncertain session.

Host regressions in `tests/runtime_tests/unit/test_angular_identity_consumer.py`
execute the original JIK applicability block and FK generator over real USD
identity cases, proving equal target/probe arrays to the leaf-name control.
`test_selected_joint_metadata.py` covers authored-cap initialization/readback
and cleanup; `test_closed_jaw_loop_identity.py` covers forwarded physical loop
ownership through actual fingertip discovery and endpoint mapping. Their host
motion/native adapters do not establish installed-SDK or native asset acceptance.

Absent/unapplied drives and valid effective zero gains remain passive.
A failed gain query or nonnumeric, nonfinite or negative effective gain is a
required setup/readback error with its original cause. Passive and loop-control
eligibility cannot interpret unavailable gains as zero.

## Tests

Each applicable articulation safety guard uses a frozen topology/reach
reference when qualified, keeping the configured volume-margin factor while
avoiding a narrow starting pose's volume as the sole motion allowance.
Unavailable topology is labelled as an unqualified initial-volume proxy.
Guard trips interrupt observation as incomplete runtime execution, not
completed range/speed/response failures; inspect the phase-owned reference
and abort provenance. These geometry proxies do not measure native collisions
or establish an asset defect. Commands, ticks and response criteria are unchanged.

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [full_range_sweep](fet022/full-range-sweep.md)
  - Commands inset/capped targets with bounded velocity-aware ramps, then checks the unchanged hold and return criteria.
  - Core PhysX / Isaac contracts
* - [velocity_limit](fet022/velocity-limit.md)
  - Compares sampled speed with the resolved runtime/authored/actuator ceiling; a pass does not prove physical hard-cap enforcement.
  - Core PhysX / Isaac contracts
* - [effort_limit](fet022/effort-limit.md)
  - Applies the configured external force and checks available runtime position ranges; spatial guard trips interrupt execution, not response verdicts. No effort-ceiling or minimum-force measurement.
  - Core PhysX / Isaac contracts
* - [drive_gain_validation](fet022/drive-gain-validation.md)
  - Reports sampled step-response metrics; exceedances are warnings unless configured fatal.
  - Core PhysX / Isaac contracts
* - [state_accuracy](fet022/state-accuracy.md)
  - Checks sampled joint positions against configured legal waypoint goals, with actual issued commands recorded separately.
  - Core PhysX / Isaac contracts
* - [mimic_joint](fet022/mimic-joint.md)
  - Checks the sampled follower/reference swept-magnitude ratio; direction and offset are diagnostics, not verdict criteria.
  - Core PhysX / Isaac contracts
* - [multi_joint_coordination](fet022/multi-joint-coordination.md)
  - Checks that each eligible joint enters its goal band during each iteration; entries need not be simultaneous.
  - Core PhysX / Isaac contracts
* - [ik_target_reach](fet022/ik-target-reach.md)
  - Checks a configured sampled position-success fraction for Lula-solved target playback; no live-orientation guarantee.
  - Core PhysX / Isaac contracts
* - [jacobian_ik](fet022/jacobian-ik.md)
  - Checks the configured sampled success fraction using final live position and solver orientation, without a Lula descriptor.
  - Core PhysX / Isaac contracts
:::

## Relationship to the Feature

This family validates the runtime behavior described by the
[PhysX](../../features/FET022_DrivenJoints.PhysX.md) and
[Isaac](../../features/FET022_DrivenJoints.Isaac.md) FET022 features. Newton's
matching runtime procedures and guidance live in the Newton tier. The Standard
authoring feature is not directly registered to this runtime suite. MuJoCo
FET022 is not registered by the current implementations.

```{toctree}
:maxdepth: 1
:hidden:

drive_gain_validation <fet022/drive-gain-validation>
effort_limit <fet022/effort-limit>
full_range_sweep <fet022/full-range-sweep>
ik_target_reach <fet022/ik-target-reach>
jacobian_ik <fet022/jacobian-ik>
mimic_joint <fet022/mimic-joint>
multi_joint_coordination <fet022/multi-joint-coordination>
state_accuracy <fet022/state-accuracy>
velocity_limit <fet022/velocity-limit>
```
