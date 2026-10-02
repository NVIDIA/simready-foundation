# metadata-union

| Code     | SR.004 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`sr-004` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

Required SimReady provenance fields must be present in the union of USD custom layer data and an optional sidecar JSON file.

## Description

USD assets that claim SimReady packaging provenance must include each required field with a non-empty value. Those fields are read from the union of:

- Root-layer `customLayerData`, including a nested `SimReady_Metadata` dictionary or JSON string
- A sidecar JSON file named `[usd_stem].json` in the same directory as the main USD file

Neither the nested dictionary nor the sidecar is required on its own, but each
field must be authored in exactly one of the two storage locations. Nested
`SimReady_Metadata` keys are unpacked into the USD side of that comparison.
A field present in both the USD root layer (top-level `customLayerData` or
its nested `SimReady_Metadata`) and the sidecar is a validation failure.
Additional custom fields are allowed.

This requirement replaces [SR.003](nested-simready-metadata.md) when a feature
needs the USD/sidecar union. [SR.001](metadata-whitelist.md) remains the earlier
root-layer-only Core identity contract. [SR.003](nested-simready-metadata.md)
remains the nested-`SimReady_Metadata`-only provenance contract.

## Why is it required?

- Provides a consistent provenance record that can live in USD, a sidecar, or split across both
- Keeps a single source of truth per field so the two locations cannot drift apart
- Supports asset discovery and classification through `author` and `category`
- Records licensing terms for package consumers through `asset_license`
- Enables automated package processing and registry workflows
- Documents asset generation pipeline and tooling ownership

## Required Metadata Fields

The following fields are required in the USD/sidecar union.
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
- Additional custom fields are allowed and will not cause validation errors

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
}
```

```text
# Valid: Required fields only in sidecar JSON
# chair.usd
# chair.json
{
    "author": "nvidia",
    "asset_name": "office_chair_01",
    "asset_type": "prop",
    "asset_license": "CC-BY-4.0",
    "category": "furniture",
    "source_file": "office_chair_01.blend",
    "usd_date_generated": "2025-10-09",
    "qcode": "Q42177",
    "rigid_body_count": 1,
    "asset_extents": [0.55, 0.55, 0.92],
    "mass": 7.5
}

# Valid: Split across USD and sidecar
# USD SimReady_Metadata provides author, asset_name, asset_type, asset_license,
# category, source_file, usd_date_generated
# chair.json provides qcode, rigid_body_count, asset_extents, mass

# Invalid: Missing required fields in the union
#usda 1.0
(
    defaultPrim = "Chair"
    customLayerData = {
        dictionary SimReady_Metadata = {
            string asset_name = "office_chair_01"
        }
    }
)

# Invalid: Empty required fields in the union

# Invalid: asset_name is authored in both storage locations
# customLayerData.SimReady_Metadata.asset_name = "office_chair_01"
# chair.json -> {"asset_name": "office_chair_01"}
```

## How to comply

- Author all required fields in USD `customLayerData`, in `[usd_stem].json`, or split across both
- Author each individual field in only one of those two locations
- Nested `SimReady_Metadata` is optional; use it when you want a single dictionary container
- Provide accurate, non-empty values for each field
- Use ISO date format (YYYY-MM-DD) for `usd_date_generated`
- Author `qcode` as a capital `Q` followed by one or more digits (a Wikidata Q-Code, for example `Q42177`)
- Author `rigid_body_count` as an integer count of the rigid bodies in the asset
- Author `asset_extents` as a `float3` or three-number JSON array (size in meters, XYZ)
- Author `mass` as a `float` in kilograms
- Additional custom metadata fields are allowed and will not cause validation errors
- Keep metadata synchronized with asset updates

## For More Information

- [metadata-whitelist](metadata-whitelist.md) (SR.001)
- [nested-simready-metadata](nested-simready-metadata.md) (SR.003)
- [USD Layer Metadata](https://openusd.org/release/glossary.html#usdglossary-metadata)
- [SimReady Asset Standards](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/simready.html)
