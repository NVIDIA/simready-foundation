# path-length-limits

| Code     | NP.004 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`np-004` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

File and directory paths shall not exceed platform limits

## Description

File and directory paths in USD assets shall not exceed the path length limitations of target platforms to ensure compatibility and proper file system operations. This includes both absolute and relative paths, and accounts for different operating system limitations.

## Why is it required?

- Ensures compatibility across different operating systems
- Prevents file system errors and access issues
- Enables proper asset portability
- Supports automated processing and deployment
- Prevents issues with version control systems

## Examples

```usd
# Valid: Short, descriptive paths
# asset_name/
#   ├── chair.usd
#   ├── materials/
#   │   └── wood_material.usd
#   └── textures/
#       └── wood_diffuse.png

# Valid: Relative paths within limits
def Material "WoodMaterial"
{
    def Shader "diffuseTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/wood_diffuse.png@  # Short relative path
        token outputs:rgb
    }
}

# Invalid: Excessively long paths
# very_long_asset_name_with_many_descriptive_words_that_make_the_path_too_long/
#   ├── very_long_asset_name_with_many_descriptive_words_that_make_the_path_too_long.usd
#   ├── materials/
#   │   └── very_long_material_name_with_many_descriptive_words_that_make_the_path_too_long.usd
#   └── textures/
#       └── very_long_texture_name_with_many_descriptive_words_that_make_the_path_too_long.png

# Invalid: Long relative paths
def Material "VeryLongMaterialNameWithManyDescriptiveWords"
{
    def Shader "VeryLongShaderNameWithManyDescriptiveWords"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./very_long_directory_name_with_many_descriptive_words/very_long_texture_name_with_many_descriptive_words.png@  # Path too long
        token outputs:rgb
    }
}
```

## How to comply

- Keep file and directory names concise but descriptive
- Use abbreviations where appropriate (e.g., "mat" for "material", "tex" for "texture")
- Limit directory nesting depth
- Use relative paths when possible
- Test paths on target platforms (Windows: 260 characters, macOS/Linux: 4096 characters)
- Consider using shorter base names for assets
- Use consistent naming patterns to reduce overall path length

## Platform Limits

- **Windows**: 260 characters for most operations (can be extended to 32,767 with UNC paths)
- **macOS**: 1024 characters (HFS+) or 4096 characters (APFS)
- **Linux**: 4096 characters
- **USD**: No specific limit, but follows underlying file system

## For More Information

- [Windows Path Length Limitations](https://docs.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation)
- [USD Best Practices - Path Management](https://openusd.org/release/tut_usd_best_practices.html#path-management)
