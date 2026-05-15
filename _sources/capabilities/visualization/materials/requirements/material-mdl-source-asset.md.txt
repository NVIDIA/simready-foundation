# material-mdl-source-asset

| Code     | VM.MDL.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-mdl-001` |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`correctness` |

## Summary

MDL material source assets must be properly referenced and accessible to ensure material loading and rendering.

## Description

MDL material source assets must be properly referenced using the `info:mdl:sourceAsset` attribute and must be accessible in the expected location. The source asset path should be relative to the USD file location.

Material paths in the info:mdl:sourceAsset property must:
1. Be present (not empty)
2. Have the .mdl extension
3. For relative paths, start with "./" 
4. Reference an existing MDL file

## Why is it required?
- Broken material references
- Non-portable assets
- Inconsistent rendering

## Examples

```usd
# Invalid: Missing MDL path
def Material "MissingPath" (
    info:mdl:sourceAsset = @@ 
)
{
}

# Invalid: Wrong extension
def Material "WrongExtension" (
    info:mdl:sourceAsset = @abc@  # Missing .mdl extension
)
{
}

# Invalid: Relative path without ./
def Material "IncorrectRelative" (
    info:mdl:sourceAsset = @material.mdl@  # Should be ./material.mdl
)
{
}

# Invalid: Non-existent MDL file
def Material "MissingFile" (
    info:mdl:sourceAsset = @./unknown.mdl@  # File doesn't exist
)
{
}

# Valid: Proper relative path to existing MDL
def Material "ValidMaterial" (
    info:mdl:sourceAsset = @./material.mdl@
)
{
}
```

## How to comply
- Ensure MDL path is specified
- Add .mdl extension if missing
- Prefix relative paths with "./"
- Verify MDL file exists at specified path

## For More Information
- [USD Material Documentation](https://openusd.org/release/api/usd_shade_page_front.html) 
- [MDL Search Path](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/mdl_search_path.html)
- [USD Resolver Documentation](https://docs.omniverse.nvidia.com/kit/docs/usd_resolver/latest/docs/resolver-details.html)