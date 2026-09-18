# grasp_and_lift  (FET005 Grasp)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | grasp_and_lift                 |
| Feature(s)   | FET_005_STANDARD               |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 1.3.0                          |

## Summary

A parallel-jaw gripper positions at each declared grasp identifier on the asset, closes onto it under real gravity, lifts it, holds it through a circular horizontal orbit shake, and releases it cleanly.

## What Pass Guarantees

A reviewer, PM, or OEM can trust that at least one declared grasp point on the asset produces a stable, physically achievable grip in the selected physics runtime. An overall pass does not guarantee that every identifier succeeds; the test fails only when all identifiers fail, and partial failures are recorded as warnings in the per-identifier metrics. A passing grasp identifier means the asset's authored mass and friction are sufficient that gravity does not pull it free during the lift, hold, or shake phases for that runtime.

## What It Checks

The test iterates every `grasp_identifier_*` prim authored on the asset. For each identifier, it runs a fresh simulation scene, positions a standardized parallel-jaw gripper at the identifier pose, and drives the gripper through nine sequential phases. The test confirms that the asset rises when the gripper lifts, remains in the jaws during a static hold and a circular horizontal orbit, and falls freely after the jaws open.

The test skips the asset entirely when no `grasp_identifier_*` prims are found, because there is no grasp metadata to evaluate. An asset whose physics setup cannot be loaded triggers a precheck failure rather than a per-phase result. If at least one identifier passes all nine phases, the overall test result is a pass; the test fails only when every identifier fails. Partial failures are logged as warnings and recorded in metrics.

## Preconditions

This benchmark depends on the FET003 feature for the active runtime:
`FET_003_PHYSX` for PhysX, `FET_003_NEWTON` for Newton, and
`FET_003_MUJOCO` for MuJoCo. An asset with a validation record but without the
matching feature is skipped rather than failed. An external or forced run with
no validation record proceeds because the dependency cannot be checked. An
unknown `SIMREADY_PHYSICS_RUNTIME` value is skipped with an explicit reason.

## How It Works

The nine phases run in order, stopping at the first failure within each identifier:

1. The Stability phase places the asset with its bounding-box bottom just above the ground plane and allows it to settle under gravity (9.81 m/s²). The phase waits up to 3.0 s for the asset centroid to remain still within a 0.002 m rest tolerance for 1.0 s. If the timeout expires before rest is detected, the phase proceeds anyway; it never blocks progress.

2. The GripperPositioning phase moves the gripper gantry to the grasp midpoint. The phase waits until the gantry converges within 5 mm of the target or 2.0 s elapses, whichever comes first. A timeout here fails the identifier.

3. The Grasping phase sizes the fixture from the rigid body that owns the grasp identifier, then closes the gripper smoothly at no more than 0.04 m/s. The commanded aperture includes 0.005 m of contact preload per jaw so a position drive develops holding force against the real collider rather than stopping at a zero-load analytical bounding-box width. After convergence, the jaws preserve the stable target for another 0.3 s before lifting. If the pads meet each other, meaning the selected body has no collider at the grasp line, the phase fails.

4. The Lifting phase freezes the gantry's final horizontal target from GripperPositioning, stops following the authored grasp line, and raises the gantry over 1.0 s with a smoothstep motion profile. The requested height is twice the longest edge of the grasped body, clamped to 0.3–0.5 m so large or eccentric assets do not receive an artificial high-speed lift. The phase passes when the grasped body's centroid has risen at least 0.02 m from its position at lift start.

5. The HoldBeforeShake phase holds the gripper position for 1.0 s. The phase fails if the asset centroid drops more than 0.10 m from its position at hold start, or if the asset centroid sinks to within 0.02 m of the ground plane.

6. The Shake phase moves the gantry in a circular horizontal orbit at 2.0 Hz with a 0.01 m radius for 1.5 s. A 0.25 s smooth envelope spirals into and out of the orbit so the first frame does not impose a discontinuous lateral target. It fails if the grasped body reaches the configured floor threshold or its authored grasp midpoint separates by 0.05 m from the live midpoint between the jaws. Measuring relative separation distinguishes a real grip loss from harmless rotation of a long body around the held point.

7. The HoldAfterShake phase holds the gripper position again for 1.0 s under the same drop and floor-contact criteria as HoldBeforeShake.

8. The Opening phase opens the gripper over 0.5 s. Once opening completes, it disables collision on both generated fixture pads so residual solver contact cannot keep an otherwise released object attached. This phase never fails; it records whether the asset moved when released.

9. The Dropping phase waits up to 3.0 s after release for the grasped-body centroid to fall by at least the larger of 0.05 m and that body's bounding-box height. A fall of this magnitude confirms that the gripper genuinely held the selected body and that it is now free under gravity.

Collision geometry is run exactly as authored. Any runtime-specific cooking or
fallback behavior is owned by the selected engine.

The generated finger controls are runtime-specific. PhysX uses two balanced
linear drives because `PhysxMimicJointAPI` does not enforce prismatic follower
motion. Each PhysX jaw retains the established safety-factored fixture load;
the test does not weaken that force when replacing the unsupported mimic.
Newton creates one `NewtonActuator` with `NewtonPDControlAPI` and
`NewtonMaxEffortClampingAPI` for each jaw and commands both jaw coordinates to
the same symmetric target. Newton's per-jaw effort and PD gains are derived
from the safety load, generated-pad friction, and pad mass to avoid unstable
acceleration with lightweight fixture pads. Friction credit is capped at 1.0
when sizing normal force; higher coefficients still improve contact but do not
erase the solver margin required by curved or eccentric grasps. Newton actuator prims live below
the generated articulation root so Newton discovers them before its first
physics cook. This control authoring is part of the temporary test fixture and
does not modify the tested asset.

For both runtimes, the fixture force is derived from every positive, finite
`PhysicsMassAPI` value below the tested asset, including values inside
instanceable runtime payloads. If the composed asset provides no usable mass,
the legacy bounding-box volume estimate is used and identified as a fallback
in the Kit log. The log records the selected source, number of authored mass
values, resolved mass, and generated jaw force so unexpectedly aggressive
fixture behavior can be diagnosed directly.

For multibody assets, motion and geometry measurements use the rigid body that
owns the current grasp identifier. Mass sizing still uses every authored mass
below the complete mounted asset, so connected bodies contribute to the load.
This prevents an unrelated wide body from determining the jaw aperture and
prevents motion of an ungrasped joint from being mistaken for grip instability.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| GripperPositioning timeout: gripper cannot reach the target within 2.0 s | The grasp identifier pose is inaccessible to the gantry, or the identifier path does not point at a graspable surface |
| Grasping fails: pads touched (no object) | The asset has no collision mesh at the grasp location, or the identifier targets empty space beside the asset |
| Lifting fails: object did not rise | Low friction, invalid mass, a grasp line outside the selected body's collider, or insufficient local contact prevents the gripper from holding the asset against gravity |
| HoldBeforeShake or HoldAfterShake fails: object dropped | The asset mass or friction is too low to sustain a 1.0 s static hold in the jaws |
| Shake fails: object left the jaws | The authored grasp midpoint separated from the live jaw midpoint by the configured tolerance, or the selected body reached the floor during the 0.01 m circular orbit; inspect mass, friction, collision, and grasp placement |
| Dropping fails: object did not fall after release | The asset is constrained in the scene or the physics configuration prevents free fall after the jaws open |
| Newton jaws do not close, or only one jaw is commanded | Verify that both generated `NewtonActuator` targets compiled and inspect the engine log for the explicit tensor-control diagnostic; ordinary contact can still produce different measured jaw positions while both targets remain symmetric |

## How to Fix

If the gripper cannot converge on a grasp identifier, inspect the identifier prim path and pose to confirm that it targets a surface on the asset rather than empty space or an interior point.

If grasping reports that the pads touched with no object, the asset is missing a collision mesh at the grasped region. Add or extend the collision approximation to cover the surfaces the pads are expected to contact.

If lifting or holding fails, check the authored mass and inertia and inspect the
active runtime's material friction values. Zero or non-finite mass properties
prevent valid dynamics, while low friction can let the asset slip from the grip.

If the shake phase fails, the same friction and mass remedies apply. Review the captured video: an asset that shoots sideways when the pads make first contact usually has misconfigured contact depth rather than low friction.

If an identifier is intentionally not graspable (for example, a side face that the asset author included but does not expect a gripper to use), remove that identifier from the asset rather than tuning physics to make it pass.

## Expected Result

![grasp-and-lift expected result](../_images/grasp-and-lift.png)

[Result video](../../../../_static/videos/grasp-and-lift.mp4)

For each grasp identifier on the asset, the parallel-jaw gripper moves to the identifier pose, closes around the asset, lifts it cleanly off the floor, holds it in mid-air, moves in a circular horizontal orbit, then opens to release. The asset follows the gripper lift motion without sliding out. An asset that slips during the lift or shake phase fails that grasp identifier.

## Notes and Caveats

The Shake phase tolerates ordinary rotation or limited shifting in the jaws, but fails when the authored grasp point separates from the live jaws by 0.05 m even if a nested PhysX bounding-box query does not report floor contact.

The Dropping phase does not check for ground penetration. Small objects can settle with their centroid at or slightly below Z = 0 due to contact tolerances, and that is not a failure of the grasp test. Ground penetration is evaluated separately by the FET003 Physics family.

A 0.3 s settle window (close_settle_seconds) is enforced after the close ramp before lifting begins. This allows the PD-driven gripper joints to physically converge against the asset. Without the settle window, tightly fitted or round assets can slip out when the lift command begins while the jaws are still moving.

Collision meshes are run exactly as authored. Inspect the active engine log for
runtime-specific collider cooking, approximation, or fallback diagnostics.
