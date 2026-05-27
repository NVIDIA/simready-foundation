# graspable-vector-line

| Code     | GSP.001 |
|----------|---------|
| Validator|                               |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential`              |

## Summary

In order for an asset to be considered graspable, an asset must have at least 1 line object defined within the asset. A line is at least 2 points in space, and this line must intersect the asset that needs to be grasped by the robotic grippers.

## Description

Graspable vectors are line representations that define how robotic grippers should approach and grasp an object. These lines serve as visual and functional guides for robotic manipulation systems, indicating the optimal approach vectors for successful grasping operations.

The lines can be authored using USD BasisCurves (recommended) or as mesh geometry. BasisCurves provide better runtime visualization support across different platforms, while mesh-based lines may have limited visibility depending on the runtime implementation.

## Why is it required?

- Robotic grippers need defined approach vectors to understand how to position themselves relative to the object
- Without grasp vectors, automated grasping systems cannot determine optimal gripper orientation and approach paths
- Grasp vectors enable consistent and reliable robotic manipulation across different simulation environments
- The vectors provide visual feedback for developers and users to understand intended grasping behavior

## Examples

```usd
# Invalid: Asset without grasp vectors
def Xform "CoffeeCup" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]
) {
   def Mesh "CupGeometry" (
      prepend apiSchemas = ["PhysicsCollisionAPI"]
   ) {
      # Missing grasp vectors - cannot be grasped by robots
   }
}

# Valid: Asset with BasisCurve grasp vectors
def Xform "CoffeeCup" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]
) {
   def Mesh "CupGeometry" (
      prepend apiSchemas = ["PhysicsCollisionAPI"]
   ) {
   }
   
   def BasisCurves "grasp_identifier_01" {
      # Grasp vector intersecting the cup handle
      point3f[] points = [(-0.05, 0.1, 0), (0.05, 0.1, 0)]
      int[] curveVertexCounts = [2]
      string type = "linear"
   }
}

# Valid: Asset with multiple grasp vectors
def Xform "ToolBox" (
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]
) {
   def Mesh "BoxGeometry" (
      prepend apiSchemas = ["PhysicsCollisionAPI"]
   ) {
   }
   
   def BasisCurves "grasp_identifier_01" {
      # Handle grasp vector
      point3f[] points = [(-0.2, 0.15, 0), (0.2, 0.15, 0)]
      int[] curveVertexCounts = [2]
      string type = "linear"
   }
   
   def BasisCurves "grasp_identifier_02" {
      # Side grasp vector
      point3f[] points = [(0.25, 0, -0.1), (0.25, 0, 0.1)]
      int[] curveVertexCounts = [2]
      string type = "linear"
   }
}
```

## How to comply

1. Create at least one line object within the asset that intersects the graspable geometry
2. Use USD BasisCurves for optimal runtime compatibility and visualization
3. Ensure the line has at least 2 points defining the grasp vector direction
4. Position the line to intersect with the part of the asset that should be grasped
5. Consider multiple grasp vectors for complex objects with different grasping options
6. Use descriptive names for grasp vector prims (e.g., "grasp_identifier")

## Related Requirements

- [Physics Rigid Body Capability](/capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-capability)
- [Physics Collision API](/capabilities/physics_bodies/physics_colliders/requirements/collider-approximation-sdf)

## For More Information

- [UsdBasisCurves Documentation](https://openusd.org/dev/api/class_usd_geom_basis_curves.html)
- [USD Physics Rigid Body Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_rigid_bodies)