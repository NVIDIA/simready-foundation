# semantic-label-time

| Code     | SL.NV.002 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`sl-nv-001` |
| Compatibility | {compatibility}`rtx`  |
| Tags     | {tag}`limitation` |

## Summary

Semantic label attributes must not contain time samples

## Description

Semantic label attributes must not contain time samples. These attributes should have static values that don't change over time, as semantic labels represent the fundamental identity of objects which should remain constant.

## Why is it required?

- Ensures consistent object identification across time
- Prevents confusion in ML training datasets
- Maintains stable ground truth for perception systems
- Required for non-visual sensor compatibility

## Examples

```usd
# Invalid: Time-varying semantic labels
def Mesh "TimeVaryingLabels" {
    uniform token[] apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]
    
    # Invalid: Time-varying semantic labels
    token[] semantics:labels:wikidata_qcode.timeSamples = {
        0: ["Q150"],      # Car at time 0
        1: ["Q1420"],     # Tree at time 1 - This will cause validation failure
        2: ["Q35509"]     # Building at time 2
    }
}

# Valid: Static semantic labels
def Mesh "StaticLabels" {
    uniform token[] apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]
    token[] semantics:labels:wikidata_qcode = ["Q150"]  # Static car label
    # No time samples - semantic identity remains constant
}
```

## How to comply

Ensure that all semantic label attributes have static values without time samples. The semantic identity of an object should remain constant throughout its existence.

## For More Information

- [Semantic Labels Capability](../capability-semantic_labels.md)
- [Semantic Label Capability Requirement](semantic-label-capability.md)
- [Semantic Label Schema Requirement](semantic-label-schema.md)
