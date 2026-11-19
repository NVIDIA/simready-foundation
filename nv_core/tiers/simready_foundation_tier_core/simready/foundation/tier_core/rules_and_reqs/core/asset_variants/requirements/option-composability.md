# Per-option composability and content validity

| Code | AV.003 |
|---|---|
| Validator | VariationOptionComposabilityChecker |
| Compatibility | {compatibility}`Open USD` |
| Tags | {tag}`correctness` {tag}`composition` |

## Summary

Every option of a variation variant set MUST compose to a valid stage, and the
category's content requirements MUST hold under **each** option, not only under
the authored default.

## Description

For each variation variant set, selecting each option in turn MUST yield a stage
that opens and composes without error, resolves the default prim, and satisfies
the content requirements the owning feature declares for that category. The
check recomposes the stage once per option by writing the selection on the
session layer, leaving the authored default untouched.

A representation option MUST carry its own valid content: a `Mesh` option
composes a valid `UsdGeomMesh` and no splat; a `GaussianSplat` option composes a
valid `ParticleField3DGaussianSplat` and no mesh gprim. A `MeshVariant` option
composes a valid mesh. A `Collision` option composes a valid collider. An
`Appearance` option binds a valid visual material.

An option that fails to compose, that leaks the content of a sibling option, or
whose content violates the category's requirements fails.

## Why

An asset advertises every option as a usable state. Validating only the default
selection would let a broken or empty non-default option ship undetected, so the
contract checks every option the way a consumer would when it switches to it.

## Examples

Content is shown inline for brevity; a production asset isolates each option's
content in its own payload (`AV.004`).

### Valid: each option composes its own non-empty content

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
                }
            }
        }
    }
)
def Xform "Asset" (
    variants = {
        string Representation = "Mesh"
    }
    prepend variantSets = ["Representation"]
)
{
    variantSet "Representation" = {
        "Mesh" {
            def Mesh "Geo_mesh"
            {
                int[] faceVertexCounts = [3]
                int[] faceVertexIndices = [0, 1, 2]
                point3f[] points = [(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)]
            }
        }
        "GaussianSplat" {
            def ParticleField3DGaussianSplat "Geo_splat"
            {
                point3f[] positions = [(0, 0, 0)]
            }
        }
    }
}
```

Both options compose a valid, non-empty subtree carrying only their own encoding.

### Invalid: an option composes nothing

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
                }
            }
        }
    }
)
def Xform "Asset" (
    variants = {
        string Representation = "Mesh"
    }
    prepend variantSets = ["Representation"]
)
{
    variantSet "Representation" = {
        "Mesh" {
            def Mesh "Geo_mesh"
            {
                int[] faceVertexCounts = [3]
                int[] faceVertexIndices = [0, 1, 2]
                point3f[] points = [(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)]
            }
        }
        "GaussianSplat" {
        }
    }
}
```

The `GaussianSplat` option composes an empty asset: a consumer that selects it
gets no content.

## How to comply

Author each option's content in its own isolated payload (`AV.004`) and open the
asset under each selection to confirm it composes and passes the category's
content checks before publishing.

## Related requirements and references

`AV.004` owns section purity and per-selection isolation; the owning feature
names the per-category content requirements (mesh `VG.*`, `SPL.*`, collider, or
material). `RV.011` performs the analogous per-selection recomposition for
physics runtimes.
