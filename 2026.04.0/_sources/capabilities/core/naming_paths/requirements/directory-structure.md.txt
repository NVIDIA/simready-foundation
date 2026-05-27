# directory-structure

| Code     | NP.003 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`np-003` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

Assets shall follow consistent directory structure

## Description

USD assets shall follow consistent directory structures to ensure proper organization, portability, and maintainability. This includes organizing related files in logical directories, using consistent naming for directories, and following established asset packaging conventions.

## Why is it required?

- Ensures consistent asset organization across different projects
- Facilitates asset discovery and management
- Improves portability between different environments
- Enables automated asset processing and validation
- Supports collaborative development workflows

## Examples

```usd
# Valid: Standard asset directory structure
# asset_name/
#   ├── asset_name.usd          # Main asset file
#   ├── materials/
#   │   ├── materials.usd       # Material definitions
#   │   └── textures/
#   │       ├── diffuse.png
#   │       ├── normal.png
#   │       └── roughness.png
#   ├── geometry/
#   │   └── geometry.usd        # Geometry definitions
#   ├── physics/
#   │   └── physics.usd         # Physics properties
#   └── variants/
#       ├── color_variants.usd
#       └── size_variants.usd

# Valid: Component-based structure
# office_chair/
#   ├── office_chair.usd        # Main composition
#   ├── base/
#   │   ├── base.usd
#   │   └── base_materials.usd
#   ├── seat/
#   │   ├── seat.usd
#   │   └── seat_materials.usd
#   ├── backrest/
#   │   ├── backrest.usd
#   │   └── backrest_materials.usd
#   └── shared/
#       ├── materials/
#       └── textures/

# Invalid: Flat structure without organization
# asset_name/
#   ├── asset_name.usd
#   ├── material1.usd
#   ├── material2.usd
#   ├── texture1.png
#   ├── texture2.png
#   ├── geometry1.usd
#   └── physics1.usd

# Invalid: Inconsistent naming
# asset_name/
#   ├── Asset_Name.usd          # Inconsistent capitalization
#   ├── Materials/              # Inconsistent capitalization
#   ├── textures/               # Inconsistent capitalization
#   └── Physics Files/          # Contains space
```

## How to comply

- Organize files in logical directories based on their purpose
- Use consistent lowercase directory names with underscores or hyphens
- Group related files together (materials, textures, geometry, physics)
- Use descriptive directory names that indicate their contents
- Follow established asset packaging conventions
- Keep directory structures shallow to avoid path length issues
- Use consistent naming patterns across all assets

## For More Information

- [USD Asset Packaging Best Practices](https://openusd.org/release/tut_usd_best_practices.html#asset-packaging)
- [USDZ File Format Specification](https://openusd.org/release/spec_usdz.html)
