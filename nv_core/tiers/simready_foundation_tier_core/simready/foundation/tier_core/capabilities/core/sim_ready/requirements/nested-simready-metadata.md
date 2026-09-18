# nested-simready-metadata

| Code     | SR.003 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`sr-003` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

Required SimReady provenance fields must be authored inside the root-layer `SimReady_Metadata` dictionary.

## Description

USD assets that claim SimReady packaging provenance must include a
`SimReady_Metadata` dictionary in the root layer's `customLayerData`, and each
required field must be authored **inside** that dictionary with a non-empty
value. Additional custom fields beyond the required ones are allowed.

This requirement is stricter than [SR.001](metadata-whitelist.md): fields must
live inside `SimReady_Metadata`, and `author`, `category`, and `asset_license`
are required.

## Why is it required?

- Provides a single, consistent location for SimReady package provenance
- Supports asset discovery and classification through `author` and `category`
- Records licensing terms for package consumers through `asset_license`
- Enables automated package processing and registry workflows
- Documents asset generation pipeline and tooling ownership

## Required Metadata Fields

The following fields are required inside `customLayerData.SimReady_Metadata`.
Each field must be present and non-empty (whitespace-only strings are treated
as empty):

- `author` (string): The author or organization responsible for the asset
- `asset_name` (string): The name of the asset
- `asset_type` (string): The type of the asset (for example, `prop` or `robot`)
- `asset_license` (string): The license that applies to the asset (for example, `CC-BY-4.0` or `proprietary`)
- `category` (string): The asset category used for discovery and classification (for example, `furniture`, `printer`)
- `source_file` (string): The original source file used to generate the asset
- `usd_date_generated` (string): The date when the USD file was generated
- `qcode` (string): The Wikidata Q-Code describing the asset's general category (for example, `Q42177`). Must be a capital `Q` followed by one or more digits.
- `rigid_body_count` (int): The number of rigid bodies present in the asset
- `asset_extents` (float3): The size of the asset's bounding box in meters, as XYZ
- `mass` (float): The mass of the asset in kilograms


Optional:
- Additional custom fields are allowed inside `SimReady_Metadata` and will not cause validation errors

## Examples

```usd


# Valid: Required fields inside the SimReady_Metadata dictionary
#usda 1.0
(
    defaultPrim = "Chair"
    customLayerData = {
        dictionary SimReady_Metadata = {
            string author = "nvidia"
            string asset_name = "office_chair_01"
            string asset_type = "prop"
            string asset_license = "CC-BY-4.0"
            string category = "furniture"
            string source_file = "office_chair_01.blend"
            string usd_date_generated = "2025-10-09"
            string qcode = "Q42177"
            int rigid_body_count = 1
            float3 asset_extents = (0.55, 0.55, 0.92)
            float mass = 7.5
        }
    }
)

def Xform "Chair"
{
    # Asset content...
}

# Valid: Additional custom nested fields are allowed
#usda 1.0
(
    defaultPrim = "Chair"
    customLayerData = {
        dictionary SimReady_Metadata = {
            string author = "nvidia"
            string asset_name = "office_chair_01"
            string asset_type = "prop"
            string asset_license = "CC-BY-4.0"
            string category = "furniture"
            string source_file = "office_chair_01.blend"
            string usd_date_generated = "2025-10-09"
            string qcode = "Q42177"
            int rigid_body_count = 1
            float3 asset_extents = (0.55, 0.55, 0.92)
            float mass = 7.5
            string custom_field = "custom_value"
        }
    }
)

def Xform "Chair"
{
    # Asset content...
}

# Invalid: Fields only at top level of customLayerData
#usda 1.0
(
    defaultPrim = "Chair"
    customLayerData = {
        string author = "nvidia"
        string asset_name = "office_chair_01"
        string asset_type = "prop"
        string asset_license = "CC-BY-4.0"
        string category = "furniture"
        string source_file = "office_chair_01.blend"
        string usd_date_generated = "2025-10-09"
    }
)

def Xform "Chair"
{
    # Asset content...
}

# Invalid: Missing required nested metadata fields
#usda 1.0
(
    defaultPrim = "Chair"
    customLayerData = {
        dictionary SimReady_Metadata = {
            string asset_name = "office_chair_01"
            # Missing author, asset_type, asset_license, category, source_file,
            # usd_date_generated, qcode, rigid_body_count, asset_extents, and mass
        }
    }
)

def Xform "Chair"
{
    # Asset content...
}

# Invalid: Empty required nested metadata fields
#usda 1.0
(
    defaultPrim = "Chair"
    customLayerData = {
        dictionary SimReady_Metadata = {
            string author = "nvidia"
            string asset_name = "office_chair_01"
            string asset_type = "prop"
            string asset_license = ""
            string category = "furniture"
            string source_file = "office_chair_01.blend"
            string usd_date_generated = "2025-10-09"
            string qcode = "Q42177"
            int rigid_body_count = 1
            float3 asset_extents = (0.55, 0.55, 0.92)
            float mass = 7.5
        }
    }
)

def Xform "Chair"
{
    # Asset content...
}
```

## How to comply

- Include the `SimReady_Metadata` dictionary in root-layer `customLayerData`
- Author all required fields inside `SimReady_Metadata`
- Provide accurate, non-empty values for each field
- Use ISO date format (YYYY-MM-DD) for `usd_date_generated`
- Author `qcode` as a capital `Q` followed by one or more digits (a Wikidata Q-Code, for example `Q42177`)
- Author `rigid_body_count` as an integer count of the rigid bodies in the asset
- Author `asset_extents` as a `float3` bounding-box size in meters (XYZ)
- Author `mass` as a `float` in kilograms
- Additional custom metadata fields are allowed and will not cause validation errors
- Keep metadata synchronized with asset updates

## For More Information

- [metadata-whitelist](metadata-whitelist.md) (SR.001)
- [USD Metadata and Custom Data](https://openusd.org/release/api/class_sdf_layer.html#a8c6e8b8b8c8e8b8b8c8e8b8b8c8e8b8b)
- [USD Layer Metadata](https://openusd.org/release/glossary.html#usdglossary-metadata)
- [SimReady Asset Standards](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/simready.html)
