# gripper_close_lift_sphere  (FET028 Gripper)

| Property     | Value                                         |
|--------------|-----------------------------------------------|
| Test name    | gripper_close_lift_sphere                     |
| Feature(s)   | FET_028_ISAAC                          |
| Engine       | Kit / Isaac Sim (>=2024.2.0)                  |
| Test version | 1.4.0                                         |

## Summary

The gripper closes on a sphere sized at 70 percent of its maximum jaw opening, at 50 percent of its rated maximum payload, then retains the sphere through a 20 cm gantry lift and a 2-second sinusoidal shake before releasing it.

## What Pass Guarantees

A reviewer, PM, or OEM can trust that the gripper produces enough finger-pad friction and contact force to hold a spherical object under real gravity through lift and shake, and that it opens cleanly on command. A sphere contacts each finger pad at a single point, so a pass at 50 percent of the rated maximum payload confirms that the authored pad friction is sufficient for point-contact loading. An asset that passes this test can be used in pick-and-place workflows where rounded or small-radius objects are handled.

## What It Checks

The test confirms that the gripper:

- discovers a valid gripper site with a positive maximum jaw opening,
- attaches to a test-owned Z-axis gantry through the gripper base rigid body,
- drives every resolved jaw leader to its open limit and verifies that the commanded leaders reach the open position,
- descends onto the sphere and detects contact before closing,
- closes with the sphere physically blocked between the finger pads (close stalled on the object, not in empty space),
- retains the sphere laterally within one object diameter of the gripper axis after the close,
- lifts the sphere at least 10 cm with the gantry and confirms the sphere follows the carrier upward within 5 cm vertical error and 5 cm horizontal drift,
- holds the sphere through 2 s of sinusoidal Z-axis perturbation with the object staying above 2 cm and slipping less than 3 cm relative to the gripper, and
- releases the sphere when commanded: the sphere falls at least 5 cm after the open command.

The test covers parallel-jaw and centric mimic grippers as well as independent-finger hands. Newton-native parallel jaws may use two leaders when both are explicit `NewtonActuator` targets and the authored grip line resolves their opposed pad branches. Mechanisms that expose no safely resolvable driven finger branches still receive a clear unsupported-topology diagnostic.

## How It Works

The test runs the following stages in order:

1. **Site discovery.** The test finds the gripper site prim, reads `custom:maxOpening` (must be positive), and resolves the gripper base as the rigid-body ancestor of the site, preferring an ancestor that has rigid-body descendants (indicating a base rather than a fingertip) and falling back to the closest rigid-body ancestor when none has descendants.

2. **Topology check.** The test traverses every `UsdPhysics.Joint` type, including fixed-joint extensions, to resolve the physical fingertip links. It then selects a shared symmetric mimic leader, a guarded pair of Newton-actuator-owned jaw leaders, or independently actuated finger branches for a hand. A two-leader jaw is accepted only when both leaders are explicit `NewtonActuator` targets and the authored grip line identifies the two opposed pad branches.

3. **Payload resolution.** The sphere mass is `0.5 * custom:maxPayload`. When the asset does not author `custom:maxPayload`, the test uses a heuristic of 50 kg/m of maximum opening, clamped between 0.1 kg and 50 kg. A warning is logged when the heuristic is used.

4. **Gantry attachment.** The test attaches a prismatic Z-axis carrier to the gripper base by a fixed joint. The gripper is oriented so its forward axis points world negative Z (top-down approach), and the gantry raises the gripper to a standoff height. The sphere is then spawned on the ground plane directly below the gripper grasp center.

5. **Sphere spawn.** A synthetic sphere with diameter `0.7 * maxOpening`, mass equal to the resolved payload, and static and dynamic friction of 2.0 is spawned on the ground plane directly below the gripper grasp center. The sphere settles briefly under gravity before the descent begins.

6. **Open.** For an authored grip-line topology, the test follows the FET028 convention that each leader's lower limit is open and upper limit is closed, avoiding a destructive endpoint pre-sweep. Otherwise it probes the leader limits and identifies the open position from the wider live fingertip aperture. For a supported two-leader Newton jaw, both leaders receive the same normalized motion through their own finite limits. Each commanded leader must reach its open target within 0.025 rad or m, which is five times the base tolerance of 0.005.

7. **Descent and contact detection.** The gantry descends in 12 chunks while holding the gripper open. When the sphere shifts by more than 3 mm (indicating contact), the descent stops and the gripper backs off 10 percent of the maximum opening before closing.

8. **Close.** The test drives the resolved grasp DOFs toward their close targets using the asset's authored drive parameters. A stall below the closed target confirms the finger pads are blocked by the sphere. DOFs held at the same open and closed target are excluded from contact inference.

9. **Grip gate.** The test verifies that the close stalled on the sphere and that the sphere remains within one object diameter of the gripper axis. If either condition fails, the test reports a failure without proceeding to lift.

10. **Lift.** The gantry raises the gripper 20 cm over 1 s. Pass criteria: the sphere's vertical deviation from the expected position is less than 5 cm and horizontal drift is less than 5 cm. Vertical motion during close is reported as a pre-load diagnostic because a hand may seat or lift the sphere while establishing contact; the subsequent carrier-follow, shake, and release phases determine whether the grasp is valid. The gantry must lift at least 10 cm; a shorter lift is an internal harness error, not an asset fault.

11. **Shake.** The gantry oscillates sinusoidally along Z at 2 Hz, 2 cm amplitude, for 2 s. The sphere must stay above 2 cm and slip less than 3 cm relative to the gripper throughout.

12. **Release.** The test drives every resolved jaw leader back to its open position. The sphere must fall at least 5 cm after the open command.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Test skipped: unsupported gripper topology | No safely drivable parallel, centric, or independent-finger topology could be resolved; inspect the emitted joint-graph diagnostic |
| Precheck failure: ambiguous or invalid transform | Duplicate physics-link names, a stale tensor view, or non-finite authored/live transforms prevent safe fingertip resolution |
| Precheck failure: invalid maxOpening | `custom:maxOpening` on the site prim is zero, negative, or absent |
| Precheck failure: no rigid-body ancestor | The gripper site is not parented under a link with `PhysicsRigidBodyAPI`; the site is mis-parented or the base link is missing its rigid-body schema |
| Open command did not reach the open position | One or more leaders have reversed or invalid limits, a drive is too weak, or the limits do not match the actual range of motion |
| Grasp center at or below the sphere | The gripper is authored pointing up or translated to the floor; the gantry has no room to descend onto the sphere |
| Close did not contact the sphere | The fingers reached their closed limit in empty space; the sphere was knocked out laterally during descent, or the drive closed before reaching grasp depth |
| Lift failed: sphere did not follow the carrier | Finger-pad friction is too low for point-contact on a sphere at 50 percent payload, or the drive's holding force is insufficient. This row applies only when the gantry itself lifted at least 10 cm; a shorter gantry lift is a harness error. |
| Shake failed: sphere dropped or slipped | Grip is too weak for sinusoidal perturbation; finger-pad friction or drive stiffness needs to increase |
| Release failed: sphere did not fall | The gripper cannot re-open; inspect the open drive parameters and joint limits |
| Physics view returns None after the open command | Internal harness error, not an asset fault. The Isaac physics view was not initialized before the open command returned. File a bug against the core tier's FET028 runtime tests. |
| Gantry lifted less than 10 cm | Internal harness error, not an asset fault. The test-owned Z-axis carrier failed to produce a meaningful lift. Refer to the gantry lift note in How It Works. |

## How to Fix

If the site is not found or the maximum opening is invalid, add a positive `custom:maxOpening` attribute to the gripper site prim, expressing the maximum jaw separation in meters. Typical industrial parallel-jaw grippers use 0.05 to 0.15 m.

If the rigid-body ancestor is missing, reparent the gripper site Xform so it lives directly under the gripper base link, and confirm that link carries `PhysicsRigidBodyAPI`.

If the open command does not reach the open position, check every commanded leader's finite `physics:lowerLimit` and `physics:upperLimit`. An authored grip-line topology follows the FET028 lower-is-open convention; topologies without resolved grip-line pads are identified from live aperture measurements. A persistent open failure usually means a leader drive is too weak to move against joint friction or the paired leaders do not represent the same normalized jaw motion.

If the close does not contact the sphere, inspect the drive stiffness and confirm the descent reached grasp depth before closing. A sphere can be knocked sideways by an overly aggressive close; lower the drive stiffness or increase damping if lateral drift is large after the close.

If the lift or shake fails, check the physics material on the finger pad collision meshes. Static and dynamic friction below 0.8 will cause a sphere to slip at point contact. Industrial pad materials typically use 1.0 to 2.0. Also confirm that every commanded leader's actuator stiffness and maximum effort are sized for the tested payload.

If the release fails, check that the open drive parameters and joint limits allow every commanded leader to return to its open position. A locked, reversed, or uncoordinated leader will prevent the gripper from re-opening.

## Expected Result

:::{note}
An expected-result still and video for this test are not captured yet. The expected result is described below.
:::

An orange sphere rests on the floor below the gripper. The gripper opens, the gantry descends, the gripper closes on the sphere, the gantry lifts 20 cm, the gantry shakes for approximately 2 s, and the gripper drops the sphere. A passing result shows the sphere held through the lift and shake, then falling clearly after the open command.

## Notes and Caveats

The sphere is tested at 50 percent of the rated maximum payload, not 85 percent. A sphere contacts each finger pad at a single point or a very small area, so its grip is friction-limited by a much smaller normal-force lever arm than a flat-faced object of the same mass. Testing a sphere at the full 85 percent payload would penalize geometrically fine grippers for a contact-area limitation unrelated to grip strength. The cube variant uses 85 percent to stress grip strength under flat-face loading.

If `custom:maxPayload` is not authored on the gripper site, the test uses a heuristic based on the maximum opening. Author a realistic `custom:maxPayload` value (in kg) on the site prim so future runs test the asset's specified capability rather than the heuristic estimate.

Parallel-jaw, centric, and independent-finger grippers use the same pass thresholds. A skip is reserved for mechanisms whose driven finger topology cannot be resolved safely, such as unsupported tendon-driven or underactuated designs.

Two-leader classification is intentionally narrow. Both leaders must be explicit `NewtonActuator` targets, their follower groups must remain symmetric, and the authored grip line must resolve one pad branch per leader. This prevents an unrelated multi-DOF mechanism from being driven as a parallel jaw.

The test does not override the gripper's finger-pad physics materials. Whatever friction the asset authors on its pad collision meshes is what the simulation uses. If the lift fails due to low friction, the friction coefficient on the finger-pad physics material requires correction in the asset.
