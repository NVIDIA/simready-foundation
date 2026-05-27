# logical-geometry-grouping

| Code     | HI.008 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`hierarchy-usd`  |
| Tags     | {tag}`usability` |

## Summary

Geometry should be grouped under parent Xforms in a way that is logical for the object's structure and intended use in layouts or simulations.

## Description

Assets should organize their geometry hierarchically under Xform prims that reflect the logical structure of the object. Parts that should move together shall be grouped under a common parent Xform. The hierarchy should facilitate navigation, selection, and manipulation while avoiding overly deep or unnecessarily complex structures.

## Why is it required?

- Enables logical selection and manipulation of asset components
- Facilitates navigation and understanding of asset structure
- Supports animation and simulation workflows
- Improves usability in content creation tools
- Enables efficient batch operations on related components

## Examples

```usd
#usda 1.0

# Valid: Logical grouping of chair components
def Xform "Chair"
{
    def Xform "Seat"
    {
        def Mesh "SeatSurface" {
            # Seat geometry
        }
        def Mesh "SeatCushion" {
            # Cushion geometry
        }
    }
    
    def Xform "Backrest"
    {
        def Mesh "BackrestFrame" {
            # Backrest frame geometry
        }
        def Mesh "BackrestCushion" {
            # Backrest cushion geometry
        }
    }
    
    def Xform "Legs"
    {
        def Mesh "FrontLeftLeg" {
            # Leg geometry
        }
        def Mesh "FrontRightLeg" {
            # Leg geometry
        }
        def Mesh "BackLeftLeg" {
            # Leg geometry
        }
        def Mesh "BackRightLeg" {
            # Leg geometry
        }
    }
}

# Invalid: Poor grouping with unnecessary complexity
def Xform "Chair"
{
    def Xform "Parts"
    {
        def Xform "Group1"
        {
            def Xform "SubGroup"
            {
                def Mesh "SeatSurface" {
                    # Overly nested structure
                }
            }
        }
    }
    def Mesh "BackrestFrame" {
        # Inconsistent grouping - some parts grouped, others not
    }
}
```

## How to comply

- Group geometry that moves together under common parent Xforms
- Use meaningful names for grouping Xforms that reflect their purpose
- Avoid overly deep hierarchies that complicate navigation
- Maintain consistent grouping patterns within the asset
- Consider the asset's intended use case when designing the hierarchy
- Group components that would be selected or manipulated together

## For more information

- [Principles of Scalable Asset Structure in OpenUSD](https://docs.omniverse.nvidia.com/usd/latest/learn-openusd/independent/asset-structure-principles.html)
- [UsdGeomXform Documentation](https://openusd.org/release/api/class_usd_geom_xform.html)
