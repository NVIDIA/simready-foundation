# kinematic-chain-hierarchy

| Code     | HI.009 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`openusd`  |
| Tags     | {tag}`correctness` |

## Summary

For assets (e.g., a robot with multiple articulated joints), the hierarchy should reflect the kinematic chain, with appropriate Xforms for each transformable link.

## Description

Assets with posable bodies should organize their hierarchy to reflect the kinematic relationships between parts. Each transformable link in the kinematic chain should have its own Xformable prim. For links with multiple kinematic parents (such as four-bar linkages or Stewart platforms), one of the parents should be chosen as the hierarchical parent.

## Why is it required?

- Supports posing and placement
- Supports animation and rigging workflows
- Provides clear structure for robotic and mechanical systems

## Examples

```usd
#usda 1.0

# Valid: Robot arm with kinematic chain hierarchy
def Xform "RobotArm"
{
    def Xform "Base" (
    )
    {
        def Mesh "BaseMesh" {
            # Base geometry
        }
        
        def Xform "Shoulder" (
        )
        {
            float3 xformOp:rotateXYZ = (0, 0, 0)  # Shoulder joint rotation
            uniform token[] xformOpOrder = ["xformOp:rotateXYZ"]
            
            def Mesh "ShoulderMesh" {
                # Shoulder link geometry
            }
            
            def Xform "Elbow" (
                prepend apiSchemas = ["GeomXformCommonAPI"]
            )
            {
                float3 xformOp:translate = (0, 0, 0.3)  # Link offset
                float3 xformOp:rotateXYZ = (0, 0, 0)   # Elbow joint rotation
                uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ"]
                
                def Mesh "ElbowMesh" {
                    # Elbow link geometry
                }
                
                def Xform "Wrist" (
                    prepend apiSchemas = ["GeomXformCommonAPI"]
                )
                {
                    float3 xformOp:translate = (0, 0, 0.25)
                    float3 xformOp:rotateXYZ = (0, 0, 0)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ"]
                    
                    def Mesh "WristMesh" {
                        # Wrist geometry
                    }
                }
            }
        }
    }
}

# Not recommended: Flat hierarchy ignoring kinematic relationships
def Xform "RobotArm"
{
    def Mesh "ShoulderMesh" {
    }
    def Mesh "ElbowMesh" {
        # Unaffected by the Shoulder
    }
    def Mesh "WristMesh" {
        # Unaffected by the Wrist
    }
}
```

## How to comply

- Structure hierarchy to follow the kinematic chain from base to end-effector
- Create Xform prims for each transformable link in the chain
- Position joint transformation points at the actual joint locations
- For complex linkages with multiple parents, choose one as the hierarchical parent
- Use meaningful names that reflect the mechanical function of each link
- Ensure transformation order supports the intended motion

## For more information

- [Principles of Scalable Asset Structure in OpenUSD](https://docs.omniverse.nvidia.com/usd/latest/learn-openusd/independent/asset-structure-principles.html)