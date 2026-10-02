# ade20k-labels

| Code     | ADE.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`ade-001` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`correctness` |


## Summary

Every `SemanticsLabelsAPI:ade20k` label value must be a member of the ADE20K (150) taxonomy.

## Description

This requirement validates semantic label *values* against the ADE20K (150) vocabulary (150 classes).
It is a closed-vocabulary check: a value that is not a ADE20K (150) class fails. Matching is
case-insensitive and tolerant of spacing (`_`/`-` are treated as spaces) and of a class's display
name or aliases — a value that matches only after that normalization passes with a warning that
suggests the canonical class name.

This rule is layered on top of the vendor-neutral existence requirement
[SL.001](../../semantic_labels/requirements/semantic-label-capability.md): SL.001 asks whether *a*
label exists; this rule asks whether the label is a valid ADE20K (150) class. It applies only to prims that
opt into the taxonomy by applying its `SemanticsLabelsAPI:ade20k` instance; prims without it are not
affected.

### Scope

Evaluated over the stage's `defaultPrim` and its descendants. The taxonomy is identified by the
`SemanticsLabelsAPI` instance name `ade20k`. Multiple taxonomies can coexist on the same prim (the
schema is a "Multiple Apply" API), so this rule never conflicts with other taxonomy or Q-code labels.

## Why is it required?

- Ground-truth and ML-training pipelines that consume this dataset's label space need values drawn
  from that exact vocabulary.
- Catches typos and out-of-vocabulary classes before the asset reaches a training run.

## Examples

```usd
# Valid: canonical ADE20K (150) classes
def Xform "Thing" (
    prepend apiSchemas = ["SemanticsLabelsAPI:ade20k"]
)
{
    token[] semantics:labels:ade20k = ["wall", "building", "sky"]
}

# Warning: matches after normalization -- suggests the canonical spelling "wall"
def Xform "ThingB" (
    prepend apiSchemas = ["SemanticsLabelsAPI:ade20k"]
)
{
    token[] semantics:labels:ade20k = ["Wall"]
}

# Invalid: not a ADE20K (150) class
def Xform "ThingC" (
    prepend apiSchemas = ["SemanticsLabelsAPI:ade20k"]
)
{
    token[] semantics:labels:ade20k = ["spaceship"]
}
```

## How to comply

- Use class names from the ADE20K (150) taxonomy for `semantics:labels:ade20k` values.
- Prefer the canonical lowercase class name to avoid the non-canonical warning.

## For More Information

- [ADE20K (150) dataset](https://groups.csail.mit.edu/vision/datasets/ADE20K/)
- [USD Semantics Documentation](https://openusd.org/release/api/usd_semantics_page_front.html)
