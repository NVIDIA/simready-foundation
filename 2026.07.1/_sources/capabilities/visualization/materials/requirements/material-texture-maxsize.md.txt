# material-texture-maxsize

| Code     | VM.TEX.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-tex-001` |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`performance` |

## Summary

Texture dimensions must not exceed 16,384 pixels on either axis to ensure optimal performance and memory usage in simulation environments.

## Description

All texture assets referenced by material shaders must comply with a maximum resolution limit of 16K (16,384 pixels) on both width and height. This requirement applies to all image formats including:

- PNG (.png)
- JPEG (.jpg, .jpeg)
- OpenEXR (.exr)
- HDR (.hdr)
- Targa (.tga)
- Bitmap (.bmp)
- TIFF (.tif, .tiff)

Textures exceeding this limit can cause:
- Excessive memory consumption
- Performance degradation in real-time simulation
- GPU memory overflow on systems with limited VRAM
- Increased loading times
- Potential crashes or instability

The 16K limit provides a balance between visual quality and performance for simulation-ready assets.

## Why is it required?
- Ensures consistent performance across different hardware configurations
- Prevents out-of-memory errors in simulation environments
- Maintains reasonable asset loading times
- Supports real-time rendering requirements
- Enables assets to work on systems with limited GPU memory
- Promotes efficient texture usage and optimization practices

## Examples

```usd
# Invalid: Texture exceeds maximum size
def Material "OversizedTextureMaterial"
{
    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./SimPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "SimPBR"
        
        # This texture is 32768x32768 pixels - exceeds 16K limit
        asset inputs:diffuse_texture = @./textures/huge_albedo_32k.png@
    }
}

# Invalid: One dimension exceeds limit
def Material "WideTextureMaterial"
{
    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./SimPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "SimPBR"
        
        # This texture is 20000x8000 pixels - width exceeds 16K limit
        asset inputs:diffuse_texture = @./textures/wide_albedo.png@
    }
}

# Valid: Texture within size limits
def Material "ValidTextureMaterial"
{
    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./SimPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "SimPBR"
        
        # 8192x8192 pixels - within 16K limit
        asset inputs:diffuse_texture = @./textures/albedo_8k.png@
        
        # 4096x4096 pixels - within 16K limit
        asset inputs:roughness_texture = @./textures/roughness_4k.png@
        
        # 2048x2048 pixels - within 16K limit
        asset inputs:normal_texture = @./textures/normal_2k.png@
    }
}

# Valid: Maximum allowed size
def Material "MaxSizeTextureMaterial"
{
    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./SimPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "SimPBR"
        
        # 16384x16384 pixels - exactly at 16K limit (valid)
        asset inputs:diffuse_texture = @./textures/albedo_16k.png@
    }
}
```

## How to comply

### Resize Existing Textures:
- Use image editing tools to downscale textures exceeding 16K
- Common target resolutions: 8K (8192), 4K (4096), 2K (2048), 1K (1024)
- Maintain aspect ratio when resizing
- Use high-quality resampling filters (bicubic or Lanczos)

### Optimize Texture Usage:
- Use appropriate resolution based on the asset's real-world size and viewing distance
- Consider texture density (pixels per meter) for optimal quality
- Use lower resolutions for textures that won't be viewed up close
- Reserve higher resolutions (8K-16K) only when absolutely necessary

### Texture Atlasing:
- Combine multiple smaller textures into atlases rather than using oversized textures
- Use texture trim/cropping to remove unused space
- Optimize UV layouts for efficient texture space usage

### Format Considerations:
- Use compression-friendly formats (PNG, JPEG) for color/albedo maps
- Consider lower resolutions for metallic, roughness, and AO maps
- Use appropriate bit depth for each texture type

## For More Information
- [USD Asset Path Resolution](https://openusd.org/release/api/ar_page_front.html)
- [Texture Optimization Best Practices](https://developer.nvidia.com/texture-optimization)
- [Real-time Rendering Texture Guidelines](https://openusd.org/release/spec_usdpreviewsurface.html)
