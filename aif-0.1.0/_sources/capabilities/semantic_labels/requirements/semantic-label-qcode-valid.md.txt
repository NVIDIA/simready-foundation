# semantic-label-qcode-valid

| Code     | SL.QCODE.001 |
|----------|--------------|
| Validator| {oav-validator-latest-link}`sl-qcode-001` |
| Compatibility | {compatibility}`nvidia-omniverse`  |
| Tags     | {tag}`correctness` |

## Summary

If the Wikidata ontology is used, Q-Codes must be valid, properly formatted, and retrievable from wikidata.org

## Description

When using Wikidata Q-Codes for semantic labeling, the codes must follow the proper format (Q followed by numbers) and represent valid Wikidata entities that can be retrieved from wikidata.org.

## Why is it required?

- Ensures semantic labels reference valid, retrievable entities
- Maintains consistency with Wikidata ontology standards
- Enables proper ML training with verified ground truth data

## Examples

```usd
# Invalid: Malformed Q-Codes
def Mesh "InvalidLabels" {
    uniform token[] apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]
    token[] semantics:labels:wikidata_qcode = [
        "Q",           # Too short
        "QABC",        # Contains letters
        "123",         # Missing Q prefix
        "Q-1"          # Contains invalid characters
    ]
}

# Valid: Properly formatted Q-Codes
def Mesh "ValidLabels" {
    uniform token[] apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]
    token[] semantics:labels:wikidata_qcode = [
        "Q150",        # Valid Q-Code for "car"
        "Q1420",       # Valid Q-Code for "tree"
        "Q35509"       # Valid Q-Code for "building"
    ]
}
```

## How to comply

Use properly formatted Q-Codes that:
1. Start with capital "Q"
2. Follow with one or more digits (0-9)
3. Reference valid Wikidata entities
4. Can be retrieved from wikidata.org

## For More Information

- [Semantic Labels Capability](../capability-semantic_labels.md)
- [Semantic Label Capability Requirement](semantic-label-capability.md)
- [Semantic Label Schema Requirement](semantic-label-schema.md)
