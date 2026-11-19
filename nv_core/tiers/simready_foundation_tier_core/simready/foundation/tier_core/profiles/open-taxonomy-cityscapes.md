# Open-Taxonomy-Cityscapes Profile

This document describes how to author a USD asset that conforms to the `Open-Taxonomy-Cityscapes` profile.

`Open-Taxonomy-Cityscapes` is an **example profile** that demonstrates labeling assets with the **Cityscapes** taxonomy
instead of NVIDIA's Wikidata Q-codes. It pairs the Core feature with one closed-vocabulary taxonomy
feature (CITY.001). See [Adding a custom taxonomy](../../../../../../sr_specs/docs/guides/adding_a_custom_taxonomy.md) to build your own.

## Profile definition

The `Open-Taxonomy-Cityscapes` profile includes the following feature set (see `open_taxonomy_profiles.toml`).
Each feature's requirements and dependencies are defined in the feature specifications.

```toml
[Open-Taxonomy-Cityscapes]
"0.1.0" = {features = [
    {selector = "FET011_SemanticLabels.0-2-0"}, # Semantic Labels
], capabilities = [
    {selector = "CAP000_Core.0-1-0"}, # Core
    {selector = "CAP041_CityscapesLabels.0-1-0"}, # Cityscapes Labels
]}
```

## Required USD properties and schemas

### Stage metadata (required)

- `defaultPrim` must be set.
- `upAxis` and `metersPerUnit` must be set on the stage.

### Semantic labels (Cityscapes)

- Apply `SemanticsLabelsAPI:cityscapes` to prims you want labeled with this taxonomy.
- Author `token[] semantics:labels:cityscapes` using **Cityscapes class names** (CITY.001).
- Values are matched case-insensitively and tolerate `_`/`-` spacing and display-name/alias forms; a
  value that matches only after normalization passes with a warning suggesting the canonical name.

```usd
def Xform "Object" (
    prepend apiSchemas = ["SemanticsLabelsAPI:cityscapes"]
)
{
    token[] semantics:labels:cityscapes = ["road", "car"]
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
                    "CAP041_CityscapesLabels" = {
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
- `docs/capabilities/CAP041_CityscapesLabels.md`
- `docs/rules_and_reqs/dataset_taxonomies/capability-dataset_taxonomies.md`
- `docs/guides/adding_a_custom_taxonomy.md`
