# socket-max-payload

| Code     | MC.006 |
|----------|--------|
| Validator| MechanicalSitePropertiesChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

A mechanical Socket mate site must author `simready:mate:mechanical:maxPayload` as a positive float. The value is always kilograms, regardless of stage units.

## Description

This attribute is required on mechanical sites with `role = Socket` only. Plugs do not author it; assembly capacity (`CN.005`) compares socket `maxPayload` to plug-subtree mass.

`maxPayload` is an author assertion of rated payload, not a derived mass. It is a property of the socket alone, so it is required even when no connection consumes it: `CN.005` skips compound connections, but a stackable part still states what its seating face is rated to carry.

## Why is it required?

- An asset is mate-ready when its socket states a rating, independent of anything currently attached.
- Kilograms match `SR.003`'s treatment of `mass`.

## Examples

```usd
# Invalid: missing on a Socket
def Xform "tool_mount_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Socket"
    uniform token simready:mate:mechanical:interface = "ISO-9409-1-50-4-M6"
}

# Invalid: non-positive
def Xform "tool_mount_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Socket"
    uniform token simready:mate:mechanical:interface = "ISO-9409-1-50-4-M6"
    float simready:mate:mechanical:maxPayload = 0
}

# Valid
def Xform "tool_mount_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Socket"
    uniform token simready:mate:mechanical:interface = "ISO-9409-1-50-4-M6"
    float simready:mate:mechanical:maxPayload = 10
}

# Valid: Plug omits maxPayload
def Xform "tool_plug_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Plug"
    uniform token simready:mate:mechanical:interface = "ISO-9409-1-50-4-M6"
}
```

## How to comply

1. On each Socket, author `float simready:mate:mechanical:maxPayload` in kilograms, greater than zero.
2. Derive the rating from the manipulator, flange, or load specification; do not invent it to force a pass.

## Related Requirements

- [payload-capacity](../../connections/requirements/payload-capacity.md)
