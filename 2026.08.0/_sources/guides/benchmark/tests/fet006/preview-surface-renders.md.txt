# preview_surface_renders  (FET006 Materials)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | preview_surface_renders        |
| Feature(s)   | FET_006_STANDARD               |
| Requirement  | com.nvidia.usd.VM.PS.001                      |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.4.0                          |

## Summary

Measures how much of the asset a viewer sees shaded by the UsdPreviewSurfaces it authored on the universal `outputs:surface`. Two renders with Kit's render-context list pinned to the universal context alone, differing only in the strength of one binding. The material network under test is left exactly as authored.

## What Pass Guarantees

Most of what the frame shows is shaded by a material of the asset's own, rendered through the universal context, rather than by the material a renderer substitutes when it finds none.

A pixel is uncovered when the geometry under it resolves no material of the asset's at all. Whether the UsdPreviewSurface itself exists and resolves is `com.nvidia.usd.VM.PS.001`, which the validator answers exactly and ahead of this benchmark. The universal context has nothing beneath it in USD's resolution chain, so on this one test a material that reaches it has no fallback left.

UsdPreviewSurface is the portable baseline: the surface any renderer falls back to when it cannot evaluate MDL or MaterialX. The baseline holds only if that fallback draws over the whole object, and on an asset that also has MDL and OpenPBR it is the surface least likely to be exercised, because Kit's shipped order reaches it last.

A pass does not confirm the UsdPreviewSurface network is correct, only that a material of the asset's own resolved. It does not confirm the surface looks correct either — this is the low-fidelity representation and is expected to look simpler than the MDL or OpenPBR surface.

## What It Checks

One number: the share of the asset's silhouette shaded by its own materials, with the render-context list pinned to the universal context alone.

- **Silhouette.** A flat magenta control material is bound on the asset's root prim with `bindMaterialAs = "strongerThanDescendants"`. It wins over everything below it, so every pixel the asset draws comes back magenta. Cutting it out by magenta dominance gives the denominator, and keeps the room out of the measurement.
- **Uncovered.** The same control is bound again with `bindMaterialAs = "weakerThanDescendants"`. Any binding the asset authored now wins, so magenta is left only where the asset binds nothing.

Coverage is `1 - uncovered / silhouette`. The floor is `min_material_coverage`.

Each pass builds its own stage. Binding both strengths in turn on one live stage does not follow USD's binding-strength rules; the [family page](../fet006-materials.md#how-a-surface-is-measured) has the measurement.

The test fails if the render-context list could not be set, or if the asset's stage path could not be determined, because neither state is measurable. It fails if the silhouette is below `min_silhouette_pixels`, because the ratio would be denominated in noise. Otherwise it passes when coverage clears the floor.

There is no skip. Planning is feature-gated — an asset whose profile does not have `FET_006_STANDARD` never picks this test up — so an asset that reaches this test has claimed the feature.

## How It Works

The test pins before anything is built. Kit reads the render-context list when a stage is attached and the framework attaches one before the test body runs, so the test sets the value through `override_render_settings`, which re-asserts it before every capture, then creates a fresh stage to read it and builds the scene in that stage. The list is read back from carb and compared entry for entry, so a setting that did not apply is reported as a failure to pin rather than measured as a surface result.

The asset is loaded into the shared FET006 scene: a mid-grey room (color 0.35, 0.35, 0.35) lit by a directional light and a weak dome fill, framed with `auto_frame_camera`.

The reported frame is captured before the control material goes on, so it shows nothing but the asset's own materials. The control is bound on the asset's root prim, never on the geometry and never on any of the asset's materials, and comes off after each capture.

The control has a surface on all three render contexts. All three, because each test in this family pins a different list and the silhouette has to be cut the same way under every one of them — a control with only a UsdPreviewSurface would fall to Kit's default material under `["mtlx"]`, which is red rather than magenta.

Whatever the outcome, a `finally` block restores the render-context list to the snapshot taken before the pin.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Coverage is low and `universal_surface_contexts_present` omits `universal` | No material bound to this geometry has an `outputs:surface`, so a viewer without MDL or MaterialX support draws it on its default material |
| Coverage is low and the metric lists `universal` | Part of the geometry resolves a different material that has no universal surface, or resolves none at all |
| The list could not be set | The setting is not writable in this Kit build; a value pinned by an earlier run survived into this one |
| The silhouette is below the floor | The camera did not frame the object; the asset has no renderable geometry of default or render purpose |
| The frames could not be measured | Pillow or numpy is not importable inside Kit |

## How to Fix

Read `universal_surface_uncovered_pixels` against `universal_surface_silhouette_pixels` and look at the second frame: the magenta in it is the geometry to fix.

For a missing UsdPreviewSurface, connect one to the universal `outputs:surface` and check the shader uses only spec-defined UsdPreviewSurface inputs and types. For a surface that is there but reaches nothing, check the material with that surface is bound to the geometry the frame is made of rather than left in `/Looks` or bound only to invisible, guide or proxy geometry (VM.MAT.001).

If the list could not be set, check that `/persistent/app/hydra/material/renderContexts` is writable in this Kit build, and restore it to the shipped `["mdl", "mtlx", ""]`. Kit writes this key to `user.config.json` on shutdown, so a value left behind by an earlier run persists across sessions and processes.

## Expected Result

![preview_surface_renders expected result](../_images/preview-surface-renders.png)

Left, `sm_obs_workbench_tool_a01_01` with the list pinned to the universal context, shaded by its UsdPreviewSurface. Right, the same render with the magenta control bound underneath the asset's own bindings. No magenta shows, so every pixel is the asset's own material: this asset measured 1.0 with zero uncovered pixels. The two panels come from separate stages, which is why the framing differs slightly between them.

The room, light rig, and camera framing match [openpbr_renders](openpbr-renders.md) and [mdl_renders](mdl-renders.md), so the frames can be read side by side.

## Notes and Caveats

The asset's materials are not edited. The test changes Kit's render-context list and binds one control material on the asset's root prim, so the network under test is measured as authored.

A material that is bound but does not evaluate still counts as covered: it wins over the weakly bound control the same way a working one does. `--/persistent/app/material/materialx/validate=true` names such a material in the Kit log, and applies to MaterialX only.

Pinning requires the pass to replace the stage after setting the value, because Kit reads the render-context list when a stage is attached. That reaches into framework internals the tests have no public call to re-seat, so a framework change to the scene handle's cached stage, its lighting manager, or the viewport binding will break this test at that point.

The reported surface inventory is of materials bound to renderable geometry. A material sitting in `/Looks` that nothing binds is not counted, because its surface never reaches a pixel.
