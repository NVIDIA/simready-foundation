# material-no-materialx-render-context

| Code | OPT.004 |
| --- | --- |
| Validator | |
| Compatibility | {compatibility}`OpenUSD` |
| Tags | {tag}`performance` |

## Summary

Materials must have no connected MaterialX render-context outputs.

## Description

The validator checks composed `UsdShade.Material` outputs in the `mtlx` render
context, ignoring case. Surface, displacement and volume connections all count.
Empty outputs blocked by a stronger layer pass.
The check includes materials in instance proxies. Materials with only universal
or MDL outputs pass unchanged.

## Why is it required?

MaterialX and OpenPBR networks can add shader compilation work during asset
loading in Isaac Lab. A portable USD Preview Surface supplies the rendering
fallback while the optimization removes the MaterialX context.

## How to comply

Run `remove_materialx_shaders` on a staged copy. Keep an existing universal USD
Preview Surface, or derive a preview from the authored OpenPBR / MaterialX
parameters and textures. Preserve MDL networks, material bindings and inputs
used by surviving shaders. Remove the MaterialX outputs and private shader
nodes, then save, reopen and validate.

Preview conversion approximates advanced shading. Unsupported procedural
connections require an authored or baked preview before automatic removal.
Failed repair restores the staged edit layer; it remains a validation failure.
