# directory-structure

| Code     | NP.003 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`np-003` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

Asset directories shall use consistent naming and logical organization

## Description

USD asset directories shall use consistent, well-formed names and a logical organization to ensure proper organization, portability, and maintainability. This requirement governs *directory naming and organization*: directory names must use valid characters, avoid reserved names, follow a consistent naming convention, and group related files into purpose-based subdirectories.

This requirement does **not** define the overall asset folder layout (root folder, intermediate folder, and main asset file placement). That layout is defined by NP.005 (`asset-folder-structure`), which is the single source of truth for where the main asset file lives relative to its root and intermediate folders. The examples below always include the NP.005-mandated intermediate folder so that an asset organized per NP.003 also satisfies NP.005.

## Why is it required?

- Ensures consistent asset organization across different projects
- Facilitates asset discovery and management
- Improves portability between different environments
- Enables automated asset processing and validation
- Supports collaborative development workflows

## Examples

The trees below include the NP.005-mandated intermediate folder (the main asset
file lives one folder deep from the asset root). Supporting folders (`materials/`,
`textures/`, `geometry/`, components, etc.) live *inside* that intermediate folder so
the main asset file can reference them with anchored `./` paths that stay within the
asset root (per AA.001 `anchored-asset-paths`). NP.003 focuses on the naming and
organization of the directories themselves.

```usd
# Valid: Consistent, purpose-based directory names with logical grouping
# asset_name/
#   └── intermediate_folder/            # Intermediate folder (per NP.005)
#       ├── asset_name.usd              # Main asset file
#       ├── materials/
#       │   ├── materials.usd           # Material definitions
#       │   └── textures/
#       │       ├── diffuse.png
#       │       ├── normal.png
#       │       └── roughness.png
#       ├── geometry/
#       │   └── geometry.usd            # Geometry definitions
#       └── physics/
#           └── physics.usd             # Physics properties

# Valid: Component-based organization with consistent directory naming
# office_chair/
#   └── intermediate_folder/            # Intermediate folder (per NP.005)
#       ├── office_chair.usd            # Main composition
#       ├── base/
#       │   └── base.usd
#       ├── seat/
#       │   └── seat.usd
#       ├── backrest/
#       │   └── backrest.usd
#       └── shared/
#           ├── materials/
#           └── textures/

# Invalid: Inconsistent directory naming
# asset_name/
#   └── intermediate_folder/
#       ├── asset_name.usd
#       ├── Materials/                  # Inconsistent capitalization
#       ├── Geometry/                   # Inconsistent capitalization
#       └── Physics Files/              # Contains a space

# Invalid: Reserved or invalid directory names
# asset_name/
#   └── intermediate_folder/
#       ├── asset_name.usd
#       ├── CON/                        # Reserved name
#       └── tex:tures/                  # Invalid character
```

## How to comply

- Use consistent lowercase directory names with underscores or hyphens
- Use only valid characters in directory names and avoid reserved names on Windows (e.g., `AUX`, `PRN`)
- Use descriptive directory names that indicate their contents
- Organize files in logical directories based on their purpose (materials, textures, geometry, physics)
- Place those purpose-based subdirectories *inside* the intermediate folder (next to the main asset file) so references can use anchored `./` paths that stay within the asset root (per AA.001 `anchored-asset-paths`)
- Keep directory structures shallow to avoid path length issues
- Use consistent naming patterns across all assets
- For the overall asset folder layout (root folder, intermediate folder, and main asset file placement), follow NP.005 (`asset-folder-structure`)

## For More Information

- [USD Asset Packaging Best Practices](https://openusd.org/release/tut_usd_best_practices.html#asset-packaging)
- [USDZ File Format Specification](https://openusd.org/release/spec_usdz.html)
