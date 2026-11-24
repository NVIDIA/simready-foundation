# mechanical-interface

| Code     | MC.004 |
|----------|--------|
| Validator| MechanicalSitePropertiesChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Every mechanical mate site must author a non-empty `simready:mate:mechanical:interface` token.

## Description

`interface` is the catalog identity of the coupling: a published standard such as ISO 9409-1, a vendor product, or the interlock pattern of a stackable part. Compatibility on an assembly (`CN.004`) is exact string equality of this token on the socket and plug. Validators on a single asset only check that the token is present and non-empty; they do not check physical fit.

Sites in other domains are out of scope, as described in [mechanical-role](mechanical-role.md).

The token may imply electrical or pneumatic pass-through that is not modeled. Recommended form: `ISO-9409-1-<designation>` or `<vendor>-<product>`. The value set is open; a future warning-level prefix check is out of scope for this requirement.

## Why is it required?

- A published asset must state what it fits without referring to any assembly.
- Exact string equality is decidable without a tolerance policy.

## Examples

```usd
# Invalid: missing interface
def Xform "tool_plug_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Plug"
}

# Invalid: empty token
def Xform "tool_plug_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Plug"
    uniform token simready:mate:mechanical:interface = ""
}

# Valid
def Xform "tool_plug_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Plug"
    uniform token simready:mate:mechanical:interface = "ISO-9409-1-50-4-M6"
}
```

## How to comply

1. Author `uniform token simready:mate:mechanical:interface` with the published coupling designation.
2. Use the same spelling on both the socket-bearing and plug-bearing assets that are meant to mate.

## Related Requirements

- [interface-match](../../connections/requirements/interface-match.md)
- [mechanical-kind](mechanical-kind.md)
