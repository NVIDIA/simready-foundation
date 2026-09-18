# gripper_close_lift_cube  (FET028 Gripper)

| Property     | Value                                         |
|--------------|-----------------------------------------------|
| Test name    | gripper_close_lift_cube                       |
| Feature(s)   | FET_028_ISAAC                          |
| Engine       | Kit / Isaac Sim (>=2024.2.0)                  |
| Test version | 1.4.0                                         |

## Summary

The gripper closes on a cube sized at 70 percent of its maximum jaw opening, at 85 percent of its rated maximum payload, then retains the cube through a 20 cm gantry lift and a 2-second sinusoidal shake before releasing it.

## What Pass Guarantees

A reviewer, PM, or OEM can trust that the gripper produces enough drive force and holding torque to retain a flat-faced object at 85 percent of the rated maximum payload through a lift and a sinusoidal perturbation, and that it opens cleanly on command. A cube presents flat faces to the finger pads, giving larger contact patches than a sphere. A pass at 85 percent of the rated maximum payload confirms that the drive stiffness, maximum force, and pad friction together produce a grip strong enough for typical payload-rated pick-and-place operations. An asset that passes this test is suitable for payload-intensive workflows with box-shaped objects.

## What It Checks

The test confirms that the gripper:

- discovers a valid gripper site with a positive maximum jaw opening,
- attaches to a test-owned Z-axis gantry through the gripper base rigid body,
- drives every resolved jaw leader to its open limit and verifies that the commanded leaders reach the open position,
- descends onto the cube and detects contact before closing,
- closes with the cube physically blocked between the finger pads (close stalled on the object, not in empty space),
- retains the cube laterally within one object diameter of the gripper axis after the close,
- lifts the cube at least 10 cm with the gantry and confirms the cube follows the carrier upward within 5 cm vertical error and 5 cm horizontal drift,
- holds the cube through 2 s of sinusoidal Z-axis perturbation with the object staying above 2 cm and slipping less than 3 cm relative to the gripper, and
- releases the cube when commanded: the cube falls at least 5 cm after the open command.

The test covers parallel-jaw and centric mimic grippers as well as independent-finger hands. Newton-native parallel jaws may use two leaders when both are explicit `NewtonActuator` targets and the authored grip line resolves their opposed pad branches. Mechanisms that expose no safely resolvable driven finger branches still receive a clear unsupported-topology diagnostic.

## How It Works

The test runs the following stages in order:

1. **Site discovery.** The test finds the gripper site prim, reads `custom:maxOpening` (must be positive), and resolves the gripper base as the rigid-body ancestor of the site, preferring an ancestor that has rigid-body descendants (indicating a base rather than a fingertip) and falling back to the closest rigid-body ancestor when none has descendants.

2. **Topology check.** The test traverses every `UsdPhysics.Joint` type, including fixed-joint extensions, to resolve the physical fingertip links. It then selects a shared symmetric mimic leader, a guarded pair of Newton-actuator-owned jaw leaders, or independently actuated finger branches for a hand. A two-leader jaw is accepted only when both leaders are explicit `NewtonActuator` targets and the authored grip line identifies the two opposed pad branches.

3. **Payload resolution.** The cube mass is `0.85 * custom:maxPayload`. When the asset does not author `custom:maxPayload`, the test uses a heuristic of 50 kg/m of maximum opening, clamped between 0.1 kg and 50 kg. A warning is logged when the heuristic is used.

4. **Gantry attachment.** The test attaches a prismatic Z-axis carrier to the gripper base by a fixed joint. The gripper is oriented so its forward axis points world negative Z (top-down approach), and the gantry raises the gripper to a standoff height. The cube is then spawned on the ground plane directly below the gripper grasp center.

5. **Cube spawn.** A synthetic cube with edge length `0.7 * maxOpening`, mass equal to the resolved payload, and static and dynamic friction of 2.0 is spawned on the ground plane directly below the gripper grasp center. The cube settles briefly under gravity before the descent begins.

6. **Open.** For an authored grip-line topology, the test follows the FET028 convention that each leader's lower limit is open and upper limit is closed, avoiding a destructive endpoint pre-sweep. Otherwise it probes the leader limits and identifies the open position from the wider live fingertip aperture. For a supported two-leader Newton jaw, both leaders receive the same normalized motion through their own finite limits. Each commanded leader must reach its open target within 0.025 rad or m, which is five times the base tolerance of 0.005.

7. **Descent and contact detection.** The gantry descends in 12 chunks while holding the gripper open. When the cube shifts by more than 3 mm (indicating contact), the descent stops and the gripper backs off 10 percent of the maximum opening before closing.

8. **Close.** The test drives the resolved grasp DOFs toward their close targets using the asset's authored drive parameters. A stall below the closed target confirms the finger pads are blocked by the cube. DOFs held at the same open and closed target are excluded from contact inference.

9. **Grip gate.** The test verifies that the close stalled on the cube and that the cube remains within one object diameter of the gripper axis. If either condition fails, the test reports a failure without proceeding to lift.

10. **Lift.** The gantry raises the gripper 20 cm over 1 s. Pass criteria: the cube's vertical deviation from the expected position is less than 5 cm and horizontal drift is less than 5 cm. Vertical motion during close is reported as a pre-load diagnostic because a hand may seat or lift the cube while establishing contact; the subsequent carrier-follow, shake, and release phases determine whether the grasp is valid. The gantry must lift at least 10 cm; a shorter lift is an internal harness error, not an asset fault.

11. **Shake.** The gantry oscillates sinusoidally along Z at 2 Hz, 2 cm amplitude, for 2 s. The cube must stay above 2 cm and slip less than 3 cm relative to the gripper throughout.

12. **Release.** The test drives every resolved jaw leader back to its open position. The cube must fall at least 5 cm after the open command.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Test skipped: unsupported gripper topology | No safely drivable parallel, centric, or independent-finger topology could be resolved; inspect the emitted joint-graph diagnostic |
| Precheck failure: ambiguous or invalid transform | Duplicate physics-link names, a stale tensor view, or non-finite authored/live transforms prevent safe fingertip resolution |
| Precheck failure: invalid maxOpening | `custom:maxOpening` on the site prim is zero, negative, or absent |
| Precheck failure: no rigid-body ancestor | The gripper site is not parented under a link with `PhysicsRigidBodyAPI`; the site is mis-parented or the base link is missing its rigid-body schema |
| Open command did not reach the open position | One or more leaders have reversed or invalid limits, a drive is too weak, or the limits do not match the actual range of motion |
| Grasp center at or below the cube | The gripper is authored pointing up or translated to the floor; the gantry has no room to descend onto the cube |
| Close did not contact the cube | The fingers reached their closed limit in empty space; the cube was knocked out laterally during descent, or the drive closed before reaching grasp depth |
| Lift failed: cube did not follow the carrier | Drive force or holding torque is insufficient for 85 percent payload under flat-face loading, or finger-pad friction is too low. This row applies only when the gantry itself lifted at least 10 cm; a shorter gantry lift is a harness error. |
| Shake failed: cube dropped or slipped | Grip is too weak for sinusoidal perturbation at 85 percent payload; drive stiffness or pad friction needs to increase |
| Release failed: cube did not fall | The gripper cannot re-open; inspect the open drive parameters and joint limits |
| Physics view returns None after the open command | Internal harness error, not an asset fault. The Isaac physics view was not initialized before the open command returned. File a bug against the core tier's FET028 runtime tests. |
| Gantry lifted less than 10 cm | Internal harness error, not an asset fault. The test-owned Z-axis carrier failed to produce a meaningful lift. Refer to the gantry lift note in How It Works. |

## How to Fix

If the site is not found or the maximum opening is invalid, add a positive `custom:maxOpening` attribute to the gripper site prim, expressing the maximum jaw separation in meters. Typical industrial parallel-jaw grippers use 0.05 to 0.15 m.

If the rigid-body ancestor is missing, reparent the gripper site Xform so it lives directly under the gripper base link, and confirm that link carries `PhysicsRigidBodyAPI`.

If the open command does not reach the open position, check every commanded leader's finite `physics:lowerLimit` and `physics:upperLimit`. An authored grip-line topology follows the FET028 lower-is-open convention; topologies without resolved grip-line pads are identified from live aperture measurements. A persistent open failure usually means a leader drive is too weak to move against joint friction or the paired leaders do not represent the same normalized jaw motion.

If the close does not contact the cube, inspect the drive stiffness and confirm the descent reached grasp depth before closing. An overly aggressive close can knock the cube laterally; lower the drive stiffness or increase damping if large lateral drift is observed after the close.

If the lift or shake fails, increase each commanded leader's actuator stiffness and maximum effort until the combined holding force is sufficient for the tested mass. Keep paired leaders balanced rather than strengthening only one jaw. Also confirm the physics material on the finger pad collision meshes; static and dynamic friction below 0.8 will cause slipping even with strong actuation. Values of 1.0 to 2.0 are typical for industrial pads.

If `custom:maxPayload` is not authored, author a realistic value in kg on the site prim. The heuristic might overestimate or underestimate the true capability, and the test will report a warning whenever the heuristic is used.

If the release fails, check that the open drive parameters and joint limits allow every commanded leader to return to its open position. A locked, reversed, or uncoordinated leader will prevent the gripper from re-opening.

## Expected Result

:::{note}
An expected-result still and video for this test are not captured yet. The expected result is described below.
:::

A cyan cube rests on the floor below the gripper. The gripper opens, the gantry descends, the gripper closes on the cube, the gantry lifts 20 cm, the gantry shakes for approximately 2 s, and the gripper drops the cube. A passing result shows the cube held through the lift and shake, then falling clearly after the open command.

## Notes and Caveats

The cube is tested at 85 percent of the rated maximum payload, the standard FET028 stress level. Flat faces give larger contact patches than a sphere, so the test stresses drive force and grip strength rather than contact geometry. The sphere variant uses 50 percent payload to account for the contact-area limitation of point-contact finger loading.

If `custom:maxPayload` is not authored on the gripper site, the test uses a heuristic based on the maximum opening. Author a realistic `custom:maxPayload` value (in kg) on the site prim so future runs test the asset's specified capability rather than the heuristic estimate.

Parallel-jaw, centric, and independent-finger grippers use the same pass thresholds. A skip is reserved for mechanisms whose driven finger topology cannot be resolved safely, such as unsupported tendon-driven or underactuated designs.

Two-leader classification is intentionally narrow. Both leaders must be explicit `NewtonActuator` targets, their follower groups must remain symmetric, and the authored grip line must resolve one pad branch per leader. This prevents an unrelated multi-DOF mechanism from being driven as a parallel jaw.

The test does not override the gripper's finger-pad physics materials. Whatever friction the asset authors on its pad collision meshes is what the simulation uses. If the lift fails due to low friction, the friction coefficient on the finger-pad physics material requires correction in the asset.
