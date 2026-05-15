# semantic-label-schema

| Code     | SL.003 |
|----------|---------|
| Validator| {oav-validator-latest-link}`sl-001` |
| Compatibility | {compatibility}`open-usd`  |
| Tags     | {tag}`correctness` |

## Summary

Semantic labels must use the SemanticsLabelsAPI schema

## Description

Semantic labels should use the modern SemanticsLabelsAPI schema rather than the legacy SemanticsAPI schema. The validator will show migration warnings for legacy SemanticsAPI usage and provide suggestions to migrate to the newer schema.

## Why is it required?

- Ensures compatibility with modern USD semantic labeling standards
- Provides better schema validation and type safety
- Enables future enhancements and improvements
- Maintains consistency with OpenUSD specifications

## Examples

```usd
# Invalid: Legacy SemanticsAPI schema (will show migration warning)
def Mesh "LegacyLabels" {
    uniform token[] apiSchemas = ["SemanticsAPI:legacy_labels"]
    string semantic:legacy_labels:params:semanticType = "wikidata_qcode"
    string semantic:legacy_labels:params:semanticData = "Q150"
}

# Valid: Modern SemanticsLabelsAPI schema
def Mesh "ModernLabels" {
    uniform token[] apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]
    token[] semantics:labels:wikidata_qcode = ["Q150"]
}
```

## How to comply

Use the SemanticsLabelsAPI schema with the `wikidata_qcode` instance name:
1. Add `"SemanticsLabelsAPI:wikidata_qcode"` to the prim's apiSchemas
2. Use the `semantics:labels:wikidata_qcode` attribute for Q-Code values
3. Migrate from legacy SemanticsAPI schema when possible

## For More Information

- [Semantic Labels Capability](../capability-semantic_labels.md)
- [Semantic Label Capability Requirement](semantic-label-capability.md)
- [Semantic Label QCode Valid Requirement](semantic-label-qcode-valid.md)
