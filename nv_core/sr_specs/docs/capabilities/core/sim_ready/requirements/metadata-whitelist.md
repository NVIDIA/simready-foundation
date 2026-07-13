# metadata-whitelist

| Code     | SR.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`sr-001` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

The asset stage must contain all required metadata fields

## Description

USD assets must include specific required metadata in the root layer's customLayerData. This metadata provides essential information about the asset's source, type, and generation details. The SimReady_Metadata dictionary key is required for compatibility with the SimReady reference pipeline. Additional custom metadata fields beyond the required ones are allowed.

## Why is it required?

- Supports asset traceability and provenance tracking
- Provides essential information for asset management systems
- Enables automated asset processing and validation
- Facilitates asset search and discovery
- Supports asset versioning and update workflows
- Documents asset generation pipeline and tools used

## Required Metadata Fields

The following fields are required:

- `asset_name` (string): The name of the asset
- `asset_type` (string): The type/category of the asset
- `source_file` (string): The original source file used to generate the asset
- `usd_date_generated` (string): The date when the USD file was generated
- `SimReady_Metadata` (dictionary): Required for compatibility with the SimReady reference pipeline; may contain required fields

Optional:
- Additional custom fields are allowed and will not cause validation errors

## Examples

```usd


# Valid: Metadata at top level
#usda 1.0
(
    defaultPrim = "Chair"
    customLayerData = {
        dictionary SimReady_Metadata = {
        }
        string asset_name = "office_chair_01"
        string asset_type = "furniture"
        string source_file = "office_chair_01.blend"
        string usd_date_generated = "2025-10-09"
    }
)

def Xform "Chair"
{
    # Asset content...
}

# Valid: Additional custom metadata fields are allowed
#usda 1.0
(
    defaultPrim = "Chair"
    customLayerData = {
        dictionary SimReady_Metadata = {
        }
        string asset_name = "office_chair_01"
        string asset_type = "furniture"
        string source_file = "office_chair_01.blend"
        string usd_date_generated = "2025-10-09"
        string custom_field = "custom_value"  # Additional fields are allowed
        int another_field = 123  # Additional fields are allowed
    }
)

def Xform "Chair"
{
    # Asset content...
}

# Invalid: Missing required metadata
#usda 1.0
(
    defaultPrim = "Chair"
    customLayerData = {
        string asset_name = "office_chair_01"
        # Missing asset_type, source_file, and usd_date_generated
    }
)

def Xform "Chair"
{
    # Asset content...
}
```

## How to comply

- Include all required metadata fields in customLayerData
- Include the SimReady_Metadata dictionary key for compatibility with the SimReady reference pipeline
- Use either SimReady_Metadata dictionary or top-level fields (consistent approach)
- Provide accurate and descriptive values for each field
- Use ISO date format (YYYY-MM-DD) for usd_date_generated
- Additional custom metadata fields are allowed and will not cause validation errors
- Keep metadata synchronized with asset updates
- Use asset generation tools that automatically populate metadata

## For More Information

- [USD Metadata and Custom Data](https://openusd.org/release/api/class_sdf_layer.html#a8c6e8b8b8c8e8b8b8c8e8b8b8c8e8b8b)
- [USD Layer Metadata](https://openusd.org/release/glossary.html#usdglossary-metadata)
- [SimReady Asset Standards](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/simready.html)