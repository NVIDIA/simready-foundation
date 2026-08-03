# state_accuracy  (FET022 Driven Joints)

| Property     | Value                                                                         |
|--------------|-------------------------------------------------------------------------------|
| Test name    | state_accuracy                                                                |
| Feature(s)   | FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC |
| Engine       | Kit / Isaac Sim (>=2024.2.0)                                                  |
| Test version | 1.0.0                                                                         |

## Summary

Commands each driven joint through a five-waypoint sequence and verifies that the
reported joint position matches the commanded position within tolerance at each
waypoint.

## What Pass Guarantees

A passing result confirms that the joint drive can hold a commanded position
accurately and that the joint-state reporting is consistent with the physics
simulation. Reviewers, PMs, and OEMs can trust that the position feedback
published by the articulation is not offset, inverted, or noisy beyond the
declared tolerance.

## What It Checks

The test commands each non-passive, non-mimic-follower joint through five
waypoints: the home position, a positive step, back to home, a negative step,
and back to home again. The step size is the smaller of `max_step_deg` (default
15 degrees) and `step_range_fraction` (default 10 percent) of the full joint
range. At each waypoint, after the joint has been given `test_duration_seconds`
(default 3.0 s) to settle, the actual position is measured and compared against
the commanded position. A joint fails if the position error at any waypoint
exceeds `position_tolerance_deg` (default 5 degrees). The test skips when no
testable joints are found.

## How It Works

Joints are tested in isolation. For each joint, the drive is commanded to each
of the five waypoints in sequence. The test waits for the settling duration at
each waypoint and then samples the current joint position from the articulation
state. The absolute position error is computed and compared to the tolerance.
If any waypoint error exceeds the tolerance, the joint is counted as failed, and
the test fails.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Position error exceeds 5 degrees at a waypoint | Drive stiffness too low; joint drifts under gravity before settling time expires |
| Error only on positive or negative step | Joint limits asymmetric relative to home; drive exhibits asymmetric backlash or compliance |
| Position error grows with each waypoint | Accumulated drift; drive does not hold between commands |

## How to Fix

If position errors are consistently large, increase `driveStiffness` on the
joint's `UsdPhysicsDriveAPI` schema to strengthen the restoring force toward the
commanded position. Verify `driveMaxForce` is high enough to deliver the required
torque, particularly for heavy links far from the base.

If errors are asymmetric, check whether the joint has an authoring offset or
whether the rest position is not centered in the joint range. Correct the joint
rest position so that positive and negative steps are symmetric about the
commanded home position.

If drift accumulates over multiple waypoints, increase `driveDamping` to prevent
residual velocity from carrying the joint past each waypoint.

## Expected Result

![state_accuracy expected result](../_images/state-accuracy.png)

[Result video](../../../../_static/videos/state-accuracy.mp4)

Each joint visits five waypoints in sequence: a small step outward, a return to
the center, a small step in the opposite direction, and a final return to center.
The joint settles visibly at each waypoint before moving on. Drift past the
commanded position, oscillation, or failure to reach the target indicates
inadequate drive stiffness or damping.

## Notes and Caveats

The test skips when no testable joints are found (all joints are passive, mimic
followers, or have no finite limits). A skip result is not a failure.

The waypoint sequence is designed to exercise both the positive and negative
direction of the drive and to confirm that the joint returns reproducibly to the
home position. If the home position is not at zero, the test uses the actual
commanded home value.
