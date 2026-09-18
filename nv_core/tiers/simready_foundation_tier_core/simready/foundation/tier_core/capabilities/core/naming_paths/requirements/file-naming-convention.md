# file-naming-convention

| Code     | NP.002 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`np-002` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

USD files shall follow consistent naming conventions

## Description

USD files shall follow consistent naming conventions to ensure proper identification, organization, and compatibility across different platforms and tools. This includes using appropriate file extensions, avoiding special characters, and following standardized naming patterns.

## Why is it required?

- Ensures proper file identification and organization
- Prevents issues with file system limitations on different platforms
- Facilitates automated processing and asset management
- Improves compatibility with various USD tools and viewers

## Examples

```usd
# Valid: Standard USD file naming
# File: chair_base.usd
# File: chair_materials.usda
# File: chair_physics.usdc

# Valid: Descriptive naming with version
# File: office_chair_v1.0.usd
# File: dining_chair_set_v2.1.usda

# Valid: Component-based naming
# File: chair_geometry.usd
# File: chair_materials.usd
# File: chair_physics.usd

# Invalid: Special characters and spaces
# File: chair base!.usd  # Contains space and special character
# File: chair@materials.usd  # Contains special character
# File: chair#physics.usd  # Contains special character

# Invalid: Inconsistent extensions
# File: chair_base.USD  # Inconsistent capitalization
# File: chair_materials.usdz  # Wrong extension for source file

# Invalid: Reserved names
# File: CON.usd  # Reserved name on Windows
# File: aux.usd  # Reserved name on Windows
```

## How to comply

- Use lowercase file names with appropriate USD extensions (.usd, .usda, .usdc, .usdz)
- Use underscores or hyphens to separate words, avoid spaces
- Avoid special characters that may cause issues on different platforms
- Use descriptive names that indicate the file's purpose
- Follow consistent naming patterns within asset collections
- Avoid reserved file names (CON, PRN, AUX, NUL, etc.)
- Use version numbers when appropriate (e.g., _v1.0, _v2.1)

## For More Information

- [USD File Format Extensions](https://openusd.org/release/spec_usdz.html)
- [USD Best Practices - File Organization](https://openusd.org/release/tut_usd_best_practices.html#file-organization)
