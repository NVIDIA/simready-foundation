# articulation-no-nesting

| Code     | JT.ART.002 |
|----------|---------|
| Validator| {oav-validator-latest-link}`jt-art-002` |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

Articulation roots cannot be nested.

## Description

Any prim of the USD scene graph hierarchy may be marked with an UsdPhysicsArticulationRootAPI. This informs the simulation that any joints found in the subtree should preferentially be simulated using a reduced coordinate approach. This should make it possible to uniquely identify a distinguished root body or root joint for the articulation. 

## Why is it required?

* A joint must be a part of exactly one articulation.

## Examples

```usd
# Invalid: Nested articulation root
def Xform "Xform" (
   prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
   def Xform "Xform" (
      prepend apiSchemas = ["PhysicsArticulationRootAPI"]
   ) {
   }
}

# Valid: Non-nested articulation root
def Xform "Xform"
{
   def Xform "Xform" (
      prepend apiSchemas = ["PhysicsArticulationRootAPI"]
   ) {
   }
}
```

## How to comply

Do not apply a UsdPhysicsArticulationRootAPI to a prim that is in a subtree of a prim with UsdPhysicsArticulationRootAPI already applied.

## For More Information

* [Articulations Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_articulations)
* [UsdPhysicsArticulationRootAPI Documentation](https://openusd.org/dev/api/class_usd_physics_articulation_root_a_p_i.html)
