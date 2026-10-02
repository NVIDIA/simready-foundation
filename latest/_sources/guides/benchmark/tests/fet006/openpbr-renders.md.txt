# openpbr_renders  (FET006 Materials)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | openpbr_renders                |
| Feature(s)   | FET_006_OPENPBR                |
| Requirement  | VM.PBR.001                     |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.4.0                          |

## Summary

Measures how much of the asset a viewer sees shaded by the OpenPBR surfaces it authored on `outputs:mtlx:surface`. Two renders with Kit's render-context list pinned to `["mtlx"]`, differing only in the strength of one binding. Reads no other feature's surface, and the material network under test is left exactly as authored.

## What Pass Guarantees

Most of what the frame shows under `["mtlx"]` is shaded by a material of the asset's own, rather than by the material Kit substitutes when it finds none. The pin decides which surface those covered pixels are shaded by, so the reported frame is the OpenPBR one.

It does not decide what counts as covered. A material with no `outputs:mtlx:surface` falls back to its universal one and still wins over the control, so it reads as covered. Whether the OpenPBR surface exists and resolves is `VM.PBR.001`, which the validator answers exactly and ahead of this benchmark.

A pass does confirm that Kit built a MaterialX document for every material under the asset root, when Kit was launched with `--/persistent/app/material/materialx/validate=true`. Coverage cannot establish that on its own — a shader naming a nodedef that does not exist still wins over the weakly bound control and counts as covered — so this test reads the second half from the Kit log. Without the setting the run reports `mtlx_surface_materialx_validation: off` and says the question went unanswered.

A pass does not confirm the OpenPBR network produced a correct image.

A pass does not confirm the surface looks correct or has its intended textures. An asset migrated from MDL whose OpenPBR inputs are still constants renders flat beside its textured MDL surface, and that passes here by design.

## What It Checks

One number: the share of the asset's silhouette shaded by its own materials, with the render-context list pinned to `["mtlx"]`.

- **Silhouette.** A flat magenta control material bound on the asset's root prim with `bindMaterialAs = "strongerThanDescendants"` wins over everything below it, so every pixel the asset draws comes back magenta. That is the denominator, and cutting it out keeps the room out of the measurement.
- **Uncovered.** The same control bound with `bindMaterialAs = "weakerThanDescendants"` lets any binding the asset authored win, so magenta is left only where the asset binds nothing.

Coverage is `1 - uncovered / silhouette`. The floor is `min_material_coverage`.

Then one question the pixels cannot answer: whether the materials evaluated. With MaterialX validation on, Kit logs a line per material whose document it could not build, and the test fails on any under the asset root. `mtlx_surface_materialx_unresolved` reports the count and `mtlx_surface_materialx_validation` reports whether the check ran at all.

Each pass builds its own stage. Binding both strengths in turn on one live stage does not follow USD's binding-strength rules; the [family page](../fet006-materials.md#how-a-surface-is-measured) has the measurement.

The pin names `mtlx` and the measurement reads no other context, so the result does not depend on what the asset authored for MDL or for the universal context.

## How It Works

The asset's materials are never edited. The only thing authored is the flat magenta control, which is bound on the asset's root prim after the reported frame is captured, and unbound after each capture.

The control has a surface on all three render contexts, so it resolves under `["mtlx"]` as magenta rather than falling to Kit's default material, which is red.

The pin is read back from carb once the stage exists and compared entry for entry, so a setting that did not apply is reported as a failure to pin rather than measured as a surface result.

## Failure Cases

| Symptom | What it means |
|---|---|
| Coverage is low and `mtlx_surface_contexts_present` omits `mtlx` | No material bound to this geometry has a connected `outputs:mtlx:surface` |
| Coverage is low and the metric lists `mtlx` | Part of the geometry resolves a different material that has no OpenPBR surface, or resolves none at all |
| Failure to pin | The render-context list read back from carb did not match what was set, so nothing was measured |
| Silhouette too small | The camera did not frame the asset, or it has no renderable geometry of default or render purpose that is visible |

## How to Fix

Read `mtlx_surface_uncovered_pixels` against `mtlx_surface_silhouette_pixels` and look at the second frame: the magenta in it is the geometry to fix.

If no bound material has the surface, connect an OpenPBR surface to `outputs:mtlx:surface`, and connect it to the nodedef's declared output, which is `out` rather than `surface`. If materials are authored correctly but left in `/Looks`, or bound only to invisible, guide or proxy geometry, that is `VM.MAT.001`.

If the asset renders flat red where it should be shaded, the surface is authored and its network did not resolve. Check the shader's `info:id` names a node that is declared in the target environment, and that every texture the network references resolves on disk. `VM.PBR.003` catches the unresolved id statically, ahead of this benchmark.

## Expected Result

![openpbr_renders expected result](../_images/openpbr-renders.png)

Left, `sm_obs_joystick_a01_01` with the list pinned to `["mtlx"]`, shaded by its OpenPBR surface. Right, the same render with the magenta control bound underneath the asset's own bindings. No magenta shows, so every pixel resolves a material of the asset's: this asset measured 1.0 with zero uncovered pixels. The two panels come from separate stages, which is why the framing differs slightly between them.

Captured on Isaac Sim 6.0.1. The OpenPBR surfaces of these assets do not resolve on Isaac Sim 5.0 — pinned to `["mtlx"]` there, the toaster comes back at (0.702, 0.180, 0.180) and the workbench at (0.291, 0.136, 0.136), both the hue of the renderer's default material — so this test needs an engine that resolves them before its result means anything.

A flat, untextured result is a pass, and is what a sample whose OpenPBR inputs are still constants looks like through the same room, light rig, and camera:

![OpenPBR surface before and after sample migration](../_images/openpbr-migration-before-after.png)

Left, constant inputs. Right, the same prop after migration onto the OpenPBR contract. Both pass. This test measures how much of the object resolves a material of its own, so the difference between these two frames is outside what it judges, and that is why the captured frames are kept alongside the numbers.

## Notes and Caveats

The asset's materials are not edited. The test changes Kit's render-context list and binds one control material on the asset's root prim, so the network under test is measured as authored.

A material that is bound but does not evaluate still counts as covered: it wins over the weakly bound control the same way a working one does. `--/persistent/app/material/materialx/validate=true` names such a material in the Kit log. It is read at startup, so it belongs to how the runner launches Kit.

Pinning requires the pass to replace the stage after setting the value, because Kit reads the render-context list when a stage is attached. That reaches into framework internals the tests have no public call to re-seat, so a framework change to the scene handle's cached stage, its lighting manager, or the viewport binding will break this test at that point.

The reported surface inventory is of materials bound to renderable geometry. A material sitting in `/Looks` that nothing binds is not counted, because its surface never reaches a pixel.

Render context and binding purpose are different mechanisms. This test concerns render context, which selects the shader inside a material; binding purpose selects which material is bound to a prim.
