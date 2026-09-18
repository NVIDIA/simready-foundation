# metadata-location

| Code     | NP.006 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`np-006` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

Asset metadata must be stored in the USD file or a sidecar JSON file

## Description

All asset metadata must be stored either within the USD file itself, in custom layer data as 'simready_metadata', or in a sidecar JSON file located alongside the USD file. This ensures metadata is always accessible and portable with the asset, preventing metadata loss during asset transfers or processing.

## Why is it required?

- Ensures metadata portability and accessibility
- Prevents metadata loss during asset transfers
- Provides a standardized approach to metadata storage
- Enables automated asset processing and validation
- Supports collaborative development workflows

## Examples

```text
# Valid: Metadata in custom layer data
# chair.usd
#usda 1.0
(
    customLayerData = {
        string simready_metadata = """{
            "identifier": "chair_001",
            "version": "1.0.0",
            "description": "Wooden dining chair",
            "tags": ["furniture", "dining"],
            "author": "John Doe"
        }"""
    }
)
{
    # Asset content...
}

# Valid: Metadata in sidecar JSON file
# chair.usd (main asset file)
# chair.json (sidecar metadata file)
{
    "identifier": "chair_001",
    "version": "1.0.0",
    "description": "Wooden dining chair",
    "tags": ["furniture", "dining"],
    "author": "John Doe"
}

# Valid: Mixed approach (custom layer data + JSON)
# chair.usd
#usda 1.0
(
    customLayerData = {
        string simready_metadata = """{
            "identifier": "chair_001",
            "version": "1.0.0"
        }"""
    }
)
{
    # Asset content...
}

# chair.json (additional metadata)
{
    "description": "Wooden dining chair",
    "tags": ["furniture", "dining"],
    "author": "John Doe"
}

# Invalid: Metadata in separate text file
# chair.usd (main asset file)
# chair_metadata.txt (Not JSON format)
Chair Metadata:
- ID: chair_001
- Version: 1.0.0

# Invalid: Metadata in remote location
# chair.usd (main asset file)
# metadata stored in external database (Not portable)

# Invalid: Metadata in unsupported format
# chair.usd (main asset file)
# chair_metadata.xml (Not JSON format)
```

## How to comply

- Use custom layer data with `simready_metadata` key for structured metadata
- Use sidecar JSON files for additional metadata that doesn't fit in USD
- Ensure JSON files are valid JSON format
- Place sidecar JSON files in the same directory as the USD file
- Use consistent naming: `[asset_name].json` for sidecar files
- Include required metadata fields: identifier, version, description
- Consider using USD's built-in metadata attributes when possible
- For custom layer data, ensure the JSON string is properly escaped

## For More Information

- [USD Asset Metadata Best Practices](https://openusd.org/release/tut_usd_best_practices.html#asset-metadata)
- [USD AssetInfo Schema](https://openusd.org/release/api/class_usd_asset_info.html)
- [JSON Schema Specification](https://json-schema.org/)
