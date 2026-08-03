# mimic_joint  (FET022 Driven Joints)

| Property     | Value                                                                         |
|--------------|-------------------------------------------------------------------------------|
| Test name    | mimic_joint                                                                   |
| Feature(s)   | FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC |
| Engine       | Kit / Isaac Sim (>=2024.2.0)                                                  |
| Test version | 1.0.0                                                                         |

## Summary

Sweeps each reference joint and verifies that every mimic-follower joint moves by
the correct magnitude according to its declared gear ratio.

## What Pass Guarantees

A passing result confirms that every `PhysxMimicJointAPI` follower joint in the
articulation tracks its reference joint by the authored absolute gear ratio within
the declared tolerance. Reviewers, PMs, and OEMs can trust that parallel linkages
and mimic drives will couple as authored in a physics simulation.

## What It Checks

The test discovers all joints that carry a `PhysxMimicJointAPI` schema. For each
such follower joint, it identifies the reference joint and sweeps the reference
joint across its range. At each measurement point, the test computes the ratio of
the follower's motion magnitude to the reference joint's motion magnitude and
compares it against the absolute value of the authored gear ratio. A follower
fails if the magnitude ratio differs from `|gear|` by more than
`gear_ratio_tolerance` (default 0.10, that is, 10 percent).

Direction mismatch (whether the follower moves in the same or opposite direction
as the reference) and rest-pose offset differences are recorded as diagnostic
warnings, not as failures. The test skips cleanly when no joints carry
`PhysxMimicJointAPI`.

## How It Works

The reference joint is driven with the same sweep mechanism used by the
full-range-sweep test. At each sampled position, the follower joint position is
read from the articulation state. The incremental displacement of both joints
from the start of the sweep is used to compute the ratio, avoiding sensitivity to
rest-pose offset. The ratio is checked against `|gear_ratio|` with the tolerance
margin applied.

The test operates on the articulation as authored, without modifying any joint
schemas.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Follower magnitude ratio differs from authored gear ratio by more than 10 percent | Gear ratio value incorrect in `PhysxMimicJointAPI`; follower joint limits prevent full coupling; solver deformation under load |
| Test skipped | No `PhysxMimicJointAPI` schema found on any joint in the articulation |
| Direction mismatch warning (not failure) | Gear ratio sign does not match the intended follower direction; noted for the author but does not fail the test |

## How to Fix

If the magnitude ratio is wrong, check the `gearing` attribute on the `PhysxMimicJointAPI:<axis>` instance applied to the follower joint (for example, `physxMimicJoint:rotX:gearing`). The absolute value of this attribute determines the coupling magnitude. If the ratio is correct but the direction is inverted, the sign of `gearing` needs to be reversed; note that direction mismatch is a warning, not a failure.

If the follower cannot reach the full excursion implied by the gear ratio, check
that the follower joint limits are wide enough to accommodate the range commanded
by the reference joint multiplied by the gear ratio.

## Expected Result

:::{note}
An expected-result still and video for this test are not captured yet. The expected result is described below.
:::

The reference joint sweeps through its range while the follower joint moves in
proportion. On a passing run, the follower joint displacement is a consistent
multiple of the reference joint displacement throughout the sweep. Asymmetric or
lagging follower motion indicates a coupling problem.

## Notes and Caveats

The test checks magnitude only. Direction and offset are reported as warnings
because some parallel-linkage designs intentionally use an opposing gear ratio or
a non-zero rest-pose offset. Treating direction as a failure would incorrectly
reject valid assets.

The test skips entirely when no `PhysxMimicJointAPI` is found. This is expected
behavior for articulations that do not use mimic joints; a skip result does not
indicate a defect.
