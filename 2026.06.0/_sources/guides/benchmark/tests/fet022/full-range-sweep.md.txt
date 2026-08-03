# full_range_sweep  (FET022 Driven Joints)

| Property     | Value                                                                         |
|--------------|-------------------------------------------------------------------------------|
| Test name    | full_range_sweep                                                              |
| Feature(s)   | FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC |
| Engine       | Kit / Isaac Sim (>=2024.2.0)                                                  |
| Test version | 1.0.0                                                                         |

## Summary

Commands each non-passive, non-mimic-follower joint through its full authored
range and confirms the measured position tracks the commanded position at every
waypoint.

## What Pass Guarantees

A passing result confirms that every non-passive, non-mimic-follower joint with
authored limits returns to its zero position within the authored tolerance, and
that the articulation stays stable throughout the sweep. Whether each joint
actually reaches its declared limit endpoints is recorded as a diagnostic
warning rather than a gated criterion, so reviewers, PMs, and OEMs should consult
the per-joint warnings to judge limit reachability.

## What It Checks

The test drives each non-passive, non-mimic-follower joint individually from
its settled starting position through its full authored range. The sweep commands the joint to its maximum
limit, then to its minimum limit, and finally back to zero. At each waypoint, the
test measures the actual joint position and compares it to the commanded position.
A joint fails if it cannot return to the zero position within the zero-return tolerance (default 0.01 rad), or if its bounding box grows to more than 10 times its baseline size during the sweep (bbox explode ratio, default 10). Failure to reach the upper or lower limit within `rest_tolerance` (default 0.10 rad) is recorded as a warning, not a failure, unless `rest_check_fatal` is set to `true`.

## How It Works

Each joint is swept in isolation. The test drives the joint to the upper limit at
a speed scaled by `sweep_speed_scale` (default 0.8), pauses for
`pause_at_limits_seconds` (default 0.15 s), then drives to the lower limit, pauses
again, and returns to zero. The baseline bounding box is captured before the sweep
begins. If the bounding box exceeds 10 times the baseline at any point, the test
immediately fails with a bbox-explode error, indicating the articulation has
become unstable or a prim has moved to an unexpected position.

Joints that have no authored lower and upper limits are skipped. Passive joints
and mimic-follower joints are excluded from the sweep; their behavior is covered
by other tests in this family.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Joint cannot reach upper or lower limit | Drive stiffness or maxForce too low; joint limited by collision geometry before the authored limit |
| Joint cannot return to zero within tolerance | Drive damping too low; residual energy keeps the joint oscillating |
| Bounding box explode at a limit | Articulation instability when joints reach their limits; physics solver divergence |
| Rest-hold warning (not failure by default) | Drive stiffness or damping insufficient to hold the joint against gravity at the limit position |

## How to Fix

If a joint cannot reach its authored limit, increase the `driveStiffness` and
`driveMaxForce` values on the `UsdPhysicsDriveAPI` schema for that joint. Confirm
that collision geometry does not physically block the joint before the authored
limit is reached.

If the joint cannot return to zero, increase `driveDamping` to dissipate kinetic
energy, or reduce the sweep speed by lowering `sweep_speed_scale`.

If bounding box explosion occurs, check that the articulation tree is correctly
rooted, that all joint bodies have valid mass and inertia values, and that the
joint limits themselves are not set to physically impossible positions that cause
solver instability.

## Expected Result

![full_range_sweep expected result](../_images/full-range-sweep.png)

[Result video](../../../../_static/videos/full-range-sweep.mp4)

Each joint moves one at a time across its full range: to the upper limit, to the
lower limit, and back to the rest position. The motion is smooth and continuous.
No joint snaps, explodes, or fails to reach its waypoint. The articulation
remains stable throughout.

## Notes and Caveats

The bbox-explode check uses the bounding box of the entire articulation, not of
the individual joint. A joint that is far from the base link can cause a large
bbox change even under normal motion; if the threshold triggers on a valid asset,
the `bbox_explode_ratio` config key can be raised.

Passive joints and mimic-follower joints are excluded from this test. Their
range compliance is implied by the passive constraint definition and by the
mimic-joint test, respectively.
