# semantic-label-deprecated-schema

| Code     | SL.002 |
|----------|---------|
| Validator| {oav-validator-latest-link}`sl-002` |
| Compatibility | {compatibility}`open-usd`  |
| Tags     | {tag}`correctness` |

## Summary

Deprecated SemanticsAPI labels must be migrated to the SemanticsLabelsAPI schema.

## Description

The legacy `SemanticsAPI` schema is deprecated; semantic labels should use the modern `SemanticsLabelsAPI` schema. This requirement only applies to prims that still carry a deprecated `SemanticsAPI` label — prims without one are unaffected.

When a deprecated `SemanticsAPI` label is present, an equivalent `SemanticsLabelsAPI` label (same value) must also exist on the prim:

- **Equivalent modern label present** → the prim *passes with a warning* recommending removal of the now-redundant deprecated schema.
- **No equivalent modern label** → the prim *fails*; the deprecated label must be migrated to `SemanticsLabelsAPI`.

## Validation

1. Detect any applied `SemanticsAPI:<instance>` schema (deprecated).
2. Read its `semantic:<instance>:params:semanticData` value.
3. Check whether an applied `SemanticsLabelsAPI:*` instance carries that same value:
   - present → **warning** (pass): remove the redundant deprecated schema.
   - absent → **failure**: migrate the label to `SemanticsLabelsAPI`.

The validator offers a suggestion to perform the migration automatically.

## Why is it required?

- Ensures compatibility with modern USD semantic labeling standards
- Provides better schema validation and type safety
- Avoids drift between deprecated and modern labels on the same prim
- Maintains consistency with OpenUSD specifications

## Examples

This requirement applies to any taxonomy; the examples use a generic `class` taxonomy.
The deprecated `semanticType` maps to the modern `SemanticsLabelsAPI` instance name of the same name.

```usd
# Fails: deprecated SemanticsAPI label with no equivalent SemanticsLabelsAPI
def Mesh "UnmigratedLegacy" {
    uniform token[] apiSchemas = ["SemanticsAPI:legacy_labels"]
    string semantic:legacy_labels:params:semanticType = "class"
    string semantic:legacy_labels:params:semanticData = "furniture"
}

# Passes with warning: deprecated schema present, but an equivalent modern label exists
def Mesh "MigratedButStale" (
    prepend apiSchemas = ["SemanticsAPI:legacy_labels", "SemanticsLabelsAPI:class"]
)
{
    string semantic:legacy_labels:params:semanticType = "class"
    string semantic:legacy_labels:params:semanticData = "furniture"
    token[] semantics:labels:class = ["furniture"]   # same value -> warning to drop the deprecated schema
}

# Passes (N/A): modern schema only, no deprecated schema
def Mesh "ModernLabels" {
    uniform token[] apiSchemas = ["SemanticsLabelsAPI:class"]
    token[] semantics:labels:class = ["furniture"]
}
```

## How to comply

1. Add an equivalent `SemanticsLabelsAPI:<instance>` label carrying the same value as the deprecated `SemanticsAPI` label (the validator can do this automatically).
2. Remove the deprecated `SemanticsAPI` schema and its `semantic:<instance>:params:*` attributes.

## For More Information

- [Semantic Labels Capability](../capability-semantic_labels.md)
- [Semantic Label Capability Requirement](semantic-label-capability.md)
- [Semantic Label QCode Valid Requirement](semantic-label-qcode-valid.md)
