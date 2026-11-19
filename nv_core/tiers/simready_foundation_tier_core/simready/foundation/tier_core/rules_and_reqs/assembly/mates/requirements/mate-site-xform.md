# mate-site-xform

| Code     | MC.001 |
|----------|--------|
| Validator| MateSiteDeclarationChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

A mate site is an `Xform` with authored `simready:mate:domain` and `simready:mate:role`. Those attributes are the discovery mechanism; prim names are unconstrained.

## Description

Validators and tools traverse the asset stage looking for `Xform` prims that author both tokens. Any other prim type that carries the attributes is not a mate site. Missing either attribute means the prim is not a mate site.

Unknown `domain` or `role` token values warn; they do not fail this requirement. Mechanical sites further constrain the values in [mechanical-role](mechanical-role.md).

## Why is it required?

- Discovery does not depend on prim naming.
- Multiple sites on one asset are supported.
- The same site object is reused across domains; `domain` selects the property table.

## Examples

```usd
# Invalid: wrong prim type
def Scope "tool_mount_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Socket"
}

# Invalid: role missing — prim is not a mate site
def Xform "tool_mount_01"
{
    uniform token simready:mate:domain = "mechanical"
}

# Valid
def Xform "tool_mount_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Socket"
}
```

## How to comply

1. Author each site as an `Xform`.
2. Set `uniform token simready:mate:domain` and `uniform token simready:mate:role`.

## Related Requirements

- [mechanical-role](mechanical-role.md)
- [mechanical-interface](mechanical-interface.md)

## For More Information

- [UsdGeomXform](https://openusd.org/dev/api/class_usd_geom_xform.html)
