# material-texture-maxsize

| Code     | VM.TEX.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-tex-001` |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`correctness` |

## Summary

Texture dimensions must not exceed 16,384 pixels on either axis.

## Description

No texture may exceed 16,384 pixels in width or height. This applies to every asset-valued
attribute whose resolved path ends in one of these extensions:

- PNG (.png)
- JPEG (.jpg, .jpeg)
- OpenEXR (.exr)
- HDR (.hdr)
- Targa (.tga)
- Bitmap (.bmp)
- TIFF (.tif, .tiff)

Dimensions come from the image file, not from the scene description, so conformance cannot be
established from the USD alone. A texture whose file is absent or unreadable is not reported.

16,384 is an API limit. `D3D11_REQ_TEXTURE2D_U_OR_V_DIMENSION` and its Direct3D 12
counterpart are both 16,384, so a D3D11 or D3D12 device rejects a larger 2D texture on any
GPU. Vulkan leaves the maximum to the device and requires only 4,096 of a conformant
implementation.

Above the limit, texture creation fails. Nothing binds, and the material renders with the
shader's fallback: a flat base color, or an unlit surface. The asset loads and renders
incorrectly instead of failing to load.

A device may report more. An NVIDIA RTX A6000 reports `maxImageDimension2D = 32768` under
Vulkan 1.4, so a 32K texture renders on the machine it was authored on and fails on a D3D11
renderer.

## Why is it required?
- A texture above the API limit is not created at all, so the material renders without it and the asset looks wrong instead of failing to load
- The limit is the same on every Direct3D device and is not guaranteed to be higher on any Vulkan one, so a texture inside it can be created wherever the asset opens
- Whether an asset renders correctly stays a property of the asset, not of the GPU that opens it
- Bounds worst-case VRAM per texture, which matters where several assets share a scene

## Examples

The USD below states which file a material reads and nothing about its size. The dimensions
in each comment are what that file holds.

### Valid: three textures inside the limit

```usd
def Material "opaque__metal__bracket"
{
    token outputs:mdl:surface.connect = </opaque__metal__bracket/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./materials/OmniPBR/OmniPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
        asset inputs:diffuse_texture = @./textures/bracket_basecolor.png@              # 8192x8192
        asset inputs:reflectionroughness_texture = @./textures/bracket_roughness.png@  # 4096x4096
        asset inputs:normalmap_texture = @./textures/bracket_normal.png@               # 2048x2048
        token outputs:out
    }
}
```

### Valid: exactly at the limit

```usd
def Material "opaque__metal__bracket"
{
    token outputs:mdl:surface.connect = </opaque__metal__bracket/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./materials/OmniPBR/OmniPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
        asset inputs:diffuse_texture = @./textures/bracket_basecolor_16k.png@  # 16384x16384
        token outputs:out
    }
}
```

16,384 itself passes: the comparison is on what exceeds the limit.

### Invalid: both dimensions above the limit

```usd
def Material "opaque__metal__bracket"
{
    token outputs:mdl:surface.connect = </opaque__metal__bracket/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./materials/OmniPBR/OmniPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
        asset inputs:diffuse_texture = @./textures/bracket_basecolor_32k.png@  # 32768x32768
        token outputs:out
    }
}
```

### Invalid: one dimension above the limit

```usd
def Material "opaque__metal__bracket"
{
    token outputs:mdl:surface.connect = </opaque__metal__bracket/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./materials/OmniPBR/OmniPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
        asset inputs:diffuse_texture = @./textures/bracket_basecolor_wide.png@  # 20000x8000
        token outputs:out
    }
}
```

Either axis is enough: 20,000 wide is reported although the height is well inside the limit.

## How to comply

- Resize any texture above 16,384 pixels on either axis. Common targets are 8K (8192), 4K (4096), 2K (2048) and 1K (1024); keep the aspect ratio.
- Split a source image needing more than 16K of detail across several textures and UV regions. Do not rely on the renderer accepting an oversize one.
- Texture density, atlasing and bit depth are authoring decisions outside this requirement.

## For More Information
- [Direct3D 11 resource limits](https://learn.microsoft.com/en-us/windows/win32/direct3d11/overviews-direct3d-11-resources-limits)
- [Vulkan required limits](https://registry.khronos.org/vulkan/specs/latest/html/vkspec.html#limits-required)
- [USD Asset Path Resolution](https://openusd.org/release/api/ar_page_front.html)
- [Texture Optimization Best Practices](https://developer.nvidia.com/texture-optimization)
