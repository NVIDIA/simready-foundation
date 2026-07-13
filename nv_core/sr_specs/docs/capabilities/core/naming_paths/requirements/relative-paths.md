# relative-paths

| Code     | NP.007 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`np-007` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

All references must use relative paths

## Description

All file references within USD assets must use relative paths rather than absolute paths. This ensures assets are portable across different systems, environments, and directory structures. Relative paths enable assets to be moved, copied, or shared without breaking internal references.

## Why is it required?

- Ensures asset portability across different systems and environments
- Prevents broken references when assets are moved or copied
- Enables collaborative development workflows
- Supports automated asset processing and deployment
- Maintains consistency across different platforms and operating systems

## Examples

```usd
# Valid: Relative path references
# chair.usd
def "Chair" (
    references = @./geometry/chair_geometry.usd@
    payloads = @./materials/chair_materials.usd@
) {
    # Asset content...
}

# Valid: Relative path with subdirectory
# chair.usd
def "Chair" (
    references = @../shared/geometry/chair_geometry.usd@
) {
    # Asset content...
}

# Valid: Relative path in custom layer data
# chair.usd
#usda 1.0
(
    customLayerData = {
        string simready_metadata = """{
            "geometry_path": "./geometry/chair_geometry.usd",
            "materials_path": "./materials/chair_materials.usd"
        }"""
    }
)
{
    # Asset content...
}

# Invalid: Absolute path references
# chair.usd
def "Chair" (
    references = @/Users/john/Projects/Assets/chair/geometry/chair_geometry.usd@
    payloads = @/Users/john/Projects/Assets/chair/materials/chair_materials.usd@
) {
    # Asset content...
}

# Invalid: Absolute path in custom layer data
# chair.usd
#usda 1.0
(
    customLayerData = {
        string simready_metadata = """{
            "geometry_path": "/Users/john/Projects/Assets/chair/geometry/chair_geometry.usd",
            "materials_path": "/Users/john/Projects/Assets/chair/materials/chair_materials.usd"
        }"""
    }
)
{
    # Asset content...
}

# Invalid: Network/UNC paths
# chair.usd
def "Chair" (
    references = @//server/shared/Assets/chair/geometry/chair_geometry.usd@
) {
    # Asset content...
}
```

## How to comply

- Use relative paths for all file references (references, payloads, subLayers)
- Start relative paths with `./` for files in the same directory
- Use `../` to reference files in parent directories
- Avoid absolute paths (starting with `/` on Unix or `C:\` on Windows)
- Avoid network/UNC paths (starting with `//` or `\\`)
- Test asset portability by moving the entire asset folder
- Use consistent path separators (`/` is preferred over `\`)
- Ensure all referenced files exist at the specified relative locations

## For More Information

- [USD Asset Packaging Best Practices](https://openusd.org/release/tut_usd_best_practices.html#asset-packaging)
- [USD References and Payloads](https://openusd.org/release/api/class_usd_references.html)
- [USD Layer Composition](https://openusd.org/release/api/class_usd_layer.html)
