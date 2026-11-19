# semantic-label-time

| Code     | SL.TIME.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`sl-time-001` |
| Compatibility | {compatibility}`rtx`  |
| Tags     | {tag}`limitation` |

## Summary

For the NVIDIA RTX perception pipeline, semantic label attributes must use static (non-time-varying) values.

## Description

Semantic label attributes targeting NVIDIA's RTX rendering and perception ground-truth pipelines must not contain time samples — labels are consumed as a single constant value per object.

Note that OpenUSD itself permits time-varying semantic labels: the [`SemanticsLabelsAPI`](https://openusd.org/release/api/usd_semantics_overview.html) supports time samples to describe actions or states that change over time (e.g. a character labeled `walking` → `running` → `jumping` across time codes). Some training workflows may legitimately rely on such temporal labels. This requirement is therefore an NVIDIA pipeline **limitation** (note the `rtx` compatibility and `limitation` tag), not a claim that time-varying semantics are invalid USD.

## Why is it required?

- The RTX perception / ground-truth pipeline samples one constant label per object and does not consume time-sampled label values
- Avoids ambiguity in ML training datasets that assume static ground truth
- Required for non-visual sensor compatibility

## Examples

```usd
# Invalid for RTX: Time-varying semantic labels (valid OpenUSD, but unsupported here)
def Mesh "TimeVaryingLabels" {
    uniform token[] apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]

    # Time samples cause this requirement to fail
    token[] semantics:labels:wikidata_qcode.timeSamples = {
        0: ["Q150"],      # Car at time 0
        1: ["Q1420"],     # Tree at time 1
        2: ["Q35509"]     # Building at time 2
    }
}

# Valid: Static semantic labels
def Mesh "StaticLabels" {
    uniform token[] apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]
    token[] semantics:labels:wikidata_qcode = ["Q150"]  # Static car label
    # No time samples
}
```

## How to comply

Author semantic label attributes as static values without time samples. If a workflow genuinely needs temporal labels (e.g. action/state labels that vary over time), that asset is outside the scope of the RTX static-label pipeline this requirement targets.

## For More Information

- [Semantic Labels Capability](../capability-semantic_labels.md)
- [Semantic Label Capability Requirement](semantic-label-capability.md)
- [Semantic Label Deprecated Schema Requirement](semantic-label-deprecated-schema.md)
- [OpenUSD Semantics Overview](https://openusd.org/release/api/usd_semantics_overview.html) — including time-varying labels for actions/states
