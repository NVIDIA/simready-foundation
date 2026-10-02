# metadata-whitelist

| Code     | SR.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`sr-001` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

The asset stage must contain all required metadata fields in root-layer `customLayerData`.

## Description

USD assets must include the original SR.001 metadata field set directly in the
root layer's `customLayerData`. The `SimReady_Metadata` key is required for
compatibility with the SimReady reference pipeline. Additional custom metadata
fields are allowed.

This stable contract intentionally does not inspect a sidecar or flatten nested
metadata. Assets that passed SR.001 continue to be evaluated against the same
authored-data locations. Use [SR.003](nested-simready-metadata.md) for nested
`SimReady_Metadata` provenance, and [SR.004](metadata-union.md) when provenance
fields must be split across USD and a sidecar.

## Why is it required?

- Supports asset traceability and provenance tracking
- Provides essential information for asset management systems
- Preserves compatibility with already validated assets
- Documents asset generation pipeline and tooling ownership

## Required Metadata Fields

The following keys must be present directly in root-layer `customLayerData`:

- `SimReady_Metadata`
- `asset_name`
- `asset_type`
- `source_file`
- `usd_date_generated`

Additional custom fields are allowed and do not cause validation errors.

## Examples

```usd
# Valid: every required key is directly in root-layer customLayerData
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
}
```

```usd
# Invalid for SR.001: identity fields exist only inside SimReady_Metadata
#usda 1.0
(
    customLayerData = {
        dictionary SimReady_Metadata = {
            string asset_name = "office_chair_01"
            string asset_type = "furniture"
            string source_file = "office_chair_01.blend"
            string usd_date_generated = "2025-10-09"
        }
    }
)
```

## How to comply

- Author every required key directly in root-layer `customLayerData`
- Include the `SimReady_Metadata` key for reference-pipeline compatibility
- Use ISO date format (`YYYY-MM-DD`) for `usd_date_generated`
- Keep metadata synchronized with asset updates
- Use [SR.004](metadata-union.md) when provenance metadata must be split across USD and a sidecar

## For More Information

- [nested-simready-metadata](nested-simready-metadata.md) (SR.003)
- [metadata-union](metadata-union.md) (SR.004)
- [USD Layer Metadata](https://openusd.org/release/glossary.html#usdglossary-metadata)
- [SimReady Asset Standards](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/simready.html)
