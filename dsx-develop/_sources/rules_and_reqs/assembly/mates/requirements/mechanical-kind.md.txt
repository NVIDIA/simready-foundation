# mechanical-kind

| Code     | MC.007 |
|----------|--------|
| Validator| MechanicalSitePropertiesChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`portability` |

## Summary

If `simready:mate:mechanical:kind` is authored, its value should be one of `Tool`, `Gripper`, `Sensor`, `ToolChanger`, `ManipulatorFlange`. Unrecognized tokens warn; they do not fail.

## Description

`kind` is informational. Compatibility is `interface`, not `kind`. The list is allowed to grow without invalidating shipped assets, so this requirement is a warning.

The attribute is optional. Absence is not a warning.

## Why is it required?

- Catalogs and UIs can group sites without overloading `interface`.
- A warning on unknown tokens catches typos without freezing the vocabulary.

## Examples

```usd
# Warning: unrecognized kind
def Xform "tool_mount_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Socket"
    uniform token simready:mate:mechanical:interface = "ISO-9409-1-50-4-M6"
    uniform token simready:mate:mechanical:kind = "Flange"
}

# Valid: omitted
def Xform "tool_mount_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Socket"
    uniform token simready:mate:mechanical:interface = "ISO-9409-1-50-4-M6"
}

# Valid
def Xform "tool_mount_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Socket"
    uniform token simready:mate:mechanical:interface = "ISO-9409-1-50-4-M6"
    uniform token simready:mate:mechanical:kind = "ManipulatorFlange"
}
```

## How to comply

1. Omit `kind` unless it helps humans or tooling classify the site.
2. If authored, use a recognized token from the list above.

## Related Requirements

- [mechanical-interface](mechanical-interface.md)
