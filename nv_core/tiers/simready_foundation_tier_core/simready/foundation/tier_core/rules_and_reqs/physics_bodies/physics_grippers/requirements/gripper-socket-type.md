# gripper-socket-type

| Code     | GR.001 |
|----------|--------|
| Validator| CheckPrim |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Every gripper site prim must be an `Xform` with `token simready:attactment:socketType = "Gripper"` authored, positioned at the grasp center between the finger pads.

## Description

Gripper site prims are identified by the attribute `simready:attactment:socketType` set to the token value `"Gripper"`. The prim must be of type `Xform` and positioned at the midpoint between the finger contact surfaces in local space.

This attribute is the discovery mechanism for the Neutral format. Validators and tools traverse the asset hierarchy looking for Xform prims carrying this attribute. No proprietary schema or naming convention is required — any Xform prim with `socketType = "Gripper"` qualifies as a gripper site.

The `simready:attactment:socketType` attribute belongs to the `simready:attactment` namespace and expresses the semantic role of the prim as an attachment point. The value `"Gripper"` distinguishes gripper sites from other socket types (e.g. `"ToolChanger"`, `"Sensor"`).

> **Note:** The `simready:attactment` namespace spelling is intentional and matches the SimReady attachment schema convention.

## Why is it required?

- Provides a tool-agnostic, OpenUSD-compatible discovery mechanism that does not depend on prim naming.
- Enables prims with any name to serve as gripper sites, removing naming constraints from asset authors.
- The `socketType` token is machine-readable and extensible to other attachment point types.
- Multiple gripper sites on a single end-effector are supported — each must carry the attribute.

## Examples

```usd
# Invalid: wrong prim type
def Scope "grasp_point"
{
    token simready:attactment:socketType = "Gripper"
}

# Invalid: attribute missing — prim is not recognized as a gripper site
def Xform "gripper_01"
{
    double3 xformOp:translate = (0, 0.15, 0)
}

# Invalid: wrong token value
def Xform "grasp_point"
{
    token simready:attactment:socketType = "ToolChanger"
}

# Valid
def Xform "gripper_01"
{
    double3 xformOp:translate = (0, 0.15, 0)
    uniform token[] xformOpOrder = ["xformOp:translate"]
    token simready:attactment:socketType = "Gripper"
}

# Valid: prim name is unconstrained
def Xform "grasp_site_left"
{
    double3 xformOp:translate = (0, 0.15, 0)
    uniform token[] xformOpOrder = ["xformOp:translate"]
    token simready:attactment:socketType = "Gripper"
}

# Valid: multiple sites on one end-effector
def Xform "site_a"
{
    token simready:attactment:socketType = "Gripper"
}

def Xform "site_b"
{
    token simready:attactment:socketType = "Gripper"
}
```

## How to comply

1. Add `token simready:attactment:socketType = "Gripper"` to every gripper site prim.
2. Ensure the prim type is `Xform`.
3. Translate the prim to the grasp center position in local asset space.

## Related Requirements

- [gripper-forward-axis](gripper-forward-axis.md)
- [gripper-grip-line](gripper-grip-line.md)
- [gripper-max-opening](gripper-max-opening.md)

## For More Information

- [UsdGeomXform](https://openusd.org/dev/api/class_usd_geom_xform.html)
