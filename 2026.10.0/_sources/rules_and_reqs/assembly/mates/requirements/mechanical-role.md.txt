# mechanical-role

| Code     | MC.002 |
|----------|--------|
| Validator| MateSiteDeclarationChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

A mechanical mate site must author `simready:mate:domain = "mechanical"` and `simready:mate:role` of `Socket` or `Plug`. `Peer` is not part of this feature.

## Description

This requirement is scoped by `domain`. It applies to every mate site whose `domain` is `mechanical`. Sites in other domains (`electrical`, `network`, `thermal`, `airflow`, `pneumatic`) are still discovered by `MC.001` and are simply out of scope here; they are not failures. A multi-domain interface authored as co-located single-domain `Xform`s is therefore conformant, and a future domain feature can pin `MC.001` plus its own property rules without touching this one.

An asset with no mechanical mate site passes. This feature constrains the mate sites an asset has; it does not require an asset to expose one.

`Socket` and `Plug` are asymmetric. The plug either moves with the socket or is fused with it onto one compound body. `Peer` states that neither side is parent, which the pairing model in `CN.003` and `CN.006` cannot express.

## Why is it required?

- Asymmetric pairing is decidable; a peer constraint network is not.
- `domain` selects the property table, so the `simready:mate:mechanical:` rules (`MC.004`, `MC.006`) know which sites they govern.

## Examples

```usd
# Invalid: Peer on a mechanical site
def Xform "tool_mount_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Peer"
}

# Out of scope, not a failure: a non-mechanical site may use any role
def Xform "coolant_return_01"
{
    uniform token simready:mate:domain = "thermal"
    uniform token simready:mate:role = "Peer"
}

# Valid: arm flange receives a tool
def Xform "tool_mount_01"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Socket"
}

# Valid: stackable prop presents the face that seats into another
def Xform "stack_plug"
{
    uniform token simready:mate:domain = "mechanical"
    uniform token simready:mate:role = "Plug"
}
```

## How to comply

1. Set `domain` to `mechanical` on sites that mate mechanically.
2. Set `role` to `Socket` (receives) or `Plug` (is received).
3. Author a separate co-located `Xform` per additional domain rather than mixing tables on one prim.

## Related Requirements

- [mate-site-xform](mate-site-xform.md)
- [mechanical-interface](mechanical-interface.md)
- [opposite-roles](../../connections/requirements/opposite-roles.md)
