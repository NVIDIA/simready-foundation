# hierarchy-has-root

| Code     | HI.001 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`hierarchy-usd`  |
| Tags     | {tag}`essential` |

## Summary

All prims in the hierarchy must be direct or indirect descendents of a single root root prim, preventing scattered or disconnected Xform hierarchies.

## Description

This requirement ensures that all prims in the asset are properly organized under a single root or ancestor prim. This prevents scenarios where prims are scattered throughout the hierarchy without a clear connection to a common ancestor.

## Why is it required?

- Ensures a single, clear entry point for the entire prim hierarchy
- Prevents orphaned prims which will not inherit transformation or visibility from the root prim
- Maintains a clean and organized asset structure
- Enables reliable traversal and manipulation of the entire hierarchy

## Examples

```usd
# Invalid: Scattered Xforms without common root
def Xform "Xform1"
{
    def Xform "Child1" {}
}

def Xform "Xform2"  # Separate root Xform
{
    def Xform "Child2" {}
}

# Valid: All Xforms under single root
def Xform "RootXform"
{
    def Xform "Xform1"
    {
        def Xform "Child1" {}
    }
    
    def Xform "Xform2"
    {
        def Xform "Child2" {}
    }
}
```

## How to comply

- Ensure all prims in the asset are descendants of a single root prim
- Avoid creating separate or disconnected prim hierarchies
- Maintain a clear and organized hierarchy structure
- Verify that all prims can be reached from the root prim

## For More Information

- [USD Hierarchy Documentation](https://openusd.org/release/api/class_usd_prim.html)
- [USD Stage Traversal](https://openusd.org/release/api/class_usd_stage.html)
