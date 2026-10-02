# mdl_renders  (FET006 Materials)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | mdl_renders                    |
| Feature(s)   | FET_006_MDL                    |
| Requirement  | VM.MDL.001                     |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.3.0                          |

## Summary

Measures how much of the asset a viewer sees shaded by the MDL surfaces it authored on `outputs:mdl:surface`. Two renders with Kit's render-context list pinned to `["mdl"]`, differing only in the strength of one binding. Reads no other feature's surface, and the material network under test is left exactly as authored.

## What Pass Guarantees

Most of what the frame shows under `["mdl"]` is shaded by a material of the asset's own, rather than by the material Kit substitutes when it finds none. The pin decides which surface those covered pixels are shaded by, so the reported frame is the MDL one.

It does not decide what counts as covered. A material with no `outputs:mdl:surface` falls back to its universal one and still wins over the control, so it reads as covered. Whether the MDL surface exists and resolves is `VM.MDL.001`, which the validator answers exactly and ahead of this benchmark. Static validation establishes that the shader names a `.mdl` file that exists and uses the current schema; it counts Gprims rather than pixels, so it cannot report how much of the object a viewer sees shaded by it.

A pass does not confirm the MDL module compiled. A module the runtime cannot load leaves the geometry on Kit's default material, which still wins over the weakly bound control and counts as covered. The captured frames show it: a red object is an unresolved surface.

A pass does not confirm the surface looks correct or has its intended textures.

## What It Checks

One number: the share of the asset's silhouette shaded by its own materials, with the render-context list pinned to `["mdl"]`.

- **Silhouette.** A flat magenta control material bound on the asset's root prim with `bindMaterialAs = "strongerThanDescendants"` wins over everything below it, so every pixel the asset draws comes back magenta. That is the denominator, and cutting it out keeps the room out of the measurement.
- **Uncovered.** The same control bound with `bindMaterialAs = "weakerThanDescendants"` lets any binding the asset authored win, so magenta is left only where the asset binds nothing.

Coverage is `1 - uncovered / silhouette`. The floor is `min_material_coverage`.

Each pass builds its own stage. Binding both strengths in turn on one live stage does not follow USD's binding-strength rules; the [family page](../fet006-materials.md#how-a-surface-is-measured) has the measurement.

The pin names `mdl` and the measurement reads no other context, so the result does not depend on what the asset authored for MaterialX or for the universal context. This matters more here than anywhere else in the family. A UsdPreviewSurface is usually baked down from the MDL surface it stands in for, so a measurement comparing them would compare an asset against its own copy.

## How It Works

The asset's materials are never edited. The only thing authored is the flat magenta control, which is bound on the asset's root prim after the reported frame is captured, and unbound after each capture.

The control has a surface on all three render contexts, so it resolves under `["mdl"]` as magenta rather than falling to Kit's default material, which is red.

The pin is read back from carb once the stage exists and compared entry for entry, so a setting that did not apply is reported as a failure to pin rather than measured as a surface result.

## Failure Cases

| Symptom | What it means |
|---|---|
| Coverage is low and `mdl_surface_contexts_present` omits `mdl` | No material bound to this geometry has a connected `outputs:mdl:surface` |
| Coverage is low and the metric lists `mdl` | Part of the geometry resolves a different material that has no MDL surface, or resolves none at all |
| Failure to pin | The render-context list read back from carb did not match what was set, so nothing was measured |
| Silhouette too small | The camera did not frame the asset, or it has no renderable geometry of default or render purpose that is visible |

## How to Fix

Read `mdl_surface_uncovered_pixels` against `mdl_surface_silhouette_pixels` and look at the second frame: the magenta in it is the geometry to fix.

If no bound material has the surface, connect one to `outputs:mdl:surface`, and check `info:mdl:sourceAsset` names a `.mdl` file that exists and `info:mdl:sourceAsset:subIdentifier` names a material in it. If materials are authored correctly but left in `/Looks`, or bound only to invisible, guide or proxy geometry, that is `VM.MAT.001`.

If the asset renders flat red where it should be shaded, the surface is authored and its module did not load. `VM.MDL.001` catches an unresolved source asset statically, ahead of this benchmark.

## Expected Result

![mdl_renders expected result](../_images/mdl-renders.png)

Left, `sm_gen_appliance_toaster_v01_01` with the list pinned to `["mdl"]`, shaded by its MDL surface. Right, the same render with the magenta control bound underneath the asset's own bindings. No magenta shows, so every pixel resolves a material of the asset's: this asset measured 1.0 with zero uncovered pixels. The two panels come from separate stages, which is why the framing differs slightly between them.

The room, light rig, and camera framing match [openpbr_renders](openpbr-renders.md) and [preview_surface_renders](preview-surface-renders.md), so the frames can be read side by side and any difference between them comes from the material.

## Notes and Caveats

The asset's materials are not edited. The test changes Kit's render-context list and binds one control material on the asset's root prim, so the network under test is measured as authored.

A material that is bound but does not evaluate still counts as covered: it wins over the weakly bound control the same way a working one does. `--/persistent/app/material/materialx/validate=true` names such a material in the Kit log, and applies to MaterialX only.

Pinning requires the pass to replace the stage after setting the value, because Kit reads the render-context list when a stage is attached. That reaches into framework internals the tests have no public call to re-seat, so a framework change to the scene handle's cached stage, its lighting manager, or the viewport binding will break this test at that point.

The reported surface inventory is of materials bound to renderable geometry. A material sitting in `/Looks` that nothing binds is not counted, because its surface never reaches a pixel.

Render context and binding purpose are different mechanisms. This test concerns render context, which selects the shader inside a material; binding purpose selects which material is bound to a prim.
