# connection-targets-resolve

| Code     | CN.002 |
|----------|--------|
| Validator| ConnectionDeclarationChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Each `socket` and `plug` relationship target must resolve on the composed stage and satisfy `MC.001` and `MC.002`.

## Description

Follow the same resolve-and-confirm pattern as `JT.002`. A dangling relationship, a target that is not an `Xform` mate site, or a site that is not a mechanical Socket/Plug, fails.

This requirement is evaluated on the **assembly** composed stage, so child asset references must be loaded.

## Why is it required?

- A connection that points at a missing or non-mate prim cannot be simulated or swapped.

## Examples

```usd
# Invalid: target does not exist
rel simready:mate:socket = </Assembly/Arm/missing_site>
rel simready:mate:plug = </Assembly/Gripper/base_link/tool_plug_01>

# Valid: both targets exist and are mechanical Socket/Plug sites
rel simready:mate:socket = </Assembly/Arm/wrist_3_link/tool_mount_01>
rel simready:mate:plug = </Assembly/Gripper/base_link/tool_plug_01>
```

## How to comply

1. Reference the socket-bearing and plug-bearing assets onto the assembly stage.
2. Point the rels at the live mate-site prims, not at placeholder paths.

## Related Requirements

- [mate-site-xform](../../mates/requirements/mate-site-xform.md)
- [mechanical-role](../../mates/requirements/mechanical-role.md)
