# semantic-label-material

| Code     | SL.MAT.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`sl-mat-001` |
| Compatibility | {compatibility}`nvidia-omniverse`  |
| Tags     | {tag}`correctness` |

## Summary

Material prims must be labeled with a non-empty `SemanticsLabelsAPI:material` label.

## Description

For ground-truth material segmentation, every `Material` prim must carry semantic labels under the `material` taxonomy: the `SemanticsLabelsAPI:material` schema applied with at least one authored value in `semantics:labels:material` (for example `"metal"`, `"plastic"`, `"wood"`).

This is an NVIDIA convention layered on top of the taxonomy-agnostic object labeling (SL.001): object/class labels describe *what an object is*, while the `material` taxonomy describes *what it is made of*. The two coexist via the OpenUSD `SemanticsLabelsAPI` "Multiple Apply" schema design.

## Examples

```usd
# Valid: the object carries a class label, and its Material carries a material label
def Xform "Car" (
    prepend apiSchemas = ["SemanticsLabelsAPI:class"]
)
{
    token[] semantics:labels:class = ["car", "vehicle"]

    def Scope "Materials" {
        def Material "Metal" (
            prepend apiSchemas = ["SemanticsLabelsAPI:material"]
        )
        {
            token[] semantics:labels:material = ["metal", "shiny"]
        }
    }
}

# Invalid: Material prim has no SemanticsLabelsAPI:material label
def Material "Metal" {
}
```

For assets intended to ship alongside NVIDIA Omniverse asset libraries, the
material *values* use the Wikidata Q-code taxonomy instead of free text. The
instance name stays `material` (that is what this requirement keys on), while the
class label uses the `wikidata_qcode` instance. Annotate each opaque code with a
comment, since a reader cannot tell at a glance that `Q11426` means "metal":

```usd
# Valid (NVIDIA Q-code values): the class uses wikidata_qcode; the material values are Q-codes
def Xform "Car" (
    prepend apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]
)
{
    token[] semantics:labels:wikidata_qcode = ["Q1420"]  # Q1420 = motor car

    def Scope "Materials" {
        def Material "Metal" (
            prepend apiSchemas = ["SemanticsLabelsAPI:material"]
        )
        {
            token[] semantics:labels:material = ["Q11426", "Q663"]  # Q11426 = metal, Q663 = aluminium
        }
    }
}
```

The Q-code format rule (SL.QCODE.001) only checks the `wikidata_qcode` instance, so
Q-code values authored under the `material` instance are not format-validated —
the comment is what keeps them legible. See
[Semantic Label QCode Valid (SL.QCODE.001)](semantic-label-qcode-valid.md).

## Why is it required?

- Enables material-segmentation ground truth for perception/ML training
- Separates "what an object is" (class) from "what it is made of" (material)
- Keeps material semantics consistent across NVIDIA Omniverse asset libraries

## How to comply

1. Apply `SemanticsLabelsAPI:material` to each `Material` prim.
2. Author at least one value in `semantics:labels:material` describing the material type.

## For More Information

- [Semantic Labels Capability](../capability-semantic_labels.md)
- [Semantic Label Capability Requirement](semantic-label-capability.md)
- [Semantic Label QCode Valid Requirement](semantic-label-qcode-valid.md)
