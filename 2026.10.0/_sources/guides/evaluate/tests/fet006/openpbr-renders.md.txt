# openpbr_renders  (FET006 Materials)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | openpbr_renders                |
| Feature(s)   | `FET006_Materials.Openpbr.0-1-0`, `FET006_Materials.Openpbr.0-2-0`, `FET009_MaterialCoverage.0-1-0` |
| Requirement  | VM.MAT.001                     |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.5.1                          |

## Summary

Measures bound-material pixel coverage with Kit's render-context list pinned to
`["mtlx"]`. Three probes use a strong magenta silhouette and separate weak
magenta and cyan coverage controls.
The authored network is unchanged; a universal fallback may still be evaluated.
Each run also counts toward `FET009_MaterialCoverage`. The test records N/A when a complete material inventory
has no resolved OpenPBR surface. Unresolved material bindings, shader sources,
or incomplete test spheres remain unassessed. An asset with no geometry has each material
rendered on a test sphere, with no coverage measurement, and fails only on a MaterialX
document error; see
[A Material Published on Its Own](../fet006-materials.md#a-material-published-on-its-own).

## What Pass Guarantees

Measured bound-material coverage reaches `min_material_coverage` (default 98%)
with `["mtlx"]` selected. The pin requests OpenPBR, but it does not establish
which network successfully evaluated for every covered pixel.

It does not decide what counts as covered. A material with no
`outputs:mtlx:surface` falls back to its universal one and still wins over the
control, so it reads as covered. `VM.PBR.001` separately checks whether the
authored OpenPBR surface exists and resolves. This evaluation does not rerun
that validator or establish its result on a forced-feature diagnostic.

With `--/persistent/app/material/materialx/validate=true`, the additional check
fails on captured MaterialX document-build errors scoped under the asset root.
No matching captured error is not proof that every material built: an
unavailable log monitor/read can also provide no entries. Without the setting,
`mtlx_surface_materialx_validation: off` records that the check was not enabled.
Neither coverage nor this log check certifies complete shader evaluation.

A pass does not confirm the OpenPBR network produced a correct image.

A pass does not confirm the surface looks correct or has its intended textures. An asset migrated from MDL whose OpenPBR inputs are still constants renders flat beside its textured MDL surface, and that passes here by design.

## What It Checks

One number: the share of the asset's silhouette shaded by its own materials, with the render-context list pinned to `["mtlx"]`.

- **Silhouette.** A flat magenta control bound on a test-owned ancestor of the loaded asset with `bindMaterialAs = "strongerThanDescendants"` overrides asset bindings. Magenta dominance identifies the denominator and excludes the room.
- **Uncovered-color proxy.** Separate stages bind weak magenta and weak cyan controls on that fixture ancestor. Authored root, descendant and subset bindings can win unchanged. A pixel counts as uncovered only inside the strong silhouette and when it matches the respective probe color in both weak frames.

Coverage is `1 - uncovered / silhouette`. The floor is `min_material_coverage`.

A static authored magenta or cyan surface does not match both different weak
controls. This avoids treating that color alone as missing coverage, but the
classifier remains a pixel proxy, not direct binding or shader identification.
Inspect appearance and resolved bindings before proposing an asset repair.

Then one question the pixels cannot answer: whether the materials evaluated. With MaterialX validation on, Kit logs a line per material whose document it could not build, and the test fails on any under the asset root. `mtlx_surface_materialx_unresolved` reports the count and `mtlx_surface_materialx_validation` reports whether the check ran at all.

Each pass builds its own stage so renderer binding state is refreshed. The
disposable stage is de-instanced using checked session-layer edits before
capture. The strong control must resolve on geometry and subsets for all-purpose,
full and preview bindings; a legal stronger descendant binding is not itself
an error. Ineffective setup leaves execution incomplete, not an asset FAIL.
Source layers and material opinions are preserved. The
[family page](../fet006-materials.md#how-a-surface-is-measured) describes the
three-frame comparison and its limitations.

There is no cross-context image comparison gate. Universal fallback resolution
can still affect the rendered pixels under the pinned `mtlx` preference.

When no material that renderable geometry resolves at the `full` purpose declares an
`outputs:mtlx:surface`, the test skips after the silhouette pass. Kit would render each
material's universal surface in its place, which `preview_surface_renders` already
measures. `mtlx_surface_contexts_declared` records the contexts those materials declare.
`FET006_Materials.Openpbr` is optional wherever a profile selects it, so a skip does not
fail it or `FET009_MaterialCoverage`.

## How It Works

Asset networks and authored bindings are not edited. Flat controls bind on a
test-owned enclosing ancestor after the appearance frame is captured, and are
removed after each capture. A root-level authored material remains intact and
can win over the weak controls just as descendant bindings can.

Each colored control has a surface on all three render contexts, so it resolves
under `["mtlx"]` using its requested color rather than Kit's default material.

The pin is read back from carb once the stage exists and compared entry for entry, so a setting that did not apply is reported as a failure to pin rather than measured as a surface result.
A failed pin, unresolved fixture root, rejected required probe binding/cleanup
or unavailable/malformed/incompatible boolean mask leaves execution incomplete
with a setup/runtime error. A strong control silhouette below
`min_silhouette_pixels` is also incomplete execution: material coverage was
not measured with a qualified denominator. An actual qualified coverage
threshold violation remains a behavioral FAIL at the unchanged floor; available scoped MaterialX
document-build errors retain their separate evaluated gate.
An earlier execution error or cancellation remains primary even if a
secondary restoration diagnostic cannot be formatted or attached to an SDK
exception without `add_note`; optional notes cannot change that verdict.

## Failure Cases

| Symptom | What it means |
|---|---|
| The test skips and names the contexts the asset has a surface on | No material that renderable geometry resolves at the `full` purpose has an `outputs:mtlx:surface` |
| Coverage is low | Part of the geometry resolves no material from the asset's own bindings: a Gprim with no binding, or faces outside every `materialBind` subset of a Gprim with no binding of its own |
| Pin/control/mask setup raises an execution error | Nothing was measured; preserve the original context, binding, image or cleanup cause before assigning ownership |
| Silhouette too small | The camera did not frame the asset, or it has no renderable geometry of default or render purpose that is visible |

## How to Fix

Read `mtlx_surface_uncovered_pixels` against `mtlx_surface_silhouette_pixels`
and inspect both weak-color frames with the appearance and resolved bindings.
Counted pixels followed both controls inside the silhouette; that still does
not establish a particular binding or network defect without other evidence.

Bind the geometry that shows a control color in both weak frames. Where a Gprim has
`materialBind` `GeomSubset` children, faces outside every subset render with the material
the Gprim itself resolves, and `VM.MAT.001` checks only the subsets: bind the Gprim itself,
or make the subsets a partition of its faces. A binding authored only for the preview
purpose does not reach a final render; bind through `material:binding` or
`material:binding:full`. A material left in `/Looks`, or bound only to invisible, guide or
proxy geometry, is a `VM.MAT.001` defect too. `simready-foundation-conform-fet-009-standard` runs
the repair on staged output.

If the asset renders flat red where other shading was expected, inspect the
authored color, captured appearance and scoped MaterialX-log diagnostics before
assigning a network-resolution failure. An intentionally red asset can look
the same. Check the shader's `info:id` names a node declared in the target
environment and that referenced textures resolve. `VM.PBR.003` checks the
authored id separately; normal planning consumes prior validation evidence,
but a forced `--features` diagnostic can run with absent or failed validation.

## Expected Result

![openpbr_renders expected result](../_images/openpbr-renders.png)

Historical single-color illustration: left, `sm_obs_joystick_a01_01` with
`["mtlx"]` selected; right, its weak magenta-control frame. That recorded
fixture had proxy coverage 1.0. It does not include the current cyan control or
qualify the revised procedure on a native renderer. The separate-stage panels
do not establish that every binding or shader evaluated correctly.

Captured on Isaac Sim 6.0.1. The OpenPBR surfaces of these assets do not resolve on Isaac Sim 5.0 — pinned to `["mtlx"]` there, the toaster comes back at (0.702, 0.180, 0.180) and the workbench at (0.291, 0.136, 0.136), both the hue of the renderer's default material — so this test needs an engine that resolves them before its result means anything.

A flat, untextured result is a pass, and is what a sample whose OpenPBR inputs are still constants looks like through the same room, light rig, and camera:

![OpenPBR surface before and after sample migration](../_images/openpbr-migration-before-after.png)

Left, constant inputs. Right, the same prop after migration onto the OpenPBR contract. Both pass. This test measures how much of the object resolves a material of its own, so the difference between these two frames is outside what it judges, and that is why the captured frames are kept alongside the numbers.

## Notes and Caveats

The asset's networks and authored bindings are not edited. The test changes
Kit's render-context list and binds controls on a test-owned enclosing ancestor.

A material that is bound but does not evaluate still counts as covered: it wins over the weakly bound control the same way a working one does. `--/persistent/app/material/materialx/validate=true` names such a material in the Kit log. It is read at startup, so it belongs to how the runner launches Kit.

Pinning requires the pass to replace the stage after setting the value, because Kit reads the render-context list when a stage is attached. That reaches into framework internals the tests have no public call to re-seat, so a framework change to the scene handle's cached stage, its lighting manager, or the viewport binding will break this test at that point.

The reported surface inventory is of materials bound to renderable geometry. A material sitting in `/Looks` that nothing binds is not counted, because its surface never reaches a pixel.

Render context and binding purpose are different mechanisms. This test concerns render context, which selects the shader inside a material; binding purpose selects which material is bound to a prim.
