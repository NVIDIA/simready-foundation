# ik_target_reach  (FET022 Driven Joints)

| Property     | Value                                                                         |
|--------------|-------------------------------------------------------------------------------|
| Test name    | ik_target_reach                                                               |
| Feature(s)   | FET022_DRIVEN_JOINTS_PHYSX, FET022_DRIVEN_JOINTS_ISAAC |
| Engine       | Kit / Isaac Sim (>=2024.2.0)                                                  |
| Test version | 1.0.0                                                                         |

## Summary

Generates a Fibonacci-sphere distribution of end-effector targets, solves them
with the Lula IK solver, commands the articulation to each solution, and verifies
that the achieved end-effector pose is within the declared tolerances.

## What Pass Guarantees

A passing result confirms that the Lula IK solver can find valid joint
configurations for reachable targets, that the articulation can execute those
configurations, and that the achieved end-effector pose matches the commanded pose
within the declared position and orientation tolerances. Reviewers, PMs, and OEMs
can trust that the robot descriptor is correctly paired with the asset and that
end-effector targets within the workspace are reachable in simulation.

## What It Checks

The test generates candidate end-effector targets distributed on a Fibonacci
sphere around the robot base. From those Fibonacci-sphere candidates, `num_reachable_targets` (default 5) are geometrically classified as reachable by proximity to the robot's estimated workspace radius. For each in-reach target, the test commands the articulation to the IK
solution and measures the actual end-effector pose. The test fails if no in-reach
targets are found, or if the fraction of targets where the achieved pose is within
tolerance falls below `min_success_rate` (default 0.50). Position tolerance is
`position_tolerance` (default 0.02 m). Orientation tolerance is
`orientation_tolerance` (default 0.25 rad, approximately 14 degrees).

The test skips cleanly when no Lula robot descriptor is found for the asset.

## How It Works

The test uses the Isaac Sim `motion_generation` extension to instantiate the Lula
IK solver. The Lula solver requires a robot descriptor (a YAML file paired with a
URDF) to be registered for the asset. If no descriptor is found, the test skips
without failure.

Fibonacci-sphere sampling distributes targets uniformly over the surface of a sphere with a radius scaled to the robot's reach estimate. Targets are pre-classified as reachable or out-of-reach geometrically: `num_reachable_targets` targets are placed at radius fractions within the estimated workspace (default 0.5, 0.7, and 0.9 of the robot's reach), and a small number of out-of-reach targets are placed beyond it. All targets are then passed to the solver, and the test tracks which targets were geometrically classified as reachable when computing the pass rate.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| No in-reach targets found | Lula descriptor does not match the asset kinematics; workspace sphere radius is too large or too small for the robot's actual reach |
| Pass rate below 50 percent | IK solutions do not transfer to the physics articulation correctly; drive gains insufficient to execute the IK configuration; large discrepancy between the descriptor kinematics and the USD joint structure |
| Test skipped | No Lula robot descriptor registered for the asset; test cannot run |

## How to Fix

If no in-reach targets are found, verify that the Lula descriptor YAML and URDF
match the kinematic structure of the USD asset, including joint order, axis
directions, and joint limits. If the workspace sphere radius is wrong, the
descriptor's reported reach estimate might need to be corrected.

If the pass rate is low but the solver finds solutions, check that the drive
gains can execute the commanded joint configurations and that the joint limits in
the USD asset match the limits in the URDF used to generate the descriptor.
Mismatched limits cause the physics simulation to clamp joints to values that
differ from the IK solution.

## Expected Result

![ik_target_reach expected result](../_images/ik-target-reach.png)

[Result video](../../../../_static/videos/ik-target-reach.mp4)

The robot moves to a series of end-effector target poses distributed around its
workspace. At each pose, the end effector is close to the commanded position and
orientation. On a passing run, the robot visibly reaches each target without
obvious configuration-space discontinuities or joint limit violations.

## Notes and Caveats

This test requires a Lula robot descriptor. Without a descriptor, the test skips.
A skip is not a failure; it means the IK feature cannot be validated for this
asset. To enable this test, register a Lula descriptor for the asset in the
SimReady asset metadata.

This test is distinct from the jacobian_ik test. The jacobian_ik test uses an
in-house damped-least-squares Jacobian solver that does not require a Lula
descriptor and samples targets differently. Refer to the
[jacobian_ik](jacobian-ik.md) doc for details.
