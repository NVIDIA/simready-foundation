---
name: simready-foundation-conform-cap-105-isaac
description: "Repair CAP105_MaterialXRemoval.Isaac by removing MaterialX rendering while preserving or deriving USD Preview Surface shading."
license: Apache-2.0
---

# MaterialX removal

Use this skill for `CAP105_MaterialXRemoval.Isaac.0-1-0` / `OPT.004`, including
when selected by `Asset-Optimization@1.1.0`.

Read the capability manifest and page, `OPT.004` requirement, and
`asset_handler_modules/isaac_optimization/materialx_preview.py` in the installed
Isaac tier. Use the installed validation library's skill for validation.

1. Open the intended composition with its payloads loaded. Validate `OPT.004`;
   if it passes, leave the material unchanged.
2. Stage a copy that retains resolvable dependencies. Preserve source layers.
3. Record material bindings, universal Preview Surface and MDL networks, and
   material interface values.
4. Run `remove_materialx_shaders(input_stage, output_stage)` from
   `simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization`.
5. Save and reopen the staged output. Validate again and compare surviving
   networks and bindings. Preserve the report with the staged output.

An existing universal USD Preview Surface is preserved. Otherwise the adapter
derives a preview from supported OpenPBR / Standard Surface parameters and
textures. Explain that advanced shading is approximated. Unsupported
procedural graphs require an authored or baked preview; report the affected
shader instead of replacing it with guessed colors. Instanced or externally
shared graphs, and a universal surface from another shading system, require a
separate authoring step.

The adapter restores its edit layer on failure. Do not alter source assets or
run the other optimization adapters unless their capabilities are selected.
Only claim load-time savings when measured in the target runtime.
