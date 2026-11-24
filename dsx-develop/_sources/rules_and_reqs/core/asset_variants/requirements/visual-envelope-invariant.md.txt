# Visual envelope invariant

| Code | AV.005 |
|---|---|
| Validator | VisualEnvelopeInvariantChecker |
| Compatibility | {compatibility}`Open USD` |
| Tags | {tag}`correctness` {tag}`geometry` |

## Summary

Every option of a variation variant set MUST hold the asset's visual envelope
size invariant within tolerance.

## Description

The visual envelope is the world-aligned bounding box computed over the
`default` and `render` purposes with `UsdGeom.BBoxCache`. For each variation
variant set, the envelope **size** (the box's XYZ extent) computed under each
option MUST match the size under the authored default within an absolute
tolerance of `1e-3` meters per axis.

A variation changes what the asset looks like or how it collides, never how much
room it occupies. An option whose selection grows or shrinks the visual envelope
is a different asset or SKU, not a variation, and fails this rule. Position of
the box may differ only insofar as the asset's origin and placement are
unchanged; the invariant is on size, not on content.

## Why

A scenario places and spaces assets by their envelope. If switching a
representation or appearance resized the asset, every placement that depended on
its footprint would break. Holding the visual envelope invariant is what lets a
variation be swapped after placement.

## Examples

Content is shown inline for brevity; a production asset isolates each option's
content in its own payload (`AV.004`).

### Valid: both options occupy the same visual envelope

```usd
#usda 1.0
(
    defaultPrim = "Asset"
    customLayerData = {
        dictionary SimReady_Metadata = {
            dictionary Variants = {
                dictionary MeshVariant = {
                    dictionary MeshVariant = {
                        string prim = "/Asset"
                        string variantSetName = "MeshVariant"
                        string category = "MeshVariant"
                        string default = "Smooth"
                        string impactClass = "visual-only"
                    }
                }
            }
        }
    }
)
def Xform "Asset" (
    variants = {
        string MeshVariant = "Smooth"
    }
    prepend variantSets = ["MeshVariant"]
)
{
    variantSet "MeshVariant" = {
        "Smooth" {
            def Cube "Geo"
            {
                double size = 0.3
            }
        }
        "Faceted" {
            def Cube "Geo"
            {
                double size = 0.3
            }
        }
    }
}
```

Both forms span the same `0.3 x 0.3 x 0.3` m box, so the visual envelope is
invariant.

### Invalid: an option resizes the visual envelope

```usd
#usda 1.0
(
    defaultPrim = "Asset"
    customLayerData = {
        dictionary SimReady_Metadata = {
            dictionary Variants = {
                dictionary MeshVariant = {
                    dictionary MeshVariant = {
                        string prim = "/Asset"
                        string variantSetName = "MeshVariant"
                        string category = "MeshVariant"
                        string default = "Smooth"
                        string impactClass = "visual-only"
                    }
                }
            }
        }
    }
)
def Xform "Asset" (
    variants = {
        string MeshVariant = "Smooth"
    }
    prepend variantSets = ["MeshVariant"]
)
{
    variantSet "MeshVariant" = {
        "Smooth" {
            def Cube "Geo"
            {
                double size = 0.3
            }
        }
        "Faceted" {
            def Cube "Geo"
            {
                double size = 0.5
            }
        }
    }
}
```

`Faceted` grows the box to `0.5 x 0.5 x 0.5` m; a variation must change the form,
not the footprint. Ship a larger form as a separate asset.

## How to comply

Author each option to the same silhouette size. If a genuinely larger or smaller
form is needed, ship it as a separate asset rather than a variation.

## Related requirements and references

`AV.006` owns the collision envelope; `AV.004` owns the isolation that keeps
unrelated geometry from drifting. `VG.014` owns authored extents and `VG.025`
root/origin conventions.
