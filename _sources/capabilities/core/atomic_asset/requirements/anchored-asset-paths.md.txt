# anchored-asset-paths

| Code     | AA.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`aa-001` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

Asset references should use anchored paths

## Description

For reproducible results, asset references should use anchored paths (paths that begin with "./" or "../") rather than absolute paths or search paths. Paths containing `../` should also be encapsulated and avoid to target locations above the asset root.

## Why is it required?

- Ensures assets resolve consistently across different environments
- Prevents dependency on environment-specific search paths
- Makes assets self-contained and portable

## Examples

```usd
# Valid: Using anchored paths
def Material "MyMaterial"
{
    def Shader "diffuseTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/diffuse.png@  # Anchored path
        token outputs:rgb
    }
}

# Invalid: Using search path
def Material "MyMaterial"
{
    def Shader "diffuseTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @textures/diffuse.png@  # Search path
        token outputs:rgb
    }
}

# Invalid: Using absolute path
def Material "MyMaterial"
{
    def Shader "diffuseTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @/projects/assets/textures/diffuse.png@  # Absolute path
        token outputs:rgb
    }
}


# Invalid: Using asset root path that targets a location above the asset root
# root.usda

def Material "MyMaterial"
{
    def Shader "diffuseTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @../another/asset/textures/diffuse.png@  # Targets a location above the asset root
        token outputs:rgb
    }
}


```

## How to comply

- Use anchored paths (starting with "./" or "../") for all asset references
- Encapsulate paths containing `../` to avoid targeting locations above the asset root
- Organize assets in a relative directory structure
- Avoid absolute paths or search paths that depend on resolver configuration
- In Omniverse, use the ["collect extension"](https://docs.omniverse.nvidia.com/extensions/latest/ext_collect.html) to localize assets
- In Omniverse, avoid using path-less material references such as `OmniPBR` or `OmniGlass` that rely on Omniverse's default material search paths


## For More Information

- [USDZ File Format Specification - For Reproducible Results, Encapsulate Using Anchored Asset Paths](https://openusd.org/release/spec_usdz.html#for-reproducible-results-encapsulate-using-anchored-asset-paths) 