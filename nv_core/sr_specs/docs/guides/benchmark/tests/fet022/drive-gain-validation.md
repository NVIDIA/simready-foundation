# drive_gain_validation  (FET022 Driven Joints)

| Property     | Value                                                                         |
|--------------|-------------------------------------------------------------------------------|
| Test name    | drive_gain_validation                                                         |
| Feature(s)   | FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC |
| Engine       | Kit / Isaac Sim (>=2024.2.0)                                                  |
| Test version | 1.0.0                                                                         |

## Summary

Commands each driven joint through a step input and evaluates the step-response
quality by measuring overshoot, settling time, and velocity sign changes.

## What Pass Guarantees

A passing result confirms that the joint drive gains produce a step response that
is stable and converges to the target position within the declared tolerances.
Reviewers, PMs, and OEMs can trust that the joint will not oscillate indefinitely,
overshoot excessively, or fail to settle when driven in a physics simulation.

## What It Checks

The test commands each non-passive, non-mimic-follower joint to step by
`step_magnitude_deg` (default 30 degrees) from its current position and observes
the response for `max_settling_seconds` (default 5.0 s). Three metrics are
evaluated:

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

Each joint is stepped individually. The drive command is sent and the joint
position is sampled at every simulation frame for the duration of the settling
window. The peak position is recorded to compute overshoot, and the velocity
series is sign-differenced to count oscillations. After the window closes, the
joint returns to its starting position before the next joint is tested.

The test uses the drive gains already authored on the asset. It does not modify
stiffness, damping, or maxForce values during execution.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Overshoot above 50 percent (warning by default) | Drive damping too low relative to stiffness; underdamped response |
| Joint does not settle within 5 s (warning by default) | Drive stiffness too low; maxForce cap preventing full drive authority |
| More than 20 velocity sign changes (warning by default) | Sustained oscillation; system is underdamped or marginally stable |

## How to Fix

If overshoot is excessive, increase `driveDamping` on the joint's
`UsdPhysicsDriveAPI` schema. Damping resists velocity and reduces the overshoot
peak. Avoid reducing stiffness to compensate, as lower stiffness causes slower
settling.

If the joint does not settle in time, increase `driveStiffness` to apply a
stronger restoring force and ensure `driveMaxForce` is set high enough to deliver
that force at the joint. A maxForce cap that is too low prevents the drive from
closing the position error.

If oscillations are excessive, increase `driveDamping`. In some cases a small
increase in maxForce is also needed to let the damping force take effect.

## Expected Result

![drive_gain_validation expected result](../_images/drive-gain-validation.png)

[Result video](../../../../_static/videos/drive-gain-validation.mp4)

Each joint steps by approximately 30 degrees, overshoots slightly, and then
settles to the target position within a few seconds. The motion looks like a
lightly damped step response: a rapid rise, a small overshoot peak, and a smooth
decay to the final position. Sustained oscillation or failure to reach the target
indicates poor gain tuning.

## Notes and Caveats

By default, all three metrics are warnings, not hard failures. This design allows
the test to report gain-quality information on assets whose specification does not
mandate a specific step-response standard. Authors who require strict gain
compliance can set `step_fatal: true` in the test configuration to promote
warnings to failures.

The test does not attempt to auto-tune gains. Its purpose is to detect clearly
poor tuning, not to prescribe optimal values.
