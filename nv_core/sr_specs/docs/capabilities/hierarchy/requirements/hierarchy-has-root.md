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

Omniverse may inject a render-settings scope at `/Render` (often with `no_delete` and `hide_in_stage_window` metadata) when an asset is opened or saved in Kit. HI.001 excludes this well-known render-settings scope from the single-root count so authors do not need to manually strip a prim the authoring tool adds automatically. If `/Render` contains asset content such as Xforms, geometry (meshes), or materials, it is treated as a real root prim and counted normally.

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
- Do not manually remove the Omniverse-generated `/Render` render-settings scope; HI.001 ignores it when counting root prims unless it contains asset Xforms, geometry, or materials
- Avoid creating separate or disconnected prim hierarchies
- Maintain a clear and organized hierarchy structure
- Verify that all prims can be reached from the root prim

## For More Information

- [USD Hierarchy Documentation](https://openusd.org/release/api/class_usd_prim.html)
- [USD Stage Traversal](https://openusd.org/release/api/class_usd_stage.html)
