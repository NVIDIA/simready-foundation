# Section purity and per-selection isolation

| Code | AV.004 |
|---|---|
| Validator | VariationSectionPurityChecker |
| Compatibility | {compatibility}`Open USD` |
| Tags | {tag}`correctness` {tag}`composition` |

## Summary

A per-part variation option MUST compose its content only through an isolated
payload arc, and selecting one option MUST NOT change any content outside that
part. A master option MUST author child variant selections only.

## Description

**Section purity.** A per-part option (`<Category>_<part>`) composes its content
through a `prepend payload` arc to an isolated layer (for example under
`variants/` or `visuals/`) and authors no inline child prims, properties, or
other composition arcs inside the variant section. Inline variant opinions
outrank payloads in USD strength ordering and would leak across selections.

A master option (`<Category>`) authors **only** child variant selections that
drive the per-part sets; it carries no schema, geometry, or property opinions of
its own. A category with no separable parts MAY carry its content directly in a
single master set's option payloads instead of a master/per-part split.

**Per-selection isolation.** Recomposing the stage with one option selected MUST
NOT alter geometry, colliders, materials, metadata, or physics outside the scope
that option owns. The check composes each option on the session layer and
confirms that prims outside the switched part are byte-for-byte unchanged across
selections.

## Why

Isolating each option in its own payload keeps selections independent: a
consumer can switch one part without disturbing the rest of the asset, and a
`visual-only` option provably leaves simulation data alone (`AV.007`).

## Examples

### Valid: per-part options compose only through a payload; the master authors only selections

```usd
#usda 1.0
(
    defaultPrim = "Asset"
    customLayerData = {
        dictionary SimReady_Metadata = {
            dictionary Variants = {
                dictionary Representation = {
                    dictionary Representation = {
                        string prim = "/Asset"
                        string variantSetName = "Representation"
                        string category = "Representation"
                        string default = "Mesh"
                        string impactClass = "visual-only"
                    }
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
        string Representation = "Mesh"
    }
    prepend variantSets = ["Representation", "Representation_shade"]
)
{
    variantSet "Representation" = {
        "Mesh" (
            variants = {
                string Representation_shade = "Mesh"
            }
        ) {
        }
        "GaussianSplat" (
            variants = {
                string Representation_shade = "GaussianSplat"
            }
        ) {
        }
    }
    variantSet "Representation_shade" = {
        "Mesh" (
            prepend payload = @./variants/shade_mesh.usd@
        ) {
        }
        "GaussianSplat" (
            prepend payload = @./variants/shade_splat.usd@
        ) {
        }
    }
}
```

Each per-part option carries only its payload arc, and each master option carries
only a child selection.

### Invalid: a per-part option inlines its content

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
    variantSet "Representation_shade" = {
        "Mesh" {
            def Mesh "ShadeMesh"
            {
                int[] faceVertexCounts = [3]
                int[] faceVertexIndices = [0, 1, 2]
                point3f[] points = [(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)]
            }
        }
        "GaussianSplat" (
            prepend payload = @./variants/shade_splat.usd@
        ) {
        }
    }
}
```

The `Mesh` option inlines a prim instead of composing a payload, so its opinion
outranks the payload and leaks across selections.

## How to comply

Move each option's content into its own payload layer and keep the variant
section limited to the payload arc. Keep the master set to child selections.

## Related requirements and references

`AV.003` owns per-option content validity; `AV.005`/`AV.006` own the envelope
invariants a leak would otherwise break. This generalizes `RV.010`
(section purity) and `RV.011` (per-selection isolation) from `Variants.Physics`
to any variation category.
