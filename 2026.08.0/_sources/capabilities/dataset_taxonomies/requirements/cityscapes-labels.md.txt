# cityscapes-labels

| Code     | CITY.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`city-001` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`correctness` |


## Summary

Every `SemanticsLabelsAPI:cityscapes` label value must be a member of the Cityscapes (fine) taxonomy.

## Description

This requirement validates semantic label *values* against the Cityscapes (fine) vocabulary (35 classes).
It is a closed-vocabulary check: a value that is not a Cityscapes (fine) class fails. Matching is
case-insensitive and tolerant of spacing (`_`/`-` are treated as spaces) and of a class's display
name or aliases — a value that matches only after that normalization passes with a warning that
suggests the canonical class name.

This rule is layered on top of the vendor-neutral existence requirement
[SL.001](../../semantic_labels/requirements/semantic-label-capability.md): SL.001 asks whether *a*
label exists; this rule asks whether the label is a valid Cityscapes (fine) class. It applies only to prims that
opt into the taxonomy by applying its `SemanticsLabelsAPI:cityscapes` instance; prims without it are not
affected.

### Scope

Evaluated over the stage's `defaultPrim` and its descendants. The taxonomy is identified by the
`SemanticsLabelsAPI` instance name `cityscapes`. Multiple taxonomies can coexist on the same prim (the
schema is a "Multiple Apply" API), so this rule never conflicts with other taxonomy or Q-code labels.

## Why is it required?

- Ground-truth and ML-training pipelines that consume this dataset's label space need values drawn
  from that exact vocabulary.
- Catches typos and out-of-vocabulary classes before the asset reaches a training run.

## Examples

```usd
# Valid: canonical Cityscapes (fine) classes
def Xform "Thing" (
    prepend apiSchemas = ["SemanticsLabelsAPI:cityscapes"]
)
{
    token[] semantics:labels:cityscapes = ["road", "car", "traffic light"]
}

# Warning: matches after normalization -- suggests the canonical spelling "road"
def Xform "ThingB" (
    prepend apiSchemas = ["SemanticsLabelsAPI:cityscapes"]
)
{
    token[] semantics:labels:cityscapes = ["Road"]
}

# Invalid: not a Cityscapes (fine) class
def Xform "ThingC" (
    prepend apiSchemas = ["SemanticsLabelsAPI:cityscapes"]
)
{
    token[] semantics:labels:cityscapes = ["spaceship"]
}
```

## How to comply

- Use class names from the Cityscapes (fine) taxonomy for `semantics:labels:cityscapes` values.
- Prefer the canonical lowercase class name to avoid the non-canonical warning.

## For More Information

- [Cityscapes (fine) dataset](https://www.cityscapes-dataset.com)
- [USD Semantics Documentation](https://openusd.org/release/api/usd_semantics_page_front.html)
