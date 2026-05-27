# asset-folder-structure

| Code     | NP.005 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`np-005` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

Assets must follow a specific folder structure with the asset name as the root folder

## Description

USD assets must be organized in a specific folder structure where the asset name serves as the root folder, followed by exactly one intermediate folder, with the main asset file name containing the asset folder name. This ensures consistent organization and makes assets easily identifiable and portable.

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
#   ├── foo/
#   │   └── chair.usd          # Main asset file
#   └── materials/
#       └── materials.usd

# Valid: Asset file name contains folder name with variant suffix
# chair/
#   ├── bar/
#   │   └── sm_chair_01.usd    # Main asset file (contains 'chair')
#   └── materials/
#       └── materials.usd

# Valid: Asset file name contains folder name with prefix and suffix
# obs_orange_a01/
#   ├── simready_usd/
#   │   └── sm_obs_orange_a01_01.usd  # Main asset file (contains 'obs_orange_a01')
#   └── materials/

# Invalid: Asset file at root level (no intermediate folder)
# chair/
#   ├── chair.usd              # Should be in intermediate folder
#   └── materials/

# Invalid: Asset file name doesn't contain folder name
# chair/
#   ├── foo/
#   │   └── table.usd          # Should contain 'chair'
#   └── materials/

# Invalid: Asset file too deep (more than one intermediate folder)
# chair/
#   ├── foo/
#   │   ├── bar/
#   │   │   └── chair.usd      # Too deep (2 intermediate folders)
#   └── materials/

# Invalid: Missing main asset file
# chair/
#   ├── foo/
#   └── materials/
#   # Missing asset file containing 'chair'
```

## How to comply

- Create a root folder named after the asset (e.g., `chair/`)
- Create exactly one intermediate subfolder (e.g., `chair/foo/`)
- Place the main USD file in the intermediate subfolder with a name that contains the root folder name (e.g., `chair/foo/chair.usd` or `chair/foo/sm_chair_01.usd`)
- Organize supporting files in subdirectories as needed
- Ensure the main asset file is exactly one folder deep from the root
- Ensure the main asset file name contains the asset folder name (allows for prefixes, suffixes, and variants)

## For More Information

- [USD Asset Packaging Best Practices](https://openusd.org/release/tut_usd_best_practices.html#asset-packaging)
- [USDZ File Format Specification](https://openusd.org/release/spec_usdz.html)
