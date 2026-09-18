# asset-folder-structure

| Code     | NP.005 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`np-005` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

Assets must follow a specific folder structure with the asset name as the root folder

## Description

USD assets must be organized in a specific folder structure where the asset name serves as the root folder, followed by exactly one intermediate folder, with the main asset file name containing the asset folder name. The intermediate folder must contain exactly one USD file (the main asset file); supporting subfolders (e.g. `materials/`, `textures/`, `payloads/`) live *inside* the intermediate folder, next to the main asset file, and may contain any number of USD files, or none. Keeping supporting folders inside the intermediate folder lets the main asset file reference them with anchored `./` paths that stay within the asset root (per AA.001 `anchored-asset-paths`). This ensures consistent organization and makes assets easily identifiable and portable.

## Why is it required?

- Ensures consistent asset organization across different projects
- Makes assets easily identifiable by their folder structure
- Improves portability and asset management
- Facilitates automated asset processing and validation
- Supports collaborative development workflows

## Examples

```usd
# Valid: Asset file name matches folder name exactly
# chair/
#   └── foo/
#       ├── chair.usd          # Main asset file
#       └── materials/
#           └── materials.usd

# Valid: Asset file name contains folder name with variant suffix
# chair/
#   └── bar/
#       ├── sm_chair_01.usd    # Main asset file (contains 'chair')
#       └── materials/
#           └── materials.usd

# Valid: Asset file name contains folder name with prefix and suffix
# obs_orange_a01/
#   └── simready_usd/
#       ├── sm_obs_orange_a01_01.usd  # Main asset file (contains 'obs_orange_a01')
#       └── materials/

# Valid: Subfolder with multiple USD files
# chair/
#   └── foo/
#       ├── chair.usd          # Main asset file (sole USD in intermediate folder)
#       └── materials/
#           ├── wood.usd
#           └── fabric.usd

# Valid: Robot asset with payloads layout (e.g. common_assets/robots_general/ur10)
# ur10/
#   └── simready_isaac_usd/
#       ├── ur10.usda              # Main asset file (sole USD in intermediate folder)
#       └── payloads/
#           ├── base.usda
#           ├── instances.usda
#           ├── materials.usda
#           └── Physics/
#               ├── physics.usda
#               └── physx.usda

# Invalid: Multiple USD files in intermediate folder
# chair/
#   └── foo/
#       ├── chair.usd          # Main asset file
#       ├── variant.usd        # Extra USD in intermediate folder
#       └── materials/

# Invalid: Asset file at root level (no intermediate folder)
# chair/
#   ├── chair.usd              # Should be in intermediate folder
#   └── materials/

# Invalid: Asset file name doesn't contain folder name
# chair/
#   └── foo/
#       ├── table.usd          # Should contain 'chair'
#       └── materials/

# Invalid: Asset file too deep (more than one intermediate folder)
# chair/
#   └── foo/
#       └── bar/
#           └── chair.usd      # Too deep (2 intermediate folders)

# Invalid: Missing main asset file
# chair/
#   └── foo/
#       └── materials/
#   # Missing asset file containing 'chair'
```

## How to comply

- Create a root folder named after the asset (e.g., `chair/`)
- Create exactly one intermediate subfolder (e.g., `chair/foo/`)
- Place the main USD file in the intermediate subfolder with a name that contains the root folder name (e.g., `chair/foo/chair.usd` or `chair/foo/sm_chair_01.usd`)
- Ensure the intermediate subfolder contains only that one USD file (no additional `.usd`/`.usda` siblings)
- Place supporting files (materials, textures, payloads, etc.) in subdirectories *inside* the intermediate folder (next to the main asset file) so the main asset file can reference them with anchored `./` paths that stay within the asset root (per AA.001 `anchored-asset-paths`); these subfolders may contain any number of USD files
- Ensure the main asset file is exactly one folder deep from the root
- Ensure the main asset file name contains the asset folder name (allows for prefixes, suffixes, and variants)

## For More Information

- [USD Asset Packaging Best Practices](https://openusd.org/release/tut_usd_best_practices.html#asset-packaging)
- [USDZ File Format Specification](https://openusd.org/release/spec_usdz.html)
