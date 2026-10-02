# Materials Requirements Overview

To fulfill the requirements of this capability, materials must be properly defined using a portable material specification such as OpenPBR.


## Material Implementation within OpenUSD

```{admonition} Requirement
- **Materials must use valid OpenPBR specifications**
- **Material paths and bindings must be properly scoped and resolvable**
- **Material attributes must comply with their respective schemas**
```

## Schema
<!-- SCORE_TAG:LINK_TO_SCHEMA_DOCS:CORE -->
Materials is defined with the [UsdShade schema](https://openusd.org/release/api/usd_shade_page_front.html), implementing OpenPBR via [MaterialX](https://developer.nvidia.com/blog/unlock-seamless-material-interchange-for-virtual-worlds-with-openusd-materialx-and-openpbr/).

## Choosing the right material feature

An asset may carry any combination of the four. None depends on another, and a consumer uses
whichever it can evaluate. **The profile decides which are required** — the current profiles
require UsdPreviewSurface and make the rest optional additions.

| Feature | What it is | Surface output | Render context |
|---|---|---|---|
| `FET_006_STANDARD` | UsdPreviewSurface — the portable baseline every OpenUSD consumer can render | `outputs:surface` | universal |
| `FET_010_STANDARD` | A flat per-prim color with no shading network, readable without evaluating a material | none — `primvars:displayColor` | none |
| `FET_006_OPENPBR` | The high-fidelity path, for physically plausible response in RTX and Isaac Sim | `outputs:mtlx:surface` | `mtlx` |
| `FET_006_MDL` | NVIDIA-specific. Add it when a consumer needs OmniPBR behaviour; it does not travel outside Omniverse | `outputs:mdl:surface` | `mdl` |

Each of the four requires its own surface to be present on the materials a renderable GPrim
resolves: `VM.PS.002`, `VM.PBR.001`, `VM.MDL.003`, and `DISP.001` for display colour. A pass
therefore means the asset has that surface, which is what lets a library search validation
metadata for the assets a given consumer can render.


Add UsdPreviewSurface always. Add display color when cheap legibility matters — highly parallel Isaac Lab training runs, fast visualizations of large datasets. Add OpenPBR when appearance has to hold up across runtimes/renders as it is the future proof material description format for OpenUSD. Add MDL only for Omniverse consumers that need it for legacy reasons.


## Texture formats

PNG and JPEG are recommended and are considered sufficient quality for
SimReady textures. TIFF, TGA and EXR are permitted.

(color-space-overview)=
## Color space

Constants are always linear. Textures carry the color space declared on them. A texture that
declares nothing is not treated the same way on every surface, so an asset carrying more than
one must declare it explicitly.

- **Display Colors**
  - `primvars:displayColor` — linear, Rec.709 primaries, D65 white point. `0.18` is mid grey.
  - `primvars:displayOpacity` — raw float, no color space. `0.5` is half transparent.
- **UsdPreviewSurface** — `VM.TEX.003`.
  - color inputs — `diffuseColor`, `emissiveColor`, `specularColor`
    - without textures:
      — values are in linear (same as display colors): `0.18` is mid grey
    - with textures:
      - color space is defined by `inputs:sourceColorSpace` on `UsdUVTexture` nodes.
      - its default value is `auto`, which resolves to `sRGB` for any 8-bit texture with 3 or
        4 channels. Bit depth and channel count decide this, not the file format: an 8-bit RGB
        TIFF or TGA decodes exactly as a PNG does, while a 16-bit PNG, an EXR or a
        single-channel mask does not
      - this means the attribute does not have to be specified for those textures
      - Note: A value of `118` in 8-bit textures equates to mid grey
  - data inputs — `roughness`, `metallic`, `opacity`, `normal`
    - without textures — raw float: `0.5` is mid roughness
    - with textures:
      - color space is defined by `inputs:sourceColorSpace` on `UsdUVTexture` nodes.
      - as above, this defaults to `sRGB` for any 8-bit 3- or 4-channel texture, which is
        *incorrect for data channels*, so `inputs:sourceColorSpace` has to be specified and set
        to `raw`. The exception is single-channel textures (only R, for example), where the
        `auto` default already resolves to `raw`. Swapping a single-channel roughness texture
        for a three-channel one therefore flips the decode with no other change to the asset
      - Note: A value of `128` in 8-bit textures equates to mid roughness/opacity etc
- **OpenPBR / MaterialX** — `VM.TEX.004`.
  - color inputs — `base_color`, `emission_color`, `specular_color`, `coat_color`,
    `fuzz_color`, `subsurface_color`, `transmission_color`
    - without textures:
      — values are in linear (same as display colors): `0.18` is mid grey
    - with textures:
      - color space is defined by `colorSpace` metadata on the image node's `inputs:file`.
      - unlike OpenUSD's `UsdUVTexture`, MaterialX has no `auto` value. An undeclared color
        space means no transform, whatever the file is, so a color texture has to declare one
        or it is consumed undecoded and renders washed out
      - two names describe this encoding. OpenUSD adopted the ASWF Color Interop Forum
        convention `srgb_rec709_scene` in 24.11; MaterialX uses `srgb_texture`, and that is the
        name its transform nodes are actually defined under. MaterialX 1.39.4 added a mapping
        so that `srgb_rec709_scene` resolves to `srgb_texture` — the USD name is translated to
        the MaterialX one, and `srgb_texture` keeps working either way.
      - **author `srgb_texture`.** It resolves in every MaterialX version, whereas
        `srgb_rec709_scene` only resolves from 1.39.4 onward and no (Omniverse) runtimes that SimReady targets
        ships that yet (Kit 110.1.0, Isaac Sim 5.0.0, USD 25.11).
        Move to `srgb_rec709_scene` once they do; MaterialX 1.40 is expected to
        make the Color Interop names native and `srgb_texture` the legacy spelling
      - Note: A value of `118` in 8-bit textures equates to mid grey
  - data inputs — `specular_roughness`, `base_metalness`, `geometry_normal`, `geometry_opacity`
    - without textures — raw float: `0.5` is mid roughness
    - with textures:
      - color space is defined by `colorSpace` metadata on the image node's `inputs:file`.
      - as there is no `auto`, leaving it undeclared already means no transform, which is what
        a data channel needs. Declare no `colorSpace`, or declare `none` — MaterialX's token
        for "apply no transform", spelled in lower case
      - Note: RTX rejects `none` and logs an error for it. The error is benign: a rejected
        transform is no transform, which is what the channel wants, so the render is unaffected
        and only the log is. hdStorm accepts `none` without complaint
      - Note: A value of `128` in 8-bit textures equates to mid roughness/opacity etc
- **MDL / OmniPBR** — `VM.TEX.002`.
  - color inputs — `diffuse_texture`, `emissive_color_texture`
    - without textures (`diffuse_color_constant`):
      — values are in linear (same as display colors): `0.18` is mid grey
    - with textures:
      - MDL has no separate texture node. The color space is `colorSpace` metadata on the
        shader's own `asset inputs:*` attribute
      - the default is `auto`, resolving to `sRGB` for 8-bit textures with 3 or 4 channels,
        so the attribute does not have to be specified for those textures
      - `srgb_rec709_scene` also resolves here and is accepted. It is not resolved on the
        OpenPBR surface, but the two surfaces declare their color space on separate
        attributes — MDL on the shader prim itself, MaterialX through the image node's
        `inputs:file` — so the spelling used here does not reach the OpenPBR one
      - Note: A value of `118` in 8-bit textures equates to mid grey
  - data inputs — `reflectionroughness_texture`, `metallic_texture`, `normalmap_texture`,
    `ao_texture`
    - without textures (`reflection_roughness_constant`) — raw float: `0.5` is mid roughness
    - with textures:
      - the color space is `colorSpace` metadata on the shader's own `asset inputs:*`
        attribute, as above
      - the `auto` default applies here too. MDL does not read the input name at render time,
        so an 8-bit RGB data texture is decoded as sRGB exactly as a color texture is, which
        is *incorrect for data channels*. Set `raw`. Single-channel textures are the exception,
        where `auto` already resolves to `raw`
      - Note: A value of `128` in 8-bit textures equates to mid roughness/opacity etc

## Requirements

The requirements listed here can be uniquely identified by their respective identifiers. Validators may refer to these ID's to denote compliance.

<!-- SCORE_TAG:LIST_OF_REQUIREMENTS -->
<!-- MATERIALS_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- MATERIALS_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/material-mdl-source-asset
requirements/material-assignment
requirements/material-shader-inputs
requirements/material-texture-colorspace-mdl
requirements/material-texture-colorspace-preview
requirements/material-texture-colorspace-openpbr
requirements/material-texture-colorspace-mdl-deprecated
requirements/material-texture-maxsize
requirements/material-final-surface
requirements/material-pbr-parameter-ranges
requirements/material-shading-network-structure
```
