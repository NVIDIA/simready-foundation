# display_color_response  (FET010 Display Color)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | display_color_response         |
| Feature(s)   | `FET010_DisplayColor.0-1-0`       |
| Requirement  | DISP.001, DISP.003                 |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.4.5                          |

## Summary

Verdict fractions must be finite real numbers in `[0, 1]`; the color-dominance
ratio remains finite and positive, not capped at one. Camera padding/load
timeout are finite and positive; settling count is a nonnegative whole
number and required measurement counts positive whole numbers. Invalid
booleans, numeric strings or nonfinite values stop before scene mutation as
configuration errors. Existing defaults and valid explicit zero fractions
are preserved. A failed required image comparison supplies no calibrated
response; it is incomplete execution, not a measured zero or an asset defect.
An identical-material swap control can mask a presence floor even when its
noise remains below `max_control_ratio`. If that nonzero noise reaches the
applicable floor and the measured response does not exceed it, the comparison
is inconclusive (execution error), not PASS or an asset-response FAIL. This
applies to color and the all-omitting opacity case; the mixed/no-change opacity
policies are unchanged. Qualified low-noise responses below their configured
floor still FAIL, and a response above both floor and noise can PASS. Recorded
ratios and configured floors are preserved; no threshold is lowered.

Binds the material DISP.001's Guidance nominates over the whole asset and renders it with the primvar reader swapped in and out. A measurable part of the silhouette must render differently from the same surface driven by the reader's own fallback color as a constant, which is `primvars:displayColor` reaching the shader and driving pixels. A further frame asks the same of `displayOpacity`. Source assets are unchanged; instances are expanded only in the disposable measurement stage.

## What Pass Guarantees

**A pass means display color is live in the engine. It does not mean the asset is conformant.**

A passing result confirms that display colors this asset ships produce a
measurable response through the nominated material in the expanded test scene.
It does not establish that the original instance/subset rendering path works,
that every consumer behaves the same way, or that every Gprim carries a color.

It does not establish how many Gprims carry one. An asset with a display color
on one prim in fifty can pass if that visible response reaches
`min_response_ratio`, while other prims fail DISP.001. A tiny or hidden prim
resolving a value is not by itself sufficient for this pixel gate.

| Question | Answered by | How |
|---|---|---|
| Is `primvars:displayColor` authored, well formed, of the right type and element count? | DISP.001, DISP.002 — validator | Reads the file, per Gprim |
| Does every renderable Gprim resolve one? | DISP.001 — validator | Reads the file, per Gprim, and names the ones that do not |
| Do the values reach a renderer at all? | **This evaluation** | Renders the asset with the reader swapped in and out |
| Are the values the *right* colors? | Nothing | DISP.002 sets no plausibility band and says none is planned |

The third row is the renderer observation this evaluation adds. Its
[instance/subset qualification](#inherited-display-color-inside-an-instance)
must succeed before those observations can support a response verdict.

The opacity criterion depends on the recorded authoring case: an all-omit
asset must respond to changing the opacity fallback, while an all-author asset
must remain within the control-noise ceiling. Mixed authored/omitted opacity
is reported without a pass floor because occlusion can hide the affected
geometry; that case does not establish an opacity-response guarantee.

A pass does not judge whether the shipped colors are the *right* ones, and it asserts nothing about which of them is brighter than which. DISP.002 sets no plausibility band and says none is planned, on the grounds that Rec.709 weights blue at 0.0722 and a saturated navy computes a lower luminance than charcoal. Nothing here computes a luminance.
These presence claims assume the default positive response floors. A custom
zero floor retains its supported policy but cannot establish a nonzero
color/opacity response; inspect the recorded configuration and measurements.

## Why Coverage Is Not Measured Here

The ratio this test produces is denominated in **pixels**. DISP.001 is denominated in **Gprims**. The two come apart badly, and the fixtures show it directly:

| Fixture | Gprims resolving no display color | Response ratio |
|---|---|---|
| Toaster, a color on the body alone | 4 of 5 | 97.5% |
| Toaster, a color on the four small parts alone | 1 of 5 | 2.7% |

The same requirement is broken in both. The larger defect reads thirty-five times *higher*, because the body is most of the toaster's silhouette and the lever, tray, dial and cancel button are not. No floor on this ratio orders those two correctly, and any floor chosen to fail one of them either fails conformant assets or passes the other.

DISP.001 orders both correctly, per Gprim, and names the offending prims. So
coverage stays with static validation; this test adds whether the visible
render response reaches its configured floor. Normal planning consumes prior
validation evidence, but `--features` diagnostics can bypass absent or failed
validation. This test does not rerun or replace those static checks.

That is why both floors here sit where *nothing* separates from *something*, an order of magnitude above the render's own noise, rather than anywhere near full coverage.

## What It Checks

Three frames, all the same OpenPBR surface bound over the whole asset, plus a duplicate of the first that serves as the noise control. They differ only in what drives `base_color` and `geometry_opacity`:

The hidden-background capture precedes two visible warmup captures: Read,
then ReadControl. The measured sequence below starts only after both materials
have been primed. Warmup captures are not used in silhouette masks or pixel
comparisons. The summary video remains `read`, `removed`, `opacity`.

| Frame | `base_color` | `geometry_opacity` fallback |
|---|---|---|
| `read` | `displayColor` reader, fallback magenta | 1.0 |
| `read_control` | byte-for-byte what `read` is, through a second material | 1.0 |
| `removed` | flat magenta constant, no reader | 1.0 |
| `opacity` | `displayColor` reader, fallback magenta | 0.0 |

**Display color reaches the shader, and it is what drove the pixels.** `read` against `removed` is one comparison answering both. The two materials paint the same magenta — one as the reader's `inputs:default`, one as a constant with no reader behind it — so geometry that resolved a display color of its own renders that color in `read` and magenta in `removed`, and geometry that resolved none renders magenta in both. Any difference above the render's own swap noise is display color reaching the shader; the size of the difference is not asserted, for the reasons above.

**Display opacity reaches the surface.** `read` against `opacity` drops the opacity reader's fallback from `1.0` to `0.0`. Where no Gprim resolves a `displayOpacity` of its own, geometry should disappear, because every one of them was holding its opacity from that fallback. Where all of them do resolve one, nothing should change, because the fallback is never reached. Both are asserted as presence, not extent; a mixed asset is measured and reported without a floor, because the geometry that would disappear may be occluded by the geometry that would not.

How much of the silhouette goes with it is deliberately not asserted. The workbench tool renders at a mean of (0.059, 0.053, 0.050) against this test's black room, so an invisible copy of it differs from a visible one over less than half the silhouette. It measured 41.2 percent with the opacity reader working correctly, and the 90 percent floor this test used to carry failed a conformant shipping sample on nothing but how dark it is.

**The measured control is qualified.** A control frame renders `read` again
through a second material that duplicates it. Both frames sit on the far side
of a material swap and should agree within the configured control ceiling.
Exceeding that ceiling leaves the response unassessed; it does not establish
whether settling or renderer initialization caused the discrepancy. The same
ceiling applies to the DISP.003 no-change case.

The test skips when the asset has no renderable geometry.

## What Changed in 0.4.0

Coverage used to be a fourth frame, `altered`, which was `read` with the reader's fallback moved from magenta to green, and it was gated the other way up: geometry resolving nothing changed color between the two frames, so a *high* difference was the failure.

`read` against `removed` measures the same geometry from the opposite side, and it establishes causality at the same time, which `read` against `altered` does not. The green reader and its gate are gone. The adaptive coverage limit — `max(max_coverage_ratio, control × coverage_noise_multiple)` — went with them.

The deeper change is what replaced it. `altered` was an attempt to measure coverage in pixels, which is the wrong instrument for a per-Gprim requirement however it is gated, so the claim went back to the validator rather than being re-tuned here. Refer to [Why Coverage Is Not Measured Here](#why-coverage-is-not-measured-here). Two thresholds moved with it: `min_response_ratio` from 0.99 to 0.005 and `min_opacity_response_ratio` from 0.90 to 0.005, both now presence floors an order of magnitude above the render's own noise.

**One case the collapse can no longer tell apart.** Geometry whose authored display color *is* the probe's magenta renders identically in `read` and `removed` and is counted as unresponsive. Under `read` against `altered` it rendered magenta in both frames and was correctly counted as covered. Refer to [When the Asset's Own Color Is the Probe's](#when-the-assets-own-color-is-the-probes).

## How It Works

Before loading the asset, the fixture snapshots the incoming render-context
list, requests `["mtlx"]` through the tracked renderer-setting API, and creates
a fresh stage that reads it. The requested and effective lists are recorded
alongside the prior list. This setup works with an incoming `["mdl"]` list;
it does not require changing the user's persistent preferences. A rejected or
unreadable effective pin is an execution error before probe binding.

Before collecting renderable Gprims, the fixture iteratively clears
`instanceable` in the disposable stage's session layer, re-querying nested
instance roots after each composition change. It records
`display_color_test_scene_deinstanced_prims` and
`display_color_test_scene_instances_remaining`. Expansion errors or remaining
instances stop setup before geometry inventory or captures; they do not
establish an asset color failure. Required source layers and their material
binding opinions are not edited or saved.

The asset loads beneath the test-owned enclosing ancestor
`/World/_SimReadyDisplayColorAsset`. The probe binds one material there for
all-purpose, full and preview purposes with `strongerThanDescendants`, rather
than overwriting a source-authored binding on the asset root. Every required
binding acknowledgement and each renderable Gprim's resolved purposes are
checked before captures. Rejected setup or a purpose that does not resolve
the intended probe leaves execution incomplete, not an asset response FAIL.

Original asset-root, descendant, collection, subset and prototype binding
opinions are preserved. The wrapper must contain only the loaded asset;
foreign content or an unresolved wrapper is a setup error. The procedure
clears only its three wrapper bindings and restores the incoming context list
in `finally`, including failed captures and cancellation. Both cleanup actions
are attempted independently; a failure retires the uncertain worker, retaining
the first measurement or cleanup error. Tracked adapter teardown restores
original setting absence as well. Instanceability overrides belong to the
disposable session layer, not source geometry or layers. Host USD
regressions cover composition/cleanup, not current native renderer qualification.

After the hidden background capture, the fixed warmup sequence binds and
captures Read and ReadControl through the same qualified `swap` path used for
measured frames. It then rebinds Read for the first measured capture. Metrics
`display_color_probe_warmup_captures` and
`display_color_probe_warmup_sequence` record the two captures and their order.
They are not candidates from which the best control is selected. The original
settling defaults, renderer settings, silhouette floor, noise ceiling and
response floors remain unchanged. Excessive measured control noise still
leaves the test unassessed; a cold-start explanation does not override it.

The material is the one DISP.001's Guidance nominates: `ND_geompropvalue_color3` on `displayColor` into `base_color` and `ND_geompropvalue_float` on `displayOpacity` into `geometry_opacity`, both feeding `ND_open_pbr_surface_surfaceshader`. Using it means the evaluation measures what the specification asks authors to produce rather than the internals of whichever fallback a renderer ships. It is also what reaches DISP.003: Kit's own fallback for unbound geometry, `kit/mdl/rtx/Default.mdl`, declares a surface and no opacity term.

The fallback color is magenta rather than the plausible grey the Guidance suggests. A plausible grey is the right thing for an asset shipping the material and the wrong thing for a probe, because it is indistinguishable from a display color that resolved.

Every ratio is denominated in the asset's own silhouette, cut out of the `removed` frame, where the asset is flat magenta by construction, by magenta dominance. A whole-frame difference would also count the shadow the asset casts and the light it bounces onto the room, neither of which is the asset.

The scene is a black room lit by a dome alone. The effective test-owned
render-context list must read `["mtlx"]`; an unqualified pin is a setup execution
error, not a measured lack of color response. Required masks, captures and
compatible image shapes must be available. Invalid/missing observations
cannot become a zero response or PASS. A successfully measured response
below its configured floor retains the existing FAIL criterion.
A silhouette below `min_silhouette_pixels` cannot provide a qualified
comparison denominator, and control noise above `max_control_ratio` leaves
the comparison unqualified. Both leave execution incomplete rather than
establishing a completed asset-response FAIL. Nonzero control noise at or above
a presence floor also makes a response at or below that noise inconclusive,
even when the global control ceiling is satisfied. These controls prevent a
noise-only PASS and a missing-response FAIL where the required signal could
be masked. A genuinely below-floor response with control noise below that floor
retains its FAIL criterion. Keep their measured diagnostics and investigate
framing, fixture, material and settling conditions; these conditions do not
establish which component is at fault. Once those prerequisites are qualified,
the configured color/opacity response floors are unchanged.

## Where the Floors Sit

Measured on Isaac Sim 6.0, inside the asset's own silhouette. The response ratio is `read` against `removed`; the control is `read` against its duplicate; the opacity ratio is `read` against `opacity`. Both floors are 0.5 percent.

| Fixture | Gprims with a display color | Control | Response | Opacity | Result |
|---|---|---|---|---|---|
| Reference toaster, a color on each Gprim | 5 of 5 | 0.002% | 100.000% | 98.510% | PASS |
| Reference toaster, one constant on an ancestor `Xform` | 5 of 5 | 0.025% | 99.994% | 99.990% | PASS |
| Workbench tool | 11 of 11 | 0.000% | 100.000% | 41.210% | PASS |
| Joystick | 3 of 3 | 0.008% | 100.000% | 99.501% | PASS |
| Lamp | 4 of 4 | 0.000% | 99.999% | 99.924% | PASS |
| Light bulb | 1 of 1 | 0.009% | 100.000% | 100.000% | PASS |
| Toaster, a color on the body alone | 1 of 5 | 0.012% | 97.499% | 99.946% | PASS |
| Toaster, a color on the four small parts alone | 4 of 5 | 0.043% | 2.741% | 99.962% | PASS |
| Toaster, no display color anywhere | 0 of 5 | 0.055% | 0.076% | 99.996% | **FAIL** |
| Toaster, every color authored as the probe's magenta | 5 of 5 | 0.055% | 0.077% | 99.996% | **FAIL** |

The two partial fixtures pass, and that is the intended behaviour. Display color is doing something in the engine on both, which is all this evaluation is in a position to say. DISP.001 fails both in the validator, per Gprim, and names the prims: four of five on one, one of five on the other. Refer to [Why Coverage Is Not Measured Here](#why-coverage-is-not-measured-here).

The floor is where the two populations part. Everything with a display color reaching the shader read 2.7 percent or more; the two assets where nothing reaches it read 0.076 and 0.077 percent, and the worst control across every run was 0.055 percent. 0.5 percent is the geometric middle of 0.077 and 2.7 — six times the loudest inert run, five times under the quietest live one, and nine times the worst control.

The gap is narrower than the conformant column suggests. The quietest live run is 2.7 percent, not 97, because the geometry carrying a display color there is small. A floor picked from the conformant assets alone — anything at or above 5 percent — fails it.

Note that the two partial fixtures sit 35 times apart with the *larger* defect reading higher. That is the measurement being denominated in pixels rather than Gprims, and it is the whole argument for leaving coverage to the validator.

## When the Asset's Own Color Is the Probe's

Geometry whose authored display color is the probe's magenta renders identically in `read` and in `removed`, and this test reads it as geometry that resolved nothing.

Measured: a toaster with `primvars:displayColor = (1, 0, 1)` on an enclosing `Xform` reads 0.077 percent, against 0.076 percent for the same toaster with no display color at all. The two are indistinguishable in the number.

This is documented rather than mitigated, on four grounds:

1. It is a false **failure**, not a false pass. It costs an author an investigation; it does not ship a defect.
2. The failure is diagnosable from what the test already reports. The file-side count says every Gprim resolves a color, the message names the probe's constant, and the `read` frame shows a magenta object.
3. The probe's constant is pure saturated magenta, which is the color a pipeline uses to mean *missing*. A display color is meant to stand in for a material's albedo, and few assets ship that value deliberately.
4. Mitigating it costs more than it looks. A second `removed` frame at a different constant would detect it, but the silhouette is cut from the `removed` frame *because* it is flat magenta, so a second constant means either another swap and capture or decoupling the mask from the frame it is currently free with.

If it turns out to matter, the fix is the fifth frame: `removed` again at a different constant, with the asset required to respond to at least one of the two.

## A Dark Asset and the DISP.003 Floor

The workbench tool renders at a mean of (0.059, 0.053, 0.050) against the test's black room. Dropping the opacity reader's fallback to zero makes it invisible, and an invisible object and a very dark one differ by less than the 0.08 pixel threshold over most of the silhouette, so it measures 41.2 percent with the opacity reader working correctly.

Against the 90 percent floor this test carried through 0.3.1, that failed a conformant shipping sample on nothing but how dark it is. It was the clearest evidence that the DISP.003 floor was measuring the wrong thing: how much of the silhouette disappears is a property of the asset's colors and of the room it is rendered in, not of whether `displayOpacity` reaches `geometry_opacity`.

The floor is now 0.5 percent and the workbench tool passes with eighty times the margin. What still fails is an opacity reader that does nothing at all, which is the only thing this frame is in a position to establish.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Replacing the reader with a constant changes nothing, and the file says every Gprim resolves no `displayColor` | The asset carries none. This is DISP.001, and the validator names every prim |
| The same, and the file says every Gprim resolves one | Inspect expansion/warmup evidence, the actual probe captures, primvar interpolation/element counts/indices and the probe's magenta ambiguity; the response alone does not identify an asset defect |
| The test passes and the validator fails DISP.001 | Expected. Some display color reaches the renderer and some Gprims carry none; the validator is the coverage check |
| The asset covers too few magenta pixels | The camera did not frame the object; `primvars:displayOpacity` resolves to zero and the geometry renders invisible; or the probe material did not resolve |
| Dropping the opacity fallback to zero changed nothing on an asset that omits `displayOpacity` | The opacity half of the nominated material is not reaching `geometry_opacity` in this build |
| Dropping it changed something on an asset that authors `displayOpacity` everywhere | The authored value is not resolving, so geometry is taking the fallback |
| Some Gprim does not resolve the probe material | Required test-owned ancestor or purpose-specific probe setup failed; inspect recorded binding paths/purposes before blaming source authoring |
| Requested `["mtlx"]` is not retained after stage creation | Required renderer/context setup did not apply; inspect the effective-context metric and engine logs. The incoming user list is not an asset defect |
| Instances remain after expansion, or expansion fails | The disposable probe scene is unqualified; no display-color verdict was measured |
| The two renders of the same material differ | The measured control is unqualified; verify provider version, warmup evidence and captures before investigating renderer initialization or settling |
| Test skipped | The asset has no renderable Gprims |

## How to Fix

A response-gate failure means the changed-pixel ratio did not reach
`min_response_ratio`, not that no display color reached the renderer at all.
Inspect the response, noise-control, opacity case and captured frames before
assigning a cause. If missing color is confirmed, author `primvars:displayColor`
on the geometry, or on an ancestor with `constant` interpolation. Only constant
primvars are inheritable, so an ancestor value at another interpolation will
not reach the Gprim through inheritance.

For *which* prims are missing one, read the validator's DISP.001 result rather
than this test's number. A subset can satisfy the response gate only if its
visible pixels reach the configured floor and the control and applicable
opacity checks also pass; resolving a single value does not guarantee PASS.

If the file says every Gprim resolves one and the render disagrees, first
verify the actual test/provider version and its expansion/warmup metrics and
captures. Successful USD binding resolution does not by itself qualify native
probe rendering. Once fixture prerequisites are established, inspect the
primvar's type, interpolation, element count and indices, and the probe's magenta
ambiguity. Valid inherited colors are not an asset defect and need not be moved
onto geometry or prototype roots solely to accommodate this fixture.

If the asset covers too few magenta pixels, check `primvars:displayOpacity` before anything else. Geometry resolving an opacity of zero renders invisible under the nominated material whatever its display color says, and DISP.003 calls that out as a common artifact of an unconfigured export.

If the two renders of the same material differ beyond the control ceiling, no
response verdict is established. Compare warmup and measured captures before
attributing the condition to settling: first-visible-probe initialization can
also differ from subsequent identical states. Longer settling is not a proven
repair for that condition. Do not weaken the noise ceiling or retune colors to
hide it.

## Expected Result

![display_color_response expected result](../_images/display-color-response.png)

The reference toaster shaded by the material DISP.001 nominates, driven by the `primvars:displayColor` it ships. The dark lever and dial against the pale body are the primvar's doing; the OmniPBR materials the asset binds are all overridden by the probe.

On this sample all 5 renderable Gprims resolved the probe material through the single root binding, and the asset covered 294,812 silhouette pixels.

| Measurement | Result | Limit |
|---|---|---|
| Two renders of the same material | 0.002% of the silhouette | below 2% |
| Replacing the reader with a constant | 100.0% | above 0.5% |
| Dropping the opacity fallback to zero | 98.5% | above 0.5% |

The two results sit three orders of magnitude above their floors, and that is the normal shape of a pass here rather than a close call. The floors are set to separate *something* from *nothing*; on an asset where the feature works at all they are not close.

No Gprim on this asset resolves a `primvars:displayOpacity`, so every one of them holds its opacity from the reader's `inputs:default` of `1.0`, and dropping that default to `0.0` took 98.5 percent of the silhouette with it. That is DISP.003 covered by render: the primvar reaches `geometry_opacity`, and the default is what keeps geometry omitting it opaque.

Run the same test against the same asset before its display colors were authored and replacing the reader with a constant moves 0.076 percent instead of 100 percent, below the floor, and the test fails. The `read` frame is then a magenta toaster.

## Inherited Display Color Inside an Instance

DISP.001 permits constant display colors inherited from ancestors. An empty
or partial probe response on instanced material subsets does not establish
that valid inheritance is broken: the renderer can still draw the source
subset material even when USD resolves the strong ancestor probe binding.

The fixture therefore expands nested instances in its disposable session
layer before inventorying geometry. A successful run measures this expanded
scene. It does not certify original instanced rendering or its performance,
and it does not justify de-instancing the source asset or relocating valid
primvars as an asset-repair workaround. The static validator remains the
authority for per-Gprim resolved coverage and authored value validity.

## Notes and Caveats

Nothing here compares one Gprim's rendered brightness with another's, and nothing compares a pixel with an authored value. DISP.002 rules out the first two kinds of claim and RTX tone-mapping rules out the third. An earlier version of this test asserted a per-Gprim rendered-luminance ordering; that assertion is gone and nothing has replaced it.

The test does not require the asset to carry more than one display color. DISP.001 explicitly allows one constant value on an enclosing `Xform` or `Scope`, and an asset shaped that way passes here with no variation to measure.

Per-Gprim coverage is not measured here. The static validator checks DISP.001;
this test adds sampled renderer response at the configured pixel floor, as
[What Pass Guarantees](#what-pass-guarantees) explains. A forced-feature run
does not establish that validation passed.

The pixel threshold is 0.08 rather than the 0.04 the material tests use. Every signal here is a swap between saturated colors: magenta against the asset's own color, opaque against invisible. A material swap, meanwhile, costs the path tracer its accumulated history and lands it on a different noise realisation. Measured on the two-box fixtures, that noise was 4.0 percent of the silhouette at 0.04 and 0.05 percent at 0.08, with every real signal still at 100 percent.

The test adds its materials and strong all-purpose/full/preview bindings on
a test-owned enclosing ancestor in the disposable stage. The bindings are
cleared on every exit; source root/descendant opinions remain intact. It
preserves authored primvars, source geometry and source layers. Its temporary
instanceability overrides stay in the disposable session layer. Historical
Isaac Sim 6.0 pixel examples above do not qualify
the revised fixture on every current renderer/runtime.

Display color itself has no material surface. Its nominated OpenPBR probe does,
so the fixture uses the tracked context-pinning helper also used by
[FET006 Materials](../fet006-materials.md). It selects `mtlx` for the probe
without changing the asset's material networks or response thresholds.
