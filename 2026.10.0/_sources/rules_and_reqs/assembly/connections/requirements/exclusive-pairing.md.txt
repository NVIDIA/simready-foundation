# exclusive-pairing

| Code     | CN.007 |
|----------|--------|
| Validator| ConnectionDeclarationChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

No mate site may appear in more than one connection: a socket holds at most one plug, and a plug sits in at most one socket.

## Description

Across all connection prims on the assembly stage, each site path used as a `socket` or `plug` target must be unique. Two connections sharing a socket (or a plug) fail.

Occupancy spans nesting. A composed-in assembly's own `Connections` scope, at any depth, occupies the sites it pairs, so an outer connection may not target them. A nested site that no connection pairs stays available to the outer assembly.

This is a static occupancy rule for the authored assembly. Runtime tool-change that destroys one joint and creates another is out of scope.

## Why is it required?

- A flange that already holds a gripper is not a free socket in this assembly snapshot.

## Examples

```usd
# Invalid: same socket used twice
def Scope "arm_to_gripper"
{
    rel simready:mate:socket = </Assembly/Arm/wrist_3_link/tool_mount_01>
    rel simready:mate:plug = </Assembly/GripperA/base_link/tool_plug_01>
}
def Scope "arm_to_other"
{
    rel simready:mate:socket = </Assembly/Arm/wrist_3_link/tool_mount_01>
    rel simready:mate:plug = </Assembly/GripperB/base_link/tool_plug_01>
}
```

```usd
# Valid: one connection per site
def Scope "arm_to_gripper"
{
    rel simready:mate:socket = </Assembly/Arm/wrist_3_link/tool_mount_01>
    rel simready:mate:plug = </Assembly/Gripper/base_link/tool_plug_01>
}
```

```usd
# Invalid: the socket is already paired by the nested stack's own connection
def Scope "stack_to_pallet"
{
    rel simready:mate:socket = </Assembly/CompoundBody/Stack_0/CompoundBody/Pallet_0/stack_socket>
    rel simready:mate:plug = </Assembly/CompoundBody/Pallet_3/stack_plug>
}
```

```usd
# Valid: the nested stack's top socket is unpaired inside it
def Scope "stack_to_pallet"
{
    rel simready:mate:socket = </Assembly/CompoundBody/Stack_0/CompoundBody/Pallet_2/stack_socket>
    rel simready:mate:plug = </Assembly/CompoundBody/Pallet_3/stack_plug>
}
```

## How to comply

1. Author one connection prim per occupied pair.
2. Use additional socket sites on the arm if it should hold more than one tool at once.

## Related Requirements

- [connection-rels](connection-rels.md)
