# pascal-voc-labels

| Code     | VOC.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`voc-001` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`correctness` |


## Summary

Every `SemanticsLabelsAPI:pascal_voc` label value must be a member of the PASCAL VOC (20) taxonomy.

## Description

This requirement validates semantic label *values* against the PASCAL VOC (20) vocabulary (20 classes).
It is a closed-vocabulary check: a value that is not a PASCAL VOC (20) class fails. Matching is
case-insensitive and tolerant of spacing (`_`/`-` are treated as spaces) and of a class's display
name or aliases — a value that matches only after that normalization passes with a warning that
suggests the canonical class name.

This rule is layered on top of the vendor-neutral existence requirement
[SL.001](../../semantic_labels/requirements/semantic-label-capability.md): SL.001 asks whether *a*
label exists; this rule asks whether the label is a valid PASCAL VOC (20) class. It applies only to prims that
opt into the taxonomy by applying its `SemanticsLabelsAPI:pascal_voc` instance; prims without it are not
affected.

### Scope

Evaluated over the stage's `defaultPrim` and its descendants. The taxonomy is identified by the
`SemanticsLabelsAPI` instance name `pascal_voc`. Multiple taxonomies can coexist on the same prim (the
schema is a "Multiple Apply" API), so this rule never conflicts with other taxonomy or Q-code labels.

## Why is it required?

- Ground-truth and ML-training pipelines that consume this dataset's label space need values drawn
  from that exact vocabulary.
- Catches typos and out-of-vocabulary classes before the asset reaches a training run.

## Examples

```usd
# Valid: canonical PASCAL VOC (20) classes
def Xform "Thing" (
    prepend apiSchemas = ["SemanticsLabelsAPI:pascal_voc"]
)
{
    token[] semantics:labels:pascal_voc = ["aeroplane", "bicycle", "person"]
}

# Warning: matches after normalization -- suggests the canonical spelling "aeroplane"
def Xform "ThingB" (
    prepend apiSchemas = ["SemanticsLabelsAPI:pascal_voc"]
)
{
    token[] semantics:labels:pascal_voc = ["Aeroplane"]
}

# Invalid: not a PASCAL VOC (20) class
def Xform "ThingC" (
    prepend apiSchemas = ["SemanticsLabelsAPI:pascal_voc"]
)
{
    token[] semantics:labels:pascal_voc = ["spaceship"]
}
```

## How to comply

- Use class names from the PASCAL VOC (20) taxonomy for `semantics:labels:pascal_voc` values.
- Prefer the canonical lowercase class name to avoid the non-canonical warning.

## For More Information

- [PASCAL VOC (20) dataset](http://host.robots.ox.ac.uk/pascal/VOC/)
- [USD Semantics Documentation](https://openusd.org/release/api/usd_semantics_page_front.html)
