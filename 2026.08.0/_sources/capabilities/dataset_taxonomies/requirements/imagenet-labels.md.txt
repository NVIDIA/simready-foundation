# imagenet-labels

| Code     | IN1K.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`in1k-001` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`correctness` |


## Summary

Every `SemanticsLabelsAPI:imagenet_1k` label value must be a member of the ImageNet-1K taxonomy.

## Description

This requirement validates semantic label *values* against the ImageNet-1K vocabulary (1000 classes).
It is a closed-vocabulary check: a value that is not a ImageNet-1K class fails. Matching is
case-insensitive and tolerant of spacing (`_`/`-` are treated as spaces) and of a class's display
name or aliases — a value that matches only after that normalization passes with a warning that
suggests the canonical class name.

This rule is layered on top of the vendor-neutral existence requirement
[SL.001](../../semantic_labels/requirements/semantic-label-capability.md): SL.001 asks whether *a*
label exists; this rule asks whether the label is a valid ImageNet-1K class. It applies only to prims that
opt into the taxonomy by applying its `SemanticsLabelsAPI:imagenet_1k` instance; prims without it are not
affected.

### Scope

Evaluated over the stage's `defaultPrim` and its descendants. The taxonomy is identified by the
`SemanticsLabelsAPI` instance name `imagenet_1k`. Multiple taxonomies can coexist on the same prim (the
schema is a "Multiple Apply" API), so this rule never conflicts with other taxonomy or Q-code labels.

## Why is it required?

- Ground-truth and ML-training pipelines that consume this dataset's label space need values drawn
  from that exact vocabulary.
- Catches typos and out-of-vocabulary classes before the asset reaches a training run.

## Examples

```usd
# Valid: canonical ImageNet-1K classes
def Xform "Thing" (
    prepend apiSchemas = ["SemanticsLabelsAPI:imagenet_1k"]
)
{
    token[] semantics:labels:imagenet_1k = ["tench", "goldfish", "tiger shark"]
}

# Warning: matches after normalization -- suggests the canonical spelling "tench"
def Xform "ThingB" (
    prepend apiSchemas = ["SemanticsLabelsAPI:imagenet_1k"]
)
{
    token[] semantics:labels:imagenet_1k = ["Tench"]
}

# Invalid: not a ImageNet-1K class
def Xform "ThingC" (
    prepend apiSchemas = ["SemanticsLabelsAPI:imagenet_1k"]
)
{
    token[] semantics:labels:imagenet_1k = ["spaceship"]
}
```

## How to comply

- Use class names from the ImageNet-1K taxonomy for `semantics:labels:imagenet_1k` values.
- Prefer the canonical lowercase class name to avoid the non-canonical warning.

## For More Information

- [ImageNet-1K dataset](https://www.image-net.org/)
- [USD Semantics Documentation](https://openusd.org/release/api/usd_semantics_page_front.html)
