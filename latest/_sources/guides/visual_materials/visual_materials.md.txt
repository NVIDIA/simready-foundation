# Visual Materials Workflow

This guide takes one asset to demonstrable conformance on visual materials. You author an
OpenPBR surface and a display colour, validate the result against a profile, render it in
Kit, and work out what the render result is worth.

Visual materials in SimReady cover two separate things. A material describes a shaded
surface through a shading network. Display colour is a primvar holding a single colour per
prim and no network at all, which is what makes it readable by consumers that never
evaluate a material. Each gets its own tool here, because they are different contracts.

There are two ways in, and both depend on the contract in step 1. Step 2 exports a
conformant material from Blender. Step 3 upgrades an asset that already exists. All
commands run from the repository root unless stated otherwise.

## What you end up with

| Stage | Tool | Outcome |
|---|---|---|
| Baseline | `simready-validate` | A profile report, and a record of what it does not cover |
| OpenPBR surfaces | `migrate_to_openpbr.py` | `outputs:mtlx:surface` on every visual material, textures reconnected |
| Display colour | `author_display_color.py` | `primvars:displayColor` on every renderable Gprim |
| Re-validation | `simready-validate` | The static contract, confirmed |
| Benchmark | `simready-benchmark` | Evidence that the geometry bound to each surface drew in the engine |

Static validation and the benchmark answer different questions. Validation inspects the
authored scene description and confirms the file holds the right values. The benchmark loads
the asset in Kit and confirms the engine resolved it. Neither establishes that the asset looks correct, and
step 5 is about where that line falls.

## Prerequisites

| Requirement | How to get it | Needed for |
|---|---|---|
| Python | 3.12 | All steps |
| Git LFS | `git lfs install` | Sample assets |
| `simready-validate` and the validator dependencies | `pip install -r requirements.txt` | Steps 2 and 3 |
| `simready-foundation-tier-core` | `pip install simready-foundation-tier-core` | Steps 2 and 3 |
| `simready-benchmark` | Refer to [Running Tests](../benchmark/running.md) | Step 4 |
| Kit or Isaac Sim | 2024.2.0 or later | Step 4 |

One environment covers steps 2 and 3. `requirements.txt` lists `simready-validate` and
`numpy`, and `usd-core` arrives behind them. Two more are needed and neither is in that
file:

```bash
pip install -r requirements.txt
pip install "MaterialX>=1.39" pillow
```

MaterialX supplies the OpenPBR node definitions. A `usd-core` wheel ships no `usdMtlx`
plugin, so in a pip environment the Python package is the only source of them. Without it
VM.PBR.002 and VM.PBR.003 have nothing to compare an asset against and report nothing,
which looks the same as a clean asset. The validator emits one line per run, `VM.PBR.002
and VM.PBR.003 did not run`. VM.PBR.001 matches one shader identifier, needs no node
definition, and runs either way. `Pillow` is how VM.TEX.001 gets a texture's dimensions,
and the display-colour script uses it to sample texture maps.

### The core tier

`simready-validate` checks an asset against the core tier: the capabilities, features,
profiles and rule checkers that make up the spec. It is a separate package from the
validator, so install it alongside:

```bash
pip install simready-foundation-tier-core
```

[SimReady Foundation PyPI Packages](../foundation_pypi.md) covers the tiers, the index to
install from, and how content is discovered.

### The benchmark

Give `simready-benchmark` a virtual environment of its own: it installs a Kit engine plugin
on top of its own USD build, and [Running Tests](../benchmark/running.md) covers the setup.

The worked example uses the toaster sample. Both conform scripts write into an asset in
place, so take a copy and work on that. The samples are LFS-tracked binaries and a rewrite
moves the file hash even when nothing about the content changes.

```bash
mkdir -p ../vm-workflow
cp -r sample_content/common_assets/props_general/gen_appliance_toaster_v01_01 ../vm-workflow/
```

The shipped samples already have an OpenPBR surface and a display colour, so the worked
example below confirms a conformant asset. Point the same commands at your own asset to see
them repair one, and read each transcript for the shape of its output; the counts and colours
belong to this sample.

## 1. The material contract

### Three surfaces on one prim

A SimReady `Material` prim can declare three surface outputs at once, one per render
context. A render context is the token a renderer uses to choose which shader inside a
material it evaluates.

| Output | Shader | Render context | Feature | Requirement |
|---|---|---|---|---|
| `outputs:surface` | UsdPreviewSurface | universal | `FET_006_STANDARD` | com.nvidia.usd.VM.PS.001 |
| `outputs:mdl:surface` | OmniPBR | `mdl` | `FET_006_MDL` | VM.MDL.001 |
| `outputs:mtlx:surface` | OpenPBR | `mtlx` | `FET_006_OPENPBR` | VM.PBR.001 |

These are sibling contracts. An asset may declare any combination, and none of the three
depends on another. OpenPBR is the recommended target for new assets because it is a
portable format that needs no vendor-specific material; MDL stays permitted for existing
content. Refer to [FET006 OpenPBR Materials](../../features/FET_006_OPENPBR.md) for the
full contract.

### Which surface the renderer picks

Kit resolves one surface per material by walking an ordered list of render contexts and
taking the first one the material has. The list is the carb setting
`/persistent/app/hydra/material/renderContexts`, and Kit ships it as `["mdl", "mtlx", ""]`.

An asset with both an OmniPBR and an OpenPBR surface therefore renders the OmniPBR
one. If you open a migrated asset in Kit and it looks unchanged, that is why: you are
looking at MDL.

The benchmark tests in step 4 pin the context themselves and verify the pin took, so you
do not need to change the setting to see the OpenPBR surface rendered. Refer to
[How a Surface Is Measured](../benchmark/tests/fet006-materials.md#how-a-surface-is-measured)
for how they do it.

Render context is a different mechanism from binding purpose. Render context selects which
shader inside a material is evaluated. Binding purpose, authored as
`material:binding:full` or `material:binding:preview`, selects which material is bound to a
prim in the first place. This guide concerns render context.

### Display colour is a primvar

`primvars:displayColor` has no render context and no surface output, because it has no
shading network. That is the point of it: it is the appearance layer available to a
consumer that never evaluates a material, such as a low-fidelity or non-ray-traced render
path. In Kit, the RTX default material takes it as its diffuse tint for geometry with no
material bound.

| Code | Requirement | Status |
|---|---|---|
| [`DISP.001`](../../capabilities/visualization/display_color/requirements/display-color-coverage.md) | Every renderable Gprim resolves a `primvars:displayColor` | Required |
| [`DISP.002`](../../capabilities/visualization/display_color/requirements/display-color-values.md) | Every component is within `[0, 1]` and finite, and the element count agrees with the interpolation | Required |
| [`DISP.003`](../../capabilities/visualization/display_color/requirements/display-opacity-values.md) | `primvars:displayOpacity`, where authored, is within `[0, 1]` and finite | Optional |

Display opacity works differently. A material has to opt in to reading
`displayOpacity`; `gltf/pbr.mdl` is one that does. Kit's RTX default material has no
opacity term, so geometry with no material bound picks up the colour and nothing else.
Neither conform script in this guide authors display opacity.

### Colour space

Colours and data channels both need colour space information, and the rules differ. Constants are
linear everywhere. Textures declare their own, and each of the three surfaces declares it
somewhere else, with a different default and a different vocabulary.

**Constants and display colour are linear.** `primvars:displayColor`, and any constant you
type onto a surface input, are Linear Rec.709 with a D65 white point. `0.18` is mid grey.
USD resolves the colour space from the attribute's own `colorSpace` metadata, then from
`UsdColorSpaceAPI` on the prim, then from the nearest ancestor that authors one, and falls
back to `lin_rec709_scene` when none is authored, so an asset that authors nothing still
has a defined colour space.

So a value taken from an sRGB colour picker needs converting before you write it. `0.5`
picked as mid grey in sRGB is much lighter once interpreted as linear. The display-colour
script in step 3 handles this by decoding every texel through the sRGB transfer function
before it averages, so you only need to think about it when you author a value by hand.

**Textures are where the three surfaces diverge.**

| Surface | Declared on | No declaration means | Requirement |
|---|---|---|---|
| UsdPreviewSurface | `inputs:sourceColorSpace` on the `UsdUVTexture` | `auto` | [`VM.TEX.003`](../../capabilities/visualization/materials/requirements/material-texture-colorspace-preview.md) |
| MDL | `colorSpace` metadata on the shader's own `asset inputs:*` | `auto` | [`VM.TEX.005`](../../capabilities/visualization/materials/requirements/material-texture-colorspace-mdl.md) |
| OpenPBR | `colorSpace` metadata on the image node's `inputs:file` | no transform at all | [`VM.TEX.004`](../../capabilities/visualization/materials/requirements/material-texture-colorspace-openpbr.md) |

`auto` reads the image file's own colour-space metadata; where the file states nothing, it
decodes any 8-bit three- or four-channel image as sRGB and treats everything else as raw.

Two consequences follow, and they pull in opposite directions.

On UsdPreviewSurface and MDL a colour texture can rely on the default, because `auto`
decodes 8-bit RGB the way a colour texture needs. A data texture cannot: image editors
write 8-bit RGB as a matter of course, so a roughness, metalness or occlusion map left
undeclared is decoded as though it held colour and every value comes out low. Declare
`raw` on data inputs. Single-channel and high-bit-depth files fall outside the sRGB branch,
so `auto` is already correct for a single-channel mask.

On OpenPBR there is no `auto`. An undeclared texture gets no transform whatever the file
is, so a colour texture must declare `srgb_texture` or it is consumed undecoded and
renders washed out. A data texture needs nothing, or `none`.

Author `srgb_texture`, not `srgb_rec709_scene`. The two name the same encoding, the sRGB
transfer function over Rec.709 primaries, but only the MaterialX spelling resolves on an
OpenPBR surface. OpenUSD adopted `srgb_rec709_scene` in 24.11; MaterialX defines its
transform nodes under `srgb_texture`, and the mapping between the two vocabularies arrived
in MaterialX 1.39.4, which no runtime SimReady targets ships. A texture tagged with the
OpenUSD name is consumed undecoded and renders washed out with nothing reported. The MDL
loader does resolve `srgb_rec709_scene`, so an asset with both surfaces can be correct on
one and wrong on the other.

Mid grey is `0.18` as a constant and code `118` in an 8-bit sRGB texture. Both are the 18%
grey card; they differ because the texture is sRGB-encoded and the constant is linear. Code
`128` is not mid grey in a colour texture: it is the middle of the *encoding* range and
decodes to `0.216`, about 20% lighter than a grey card.

The [materials requirements overview](../../capabilities/visualization/materials/requirements.md)
states the conventions of all four appearance formats side by side, including display colour.

## 2. Authoring in Blender

Blender 5.2 LTS writes an OpenPBR surface with no add-on. One export puts both a
UsdPreviewSurface and an OpenPBR surface on the same `Material` prim, which is the shape
[FET006 OpenPBR Materials](../../features/FET_006_OPENPBR.md) describes. One thing stands
between that and a conformant material: the setting that writes the OpenPBR network is off
by default.

This is the path for a material built from scratch. Step 3 is the other one, for an asset
that already exists. This section covers the stock exporter only.

The commands here run outside the repository, against Blender 5.2.0 LTS in headless mode:

```bash
blender --background --factory-startup --python export.py
```

The export operator is `bpy.ops.wm.usd_export`. It takes around seventy properties, so read
them off the build in front of you instead of from a list that may have moved:

```python
for p in bpy.ops.wm.usd_export.get_rna_type().properties:
    print(p.identifier, p.type, p.default)
```

### Export settings

| Property | Default | Use | What it does |
|---|---|---|---|
| `generate_materialx_network` | `False` | `True` | Writes the OpenPBR network |
| `generate_preview_surface` | `True` | leave on | Derives the UsdPreviewSurface from the Principled BSDF |
| `export_textures_mode` | `NEW` | leave on `NEW` | Copies referenced maps into `textures/` beside the USD and points the asset paths at the copies |
| `export_materials` | `True` | leave on | Off writes no materials at all |

Nothing in the output flags `generate_materialx_network` being off. An export with it off
is a complete, valid USD file with a working UsdPreviewSurface and no OpenPBR anywhere.

Turning `generate_preview_surface` off does not remove the UsdPreviewSurface. It swaps the
one derived from the Principled BSDF for a placeholder built from the material's viewport
display settings, and renames the prim from `Principled_BSDF` to `previewShader`. A material
whose Principled BSDF base colour is `(0.11, 0.12, 0.13)` and whose viewport colour is left
at Blender's default exports `diffuseColor = (0.8, 0.8, 0.8)`. The terminal still satisfies
com.nvidia.usd.VM.PS.001 while showing an appearance nobody authored, so leave the setting on.

### What Principled BSDF maps to

Principled BSDF is the route to OpenPBR. Blender translates its inputs to
`ND_open_pbr_surface_surfaceshader` one at a time, and several do not survive the trip
intact. The table covers every input the Principled BSDF panel exposes. It comes from giving
each one a distinct constant, exporting once, and reading which value landed where. The three
vector inputs need a node connected, so they were measured separately.

| Principled BSDF input | OpenPBR input | Carried as |
|---|---|---|
| Base Color | `base_color`, `subsurface_color`, `transmission_color` | Copied to all three |
| Metallic | `base_metalness` | Unchanged |
| Roughness | `specular_roughness` | Unchanged |
| IOR | `specular_ior` | Unchanged |
| Alpha | `geometry_opacity` | Unchanged |
| Thin Wall | `geometry_thin_walled` | Unchanged |
| Diffuse Roughness | `base_diffuse_roughness` | Unchanged |
| Subsurface Weight | `subsurface_weight` | Unchanged |
| Subsurface Scale | `subsurface_radius` | Unchanged |
| Subsurface Radius | `subsurface_radius_scale` | Unchanged |
| Subsurface Anisotropy | `subsurface_scatter_anisotropy` | Unchanged |
| Specular Tint | `specular_color` | Unchanged |
| Transmission Weight | `transmission_weight` | Unchanged |
| Coat Weight | `coat_weight` | Unchanged |
| Coat Roughness | `coat_roughness` | Unchanged |
| Coat IOR | `coat_ior` | Unchanged |
| Coat Tint | `coat_color` | Unchanged |
| Sheen Weight | `fuzz_weight` | Unchanged |
| Sheen Roughness | `fuzz_roughness` | Unchanged |
| Sheen Tint | `fuzz_color` | Unchanged |
| Emission Color | `emission_color` | Unchanged |
| Thin Film IOR | `thin_film_ior` | Unchanged |
| Normal | `geometry_normal` | Through `ND_normalmap_float` |
| Coat Normal | `geometry_coat_normal` | Through `ND_normalmap_float` |
| Specular IOR Level | `specular_weight` | Doubled |
| Anisotropic | `specular_roughness_anisotropy` | Scaled by 0.7 |
| Emission Strength | `emission_luminance` | Number copied, meaning changed |
| Thin Film Thickness | `thin_film_thickness` | Nanometres to micrometres |
| Anisotropic Rotation | none | A rotation inside the tangent chain |
| Tangent | `geometry_tangent` | Flattened to a world-space tangent |
| Subsurface IOR | none | Dropped |

Five are not straight copies, so know them before you tune a material in Blender and expect
the numbers back.

**Specular IOR Level is doubled.** Blender's 0.5 default becomes `specular_weight = 1`, and
1.0 becomes 2, above the node definition's soft maximum of 1.

**Anisotropic is scaled by 0.7.** Blender's full 1.0 reaches 0.7 of a range the node definition caps
at 1, so the slider cannot reach the top of OpenPBR's anisotropy.

**Anisotropic Rotation never reaches an OpenPBR input.** It becomes the `amount` on an
`ND_rotate3d_vector3` node in the tangent chain, in degrees, as `-(turns * 360 + 90)`: 0
gives -90 and 0.25 gives -180. That chain only feeds `geometry_tangent` when Anisotropic is
above zero. At zero the unrotated tangent is connected instead and the rotation node is left
dangling in the graph.

**Thin Film Thickness is divided by 1000**, converting Blender's nanometres to the
micrometres the node definition asks for. Authoring any non-zero thickness also sets
`thin_film_weight` to 1, which has no Blender input of its own.

**Emission Strength is copied unchanged** into `emission_luminance`, which the node definition
defines as a luminance in nits. Blender treats the same number as a multiplier on Emission
Color. The number survives and the brightness does not.

Two inputs go nowhere useful. Subsurface IOR leaves no trace in the export. Tangent does
reach the graph, and lands the same way whatever you feed it: a Blender Tangent node
exports as `ND_tangent_vector3` with `space = "world"` whether it is set to a UV map or to
radial around an axis, and with nothing connected the exporter emits that same node itself.
So the OpenPBR tangent is the world-space one either way, and choosing a tangent in Blender
changes nothing in the file.

Going the other way, `base_weight` is written as 1 with no Blender input behind it, the same
way `thin_film_weight` is. And eight OpenPBR inputs are declared with no value, because
nothing on the Principled BSDF feeds them: `coat_darkening`,
`coat_roughness_anisotropy`, `geometry_coat_tangent`, `transmission_depth`,
`transmission_dispersion_abbe_number`, `transmission_dispersion_scale`,
`transmission_scatter` and `transmission_scatter_anisotropy`.

The UsdPreviewSurface written alongside is derived on its own terms, and it disagrees with
the OpenPBR surface in one place. Alpha reaches `geometry_opacity` on the OpenPBR shader but
never reaches `opacity` on the UsdPreviewSurface, which is set to `1 - Transmission Weight`
instead. A material with Alpha 0.24 and no transmission exports `geometry_opacity = 0.24`
alongside `opacity = 1`. Emission is combined instead of passed through: `emissiveColor` is
Emission Color multiplied by Emission Strength and left unclamped, so strength 2 on a light
colour writes components above 1.

### Textures

Wire an image texture to Base Color and the map crosses into the MaterialX network. The
reader node is `ND_image_*`, one per Blender image node, all fed from a single shared
`ND_texcoord_vector2`. Blender never emits `tiledimage`.

| Blender wiring | MaterialX nodes | Feeds |
|---|---|---|
| Image Texture -> Base Color | `ND_image_color4` -> `ND_convert_color4_color3` | `base_color` |
| Image Texture -> Roughness | `ND_image_vector4` -> `ND_extract_vector4` (`index = 0`) | `specular_roughness` |
| Image Texture -> Normal Map -> Normal | `ND_image_vector4` -> `ND_convert_vector4_vector3` -> `ND_normalmap_float` | `geometry_normal` |

Colour space lands in three places on a Blender export.

On the MaterialX image node, a colour map gets `colorSpace = "srgb_texture"` on its
`inputs:file`. A map set to Non-Color in Blender gets no colour space metadata there at all.

On the UsdPreviewSurface side, Blender writes `inputs:sourceColorSpace` on the
`UsdUVTexture` and gets it right both ways: a colour map exports `sRGB`, and a map set to
Non-Color exports `raw`.

Blender also writes `colorSpace:name` on the texture `Shader` prims themselves,
`srgb_rec709_display` for a colour map and `data` for a Non-Color map.
`srgb_rec709_display` is display-referred, where a texture needs the scene-referred
`srgb_rec709_scene`. No renderer consults `UsdColorSpaceAPI` today, so it has no effect on
what you see, but it would be wrong if one started.

`export_textures_mode` controls where the file itself lands, and it interacts with the
MaterialX network in a way its three descriptions do not cover. Measured on one texture:

| Mode | Asset path written | Copy in `textures/` |
|---|---|---|
| `KEEP` | The original location, relative | Written, referenced by nothing |
| `PRESERVE` | The original location, relative | Written, referenced by nothing |
| `NEW` (default) | `./textures/<name>` | Written and referenced |

With `generate_materialx_network` off, `KEEP` and `PRESERVE` copy nothing, which is what
their descriptions state. Turning the MaterialX network on copies them anyway while the
asset paths still point at the originals, so the export ends up with a duplicate nothing
uses and stays dependent on a path outside itself. Leave the mode on `NEW`, which is
self-contained and leaves no stray file.

### What the export looks like

Both terminals sit on one `Material` prim, with the OpenPBR reader nodes gathered into a
`NodeGraph` and the UsdPreviewSurface readers as siblings beside the shader:

```usda
def Material "ProbeMat" (
    prepend apiSchemas = ["MaterialXConfigAPI", "ColorSpaceAPI"]
)
{
    uniform token colorSpace:name = "lin_rec709_scene"
    string config:mtlx:version = "1.39"
    token outputs:mtlx:surface.connect = </root/_materials/ProbeMat/bnode__Principled_BSDF.outputs:surface>
    token outputs:surface.connect = </root/_materials/ProbeMat/Principled_BSDF.outputs:surface>

    def Shader "Principled_BSDF"
    {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor.connect = </root/_materials/ProbeMat/Image_Texture.outputs:rgb>
        ...
    }

    def Shader "Image_Texture" ...
    def Shader "uvmap" ...

    def Shader "bnode__Principled_BSDF"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color.connect = </root/_materials/ProbeMat/NodeGraphs.outputs:node_out>
        ...
    }

    def NodeGraph "NodeGraphs" ...
}
```

The OpenPBR shader's output is named `surface` here, where the node definition declares
`out`. Both names resolve, and VM.PBR.001 accepts either. Hydra derives the MaterialX
terminal from the node definition's type, through `HdMtlxGetMxTerminalName`, and never looks
at the USD output property name. Both names are in circulation: `usdMtlx` normalises any
`surfaceshader`-typed output to `surface` when it loads a MaterialX document, so a MaterialX
file converted with no Blender in the picture lands the same way, while the shipped OpenPBR
material library authors `out`. Expect either in an asset somebody else made, and author
`out` to match the library.

No MDL surface is written, and that determines what Kit draws. Kit walks
`["mdl", "mtlx", ""]` and takes the first context the material has, as step 1 describes.
A Blender export has nothing ahead of `mtlx` in that list, so the OpenPBR surface is the
one that resolves, with no setting changed. The migrated sample in step 3 goes the other
way, with MDL in front.

### Confirm it conforms

The materials come out conformant, so the profile run is about what the rest of the export
is missing. Copy `bl_probe.usda` and its `textures/` beside it into the repository root, or
give the command an absolute path to where the export landed:

```bash
simready-validate --project-config sample_content/project_config.toml --profile Robotics-Prop --version 3.3.0 --output results.json bl_probe.usda
```

3.3.0 is the first Robotics-Prop version that requires `FET_006_STANDARD` instead of
marking it optional, so it is the one that tests whether the UsdPreviewSurface half of the
export holds up.

```text
Asset: bl_probe.usda
  [FAILED] Robotics-Prop v3.3.0
           FET_000_STANDARD: failing requirements: ['com.nvidia.simready.NP.005', 'com.nvidia.simready.NP.006']
           FET_003_STANDARD: failing requirements: ['com.nvidia.simready.RB.001']
           FET_004_STANDARD: failing requirements: ['com.nvidia.simready.RB.001']
           ...
```

Twelve lines, three distinct requirements, each repeated once per runtime physics variant.
RB.001 is `No physics rigid bodies found under the default prim`; NP.005 and NP.006 are
naming and path requirements a bare export does not meet. Physics and naming are outside
what this section covers.

The material features are absent from that list. The `features_summary` in `results.json`
gives them by name:

```text
FET_006_STANDARD      {"dependencies": "[]", "passed": true, "version": "0.2.0"}
FET_006_OPENPBR       {"dependencies": "[]", "passed": true, "version": "0.1.0"}
FET_006_MDL           {"dependencies": "[]", "passed": true, "version": "0.2.0"}
FET_010_STANDARD {"dependencies": "[]", "optional requirements": "['com.nvidia.simready.DISP.001']", "passed": true, "version": "0.1.0"}
```

The first three pass. The fourth is this export's one gap on visual materials: the probe
has no `primvars:displayColor`, so DISP.001 goes unsatisfied and shows up as an optional
requirement instead of a failure. The next subsection closes it.

```{note}
`migrate_to_openpbr.py --verify` and VM.PBR.001 both read `outputs:mtlx:surface`, so a
material with only OmniPBR on `outputs:mdl:surface` is a problem to each of them. They differ
in scope: `--verify` reads every material in the asset, while VM.PBR.001 resolves each
renderable Gprim's binding at the `full` purpose and judges only what comes back. A material
nothing binds is a `--verify` problem and outside VM.PBR.001.

Run the migration script over a Blender export and it leaves the material alone, reporting
a conflict, because it owns a prim named `OpenPBR_Shader` and Blender names its shader after
the Blender node.
```

### Display colour

A Color Attribute named `displayColor` is what produces `primvars:displayColor`. The name
does all the work. Three candidates measured on one export:

| Authored in Blender | Exported as |
|---|---|
| Color Attribute named `Col`, Blender's default | `color4f[] primvars:Col` |
| Color Attribute named `displayColor` | `color3f[] primvars:displayColor`, `interpolation = "faceVarying"` |
| Viewport Display colour on the material | nothing |

Only the rename gives both the right name and the right type, with alpha dropped on the
way. The Viewport Display colour never reaches the file.

For a mesh with no Color Attribute, step 3's script reads the export and authors the primvar
from the bound material instead:

```bash
python skills/simready-foundation-conform-fet-010-standard/assets/scripts/author_display_color.py bl_probe.usda --verify
```

```text
FAIL bl_probe.usda
  /root/ProbeCube/Cube: GPrim '/root/ProbeCube/Cube' does not resolve a 'primvars:displayColor', authored on the prim or inherited from an ancestor (DISP.001)

1 problem(s) across 1 asset(s) checked
```

```bash
python skills/simready-foundation-conform-fet-010-standard/assets/scripts/author_display_color.py bl_probe.usda
```

```text
bl_probe.usda: 1 authored, 0 skipped
  /root/ProbeCube/Cube: (0.3419, 0.1413, 0.0273)
      ProbeMat -> (0.3419, 0.1413, 0.0273)  UsdPreviewSurface diffuseColor <- be_basecolor.png sampled over 12 triangle(s)

Per-material area-weighted colour:
  ./ProbeMat: (0.3419, 0.1413, 0.0273) across 1 Gprim(s)

1 Gprim(s) given a display colour across 1 asset(s)
```

Note which tier the value came from. The script resolves OpenPBR first and here it fell
through to the UsdPreviewSurface, because on a Blender export the OpenPBR `base_color`
arrives through a `NodeGraph` output instead of straight from an image reader. Both tiers
hold the same map, so the value is the same either way.

## 3. Upgrading an Omniverse asset with OmniPBR

This path is for an asset that already exists and already has an OmniPBR (MDL) surface on
`outputs:mdl:surface`. The job is to add an OpenPBR surface and a display colour beside it
without disturbing what is there. It assumes an asset that already loads and passes the
core SimReady features.

Four passes follow: a baseline profile run, the OpenPBR conform, the display-colour
conform, and a second profile run.

### Establish a baseline

Run the profile the asset targets:

```bash
simready-validate --project-config sample_content/project_config.toml --profile Robotics-Prop --version 3.3.0 ../vm-workflow/gen_appliance_toaster_v01_01/simready_usd/sm_gen_appliance_toaster_v01_01.usd
```

`--project-config` takes the capability, feature and profile directories from the
`[validate]` section of that file, which the repository keeps pointed at the core tier.
Spelling the three out with `--rules-path`, `--features-path` and `--profiles-path` does
the same thing, and is the form
[SimReady Validation Workflow](../validate_workflow.md) shows. This guide takes the short
one because it runs the command four times.

The run prints a page of capability-parsing warnings before it prints anything about your
asset. The result is the last two lines, and the exit code is 0 for a pass and 1 for
anything else:

```text
Asset: ../vm-workflow/gen_appliance_toaster_v01_01/simready_usd/sm_gen_appliance_toaster_v01_01.usd
  [PASSED] Robotics-Prop v3.3.0
```

Name a profile version that does not exist and you get the `Asset:` line, no verdict, and
exit 1. The reason is in the warnings above it, as `Profile ... is not registered — cannot
validate`. Refer to [Profiles](../../profiles/profiles.md) for the versions on offer.

```{note}
A green profile line establishes less about visual materials than it appears to.
Robotics-Prop 3.3.0 requires the UsdPreviewSurface preview (`FET_006_STANDARD`) and marks
display colour, OpenPBR and MDL optional. Three profiles list `FET_006_OPENPBR` and
`FET_010_STANDARD`: Robotics-Prop, Robot-Body and Robot-Gripper. All three mark both
optional. An optional feature's requirements still run, and they are reported under
`optional requirements` in the JSON report, but they cannot fail the profile. So no profile
today fails an asset for shipping no OpenPBR surface or no display colour.
```

Two requirements ask for less than their names suggest:

- VM.PBR.001 asks for an OpenPBR surface on `outputs:mtlx:surface`, and nothing else on
  that terminal satisfies it. An MDL surface is `VM.MDL.003`, a separate requirement, so a
  profile that accepts either lists both. It resolves each renderable Gprim's binding at
  the `full` purpose and judges the material that comes back, so an unused material in
  `/Looks` and one bound only for preview both fall outside it.
- VM.PBR.003 asks for a connected surface terminal in *some* render context. A preview plus
  an MDL surface satisfies it with no MaterialX anywhere.

So a profile run covers everything except the OpenPBR and display-colour contracts. The
next two subsections each open with the tool that covers one of those.

### Conform the OpenPBR surfaces

Use the skill at `skills/simready-foundation-conform-fet-006-openpbr/`. Its bundled script
authors an OpenPBR surface on materials that already have a UsdPreviewSurface preview and an
OmniPBR final surface, which is the shape every sample under
`sample_content/common_assets/props_general/` has.

The path argument takes a USD file, or a directory to search for `simready_usd` assets.

Start with the state of the asset:

```bash
python skills/simready-foundation-conform-fet-006-openpbr/assets/scripts/migrate_to_openpbr.py ../vm-workflow/gen_appliance_toaster_v01_01 --verify
```

```text
ok   ../vm-workflow/gen_appliance_toaster_v01_01/simready_usd/sm_gen_appliance_toaster_v01_01.usd

0 problem(s) across 1 asset(s)
```

`--verify` reports VM.PBR.001, VM.PBR.002 and texture resolution, and exits 0 only when it
finds nothing. On an asset with no OpenPBR surface it exits 1 and prints one line per
material, each naming the prim, the problem and the requirement:

```text
/RootNode/Geometry/body_obj_01/body_mesh_01/VisualMaterials/m_opaque__plastic__toaster_v01_01: no outputs:mtlx:surface (VM.PBR.001)
```

Now see what a run would write, without writing anything:

```bash
python skills/simready-foundation-conform-fet-006-openpbr/assets/scripts/migrate_to_openpbr.py ../vm-workflow/gen_appliance_toaster_v01_01 --dry-run
```

```text
../vm-workflow/gen_appliance_toaster_v01_01/simready_usd/sm_gen_appliance_toaster_v01_01.usd: 6 migrated, 2 skipped (dry run)
  /RootNode/Geometry/body_obj_01/body_mesh_01/VisualMaterials/m_opaque__plastic__toaster_v01_01: emission_color=(1, 1, 1), geometry_opacity=1.0, specular_ior=1.5
      texture: base_color <- t_gen_appliance_toaster_v01_01_a.png (rgb)
      texture: base_metalness <- t_gen_appliance_toaster_v01_01_orm.png (b)
      texture: specular_roughness <- t_gen_appliance_toaster_v01_01_orm.png (g)
      texture: geometry_normal <- t_gen_appliance_toaster_v01_01_n.png (rgb)
  /RootNode/Geometry/body_obj_01/body_mesh_01/VisualMaterials/m_opaque__metal__toaster_v01_01: emission_color=(1, 1, 1), geometry_opacity=1.0, specular_ior=1.5
      texture: base_color <- t_gen_appliance_toaster_v01_01_a.png (rgb)
      texture: base_metalness <- t_gen_appliance_toaster_v01_01_orm.png (b)
      texture: specular_roughness <- t_gen_appliance_toaster_v01_01_orm.png (g)
      texture: geometry_normal <- t_gen_appliance_toaster_v01_01_n.png (rgb)
  ...

6 material(s) migrated across 1 asset(s)
24 channel(s) carried across as textures.
```

Those counts are what the run would author, whatever is there already. The script owns the
prims it writes and rewrites them from scratch every pass, so a conformant asset reports
the same six materials as a broken one. Each mesh has its own `VisualMaterials` scope, so a
material shared by several meshes is authored once per mesh. The two skipped materials are
the asset's physics materials, which describe friction, so the script leaves them alone.

Drop `--dry-run` to write. The output is the same, without `(dry run)`:

```bash
python skills/simready-foundation-conform-fet-006-openpbr/assets/scripts/migrate_to_openpbr.py ../vm-workflow/gen_appliance_toaster_v01_01
```

The four flags are `--verify`, `--dry-run`, `--textures` and `--no-textures`. Textures are
reconnected by default, so `--textures` names the default and changes nothing.
`--no-textures` flattens texture-driven channels to constants instead; those materials
still satisfy VM.PBR.001 and VM.PBR.002, and they will not look like the original. The
before-and-after image in step 5 is exactly that difference.

The prims the script owns are one `OpenPBR_Shader` per material plus the reader nodes named
`OpenPBR_Shader_*` beside it. A material that already has an OpenPBR surface under a
different prim name was authored by hand or by a DCC; the script reports it as a conflict
and leaves it alone. Because these assets are LFS-tracked binaries that cannot be merged,
re-running the script is the way to resolve a collision with someone else's edit.

A re-run rewrites the binary layer even when nothing changes, so the file hash moves. To
confirm a re-run was inert, compare flattened USD instead of file hashes.

```{note}
`--verify` checks authored scene description. It covers VM.PBR.001, VM.PBR.002 and whether
each texture it names resolves to a file. VM.PBR.003, the structural check on the shading
network, belongs to `simready-validate`.

VM.PBR.002 and VM.PBR.003 need MaterialX installed, which the Prerequisites cover.
```

### Conform display colour

Use the skill at `skills/simready-foundation-conform-fet-010-standard/`. Its script
authors a constant `primvars:displayColor` on every renderable Gprim, derived from the
material bound to that Gprim. It takes the same four flags as the OpenPBR script, with
`--textures` and `--no-textures` controlling whether base colour maps are sampled.

The script resolves base colour through OpenPBR first, then UsdPreviewSurface, then MDL, and
reports which tier it used. On these samples the first two tiers hold the same map, so
running this before or after the OpenPBR conform gives the same values.

```bash
python skills/simready-foundation-conform-fet-010-standard/assets/scripts/author_display_color.py ../vm-workflow/gen_appliance_toaster_v01_01 --verify
```

```text
FAIL ../vm-workflow/gen_appliance_toaster_v01_01/simready_usd/sm_gen_appliance_toaster_v01_01.usd
  /RootNode/Geometry/body_obj_01/body_mesh_01/body_mesh_01: GPrim '/RootNode/Geometry/body_obj_01/body_mesh_01/body_mesh_01' does not resolve a 'primvars:displayColor', authored on the prim or inherited from an ancestor (DISP.001)
  /RootNode/Geometry/lever_obj_01/lever_mesh_01: GPrim '/RootNode/Geometry/lever_obj_01/lever_mesh_01' does not resolve a 'primvars:displayColor', authored on the prim or inherited from an ancestor (DISP.001)
  ...

5 problem(s) across 1 asset(s) checked
```

`--verify` reports DISP.001 and DISP.002, one line per Gprim, and exits 1. None of the five
meshes has a display colour yet, which is what the authoring step below fixes; re-run it
afterwards and it reports `ok` and `0 problem(s)`.

Then author. `--edit-target binding` puts each opinion in the layer holding that Gprim's
`material:binding`, which for these samples is `payloads/instances.usda`. The meshes are
instanceable, and a primvar cannot be authored on an instance proxy at the path it appears
on, so the default `--edit-target stage` reaches nothing here:

```bash
python skills/simready-foundation-conform-fet-010-standard/assets/scripts/author_display_color.py ../vm-workflow/gen_appliance_toaster_v01_01 --edit-target binding
```

```text
../vm-workflow/gen_appliance_toaster_v01_01/simready_usd/sm_gen_appliance_toaster_v01_01.usd: 5 authored, 0 skipped
  /RootNode/Geometry/body_obj_01/body_mesh_01/body_mesh_01: (0.2469, 0.2459, 0.2434) -> instances.usda/Instances/body_mesh_01/body_mesh_01
      m_opaque__plastic__toaster_v01_01 -> (0.0840, 0.0840, 0.0840)  OpenPBR base_color <- t_gen_appliance_toaster_v01_01_a.png sampled over 13952 triangle(s)
      m_opaque__metal__toaster_v01_01 -> (0.3500, 0.3484, 0.3443)  OpenPBR base_color <- t_gen_appliance_toaster_v01_01_a.png sampled over 20640 triangle(s)
  /RootNode/Geometry/lever_obj_01/lever_mesh_01: (0.0123, 0.0123, 0.0123) -> instances.usda/Instances/lever_mesh_01/lever_mesh_01
      m_opaque__plastic__toaster_v01_01 -> (0.0123, 0.0123, 0.0123)  OpenPBR base_color <- t_gen_appliance_toaster_v01_01_a.png sampled over 940 triangle(s)
  /RootNode/Geometry/tray_obj_01/tray_mesh_01: (0.3788, 0.3731, 0.3592) -> instances.usda/Instances/tray_mesh_01/tray_mesh_01
      m_opaque__metal__toaster_v01_01 -> (0.3788, 0.3731, 0.3592)  OpenPBR base_color <- t_gen_appliance_toaster_v01_01_a.png sampled over 2012 triangle(s)
  ...
  instances.usda: 5 colour(s) authored

Per-material area-weighted colour:
  gen_appliance_toaster_v01_01/m_opaque__metal__toaster_v01_01: (0.3506, 0.3489, 0.3446) across 2 Gprim(s)
  gen_appliance_toaster_v01_01/m_opaque__plastic__toaster_v01_01: (0.0822, 0.0822, 0.0822) across 4 Gprim(s)

5 Gprim(s) given a display colour across 1 asset(s)
```

Read the per-material lines under each Gprim as well as the value. They name which material
each contribution came from and how it was derived, and the same record goes into the
primvar's `customData` so it survives in the file:

```usda
color3f[] primvars:displayColor = [(0.37882704, 0.3730906, 0.35922563)] (
    colorSpace = "lin_rec709_scene"
    customData = {
        dictionary simready = {
            string displayColorSource = "m_opaque__metal__toaster_v01_01: OpenPBR base_color <- t_gen_appliance_toaster_v01_01_a.png sampled over 2012 triangle(s)"
        }
    }
    interpolation = "constant"
)
```

The console rounds to four decimals for reading; the primvar holds the full value.

Three properties of the derivation decide what its output is good for.

**One colour per Gprim.** The value is the area-weighted mean of the texels the bound
geometry lands on, taken in linear light. Where a Gprim has several materials through
`materialBind` GeomSubsets, they are blended. The toaster's body mesh resolves
`(0.2469, 0.2459, 0.2434)`, which matches neither its plastic `(0.0840, 0.0840, 0.0840)`
nor its metal `(0.3500, 0.3484, 0.3443)`. A printed label or a painted stripe disappears
into the mean.

**Sampling only where the geometry lands.** Five of the electricians toolbox's materials
share one atlas. Averaging the whole image would hand the same yellow to all five;
sampling per material gives the locks `(0.011, 0.010, 0.007)` and the lid
`(0.633, 0.448, 0.042)`.

**Nothing is invented.** A Gprim with no bound material, no base colour, or an unresolvable
texture is listed as `SKIPPED` with its reason and left without a display colour, so
DISP.001 still fails on it visibly. Out-of-range components are clamped; NaN and Inf are
refused.

The script is safe to re-run, and its sampling uses a fixed stratified point set instead of
a random one, so a second pass over an unchanged asset produces the same values. Geometry
that already has a display colour without the `simready:displayColorSource` record was
authored by hand, and is reported as a conflict and left alone.

### Re-validate

Run the baseline command again, against the copy you have been working on:

```bash
simready-validate --project-config sample_content/project_config.toml --profile Robotics-Prop --version 3.3.0 ../vm-workflow/gen_appliance_toaster_v01_01/simready_usd/sm_gen_appliance_toaster_v01_01.usd
```

```text
Asset: ../vm-workflow/gen_appliance_toaster_v01_01/simready_usd/sm_gen_appliance_toaster_v01_01.usd
  [PASSED] Robotics-Prop v3.3.0
```

The console line is identical whatever the two conform scripts did, because the features
they conform are optional in every profile that lists them. To see per-feature detail, write
a JSON report:

```bash
simready-validate --project-config sample_content/project_config.toml --profile Robotics-Prop --version 3.3.0 --output results.json ../vm-workflow/gen_appliance_toaster_v01_01/simready_usd/sm_gen_appliance_toaster_v01_01.usd
```

`results.json` is keyed by asset path, and each asset has a `features_summary` with one
entry per feature holding `passed`, `version`, `dependencies` and, where they apply,
`failing requirements` and `optional requirements`. The four visual-material features on
the conformed toaster:

```text
FET_010_STANDARD {"dependencies": "[]", "passed": true, "version": "0.1.0"}
FET_006_MDL           {"dependencies": "[]", "passed": true, "version": "0.2.0"}
FET_006_OPENPBR       {"dependencies": "[]", "passed": true, "version": "0.1.0"}
FET_006_STANDARD      {"dependencies": "[]", "passed": true, "version": "0.2.0"}
```

This is where an unmet optional requirement shows up. An asset whose materials have no
physically based final surface still reports `"passed": true` for `FET_006_OPENPBR`, with
the requirement it missed listed alongside:

```text
FET_006_OPENPBR       {"dependencies": "[]", "optional requirements": "['com.nvidia.simready.VM.PBR.001']", "passed": true, "version": "0.1.0"}
```

Removing the OpenPBR surface produces that line even where an MDL surface remains, since
VM.PBR.001 reads only `outputs:mtlx:surface`.

So `optional requirements` lists what did not pass and did not block. For a visual-materials
review that makes the JSON the interesting output, and it makes each conform script's
`--verify` your pass or fail gate for its own feature. `--verify` is the only place today
where a missing OpenPBR surface or a missing display colour produces a non-zero exit code.

Refer to [SimReady Validation Workflow](../validate_workflow.md) for stamping results into
the asset with `--stamp-asset-validation`, which is what makes the benchmark plan these
tests without `--features`.

## 4. Benchmark

Four tests cover visual materials. Each loads the asset in Kit and measures pixels.

| Test | What it renders | Feature |
|---|---|---|
| [openpbr_renders](../benchmark/tests/fet006/openpbr-renders.md) | The OpenPBR surface on `outputs:mtlx:surface` | `FET_006_OPENPBR` |
| [mdl_renders](../benchmark/tests/fet006/mdl-renders.md) | The MDL surface on `outputs:mdl:surface` | `FET_006_MDL` |
| [preview_surface_renders](../benchmark/tests/fet006/preview-surface-renders.md) | The UsdPreviewSurface on `outputs:surface` | `FET_006_STANDARD` |
| [display_color_response](../benchmark/tests/fet010/display-color-response.md) | `primvars:displayColor` through the OpenPBR material DISP.001 nominates | `FET_010_STANDARD` |

The first three share a room, a light rig and a camera framing, so a difference between them
comes from the material. Each puts its own render context at the front of Kit's list, checks
the value took before it renders anything, and puts the list back afterwards. Nothing edits
the asset's materials. The number each one reports is what the geometry bound to a material
with that context contributed, measured by hiding exactly that geometry and differencing, so
on a partly migrated asset it is smaller than what the asset as a whole drew.

`display_color_response` works by substitution. It binds one material over the whole asset
from a single relationship on the asset's root prim, marked
`bindMaterialAs = "strongerThanDescendants"`, which beats every binding the asset authors
below it, including bindings inside prototypes. That material is the OpenPBR surface DISP.001's
guidance nominates, with a MaterialX primvar reader feeding `displayColor` into `base_color`.
The test renders the asset through four variants of it and takes the answer from the
differences:

| Variant | What it changes | What the difference answers |
|---|---|---|
| Read | The reader, falling back to magenta | The frame everything else is compared against |
| Altered | The same reader, falling back to green | Whether any Gprim fell back, which is DISP.001 |
| Removed | No reader, flat magenta | Whether the primvar drove the pixels, or a constant did |
| Opacity | The Read material with the `displayOpacity` fallback at 0 | DISP.003 |

Nothing on the asset is edited and nothing is written to disk. `mtlx` has to be in Kit's
render-context list for the substituted material to resolve at all, so the test checks the
list and fails the run when it is missing.

The asset's stamped profile drives planning, so an asset stamped against a profile without
a feature will not pick its tests up. `--features` bypasses that gate while the plan is
built:

```bash
simready-benchmark --assets ../vm-workflow/gen_appliance_toaster_v01_01/simready_usd/sm_gen_appliance_toaster_v01_01.usd --features FET_006_OPENPBR
```

```bash
simready-benchmark --assets ../vm-workflow/gen_appliance_toaster_v01_01/simready_usd/sm_gen_appliance_toaster_v01_01.usd --features FET_010_STANDARD
```

Pass one `--features` value per invocation. `--only-features` is a different flag: it
narrows a plan that already exists, where `--features` acts while the plan is built. Refer
to [Running Tests](../benchmark/running.md) for installation and engine configuration.

A surface test can skip, fail or pass. It skips when no material on the asset has a surface
for its context, because the asset never claimed that feature: an asset shipping only MDL
skips the OpenPBR and UsdPreviewSurface tests instead of failing them. It fails in two
cases: the asset has the surface but no material with it is bound to geometry the render
draws, and the bound geometry draws too few pixels to measure. Otherwise it passes.

## 5. Read the report

Results land under `_testing/`. Open `index.html` for the run, with a page per asset under
`_testing/assets/`. Captured frames and the per-test `result.json` sit under
`_testing/results/<asset path>/.simready/runtime/<test name>/`. Refer to
[Reading Reports](../benchmark/reading-reports.md) for the full layout and exit codes.

The frames are more informative than the counts, so open them. Each surface test keeps four: the
asset hidden, that frame repeated to establish a noise floor, the asset shown with its
supporting geometry hidden, and the asset shown. The number the test judges is the difference
between the last two.

![openpbr_renders expected result](../benchmark/tests/_images/openpbr-renders.png)

The toaster in the mid-grey room, shaded by the OpenPBR surface on `outputs:mtlx:surface`.
One run of `openpbr_renders` on this sample reported five Gprims bound to a material with
an OpenPBR surface, drawing 293,685 pixels against a 212 pixel noise floor, with the
context list pinned to `[mtlx, mdl, universal]`. Two identical frames would mean that
geometry contributed nothing.

### What a pass establishes

Geometry bound to a material with the named surface drew the frame, with that context
first in Kit's list. That is a stronger claim than "the asset rendered": the test resolves
bindings before it measures, so an unbound MaterialX material sitting in `/Looks` cannot
supply the pass while other materials supply the pixels.

`display_color_response` establishes that the display colours in the file reach the shader.
Swapping the primvar reader's fallback changes the frame only where a Gprim resolved no
display colour, so a pass means none did. Taking the reader out entirely changes the frame
wherever the primvar was driving the shading, so a pass means it was. The test also checks
the file for coverage and reports both answers side by side. Their disagreement is the
useful signal: a file that resolves everywhere and a render that does not means the primvar
is not reaching the shader, which is a different defect from the asset not having one.

![display_color_response expected result](../benchmark/tests/_images/display-color-response.png)

### What a pass does not establish

That the surface network under test is the one Kit evaluated. The trailing render contexts
stay in the list as fallbacks, deliberately, because without them everything with no surface
for the pinned context renders as the default material. So geometry whose OpenPBR network
fails to resolve still draws, through MDL, and still counts. Catching that needs a probe
that writes a known value into the shader under test and looks for it, which means editing
the material, and no test in this family does that today.

Nor does a pass establish that the surface looks correct or has its intended textures. The clearest
way to see the size of that gap is the same prop rendered through the same room, light rig
and camera, before and after migration:

![OpenPBR surface before and after sample migration](../benchmark/tests/_images/openpbr-migration-before-after.png)

Left, the OpenPBR surface with constant inputs and no textures wired: flat white, because
`base_color` was unauthored and fell back to the node definition's default. Right, the same
prop after migration kept its maps. Both pass `openpbr_renders`. Everything
separating those two frames is outside what the test judges, which is why the frames are
kept instead of reduced to a number.

The same boundary applies to display colour, and `display_color_response` is explicit about
it. The test asserts nothing about which display colour is brighter than which, and no match
between a pixel and an authored value. RTX tone-maps and the scene is dome-lit, so no
absolute match is available, and DISP.002 sets no plausibility band to check a relative one
against. Whether the shipped colours are the right colours is not something a render can
settle: the conform script's derivation approximates albedo without claiming to match what a
path tracer produces for the same object.

A full green run supports one narrow claim. The asset has the surfaces and primvars the
features describe, the values are in range, and the geometry bound to each surface drew the
frame with that context resolved first. Whether the asset looks right is a judgement a human
still has to make by looking at the frames.

## Common mistakes

| Symptom | Cause | Fix |
|---|---|---|
| Migrated asset looks unchanged in Kit | Kit resolved the MDL surface, which sits ahead of `mtlx` in the shipped context order | Run the step 4 benchmark, which pins the context and confirms the pin took |
| Display colours all come back `(0.8, 0.8, 0.8)` | `numpy` or `Pillow` is missing, so the script fell back to material constants | Install both and re-run; the log records when this happened |
| Display colour looks washed out | An sRGB value was written without converting to linear | Decode through the sRGB transfer function first |
| A profile pass on an asset with no OpenPBR surface | `FET_006_OPENPBR` is `optional=true` in every shipped profile | Use `migrate_to_openpbr.py --verify` as the gate |
| A Blender export has no `outputs:mtlx:surface` | `generate_materialx_network` is `False` by default | Set it to `True` and export again |
| A Blender export has an unreferenced copy under `textures/` | `export_textures_mode` was set to `KEEP` or `PRESERVE` with the MaterialX network on | Leave the mode on `NEW` |

## Where to go next

- [FET006 OpenPBR Materials](../../features/FET_006_OPENPBR.md) and [FET010 Display Color](../../features/FET_010_STANDARD.md) for the two contracts in full.
- [Visual Materials capability](../../capabilities/visualization/materials/requirements/material-final-surface.md) for VM.PBR.001, and [Display Color capability](../../capabilities/visualization/display_color/capability-display_color.md) for DISP.001 to DISP.003.
- [FET006 Materials](../benchmark/tests/fet006-materials.md) and [FET010 Display Color](../benchmark/tests/fet010-display-color.md) for the benchmark families and what each test guards against.
- [SimReady Validation Workflow](../validate_workflow.md) for validator setup, JSON reports and stamping.
- [Profiles](../../profiles/profiles.md) for which profiles select these features and at which version.
