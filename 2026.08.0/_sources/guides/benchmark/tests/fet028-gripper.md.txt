# FET028 Gripper

Tests in this family verify that a gripper asset can close on a test object, lift it, shake it, and release it cleanly.

## Overview

This family exercises the gripper itself rather than an object being grasped. The test spawns a standard synthetic test object on the ground plane, opens the gripper, descends a Z-axis gantry onto the object, closes the gripper on the object, lifts it 20 cm using the gantry, shakes the gantry to perturb the grip, and then opens the gripper to verify the object is released. The gantry is a test-owned prismatic carrier attached to the gripper base by a fixed joint, so a fixed-base gripper is still fully exercised through all stages.

Two test objects serve as complementary stress cases. A sphere contacts each finger pad at a single point, making the grip friction-limited by a small normal-force lever arm; the sphere is therefore tested at 50 percent of the gripper's rated maximum payload. A cube has flat faces that produce larger contact patches, stressing grip strength rather than contact geometry; the cube is tested at 85 percent of the rated maximum payload.

The runtime covers parallel-jaw and centric mimic grippers as well as independent-finger hands. A conventional mimic jaw may expose one shared driven leader. A Newton-native parallel jaw may instead expose exactly two independently actuated leaders, one per jaw, when both leaders are explicit `NewtonActuator` targets and the authored grip line resolves their opposed pad branches. The test coordinates both leaders through the same normalized open-to-close motion. Arbitrary multi-master mechanisms are rejected rather than guessed. Joint traversal includes fixed-joint extensions when resolving the physical fingertip links. Invalid or non-finite authored site metadata and ambiguous live link transforms are likewise rejected rather than repaired by the harness.

The test does not require robot-specific prim, joint, actuator, or collider
names. It discovers the gripper site from its schemas and relationships,
resolves fingertip links through the joint graph, and treats collision shapes
at or below those fingertip prims as the contact surfaces. Its temporary lift
carrier uses a unique test-owned joint identity so an asset may use common DOF
names such as `joint_z` without being filtered or commanded accidentally.

## What a Passing Family Means

A reviewer, PM, or OEM can trust that the gripper closes with enough contact force and friction to retain a held object through a 20 cm lift and a 2-second sinusoidal perturbation, and that it releases the object cleanly on command. The two test objects cover complementary failure modes: the sphere reveals grippers that lack sufficient finger-pad friction for point contact, and the cube reveals grippers whose drive force is insufficient for the rated payload under flat-face loading. Each test is registered independently; the framework marks the feature FAIL if either test fails, regardless of the other test's outcome.

## Tests

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [gripper_close_lift_sphere](fet028/gripper-close-lift-sphere.md)
  - The gripper closes on a sphere at 50 percent of its rated payload and retains it through lift and shake.
  - FET_028_ISAAC
* - [gripper_close_lift_cube](fet028/gripper-close-lift-cube.md)
  - The gripper closes on a cube at 85 percent of its rated payload and retains it through lift and shake.
  - FET_028_ISAAC
:::

## Relationship to the Feature

This family validates the runtime behavior described by
[FET028 Gripper](../../../features/FET_028_ISAAC.md).

```{toctree}
:maxdepth: 1
:hidden:

gripper_close_lift_sphere <fet028/gripper-close-lift-sphere>
gripper_close_lift_cube <fet028/gripper-close-lift-cube>
```
