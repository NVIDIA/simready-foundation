# stage-has-default-prim

| Code     | HI.004 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`hierarchy-usd`  |
| Tags     | {tag}`essential` |

## Summary

Stage must specify a default prim to define the root entry point.

## Description

The stage shall have a valid defaultPrim specified in the stage metadata. The defaultPrim shall identify the prim considered the root or entry point of the stage. The default prim shall be used by tools and systems to determine where to start traversing the stage hierarchy.

## Why is it required?

- Provides a consistent entry point for stage traversal
- Required by many USD tools and systems
- Helps with stage composition, assembly and referencing
- Essential for proper stage organization

## Examples

```usd
# Invalid: No defaultPrim specified
#usda 1.0
(
    metersPerUnit = 0.01
)

def Xform "World"
{
    def Cube "MyCube"
    {
        double size = 1.0
    }
}

# Valid: defaultPrim specified
#usda 1.0
(
    defaultPrim = "World"
    metersPerUnit = 1.0
)

def Xform "World"
{
    def Cube "MyCube"
    {
        double size = 1.0
    }
}
```

## How to comply

- Set the stage defaultPrim value in the stage metadata
- The specified prim shall exist in the stage

## For More Information

- [USD Stage Documentation](https://openusd.org/release/api/class_usd_stage.html)
- [USD Stage Metadata Documentation](https://openusd.org/release/api/class_sdf_layer.html)