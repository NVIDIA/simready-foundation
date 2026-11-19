# asset-folder-structure

| Code     | NP.005 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`np-005` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

The folder holding the main asset file must not contain any other USD file.

## Description

The main asset file's own folder may hold exactly one USD file: the main asset file itself. Supporting subfolders (e.g. `materials/`, `textures/`, `payloads/`) may sit next to the main asset file and may contain any number of USD files, or none. This requirement does not constrain how many folders deep the main asset file is, and does not require the file name to relate to any containing folder's name; see `NP.002` (`file-naming-conventions`) for file naming and `NP.003` (`directory-structure`) for directory naming.

## Why is it required?

- Prevents stray or duplicate root-level USD files from competing with the main asset file as the entry point
- Facilitates automated asset processing and validation
- Supports collaborative development workflows

## Examples

```usd
# Valid: sole USD file in its folder
# chair/
#   └── foo/
#       ├── chair.usd          # Main asset file (sole USD in its folder)
#       └── materials/
#           └── materials.usd

# Valid: subfolder may contain multiple USD files
# chair/
#   └── foo/
#       ├── chair.usd          # Main asset file (sole USD in its folder)
#       └── materials/
#           ├── wood.usd
#           └── fabric.usd

# Valid: main asset file at the root, with no other USD file alongside it
# chair/
#   ├── chair.usd              # Main asset file (sole USD in its folder)
#   └── materials/
#       └── materials.usd

# Invalid: multiple USD files in the main asset file's own folder
# chair/
#   └── foo/
#       ├── chair.usd          # Main asset file
#       ├── variant.usd        # Extra USD file alongside the main asset file
#       └── materials/
```

## How to comply

- Keep exactly one USD file (the main asset file) directly in the folder that holds it (no additional `.usd`/`.usda`/`.usdc`/`.usdz` siblings)
- Place supporting files (materials, textures, payloads, etc.) in subdirectories next to the main asset file; these subfolders may contain any number of USD files

## For More Information

- [USD Asset Packaging Best Practices](https://openusd.org/release/tut_usd_best_practices.html#asset-packaging)
- [USDZ File Format Specification](https://openusd.org/release/spec_usdz.html)
