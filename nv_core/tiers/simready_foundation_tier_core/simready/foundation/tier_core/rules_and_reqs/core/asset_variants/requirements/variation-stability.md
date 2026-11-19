# Variation stability

| Code | AV.010 |
|---|---|
| Validator | VariationStabilityChecker |
| Compatibility | {compatibility}`Open USD` |
| Tags | {tag}`correctness` {tag}`composition` |

## Summary

Across a variation set's options, no prim that is present in two or more options
MAY change its prim **type** or its authored local **transform**. A variation MAY
only add or remove geometry leaves under a stable part prim.

## Description

Every varied scope is a stable `Xform` defined in the asset's root layer (for
example `/Asset/Part`). That prim owns the part's transform (pose and pivot),
physics, collider, mass, and semantics, and persists unchanged across every
selection. Each option composes its representation, mesh, collider, or material
only as a **child** of that prim (for example `/Asset/Part/Geo_mesh`). An option
therefore adds and removes whole child subtrees; it never redefines the part prim
itself.

The checker composes each option of a declared variation set and builds a
per-prim fingerprint of `(typeName, composed local transform)` under the default
prim. For any prim present in two or more of a set's options it fails when:

- the prim's **type** differs between options (for example a `Mesh` in one option
  and a `GaussianSplat` in another at the same path), or
- the prim's authored local **transform** differs between options.

A prim present in only some options is an added or removed geometry leaf and is
allowed; that is the sanctioned way a variation swaps content.

## Why

Two failure modes motivate this rule, both observed on real assets:

- **Dropped pose.** When an option re-defines the part prim instead of a child,
  the part's transform is authored inside the variant section. An authored or
  interactive pose applied to the part (for example posed open) is then dropped the moment
  a different option is selected, because the new section does not carry it.
- **Renderer ghost.** When two options redefine one shared child prim with a
  different type (a render mesh versus a Gaussian splat), switching mutates a
  single prim's type in place. Some Hydra versions resync that poorly and leave a
  ghost of the inactive representation on screen until reload. Giving each type
  its own child name turns the switch into a clean subtree add/remove.

Holding type and transform stable also makes the envelope and impact invariants
(`AV.005`-`AV.007`) hold by construction, because the collider and physics live on
the stable prim outside every variant section.

## Examples

Content is shown inline for brevity; a production asset isolates each option's
content in its own payload (`AV.004`).

### Valid: each option adds its own geometry child under a stable part Xform

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
    def Xform "Part"
    {
        double3 xformOp:translate = (0, 0, 0.2)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }

    variantSet "Representation" = {
        "Mesh" {
            over "Part"
            {
                def Mesh "Geo_mesh"
                {
                    int[] faceVertexCounts = [3]
                    int[] faceVertexIndices = [0, 1, 2]
                    point3f[] points = [(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)]
                }
            }
        }
        "Splat" {
            over "Part"
            {
                def ParticleField3DGaussianSplat "Geo_splat"
                {
                    point3f[] positions = [(0, 0, 0)]
                }
            }
        }
    }
}
```

`/Asset/Part` keeps its type (`Xform`) and transform across both options. `Geo_mesh`
and `Geo_splat` each appear in one option only, so they are added-only leaves and
the switch is a clean subtree swap.

### Invalid: a shared child changes type between options

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
    def Xform "Part"
    {
        double3 xformOp:translate = (0, 0, 0.2)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }

    variantSet "Representation" = {
        "Mesh" {
            over "Part"
            {
                def Mesh "Geo"
                {
                    int[] faceVertexCounts = [3]
                    int[] faceVertexIndices = [0, 1, 2]
                    point3f[] points = [(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)]
                }
            }
        }
        "Splat" {
            over "Part"
            {
                def ParticleField3DGaussianSplat "Geo"
                {
                    point3f[] positions = [(0, 0, 0)]
                }
            }
        }
    }
}
```

`/Asset/Part/Geo` is a `Mesh` under `Mesh` and a `ParticleField3DGaussianSplat` under
`Splat`. Mutating one prim's type in place is the renderer-ghost case; give each
encoding its own child name instead.

### Invalid: the part's transform differs between options

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
                        string default = "Closed"
                        string impactClass = "visual-only"
                    }
                }
            }
        }
    }
)
def Xform "Asset" (
    variants = {
        string Representation = "Closed"
    }
    prepend variantSets = ["Representation"]
)
{
    def Xform "Part"
    {
    }

    variantSet "Representation" = {
        "Closed" {
            over "Part"
            {
                double3 xformOp:translate = (0, 0, 0.2)
                uniform token[] xformOpOrder = ["xformOp:translate"]
                def Mesh "Geo_mesh"
                {
                    int[] faceVertexCounts = [3]
                    int[] faceVertexIndices = [0, 1, 2]
                    point3f[] points = [(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)]
                }
            }
        }
        "Open" {
            over "Part"
            {
                double3 xformOp:translate = (0, 0, 0.2)
                float3 xformOp:rotateXYZ = (45, 0, 0)
                uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ"]
                def Mesh "Geo_mesh"
                {
                    int[] faceVertexCounts = [3]
                    int[] faceVertexIndices = [0, 1, 2]
                    point3f[] points = [(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)]
                }
            }
        }
    }
}
```

`/Asset/Part` carries a different composed transform under `Closed` and `Open`, so
selecting a different option drops the authored pose. The transform belongs on the
stable part prim outside every option.

## How to comply

Define each varied part as a stable `Xform` in the root layer with its transform,
physics, collider, and semantics. Compose each option's geometry as a child of
that prim. When options differ in prim type, give each option its own child name
(for example `Geo_mesh` and `Geo_splat`); same-type options may reuse one child
name.

## Related requirements and references

`AV.002`/`AV.004` own where the variant set lives and the purity of each option's
composition; `AV.005`-`AV.007` own the envelope and impact invariants that a
redefinition would otherwise break. `AV.010` is the structural invariant that
keeps a part's pose and a representation's identity stable across selections.
