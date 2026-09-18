# Open-Taxonomy-PascalVOC Profile

This document describes how to author a USD asset that conforms to the `Open-Taxonomy-PascalVOC` profile.

`Open-Taxonomy-PascalVOC` is an **example profile** that demonstrates labeling assets with the **PASCAL VOC** taxonomy
instead of NVIDIA's Wikidata Q-codes. It pairs the Core feature with one closed-vocabulary taxonomy
feature (VOC.001). See [Adding a custom taxonomy](../guides/adding_a_custom_taxonomy.md) to build your own.

## Profile definition

The `Open-Taxonomy-PascalVOC` profile includes the following feature set (see `open_taxonomy_profiles.toml`).
Each feature's requirements and dependencies are defined in the feature specifications.

```toml
[Open-Taxonomy-PascalVOC]
"0.1.0" = {features = [
    {"FET_000_STANDARD" = {version = "0.1.0"}}, # Core
    {"FET_043_STANDARD" = {version = "0.1.0"}}, # PASCAL VOC Labels
]}
```

## Required USD properties and schemas

### Stage metadata (required)

- `defaultPrim` must be set.
- `upAxis` and `metersPerUnit` must be set on the stage.

### Semantic labels (PASCAL VOC)

- Apply `SemanticsLabelsAPI:pascal_voc` to prims you want labeled with this taxonomy.
- Author `token[] semantics:labels:pascal_voc` using **PASCAL VOC class names** (VOC.001).
- Values are matched case-insensitively and tolerate `_`/`-` spacing and display-name/alias forms; a
  value that matches only after normalization passes with a warning suggesting the canonical name.

```usd
def Xform "Object" (
    prepend apiSchemas = ["SemanticsLabelsAPI:pascal_voc"]
)
{
    token[] semantics:labels:pascal_voc = ["aeroplane", "person"]
}
```

## Validation metadata

When validation is stamped into the asset, the validator records the result under
`customLayerData["SimReady_Metadata"]["validation"]`. Search for `validated_features` to inspect
the dated validation result and the feature IDs and versions that were checked.

The result has this general shape:

```usd
customLayerData = {
    "SimReady_Metadata" = {
        "validation" = {
            "validated_features" = {
                "<YYYY-MM-DD>" = {
                    "FET_043_STANDARD" = {
                        "version" = "0.1.0"
                        "passed" = true
                    }
                }
            }
        }
    }
}
```

## References

- `docs/profiles/open_taxonomy_profiles.toml`
- `docs/features/FET_043_STANDARD.md`
- `docs/capabilities/dataset_taxonomies/capability-dataset_taxonomies.md`
- `docs/guides/adding_a_custom_taxonomy.md`
