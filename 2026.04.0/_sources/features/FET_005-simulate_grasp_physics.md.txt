# Feature: `ID:005 - Simulate Grasp Physics - Base`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Internal ID             | `FET005_BASE_NEUTRAL`|


## Description
Support for grasping feature. This feature enables a prop to be considered "graspable".  Conditions to pass are related to colliders, physics materials, and rigid bodies.

The graspable feature comprises a list of requirements that enable whether or not a particular prop is graspable via robotic grippers. It is worth noting that graspable feature requires a runtime test component to identify if the grasp vectors are indeed correct.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products that consume this feature:

- IsaacSim
- MEGA
- Lightwheel SOW1

## Neutral Format
### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Prop Robotics Neutral Profile](../profiles/prop-robotics-neutral.md)** (v0.1.0) - Used for graspable vector support and robotic gripper compatibility
- **[Prop Robotics Physx Profile](../profiles/prop-robotics-physx.md)** (v0.1.0) - Used for PhysX-optimized grasping simulation and advanced gripper physics

#### Requirements

* Capability: [Physics_Bodies/Physics_Graspable](../capabilities/physics_bodies/physics_graspable/capability-physics_graspable.md)
  * Requirements:
    * [Graspable-Vector-Line](../capabilities/physics_bodies/physics_graspable/requirements/graspable-vector-line.md)
      * GSP.001 | Version 0.1.0

### Comments
* Need Physx CCD on smaller meshes potentially, would need new Physx capability for this
* Working out how to specify rubber physics material (friction is being worked out by Isaacsim and Physx folks)
* Collider Convex Hull will not work properly, need to be Convex Decomp + Shrink wrap (or custom collider)
* More discussions will follow

</details>
