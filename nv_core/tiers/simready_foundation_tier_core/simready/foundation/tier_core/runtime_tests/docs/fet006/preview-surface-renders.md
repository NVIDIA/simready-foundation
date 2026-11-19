# preview_surface_renders  (FET006 Materials)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | preview_surface_renders        |
| Feature(s)   | `FET006_Materials.0-1-0`, `FET006_Materials.0-2-0`, `FET006_Materials.0-3-0`, `FET009_MaterialCoverage.0-1-0` |
| Requirement  | VM.MAT.001                     |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.5.1                          |

## Summary

Measures bound-material pixel coverage with the universal render context
selected. Three probe renders establish a strong magenta silhouette, then
weak magenta and cyan coverage controls.
The authored network is unchanged; coverage alone does not establish that the
UsdPreviewSurface successfully evaluated. Each run also counts toward
`FET009_MaterialCoverage`. The test never skips. An asset with no
geometry has each material rendered on a test sphere, with no coverage
measurement, and passes once the spheres render; see
[A Material Published on Its Own](../fet006-materials.md#a-material-published-on-its-own).

## What Pass Guarantees

Measured bound-material coverage reaches `min_material_coverage` (default 98%)
with the universal context selected. It does not certify correct shader
evaluation, textures or appearance for every covered pixel.

A pixel is counted as uncovered only when it lies in the silhouette and follows
both the magenta and cyan weak controls. From `FET006_Materials`
0-2-0, `VM.PS.002` checks separately whether the material a renderable Gprim
renders with connects a UsdPreviewSurface; this evaluation does not rerun that
validator or establish its result on a forced-feature diagnostic. Although the universal
context has no subsequent authored context fallback, a bound shader that
fails to evaluate can still count as covered.

UsdPreviewSurface is the portable baseline: the surface any renderer falls back to when it cannot evaluate MDL or MaterialX. The baseline holds only if that fallback draws over the whole object, and on an asset that also has MDL and OpenPBR it is the surface least likely to be exercised, because Kit's shipped order reaches it last.

A pass does not confirm the UsdPreviewSurface network is correct, only that a material of the asset's own resolved. It does not confirm the surface looks correct either — this is the low-fidelity representation and is expected to look simpler than the MDL or OpenPBR surface.

## What It Checks

One number: the share of the asset's silhouette shaded by its own materials, with the render-context list pinned to the universal context alone.

- **Silhouette.** A flat magenta control bound on a test-owned ancestor of the loaded asset with `bindMaterialAs = "strongerThanDescendants"` overrides asset bindings. Magenta dominance identifies the denominator and excludes the room.
- **Uncovered-color proxy.** Separate stages bind weak magenta and weak cyan controls on that same fixture ancestor. Authored root, descendant and subset bindings can win unchanged. A pixel counts as uncovered only inside the strong silhouette and when it matches the respective probe color in both weak frames.

Coverage is `1 - uncovered / silhouette`. The floor is `min_material_coverage`.

A static authored magenta or cyan surface does not match both different weak
controls. This avoids treating that color alone as missing coverage, but the
classifier remains a pixel proxy, not direct binding or shader identification.
Inspect the original appearance and resolved USD bindings before repair; do
not recolor a valid asset merely to satisfy a diagnostic control.

Each pass builds its own stage so renderer binding state is refreshed. The
disposable stage is de-instanced using checked session-layer edits before
capture. The strong control must resolve on geometry and subsets for all-purpose,
full and preview bindings; a legal stronger descendant binding is not itself
an error. Ineffective setup leaves execution incomplete, not an asset FAIL.
Source layers and material opinions are preserved. The
[family page](../fet006-materials.md#how-a-surface-is-measured) describes the
three-frame comparison and its limitations.

A failed context pin, unresolved fixture root, rejected control binding or
cleanup, and unavailable/malformed/incompatible probe masks are setup/runtime
errors: no material coverage verdict is established. A strong control silhouette
below `min_silhouette_pixels` also leaves execution incomplete: the denominator
cannot support a qualified material-coverage measurement. Its count remains
available for setup/framing diagnosis. With a qualified denominator, measured
coverage must still clear its unchanged floor.
An earlier execution error or cancellation remains primary even if a
secondary restoration diagnostic cannot be formatted or attached to an SDK
exception without `add_note`; optional notes cannot change that verdict.

There is no skip. Normal planning is feature-gated. An explicit `--features`
diagnostic can also select this test without a passed validation result; the
evaluation does not rerun or substitute for the static material checks.

## How It Works

The test pins before anything is built. Kit reads the render-context list when a stage is attached and the framework attaches one before the test body runs, so the test sets the value through `override_render_settings`, which re-asserts it before every capture, then creates a fresh stage to read it and builds the scene in that stage. The list is read back from carb and compared entry for entry, so a setting that did not apply is reported as a failure to pin rather than measured as a surface result.

The asset is loaded into the shared FET006 scene: a mid-grey room (color 0.35, 0.35, 0.35) lit by a directional light and a weak dome fill, framed with `auto_frame_camera`.

The appearance frame is captured before the control is bound and preserves
the asset's authored material resolution. Controls bind only on a test-owned
enclosing ancestor, never replacing the loaded asset root's own binding,
geometry bindings or material networks, and are removed after each capture.

The control has a surface on all three render contexts. All three, because each test in this family pins a different list and the silhouette has to be cut the same way under every one of them — a control with only a UsdPreviewSurface would fall to Kit's default material under `["mtlx"]`, which is red rather than magenta.

Whatever the outcome, a `finally` block restores the render-context list to the snapshot taken before the pin.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Coverage is low | Part of the geometry resolves no material from the asset's own bindings: a Gprim with no binding, or faces outside every `materialBind` subset of a Gprim with no binding of its own |
| Context pin, required control or mask fails with an execution error | No coverage was established; inspect the concrete setup/readback/cleanup cause, not the asset's material quality |
| The strong silhouette is below its prerequisite floor | Coverage was not measured; inspect camera framing, visible/default/render-purpose geometry and control setup before assigning an asset defect |
| Probe frames could not be measured | Required image/dependency/readback state is unavailable; execution is incomplete, not a measured material FAIL |

## How to Fix

Read `universal_surface_uncovered_pixels` against `universal_surface_silhouette_pixels`
and inspect both weak-color frames together with the appearance and resolved
bindings. Counted pixels followed both probes within the silhouette; that
still does not independently identify the missing binding or failed shader.

Bind the geometry that shows a control color in both weak frames. Where a Gprim has
`materialBind` `GeomSubset` children, faces outside every subset render with the material
the Gprim itself resolves, and `VM.MAT.001` checks only the subsets: bind the Gprim itself,
or make the subsets a partition of its faces. A binding authored only for the preview
purpose does not reach a final render; bind through `material:binding` or
`material:binding:full`. A material left in `/Looks`, or bound only to invisible, guide or
proxy geometry, is a `VM.MAT.001` defect too. `simready-foundation-conform-fet-009-standard` runs
the repair on staged output.

If the list could not be set, check that `/persistent/app/hydra/material/renderContexts` is writable in this Kit build, and restore it to the shipped `["mdl", "mtlx", ""]`. Kit writes this key to `user.config.json` on shutdown, so a value left behind by an earlier run persists across sessions and processes.

## Expected Result

![preview_surface_renders expected result](../_images/preview-surface-renders.png)

Historical single-color illustration: left, `sm_obs_workbench_tool_a01_01`
with the universal context selected; right, its weak magenta-control frame.
That recorded fixture had proxy coverage 1.0. It does not include the current
cyan control or qualify the revised procedure on a native renderer. The two
panels come from separate stages and do not prove every binding or shader
evaluated correctly.

The room, light rig, and camera framing match [openpbr_renders](openpbr-renders.md) and [mdl_renders](mdl-renders.md), so the frames can be read side by side.

## Notes and Caveats

The asset's networks and authored bindings are not edited. The test changes
Kit's render-context list and binds controls on a test-owned enclosing ancestor.

A material that is bound but does not evaluate still counts as covered: it wins over the weakly bound control the same way a working one does. `--/persistent/app/material/materialx/validate=true` names such a material in the Kit log, and applies to MaterialX only.

Pinning requires the pass to replace the stage after setting the value, because Kit reads the render-context list when a stage is attached. That reaches into framework internals the tests have no public call to re-seat, so a framework change to the scene handle's cached stage, its lighting manager, or the viewport binding will break this test at that point.

The reported surface inventory is of materials bound to renderable geometry. A material sitting in `/Looks` that nothing binds is not counted, because its surface never reaches a pixel.
