# multi_joint_coordination  (FET022 Driven Joints)

| Property     | Value                                                                         |
|--------------|-------------------------------------------------------------------------------|
| Test name    | multi_joint_coordination                                                      |
| Feature(s)   | FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC |
| Engine       | Kit / Isaac Sim (>=2024.2.0)                                                  |
| Test version | 1.0.0                                                                         |

## Summary

Commands all non-passive, non-mimic-follower joints simultaneously to a target
configuration and verifies that every joint reaches its target within tolerance
and within the settling time limit.

## What Pass Guarantees

A passing result confirms that the drive controllers for all joints do not
interfere with or stall each other during simultaneous motion. Reviewers, PMs,
and OEMs can trust that the articulation can execute coordinated trajectories
without joint-by-joint deadlock or oscillatory coupling between adjacent drives.

## What It Checks

The test commands all non-passive, non-mimic-follower joints simultaneously to
a target configuration. The target positions are computed as fractions of each
joint's range (target factors: 0.3, 0.6, and 0.5 of the range, applied across
`num_iterations` (default 3) iterations). After each command, the test waits up
to `max_settling_seconds` (default 8.0 s) and then measures each joint's
position. A joint fails if its position error exceeds `position_tolerance_deg`
(default 1 degree). If any joint fails in any iteration, the test fails. The
test skips when fewer than two joints with finite limits are found.

## How It Works

At each iteration, all drive targets are set simultaneously. The test then polls
the articulation state at the simulation frame rate until either all joints are
within tolerance or the settling timeout expires. The worst-case residual error
is recorded for each joint. After the settling window closes, joints that have
not converged are counted as failed.

The carrier fixture holds the robot base fixed throughout the test so that base
drift does not inflate the per-joint position error.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| One joint fails to converge while others do | Drive stiffness or maxForce too low on the failing joint; adjacent joints creating a reactive torque that the drive cannot overcome |
| All joints fail to converge | Drive gains globally insufficient for the articulation mass; maxForce limits too low across the board |
| Joints converge individually but oscillate together | Coupled dynamics between adjacent drives; damping values too low in the presence of inter-joint coupling |

## How to Fix

If specific joints fail to converge, increase `driveStiffness` and `driveMaxForce`
on those joints' `UsdPhysicsDriveAPI` schemas. Verify that gravity compensation or
link mass values are physically correct, because an underestimated link mass can
make a joint appear to stall even with reasonable drive gains.

If oscillation occurs across multiple joints simultaneously, increase
`driveDamping` on all joints in the kinematic chain that connects the oscillating
links. Coupled oscillation often requires damping increases on multiple joints
rather than on only the joint that appears to be lagging.

## Expected Result

![multi_joint_coordination expected result](../_images/multi-joint-coordination.png)

[Result video](../../../../_static/videos/multi-joint-coordination.mp4)

All robot joints move simultaneously toward a single target configuration. The
motion looks fluid: joints accelerate and decelerate in concert rather than one
at a time. The end effector smoothly reaches its target and holds. Joints
stalling, jittering, or arriving at substantially different times indicates
inadequate drive coordination.

## Notes and Caveats

The test skips when fewer than two joints with finite limits are present. A single
joint cannot produce a meaningful coordination test, so the skip is expected
behavior for simple articulations such as a single-axis gripper.

The tolerance is tighter than in the state-accuracy test (1 degree versus
5 degrees) because coordinated motion requires more precise convergence to avoid
configuration-space drift accumulating over multiple simultaneous joints.
