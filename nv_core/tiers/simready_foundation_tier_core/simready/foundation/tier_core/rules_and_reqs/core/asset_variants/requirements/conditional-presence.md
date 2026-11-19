# Conditional presence

| Code | AV.008 |
|---|---|
| Validator | ConditionalPresenceChecker |
| Compatibility | {compatibility}`Open USD` |
| Tags | {tag}`correctness` {tag}`composition` |

## Summary

A variation variant set MUST exist if and only if its scope offers two or more
options; a scope with a single representation carries no variant set.

## Description

A category's master or per-part set is authored only when that scope genuinely
offers a choice. A part that has exactly one representation MUST NOT carry a
per-part set and MUST NOT appear in the master set; it composes unconditionally.
Conversely, a scope that offers two or more options MUST expose them through a
variant set rather than, for example, an authored metadata entry with no set.

A master set MUST list exactly the parts that have two or more options. A
discovery-metadata entry (`AV.001`) MUST exist for each present set and MUST NOT
exist for an absent one.

## Why

An empty or single-option variant set is noise: it implies a choice that does
not exist and forces consumers to handle a degenerate switch. Requiring a set
only where a real choice exists keeps the asset's advertised variations
truthful.

## Examples

### Valid: a multi-option part carries a set; a single-representation part does not

```usd
#usda 1.0
(
    defaultPrim = "Asset"
    customLayerData = {
        dictionary SimReady_Metadata = {
            dictionary Variants = {
                dictionary Representation = {
                    dictionary Representation_shade = {
                        string prim = "/Asset"
                        string variantSetName = "Representation_shade"
                        string category = "Representation"
                        string default = "Mesh"
                        string impactClass = "visual-only"
                    }
                }
            }
        }
    }
)
def Xform "Asset" (
    variants = {
        string Representation_shade = "Mesh"
    }
    prepend variantSets = ["Representation_shade"]
)
{
    def Xform "Base"
    {
    }

    variantSet "Representation_shade" = {
        "Mesh" {
        }
        "GaussianSplat" {
        }
    }
}
```

The `shade` offers two forms, so it carries `Representation_shade`. The
single-representation `Base` composes unconditionally with no set of its own.

### Invalid: a variant set with a single option

```usd
#usda 1.0
(
    defaultPrim = "Asset"
    customLayerData = {
        dictionary SimReady_Metadata = {
            dictionary Variants = {
                dictionary Representation = {
                    dictionary Representation_base = {
                        string prim = "/Asset"
                        string variantSetName = "Representation_base"
                        string category = "Representation"
                        string default = "Mesh"
                        string impactClass = "visual-only"
                    }
                }
            }
        }
    }
)
def Xform "Asset" (
    variants = {
        string Representation_base = "Mesh"
    }
    prepend variantSets = ["Representation_base"]
)
{
    variantSet "Representation_base" = {
        "Mesh" {
        }
    }
}
```

`Representation_base` offers a single option, so it implies a choice that does not
exist. Remove the set and let the base compose unconditionally.

## How to comply

Author a variant set only where a scope has two or more options, and list only
multi-option parts in the master set. Remove single-option sets.

## Related requirements and references

`AV.002` owns the two-option threshold per set; `AV.001` owns the metadata that
must match presence; `AV.004` owns master/per-part composition.
