---
name: simready-foundation-conform-fet-010-standard
description: "Use for repairing exact FET_010_STANDARD SimReady conformance for display colour (`primvars:displayColor`) on renderable geometry. Use when a profile, validation report, or user request names FET_010_STANDARD, DISP.001 or DISP.002; default to version `0.1.0` unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Jens Jebens <jjebens@nvidia.com>"
  tags:
    - simready
    - conformance
    - display-color
---

# SimReady Conform FET_010_STANDARD

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request
names `FET_010_STANDARD`. It authors or repairs `primvars:displayColor` on renderable
geometry without touching the shaded surfaces, which are the sibling contracts
`FET_006_STANDARD` (UsdPreviewSurface), `FET_006_MDL` and `FET_006_OPENPBR`.

Default to `FET_010_STANDARD@0.1.0` when the user asks for this feature without a
version. Use another version only when the profile, validation report, or user explicitly
pins it. If the report names a different `FET_###_RUNTIME` feature, switch to that feature's
matching skill before editing.

Display colour is the appearance layer available to a consumer that does not evaluate
materials, so it is repaired independently of them and can be repaired on an asset that has
no material at all. What it cannot do is invent one: the colour is derived from a bound
material, and geometry with nothing to derive from is reported rather than given a guess.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_010_STANDARD-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_010_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/visualization/display_color/requirements/display-color-coverage.md` (DISP.001)
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/visualization/display_color/requirements/display-color-values.md` (DISP.002)

Treat the JSON manifest as authoritative for requirement IDs. Use the feature markdown for
contract details, requirement links, samples and benchmarks. The Display Color capability
and its feature manifest land with the capability change; if they are not on the branch you
are working from, read them from the branch that introduces them before editing an asset.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | None | `DISP.001`, `DISP.002`, `DISP.003` |

`DISP.003` covers `primvars:displayOpacity`, which is optional and which this skill does not
author. An asset that carries no display opacity satisfies it.

## Bundled script

`assets/scripts/author_display_color.py` authors a constant `primvars:displayColor` on every
renderable Gprim, derived from the material bound to that Gprim.

```bash
# report DISP.001, DISP.002 and DISP.003 conformance, change nothing
python author_display_color.py <path> --verify

# show what would change
python author_display_color.py <path> --dry-run

# author, sampling base colour maps
python author_display_color.py <path>

# author from material constants only, never opening a texture
python author_display_color.py <path> --no-textures

# author into each Gprim's material:binding layer, which reaches instanced geometry
python author_display_color.py <path> --edit-target binding
```

### Options

| Option | Default | What it does |
|---|---|---|
| `--verify` | off | Report `DISP.001`, `DISP.002` and `DISP.003`. Writes nothing. |
| `--dry-run` | off | Report what a run would author. Writes nothing. |
| `--textures` | **on** | Sample base colour maps over the bound faces. Naming it changes nothing; it is the default. |
| `--no-textures` | off | Derive from material constants only, never opening a texture. |
| `--edit-target stage` | **default** | Author on the composed stage. Geometry inside an instance is out of reach. |
| `--edit-target binding` | off | Author into the layer holding each Gprim's `material:binding`, which is where instanced geometry can be written at all. |

`--edit-target binding` is what a referenced or instanced asset needs. On the Audi A6
vehicle sample the default reaches 5 renderable Gprims and leaves 16 inside 9 prototypes
untouched; `binding` reaches all of them, authoring 15 opinions that 17 Gprims resolve,
because instances share one.

`<path>` is a USD file or a directory, which is searched for `simready_usd` assets. The
script needs USD Python (`pip install usd-core`). Sampling additionally needs `numpy` and
`Pillow`; without them the script says so and falls back to `--no-textures` behaviour, which
on this library authors almost nothing. See **What `--no-textures` actually gives you** below.

`--verify` and `--dry-run` are rejected together. `--verify` already changes nothing, so
`--dry-run` alongside it would guard a run that was never going to write; the script says
which flag to drop rather than accepting the pair and ignoring one.

It is safe to re-run. Every value is re-derived from scratch on each pass and the derivation
is deterministic, so a second run over an unchanged asset leaves the same colour on the same
prim. Sampling uses a fixed stratified point set rather than a random one for exactly this
reason: a random sequence would move every value slightly on every pass and rewrite all
fourteen sample assets each time. Re-running still rewrites the binary layer, so compare
flattened USD rather than file hashes when checking that a re-run changed nothing.

Exit codes, so a script driving this can tell a crash from a finding:

| Code | Meaning |
|---|---|
| `0` | clean |
| `1` | `--verify` found DISP.001, DISP.002 or DISP.003 problems |
| `2` | bad arguments, or no USD assets under the given paths |
| `3` | at least one asset could not be read or raised |

An asset that raises is reported as `ERROR` with its traceback on stderr, and the walk
carries on to the rest.

### What `--verify` checks

Whether a renderable Gprim resolves a display colour at all; whether the resolved value
carries the `color3f[]` that `UsdGeomGprim` declares, including the two ways a scalar gets
past a type check (authored on an enclosing `Xform`, or authored on the Gprim itself, where
the schema's own type name hides it); component range and finiteness; element count against
the declared interpolation and the prim's topology; and, on an indexed primvar, the index
count against topology and every index against the value array. Where a primvar carries only
time samples, the earliest authored sample is what gets checked, which is what DISP.002 says.

`primvars:displayOpacity` is checked on the same terms, so DISP.003 is reported even though
this skill never authors it. A preflight that says `ok` on an asset the capability validator
fails is worse than no preflight.

All of it is transcribed from the capability validator at
`nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/visualization/display_color/validation.py`,
which a standalone run cannot import: it needs `simready.foundation.tier_core.requirements`
and `usd_validation_nvidia`, and their absence is why this preflight exists. Each function in the script names the validator
method it mirrors. Change one, change the other.

### Which layer the primvar is authored in

Under `--edit-target binding`, the layer holding the strongest binding opinion for that
Gprim, resolved through `UsdShade.MaterialBindingAPI` so a binding authored per purpose
(`material:binding:full`, `material:binding:preview`) counts the same as a plain one.
Where the geometry carries no binding of its own, an ancestor's is used: the primvar is
authored with `constant` interpolation, which inherits down namespace. Display colour is an attribute, so it belongs where this asset's existing
opinion about the prim's appearance is expressed -- which is not always where the prim is
defined, since a stronger layer often holds an `over` for a transform or visibility and
says nothing about appearance.

It also resolves instancing. A Gprim reached through an instance proxy cannot be authored
at the path it appears on, and its prototype path is not persistent. The binding's
property spec names both the layer and the path within it, which is where the opinion has
to go for every instance to inherit it. Reading that property stack needs the prim inside
the prototype: through the proxy the stack reads empty, which looks like a material with
no binding at all.

### Where the primvar is authored

On each renderable Gprim, with `constant` interpolation and one element.

DISP.001 permits authoring once on an ancestor and letting `UsdGeomPrimvarsAPI` inheritance
carry it down. That is the better shape when one colour covers the whole asset, and it is
the wrong shape here: the colour is derived per bound material, and every multi-material
sample in this library would collapse to a single asset-wide average. The toaster's chrome
tray resolves `(0.379, 0.373, 0.359)` and its plastic lever `(0.012, 0.012, 0.012)`; one
ancestor value cannot hold both. DISP.001's guidance to leave descendants unauthored applies
to restating the same value, which is not the case when the values differ.

`constant` rather than `uniform` is a deliberate loss. A Gprim can carry several materials
through `materialBind` GeomSubsets, and the toaster's body is one Mesh with 8,008 plastic
faces and 12,356 metal ones. `uniform` interpolation would give each face its own colour and
hold both exactly. It would also add 20,364 colour values to one mesh in an LFS-tracked
binary, and only `constant` primvars are inheritable, so the value would stop working if the
asset were later restructured to author once on an ancestor. The script takes the
area-weighted mean of the materials on the Gprim instead, and reports each contribution so
the blend is visible rather than silent.

Material bindings are irrelevant to whether the value survives. The FET006 render benchmark
strips every binding before it measures, and primvars are untouched by that.

### What the colour is derived from

The base colour of the bound material, resolved through the surface outputs in this order:

| Order | Surface | Input |
|---|---|---|
| 1 | `outputs:mtlx:surface` (OpenPBR) | `base_color` |
| 2 | `outputs:surface` (UsdPreviewSurface) | `diffuseColor` |
| 3 | `outputs:mdl:surface` (OmniPBR) | `diffuse_texture`, `diffuse_color_constant` |
| 3 | `outputs:mdl:surface` (OmniGlass) | `glass_color_texture`, `glass_color` |

OpenPBR comes first because it is the final surface the material declares, so where one is
authored it carries the intent and the preview surface below it is the compatibility
fallback. The order is strict: a hand-tuned OpenPBR constant wins over a legacy preview
texture rather than being averaged with it.

Within a tier a texture beats a constant. Where a source drives base colour from a map, the
constant sitting beside it is usually the exporter's neutral default rather than the colour
the material shows.

On the migrated samples the first two tiers agree exactly, which is the expected result
rather than a coincidence: the OpenPBR migration carried the same diffuse map onto
`base_color` that the preview surface already read. Running this script before and after
that migration produces identical display colours.

`base_color` on an OpenPBR surface is followed through the reference topology the migration
writes, so the file is read from the `Material`'s `*_texture_file` interface input rather
than from the reader node. An OmniGlass source is read through `glass_color` because that is
what it calls its base colour.

### Reducing a texture to one colour

A constant primvar holds one colour and `base_color` is usually a map, so the map is reduced
to a single value: **the mean of the texels the bound geometry actually lands on, weighted by
world-space surface area, taken in linear light.**

Concretely, for each Gprim and each material bound to it:

1. Fan-triangulate the faces bound to that material, respecting `materialBind` GeomSubsets.
2. Take each triangle's world-space area and its three UV corners from the `st` primvar,
   at whatever interpolation the mesh declares.
3. Sample each triangle at stratified barycentric points, mapped through any
   `UsdTransform2d` or MDL/MaterialX UV scale and offset, wrapped per `wrapS`/`wrapT`.
4. Decode each texel to linear and accumulate it weighted by triangle area.
5. Divide by total area, apply the texture's `scale` and `bias`, clamp to `[0, 1]`.

**What this buys.** Five of the electricians toolbox's materials share one 2048×2048 atlas,
`trim_plastic_yellow_02_a.png`. A mean over the whole image gives `(0.521, 0.366, 0.024)`,
and would hand that same yellow to all five. Sampling only where the geometry lands gives
`(0.011, 0.010, 0.007)` on the locks and `(0.633, 0.448, 0.042)` on the lid. The toaster's
two materials share an atlas the same way.

**What it loses.**

- One number per Gprim. A printed label, a painted stripe, or a second material on the same
  mesh disappears into the mean. The toaster's body mesh resolves `(0.247, 0.246, 0.243)`,
  which matches neither its plastic `(0.084, 0.084, 0.084)` nor its metal
  `(0.350, 0.348, 0.344)`.
- Weighting is by surface area, so a large flat region moves the value a long way even when
  it covers few texels. 97.7% of the samples on the toaster's plastic are below 0.02
  luminance, but the 14.6% of its area that sits on a flat mid-grey region lifts the constant
  from 0.023 to 0.084. Area weighting is the intent, since a viewer sees surface rather than
  texels, and it makes the result sensitive to UV density.
- Surface area, not visible area. An interior face nobody sees pulls the mean as hard as an
  equal-area face on the front.
- Nearest-texel point sampling with a bounded budget: roughly 200,000 samples per face group,
  capped at 64 per triangle. Detail finer than the sample spacing is aliased rather than
  integrated. A mesh with very few, very large triangles gets the fewest samples.
- Base colour only. No occlusion, no metalness tint, no vertex colour, no opacity. A polished
  metal's albedo map is often near-black, so its display colour comes out dark. That is what
  the map says, and DISP.002 permits it.
- Alpha is ignored. A cutout map whose transparent texels carry junk colour would skew the
  mean. None of the samples in this library does; display opacity is DISP.003 and out of scope.

**Why not the reader's `default` input.** The OpenPBR migration exposes a constant beside
every texture-driven channel as the reader's fallback, and taking that would avoid opening a
single image. It carries no information. Where the source had no constant of its own the
migration writes the OpenPBR nodedef default, so `--no-textures` on the migrated toaster
returns `(0.8, 0.8, 0.8)` for all five Gprims and both materials. It is kept as a last resort
for a run with no `numpy` or `Pillow`, and the run says plainly that is what happened.

### What `--no-textures` actually gives you

Nothing, on most of this library. `--no-textures` and a run with `numpy` or `Pillow` missing
both leave a texture-driven material with only whatever constant the material authors beside
its texture. On the samples as they stand there is no such constant anywhere: every
texture-driven material reaches its base colour through a `UsdPreviewSurface` whose
`diffuseColor` is connected, none of the `UsdUVTexture` readers authors `inputs:fallback`,
and none of the `mdl:OmniPBR` surfaces beside them authors `diffuse_color_constant`. So
`--no-textures` over `sample_content` authors 26 Gprims out of the 57 it walks and skips 31,
and 15 of the 20 assets that resolve any renderable geometry author nothing at all and are
therefore never saved. Those Gprims still fail DISP.001 afterwards.

The OpenPBR migration is the one path that writes a usable fallback, on the MaterialX
reader's `default` input, and the paragraph above says what that value is worth. Install
`numpy` and `Pillow` and sample the maps. Treat `--no-textures` as a way to see what the
constants alone would say; it will not conform an asset in this library.

### Colour space

`displayColor` resolves to linear Rec.709 with a D65 white point unless a colour space says
otherwise, so every texel is decoded through the sRGB transfer function before it enters the
mean. sRGB and Rec.709 share primaries and white point, so the transfer function is the whole
conversion and no primary matrix is involved.

Averaging the encoded bytes and writing the result as linear is a real defect, not a rounding
question. On the orange's diffuse map the byte mean is `(0.736, 0.343, 0.192)` where the
linear mean is `(0.533, 0.097, 0.031)`: 1.4× too high in red and 6.2× too high in blue. It
would not simply brighten the asset, it would desaturate it.

Whether a map is encoded is decided by what the map is for. A base colour map in an integer
format is sRGB-encoded; only a floating-point format is linear by construction. Source
metadata is not reliable enough to follow: the dishwand's OmniGlass shader labels
`t_plastic_clear_v01_01_a.png` as `raw` while the UsdPreviewSurface reading the same file
labels it `sRGB`, and the sledge hammer labels its ORM and normal maps `sRGB`. Where the
asset's declaration contradicts the role, the run says so on the line it affects.

Constants are carried across untouched. `diffuseColor`, `diffuse_color_constant`,
`glass_color` and OpenPBR `base_color` are all defined as linear scene-referred values
already.

The script authors `colorSpace = "lin_rec709_scene"` on the primvar. This is the OpenUSD
default, so it changes nothing for a consumer, and DISP.002 requires that a validator not
demand it. It is written because these values were decoded out of sRGB, and recording where
they landed is what makes that decode auditable in the file itself.

### Values it holds and values it refuses

DISP.002 requires every component within `[0, 1]` and finite.

Out of range is **clamped**. A source value slightly outside the range is an export artefact,
and the colour it names is still the right one.

Non-finite is **refused**. There is no defensible value to clamp NaN to, and substituting one
would invent a colour rather than derive it. The material is reported and the Gprim is left
without a display colour, so DISP.001 still fails on it and the failure is visible.

The same applies when nothing can be derived at all: no bound material, no base colour on any
surface, a texture that does not resolve on disk, or a prim with no UVs and no constant to
fall back on. Each is listed as `SKIPPED` with its reason, and the run says at the end that
those prims still fail DISP.001. No colour is invented for them.

### Geometry it will not touch

The script only ever rewrites a display colour it authored itself, which it recognises by the
derivation it records in the primvar's `customData` under `simready:displayColorSource`:

```usda
color3f[] primvars:displayColor = [(0.3788, 0.3731, 0.3592)] (
    colorSpace = "lin_rec709_scene"
    customData = {
        dictionary simready = {
            string displayColorSource = "m_opaque__metal__toaster_v01_01: UsdPreviewSurface diffuseColor <- t_gen_appliance_toaster_v01_01_a.png sampled over 2012 triangle(s)"
        }
    }
    interpolation = "constant"
)
```

Two states are reported as a conflict and left alone:

```
/RootNode/Geometry/body_obj_01/body_mesh_01: CONFLICT, display colour already authored on the prim, left alone
/RootNode/Geometry/lever_obj_01/lever_mesh_01: CONFLICT, display colour inherited from /RootNode/Geometry, left alone
```

The first is a value authored without that record, so somebody put it there by hand. The
second is an ancestor carrying a value the Gprim already inherits, which is the shape DISP.001
recommends and which this script must not shadow with a per-prim override. Resolve both by
hand.

## Feature Adapter

The same derivation is declared as a feature adapter, so the move onto display colour has a
known code path that runs without a person driving it. See
`nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/cip_specs/asset_handler_modules/neutral_to_display_color` | `material_neutral_to_display_color` | `FET_006_STANDARD@0.1.0` -> `FET_010_STANDARD@0.1.0` | Constant `primvars:displayColor` per renderable Gprim, derived from the UsdPreviewSurface `diffuseColor`. |
| `nv_core/cip_specs/asset_handler_modules/neutral_to_display_color` | `material_openpbr_to_display_color` | `FET_006_OPENPBR@0.1.0` -> `FET_010_STANDARD@0.1.0` | Constant `primvars:displayColor` per renderable Gprim, derived from the OpenPBR `base_color`. |
| `nv_core/cip_specs/asset_handler_modules/neutral_to_display_color` | `material_mdl_to_display_color` | `FET_006_MDL@0.1.0` -> `FET_010_STANDARD@0.1.0` | Constant `primvars:displayColor` per renderable Gprim, derived from the OmniPBR or OmniGlass MDL base colour. |

- The adapter holds no derivation of its own. It calls `author_stage()` in the bundled script
  above, which is the single implementation of this derivation, so running the skill by hand and
  running the adapter produce the same value. Change the script, not the adapter, to change what
  is authored.
- All three transitions are the conformance case where an asset had no display colour and now
  has one. None is a version migration: `FET_010_STANDARD` has only `0.1.0`. When a later
  version exists, add another decorated function pinning the two versions rather than editing
  these, which is what `neutral_to_physx` does for its `@0.2.0` -> `@0.3.0` path.
- Three input features are declared rather than one because the derivation resolves whichever
  surface a material carries, in the order OpenPBR, UsdPreviewSurface, MDL. On an asset that
  carries several the result is the same either way; declaring them separately keeps the adapter
  graph explicit about which contracts have a known path here.
- The adapter cannot conform geometry with no bound material, because the colour is derived
  rather than invented. Those Gprims are logged as skipped and left without a display colour, so
  the stage can still fail `DISP.001` after the adapter runs.
- Texture sampling needs `numpy` and `Pillow`, and the adapter's environment should have them.
  Without them the adapter does not fail, but on a texture-driven material it has only the
  constant the material authors beside its texture, and on these samples there is none — so it
  authors nothing, saves nothing, and `DISP.001` still fails afterwards. See **What
  `--no-textures` actually gives you** above.
### Running it

Two paths, and they author the same value because they call the same function.

**Without Kit**, call the derivation on an open stage. This needs `pxr`, plus `numpy` and
`Pillow` for texture sampling:

```python
from pxr import Usd
from author_display_color import author_stage

stage = Usd.Stage.Open("sm_asset.usd")
authored, skipped, conflicts, per_material, notes = author_stage(stage, sample_textures=True)
stage.Save()

print(f"{authored} Gprims authored, {skipped} skipped, {conflicts} conflicts")
for material, entry in per_material.items():
    count, weight, accumulated = entry
    colour = [c / weight for c in accumulated] if weight else [0.0, 0.0, 0.0]
    print(f"  {material}: {colour} across {count} Gprim(s)")
```

`author_stage` opens nothing and saves nothing, so the caller controls both. Pass
`dry_run=True` for the same counts without authoring, and `sample_textures=False` for the
`--no-textures` derivation, which on this library authors almost nothing. The command line
above wraps this with file handling and is the easier route for a directory of assets.

`per_material` maps a material name to `[gprim_count, accumulated_weight, accumulated_colour]`,
where `accumulated_colour` is each contributing colour multiplied by that contribution's
world-space area and summed. Divide it by `accumulated_weight` to get the area-weighted colour,
as above. Read the third element directly and it is off by the material's total area, which can
land it anywhere — well below the real colour on a small asset, above `1.0` and outside the
legal `displayColor` range on one covering more than a square stage unit. The accumulator is
returned unnormalised on purpose, so a caller running a directory of assets can sum the entries
across all of them and divide once at the end, which is what the command line does.

**Inside the registry**, the adapter is resolved by feature rather than called by name. That
path lives in the `omni.cip.configurable` extension in the **simready-explorer** repository:
`loader.py` scans the adapter modules named by `adapter_modules_path` in
`nv_core/sr_specs/docs/config.json`, the `@feature_adapter` decorator registers each function,
and `pipeline.py` drives an asset from an input profile to an output profile, selecting
adapters with `FeatureAdapter.get_adapters_for_features()`. Use this when moving a whole asset
between profiles rather than applying one known derivation.

It needs a Kit environment. `omni.cip.configurable.feature_adapter` imports
`omni.asset_validator.core`, which is not on the Python package index, so the adapter module
cannot be imported outside Kit at all — which is why the standalone entry point above exists.

Note also that `workspace upgrade`, which the physics conform skills name as the way to run an
adapter, has no implementation in this repository (`AGENTS.md`).

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile
   TOML, validation report, or user request.
2. Load the selected `FET_010_STANDARD` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing
   requirement.
4. Run the bundled script with `--verify` to establish the starting state. See **What
   `--verify` checks** above for what it covers and what its exit codes mean.
5. Create or use a staged output location unless the user explicitly asks for in-place edits.
6. Repair only the requirements listed by the selected manifest and its dependencies.
7. Rerun the same profile gate or the narrowest available feature/capability validation gate.
   If runtime evidence is required and unavailable, report that limitation instead of claiming
   a pass.
8. Summarize the selected version, changed files, validation evidence, and the first remaining
   blocker.

## Limits

- The script authors `primvars:displayColor` and nothing else. `primvars:displayOpacity`
  (DISP.003) is optional and is left alone, so an asset that carried none still carries none.
- Only meshes can be sampled. A Gprim with a material but no mesh topology, such as a Sphere
  or a Capsule, falls back to the material's constant and is reported as doing so.
- 16-bit and higher integer maps are read at 8 bits per channel, which is below the precision
  a mean over hundreds of thousands of texels would justify. Every map in the sample library
  is an 8-bit PNG.
- UV handling covers the forms these assets use: `st` at any interpolation, `UsdTransform2d`,
  MaterialX `uvtiling`/`uvoffset`, MDL `texture_scale`/`texture_translate`/`texture_rotate`,
  and `repeat`/`clamp` wrapping. Every one of them is identity on the current samples, so
  none of that is exercised by them. A material using a UV setup outside this set would
  sample the wrong region of its map.
- `--verify` reads authored scene description. It establishes DISP.001, DISP.002 and DISP.003,
  which are statically checkable. It says nothing about how the asset renders; that is the
  FET006 display colour benchmark's job and it needs Kit or Isaac Sim.
- `--verify` is a transcription of the capability validator, not that validator running. It
  can drift, and one difference is already deliberate: it walks `Usd.Stage.Traverse()` while
  the validator is handed prims by the asset validator engine, so the two can disagree about
  instance prototypes and unloaded payloads. Run the real validation gate before claiming a
  pass.
- The derivation approximates albedo. It does not claim to match what a path tracer produces
  for the same object, and DISP.002 sets no plausibility band against which such a claim could
  be checked.
