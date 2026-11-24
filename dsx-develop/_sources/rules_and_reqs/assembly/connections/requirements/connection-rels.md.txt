# connection-rels

| Code     | CN.001 |
|----------|--------|
| Validator| ConnectionDeclarationChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The assembly default prim has a `Connections` Scope. Each connection prim under it authors exactly one `simready:mate:socket` relationship and exactly one `simready:mate:plug` relationship, each with exactly one target.

## Description

Connection prims are descendants of `<defaultPrim>/Connections` that author `simready:mate:realization` and/or the socket and plug relationships. The recommended type is `Scope`.

This feature pairs sites with the asymmetric socket/plug rels. The two-`simready:mate:site` form used for `Peer` pairings is not covered.

A missing `Connections` Scope, or a connection prim with zero/multiple targets on either rel, fails.

## Why is it required?

- Pairing is declared on the assembly, not on the mate sites.
- Single-target rels keep the remaining connection checks decidable.

## Examples

```usd
# Invalid: neither rel present
def Scope "Connections"
{
    def Scope "arm_to_gripper"
    {
        uniform token simready:mate:realization = "jointed"
    }
}

# Valid
def Scope "Connections"
{
    def Scope "arm_to_gripper"
    {
        uniform token simready:mate:realization = "jointed"
        rel simready:mate:socket = </Assembly/Arm/wrist_3_link/tool_mount_01>
        rel simready:mate:plug = </Assembly/Gripper/base_link/tool_plug_01>
        rel simready:mate:joint = </Assembly/Connections/arm_to_gripper_joint>
    }
}
```

## How to comply

1. Create `Scope "Connections"` under the assembly default prim.
2. For each pairing, add a child prim with one `socket` rel and one `plug` rel.

## Related Requirements

- [connection-targets-resolve](connection-targets-resolve.md)
- [mate-realization](mate-realization.md)
- [exclusive-pairing](exclusive-pairing.md)
