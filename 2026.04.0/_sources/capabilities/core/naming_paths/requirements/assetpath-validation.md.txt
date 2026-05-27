# path-validation

| Code     | NP.008 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`np-008` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

All asset, reference, and payload paths must resolve to files that exist

## Description

All file references within a USD asset (asset paths, references, payloads, and sublayers) must resolve to files that actually exist on disk or in Omniverse. This ensures that assets can be properly loaded and that all dependencies are available. Missing files will cause loading errors and incomplete asset composition.

## Why is it required?

- Ensures assets can be loaded successfully without missing dependencies
- Prevents broken references that cause incomplete asset composition
- Enables proper validation of asset integrity
- Facilitates asset packaging and deployment
- Helps identify missing or incorrectly referenced files early in the pipeline

## Examples

```usd
# Valid: All referenced files exist
# chair.usd
def "Chair" (
    references = @./geometry/chair_geometry.usd@  # File exists at this path
    payloads = @./materials/chair_materials.usd@  # File exists at this path
) {
    asset inputs:diffuseTexture = @./textures/chair_diffuse.png@  # File exists
}

# Invalid: Referenced file does not exist
# chair.usd
def "Chair" (
    references = @./geometry/chair_geometry.usd@  # File does NOT exist
) {
    # Asset content...
}

# Invalid: Missing texture file
# chair.usd
def "Chair" {
    asset inputs:diffuseTexture = @./textures/missing_texture.png@  # File does NOT exist
}

# Invalid: Missing payload file
# chair.usd
def "Chair" (
    payloads = @./materials/nonexistent_materials.usd@  # File does NOT exist
) {
    # Asset content...
}

# Invalid: Absolute path
# chair.usd
def "Chair" (
    payloads = @c:/local_user_content/materials/nonexistent_materials.usd@  # File exists only found if the local user has that path, not deployable
) {
    # Asset content...
}
```

## How to comply

- Verify that all referenced files exist before referencing them
- Use relative paths to maintain portability
- Include all dependent files when packaging assets
- Test asset loading in a clean environment to catch missing files
- Use validation tools to check for broken references
- Maintain consistent file organization within asset folders

## For More Information

- [USD References and Payloads](https://openusd.org/release/api/class_usd_references.html)
- [USD Asset Resolution](https://openusd.org/release/api/ar_page_front.html)
- [USD Layer Composition](https://openusd.org/release/api/class_usd_layer.html)

