# opposite-roles

| Code     | CN.003 |
|----------|--------|
| Validator| ConnectionDeclarationChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The two targets of a connection must have opposite roles: one `Socket` and one `Plug`.

## Description

The `socket` relationship must target a site with `role = Socket`. The `plug` relationship must target a site with `role = Plug`. Two sockets, two plugs, or swapped rels fail.

## Why is it required?

- The pairing is asymmetric. The plug moves with the socket, or is fused with it onto one compound body.

## Examples

```usd
# Invalid: both sites are Sockets
rel simready:mate:socket = </Assembly/ArmA/tool_mount_01>
rel simready:mate:plug = </Assembly/ArmB/tool_mount_01>

# Valid: jointed pairing
rel simready:mate:socket = </Assembly/Arm/wrist_3_link/tool_mount_01>
rel simready:mate:plug = </Assembly/Gripper/base_link/tool_plug_01>

# Valid: compound pairing
rel simready:mate:socket = </Stack/Pallet_0/stack_socket>
rel simready:mate:plug = </Stack/Pallet_0/Pallet_1/stack_plug>
```

## How to comply

1. Put the receiving asset's site on `simready:mate:socket` — the arm flange, the tool changer, the part beneath in a stack.
2. Put the received asset's site on `simready:mate:plug` — the tool, gripper, sensor, or the part that seats into it.

## Related Requirements

- [mechanical-role](../../mates/requirements/mechanical-role.md)
