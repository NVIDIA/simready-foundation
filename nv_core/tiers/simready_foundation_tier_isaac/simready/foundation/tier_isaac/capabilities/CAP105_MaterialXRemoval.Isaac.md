# MaterialX Removal

| Property | Value |
| --- | --- |
| Capability | `CAP105_MaterialXRemoval.Isaac.0-1-0` |
| Owning tier | Isaac |
| Requirement | [`OPT.004`](../rules_and_reqs/isaac_sim/optimizations/requirements/material-no-materialx-render-context.md) |
| Dependencies | None |
| Profile | [Asset-Optimization@1.1.0](../profiles/asset-optimization.md) |

Materials have no connected `mtlx` render-context outputs; matching is
case-insensitive. Assets without MaterialX materials pass unchanged.

Run `remove_materialx_shaders` on a staged copy. It preserves a connected
universal `UsdPreviewSurface` and MDL networks, removes the MaterialX context and
its private shader graph, and preserves material bindings and shared inputs.
Referenced shaders are disabled through local overrides, preserving source
layers. A universal surface from another shading system requires an authored
preview; the adapter preserves it and reports the conflict.

When no preview exists, the adapter derives one from OpenPBR or MaterialX
Standard Surface parameters and supported textures. USD Preview Surface
approximates advanced shading such as transmission, subsurface scattering and
anisotropy. Unsupported procedural graphs require an authored or baked preview.
The adapter refuses unsupported connections, instanced materials and graphs
shared with another render context. Failed repair restores the staged edit layer.

Save, reopen and validate using `Asset-Optimization@1.1.0`. Measure load-time
improvement in the target runtime.
