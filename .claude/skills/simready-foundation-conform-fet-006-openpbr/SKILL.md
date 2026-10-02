---
name: simready-foundation-conform-fet-006-openpbr
description: "Use for repairing exact FET_006_OPENPBR SimReady conformance for OpenPBR (MaterialX) material conformance. Use when a profile, validation report, or user request names FET_006_OPENPBR; default to version `0.1.0` unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Jens Jebens <jjebens@nvidia.com>"
  tags:
    - simready
    - conformance
    - openpbr
---

# SimReady Conform FET_006_OPENPBR

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_006_OPENPBR`. It adds or repairs the OpenPBR final surface on a material without touching the UsdPreviewSurface preview (`FET_006_STANDARD`) or the MDL surface (`FET_006_MDL`), which are sibling contracts.

Default to `FET_006_OPENPBR@0.1.0` when the user asks for this feature without a version. Use another version only when the profile, validation report, or user explicitly pins it. If the report names a different `FET_###_RUNTIME` feature, switch to that feature's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_006_OPENPBR-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_006_OPENPBR.md`

Treat the JSON manifest as authoritative for requirement IDs. Use the feature markdown for contract details, requirement links, samples and benchmarks.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | None | `com.nvidia.usd.VM.BIND.001`, `VM.BIND.002`, `VM.MAT.001`, `VM.PBR.001`, `VM.PBR.002`, `VM.PBR.003`, `VM.TEX.001`, `VM.TEX.004` |

## Bundled script

`assets/scripts/migrate_to_openpbr.py` authors the OpenPBR surface onto a material from
whatever it already has: a UsdPreviewSurface preview, an MDL final surface, or both. The
MDL models it reads are listed under **Which MDL models it reads**; a material built on
anything else is reported and left alone.

```bash
# report conformance, change nothing
python migrate_to_openpbr.py <path> --verify

# show what would change
python migrate_to_openpbr.py <path> --dry-run

# migrate, carrying textures across
python migrate_to_openpbr.py <path>

# migrate, flattening texture-driven channels to constants instead
python migrate_to_openpbr.py <path> --no-textures

# include materials defined outside this asset, such as a shared material library
python migrate_to_openpbr.py <path> --shared-materials migrate
```

### Options

| Option | Default | What it does |
|---|---|---|
| `--verify` | off | Report `VM.PBR.001` / `VM.PBR.002` conformance and texture resolution. Writes nothing. |
| `--dry-run` | off | Report what a run would author. Writes nothing. |
| `--textures` | **on** | Wire MaterialX reader nodes for texture-driven inputs. Naming it changes nothing; it is the default. |
| `--no-textures` | off | Flatten texture-driven inputs to the constant beside the map instead of wiring readers. |
| `--variants selected` | **default** | Migrate only the variants the asset ships selected. |
| `--variants all` | off | Visit every variant of every variant set. What an asset whose materials are specialised per variant needs. |
| `--shared-materials skip` | **default** | A material defined outside this asset's directory is reported by the layer it lives in and left alone. |
| `--shared-materials migrate` | off | Author into that layer too. It is shared, so this changes every asset that references it. |

A material whose surface already matches what the run would author is reported as
unchanged and its layer is not rewritten, so a second pass over a library is quiet on
everything it has already done.

### Variants

A material specialised inside a variant is only on the stage while that variant is
selected. One pass sees one variant's worth, and the rest are invisible rather than
absent: the Audi A6 vehicle sample ships with `Midnight_Black` and `Metallic_Black_Rim`
chosen, and under `--variants selected` every other paint colour and rim finish migrates
as nothing at all.

`--variants all` visits each variant of each set in turn rather than each combination, so
ten paint colours and seven rim finishes are seventeen passes, not seventy. A material
shared across variants is authored on the first pass that reaches it and reported
unchanged by the rest, so the run converges: on the A6 the first pass authors 80 materials
and each variant pass after it authors the single material that variant specialises.

`<path>` is a USD file or a directory, which is searched for `simready_usd` assets.
The script needs USD Python (`pip install usd-core`).

Textures are carried across by default. `--textures` used to be the opt-in that wired them
and is still accepted, but it no longer changes anything: it names the default. `--no-textures`
is the opt-out that flattens texture-driven channels to constants, which is what a plain run
used to do. The constant is whatever the source carries beside the map, and the OpenPBR nodedef
default where the source carries none. `geometry_normal` is the exception: it has no constant
form, so a flattened run leaves it unauthored.

It is safe to re-run. The script owns one prim per material, `OpenPBR_Shader`, plus the reader
nodes named `OpenPBR_Shader_*` beside it, and rewrites all of them from scratch on each pass:
whatever the previous run authored is removed before the fresh derivation is written, so a
re-run leaves exactly what the current derivation produces and never duplicates a texture node.
That matters because these assets are binary and LFS-tracked, so they cannot be merged: when
someone else edits an asset, re-run the script rather than resolving a conflict.

Three consequences of that rewrite:

- Only the input names the script itself authors are removed, and only on `OpenPBR_Shader`,
  the `OpenPBR_Shader_*` nodes, and the interface inputs it exposes on the `Material` prim.
  An input someone added outside that set, and every other shader under the material, is left
  alone.
- On the `Material` prim the script also claims any input whose name ends `_texture_file`,
  because a packed map is exposed under the map's own name rather than a parameter name.
- The reader nodes are rebuilt each pass. A `--no-textures` run after a normal run drops the
  wiring, because the current derivation no longer produces it, and leaves each channel at
  the constant that derivation does produce.

Re-running rewrites the binary layer, so the file hash changes even when the scene description
does not. Compare flattened USD rather than file hashes when checking a re-run changed nothing.

### The surface output

The OpenPBR nodedef declares a single output, `out`:

```xml
<nodedef name="ND_open_pbr_surface_surfaceshader" node="open_pbr_surface" ...>
  <output name="out" type="surfaceshader" />
```

so `outputs:mtlx:surface` connects to `OpenPBR_Shader.outputs:out`, matching NVIDIA's
`open_pbr_uber_base_class.usda`, where all 904 shipped OpenPBR materials use `out`.

That is the name to author, but it is not load-bearing, and `--verify` does not check it. Kit
accepts `outputs:out` and `outputs:surface` alike. Hydra derives the MaterialX terminal from the
nodedef's type and never reads the USD output property name, in
`HdMtlxGetMxTerminalName(terminalNodeDef->getType())` in `hdMtlx.cpp`. That was measured on
three isolated mtlx-only assets, magenta-probed with `mtlx` pinned first: `surface` rendered
99.63% magenta and `out` 99.58%, against a bogus-nodedef control at 0%.

Nothing else in the contract reads it either. VM.PBR.001 names no output. USD's own `usdMtlx`
reader deliberately normalises the other way, to `outputs:surface`, which is why an asset
round-tripped through it, or exported from Blender, carries that name. An earlier version of
this skill gated `--verify` on the name, and so rejected assets USD's own converter produces.
That gate is gone.

### Materials it will not touch

The script only ever rewrites a surface it created itself. A material that already carries an
OpenPBR surface under a prim name other than `OpenPBR_Shader`, or something other than that
surface sitting on the `OpenPBR_Shader` name, was authored by hand. The script reports it as a
conflict, leaves it exactly as it is, and counts it separately at the end of the run:

```
/World/Looks/ForeignMat: CONFLICT, OpenPBR surface already authored at MyOpenPBR, left alone
/Looks/SquatMat: CONFLICT, OpenPBR_Shader is already a Shader (ND_standard_surface_surfaceshader), left alone
```

Resolve those by hand. The script will not overwrite them and will not author a second,
competing surface beside them.

### What it maps

| OpenPBR input | From UsdPreviewSurface | From OmniPBR |
|---|---|---|
| `base_color` | `diffuseColor` | `diffuse_color_constant`, `diffuse_texture` |
| `base_metalness` | `metallic` | `metallic_constant`, `ORM_texture` (blue) |
| `specular_roughness` | `roughness` | `reflection_roughness_constant`, `ORM_texture` (green) |
| `specular_ior` | `ior` | — |
| `geometry_opacity` | `opacity` | `opacity_constant` |
| `emission_color` | `emissiveColor` | `emissive_color` |
| `emission_luminance` | — | `emissive_intensity` |
| `geometry_normal` | `normal` | `normalmap_texture` |

The OmniPBR ORM channels are only read when `enable_ORM_texture` is set. `geometry_normal` has
no constant form: it comes across when the source has a normal map and is absent otherwise.

### Which materials it writes to, and where

A material is migrated in the layer where it is defined — the weakest `def` in its prim
stack — because a new render-context output belongs with the material rather than with the
asset that binds it.

That layer is often not this asset's. A shared material library is referenced by many assets,
so migrating one of its materials from inside one asset's run changes how every other asset
renders. `--shared-materials` decides what happens to those:

- `skip` (default) reports each one by the layer it lives in and leaves it alone.
- `migrate` authors into that layer, which is what a deliberate library-wide pass wants.

Containment is by directory, not by layer stack: an asset's own parts arrive through
references too, so a layer-stack test would call its doors and wheels external. A material
defined under the root layer's directory is this asset's; anything else is not.

A material whose surface is already what the run would author is reported as unchanged and
its layer is not rewritten, so a second pass over a library is quiet on everything it has
already done.

### Reading a model's semantics, not just its input names

Two models can spell an input the same way and mean different things by it, and three of
those differences change how a migrated material renders. Each is read out of the MDL
rather than inferred:

- **Gated inputs.** SimPBR authors `emissive_color`, `emissive_intensity` and the opacity
  inputs on every material and gates each behind a boolean. Where `enable_emission` or
  `enable_opacity` is false the value beside it is inert. Carried across ungated, a matte
  car paint arrives glowing at 40 nits.
- **Albedo tint.** `SimPBR_Model.mdl` computes
  `base_color = multiply_colors(diffuse_color, diffuse_tint, 1.0).tint`, so the tint is a
  multiplier on the albedo. Dropped, a material with a 0.5 tint arrives twice as bright as
  it renders.
- **Coat darkening.** OpenPBR darkens what sits under a coat, modelling light reflected
  back internally, and `coat_darkening` defaults to 1.0. SimPBR's coat is a `fresnel_layer`
  over a base that is only tinted, so with a white `clearcoat_tint` the base is untouched.
  A coat migrated without setting `coat_darkening` to 0 renders the base darker than the
  source does, most visibly on a dark metallic under a full-weight coat.

### Which MDL models it reads

`OmniPBR`, `OmniGlass`, `SimPBR` and `SimPBR_Translucent`, matched on
`info:mdl:sourceAsset:subIdentifier`. A material built on any other MDL model is reported and
left alone, because the mapping matches source inputs by name and different models spell the
same name with different meaning.

SimPBR maps albedo, metalness and roughness as OmniPBR does, and takes `alpha_constant` for
`geometry_opacity`. It has no plain index of refraction — `clearcoat_ior` describes the coat,
not the base — so `specular_ior` comes from the UsdPreviewSurface or the nodedef default.
`SimPBR_Translucent` maps no `base_color`: it describes what light picks up passing through
rather than what the surface reflects, so it takes `ior_constant` for `specular_ior` and gets
`transmission_weight` 1.0, as OmniGlass does.

SimPBR authors `emissive_color`, `emissive_intensity` and the opacity inputs on every material
whether or not it uses them, and gates each behind a boolean. Where `enable_emission` or
`enable_opacity` is false the value beside it is inert and does not migrate; the run says which
input it held back and why. Read without those gates, a matte car paint arrives glowing.

Clearcoat maps one to one, gated behind `enable_clearcoat`: `clearcoat_weight` to
`coat_weight`, `clearcoat_reflection_roughness` to `coat_roughness`, `clearcoat_tint` to
`coat_color` and `clearcoat_ior` to `coat_ior`. `coat_weight` and `coat_roughness` are held in
`[0, 1]` and `coat_ior` in `[1, 3]`, on the same terms as every other bounded input.

Precedence runs texture first. For each channel the script looks for a texture on the
UsdPreviewSurface, then on the MDL surface, and takes a constant only when neither source has
one. A shader that authors a constant beside its own map carries the map across rather than the
constant: OmniPBR declares `diffuse_color_constant` ("Albedo Color") beside `diffuse_texture`
("Albedo Map"), and `metallic_texture_influence` / `reflection_roughness_texture_influence`
exist precisely to blend one against the other, so the constant next to a map is a default and
not the authored value. Between two constants the UsdPreviewSurface is read first, with the
OmniGlass exception noted below.

Every value is held inside the range VM.PBR.002 defines, so an out-of-range source value is
clamped rather than carried across. Physics materials are left alone.

An `OmniGlass` source is mapped differently, because it names its inputs differently and
describes a transmissive material:

| OpenPBR input | From OmniGlass |
|---|---|
| `base_color` | `glass_color`, `glass_color_texture` |
| `specular_roughness` | `frosting_roughness`, `ORM_texture` (green) |
| `specular_ior` | `glass_ior` |
| `geometry_opacity` | `cutout_opacity` |
| `geometry_normal` | `normal_map_texture` |
| `transmission_weight` | set to `1.0` |

OmniGlass spells its albedo and normal maps `glass_color_texture` and `normal_map_texture`,
where OmniPBR writes `diffuse_texture` and `normalmap_texture`. Both spellings are read, so a
material carrying only an OmniGlass surface keeps those two maps. It packs its ORM the same way
OmniPBR does, under the same `ORM_texture` and `enable_ORM_texture` names.

`base_metalness` is not mapped from an OmniGlass source. It is pinned to `0.0`, which is what a
dielectric is, so the ORM blue channel is deliberately not read for glass.

Where both sources hold a constant for the same channel, the OmniGlass value wins, because the
preview surface usually holds a generic default. That ordering settles constants only: a texture
on either source still beats a constant on either source, so `frosting_roughness` does not
displace a roughness map the source also carries.

No sample in this repository exercises the constant-against-constant case. `clear__platic_01` in
`gen_cleaning_dishwand_v01_01` is the only OmniGlass material here, and its preview `ior` and its
`glass_ior` are both 1.52, so the two sources agree.

### Texture-driven inputs

Where a source input is driven by a texture, the script authors the MaterialX reader nodes that
sample it and wires them into the OpenPBR surface. The topology follows NVIDIA's PhysicalAI
SimReady materials library (`open_pbr_uber_base_class.usda`):

| Piece | Node |
|---|---|
| UV source, one per material | `ND_texcoord_vector2`, `index = 0` |
| Colour map | `ND_tiledimage_color3` |
| Single-channel map | `ND_tiledimage_float` |
| Packed map (ORM) | `ND_tiledimage_vector3` + `ND_separate3_vector3` |
| Normal map | `ND_tiledimage_vector3` + `ND_normalmap_float` |

Each reader takes `texcoord` from the shared texcoord node and `uvtiling`/`uvoffset` from the
`Material`, matching the reference wiring.

A packed map is read once and split once, however many channels come out of it: an ORM map
feeding both roughness and metalness produces one reader and one `separate3`, not two of each.
Which channel feeds which input is read from the source connection rather than assumed, so a
material that wires roughness to the red channel keeps doing that.

The reference library writes `ND_normalmap`, which is the MaterialX 1.38 name. 1.39 split that
nodedef by the type of its `scale` input, and the plain name resolves in neither the 1.39
stdlib nor the library Kit ships, so the script writes `ND_normalmap_float`. `ND_normalmap`
would leave the normal unresolvable, which renders flat rather than failing loudly.

`ND_normalmap` decodes the tangent-space range itself, so the reader feeds it the raw texture
value and the script authors no scale/bias node.

Colour space is set on the `Material`'s asset input, as the reference library sets it, and is
decided by what the texture is rather than by what the source says: `srgb_texture` for colour
channels, `none` for roughness, metalness, normals and opacity. Several source assets label an
ORM or normal map `sRGB`, which would skew those values if it were carried across verbatim.

Running with `--no-textures` reports these channels as `FLAT` and holds the OpenPBR input at a
constant: the one the source carries beside the map, or the OpenPBR nodedef default where it
carries none, which is what most of these samples hit, since a Blender export writes the map
and no value beside it. `geometry_normal` is the exception and is left unauthored, having no
constant form. Those materials satisfy VM.PBR.001 and VM.PBR.002 but will not look like the
original.

The reader nodes need something that resolves MaterialX nodedefs, and Kit is not the only thing
that does. `usd-core` on its own does not register them, so `Sdr` resolves neither
`ND_open_pbr_surface_surfaceshader` nor `ND_tiledimage_color3` under a bare
`pip install usd-core`. The materials validator falls back to the `MaterialX` Python package
when `Sdr` comes up empty, so `pip install MaterialX>=1.39` beside `usd-core` is enough for
VM.PBR.003 to run, with no Kit and no Isaac Sim. What still needs a renderer is the rendered
result: whether the migrated material looks right is a render question, not a nodedef one.

### Parameters on the Material prim

Every parameter the OpenPBR surface reads is exposed as an interface input on the `Material`
prim, and the shader reads it through that input, so a material can be retuned without reaching
into its shader network:

```usda
def Material "m_opaque__plastic__toaster_v01_01"
{
    color3f inputs:base_color = (0.8, 0.8, 0.8)
    asset inputs:base_color_texture_file = @./textures/..._a.png@ ( colorSpace = "srgb_texture" )
    float inputs:specular_ior = 1.5
    float2 inputs:uvtiling = (1, 1)
    ...
    def Shader "OpenPBR_Shader"
    {
        float inputs:specular_ior.connect = </...m_opaque__plastic__toaster_v01_01.inputs:specular_ior>
```

For a channel driven by its own texture the constant is still exposed and feeds the reader's
`default`, which is the reference library's texture-else-value idiom: it is what the material
falls back to if the texture fails to load, and the one place to retune the channel.

A channel unpacked from a packed map has no constant of its own, because the reader's fallback
is one value shared by every channel in the map. Retune those by swapping the map, which is
exposed as `inputs:<map name>_texture_file`.

Unlike the reference library, the materials this script writes carry no `inherits` or
`specializes` arc. The reference shares one base class across a library; a migrated sample has
to stand on its own, so each material carries its own copy of the network it needs.

## Feature Adapter

The same migration is declared as a feature adapter, so the move onto OpenPBR has a known code
path that runs without a person driving it. See
`nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/cip_specs/asset_handler_modules/neutral_to_openpbr` | `material_neutral_to_openpbr` | `FET_006_STANDARD@0.1.0` -> `FET_006_OPENPBR@0.1.0` | OpenPBR surface on `outputs:mtlx:surface`, derived from the UsdPreviewSurface preview. |
| `nv_core/cip_specs/asset_handler_modules/neutral_to_openpbr` | `material_mdl_to_openpbr` | `FET_006_MDL@0.1.0` -> `FET_006_OPENPBR@0.1.0` | OpenPBR surface on `outputs:mtlx:surface`, derived from the OmniPBR or OmniGlass MDL surface. |

- The adapter holds no derivation of its own. It calls `migrate_stage()` in the bundled script
  above, which is the single implementation of this migration, so running the skill by hand and
  running the adapter author the same thing. Change the script, not the adapter, to change what
  is authored.
- Both transitions are the conformance case where an asset had no OpenPBR surface and now has
  one. Neither is a version migration: `FET_006_OPENPBR` has only `0.1.0`. When a later version
  exists, add another decorated function pinning the two versions rather than editing these,
  which is what `neutral_to_physx` does for its `@0.2.0` -> `@0.3.0` path.
- The adapter adds; it removes nothing. The preview and MDL surfaces are separate contracts an
  asset may hold at the same time, and both survive the run.
- A material carrying a hand-authored OpenPBR surface is left alone and logged as a conflict, so
  the stage can still fail `FET_006_OPENPBR` after the adapter runs. Resolve those by hand.
### Running it

Two paths, and they author the same thing because they call the same function.

**Without Kit**, call the migration on an open stage. This needs nothing but `pxr`:

```python
from pxr import Usd
from migrate_to_openpbr import migrate_stage

stage = Usd.Stage.Open("sm_asset.usd")
migrated, skipped, conflicts, wired, flattened, notes = migrate_stage(stage, wire_textures=True)
stage.Save()

print(f"{migrated} materials migrated, {wired} channels wired, {conflicts} conflicts")
for note in notes:
    print(note)
```

`migrate_stage` opens nothing and saves nothing, so the caller controls both. Pass
`dry_run=True` for the same counts without authoring. The command line above wraps this with
file handling and is the easier route for a directory of assets.

**Inside the registry**, the adapter is resolved by feature rather than called by name. That
path lives in the `omni.cip.configurable` extension in the **simready-explorer** repository:
`loader.py` scans the adapter modules named by `adapter_modules_path` in
`nv_core/sr_specs/docs/config.json`, the `@feature_adapter` decorator registers each function,
and `pipeline.py` drives an asset from an input profile to an output profile, selecting
adapters with `FeatureAdapter.get_adapters_for_features()`. Use this when moving a whole asset
between profiles rather than applying one known migration.

It needs a Kit environment. `omni.cip.configurable.feature_adapter` imports
`omni.asset_validator.core`, which is not on the Python package index, so the adapter module
cannot be imported outside Kit at all — which is why the standalone entry point above exists.

Note also that `workspace upgrade`, which the physics conform skills name as the way to run an
adapter, has no implementation in this repository (`AGENTS.md`).

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET_006_OPENPBR` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Run the bundled script with `--verify` to establish the starting state. It reports the
   surface contract, the VM.PBR.002 ranges, and any texture the material names that does not
   resolve to a file on disk. All three are reported on every material, including one that has
   not been migrated yet, so a missing texture on an unmigrated asset is visible here. The
   texture check reads every asset-valued shader input, so it covers the MDL-named maps
   (`inputs:diffuse_texture`, `inputs:ORM_texture`, `inputs:normalmap_texture`) as well as the
   ones the migration authors, which is what makes it say anything about an unmigrated asset.
5. Create or use a staged output location unless the user explicitly asks for in-place edits.
6. Repair only the requirements listed by the selected manifest and its dependencies.
7. Re-run `--verify` after migrating. A texture the migration carried across is a texture the
   migrated asset now names, so the reader nodes have to resolve too.
8. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
9. Summarize the selected version, changed files, validation evidence, and the first remaining blocker.

## Limits

- The script authors the surface, its parameters, its textures and the normal map. It does not
  author coat or subsurface, which need per-asset judgement. Transmission is authored only for
  an OmniGlass source.
- Normal maps come across without the per-channel flip controls the reference library carries.
  The sample sources set `flip_tangent_u` and `flip_tangent_v` to false, so there is nothing to
  flip; a source that needs a flipped green channel would need it added.
- `--verify` checks that every texture a material names resolves to a file on disk, but not
  that the image is the right size or bit depth. VM.TEX.001's own check silently passes when
  PIL is absent, so a green result does not establish that texture sizes were checked.
- Nothing reports a source channel that did not come across. A map the script cannot map to an
  OpenPBR input is absent from the run output and from `--verify`, which only sees what was
  authored. Read the run's `texture:` lines against the source shader when that matters.
- VM.PBR.003 checks MaterialX graph structure against a resolved nodedef, so it needs a source
  of nodedefs, which `usd-core` alone is not. It does not need Kit: the validator falls back to
  the `MaterialX` Python package, so `pip install MaterialX>=1.39` is enough. `--verify` in this
  script resolves nothing either way. It reads the authored scene description, so run the
  validator for VM.PBR.003 rather than reading a green `--verify` as covering it.
