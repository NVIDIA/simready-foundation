# Impact-class honesty

| Code | AV.007 |
|---|---|
| Validator | ImpactClassHonestyChecker |
| Compatibility | {compatibility}`Open USD` |
| Tags | {tag}`correctness` |

## Summary

A variant set's declared `impactClass` MUST match what its options actually
change: a `visual-only` set changes no simulation-relevant data; a
`simulation-affecting` set changes only the domain it declares.

## Description

Each variant set declares `impactClass` of `visual-only` or
`simulation-affecting` in its `AV.001` metadata. The declaration MUST be true
under recomposition of every option:

- A **`visual-only`** set MUST NOT change colliders, physics schemas or
  attributes (`UsdPhysics`, `physx`, `newton:`, `mjc:`), mass properties, or the
  collision envelope across its options. Only visual geometry/material/encoding
  may differ.
- A **`simulation-affecting`** set MUST change only its declared domain. The
  `Collision` category declares collision-contact behavior: its options may
  differ in collider approximation but MUST hold the collision envelope
  (`AV.006`) and the authored mass/center-of-mass/inertia (`AV.009`) invariant,
  and MUST NOT alter unrelated physics.

A set whose options change simulation data while declaring `visual-only`, or a
`simulation-affecting` set that changes data outside its declared domain, fails.

## Why

Consumers trust the impact class to decide whether re-selecting an option is a
free visual swap or a change that must be re-simulated or re-validated. A
dishonest class silently breaks that decision.

## Examples

Content is shown inline for brevity; a production asset isolates each option's
content in its own payload (`AV.004`).

### Valid: a visual-only set changes only visual data

```usd
#usda 1.0
(
    defaultPrim = "Asset"
    customLayerData = {
        dictionary SimReady_Metadata = {
            dictionary Variants = {
                dictionary Appearance = {
                    dictionary Appearance = {
                        string prim = "/Asset"
                        string variantSetName = "Appearance"
                        string category = "Appearance"
                        string default = "Red"
                        string impactClass = "visual-only"
                    }
                }
            }
        }
    }
)
def Xform "Asset" (
    variants = {
        string Appearance = "Red"
    }
    prepend variantSets = ["Appearance"]
)
{
    variantSet "Appearance" = {
        "Red" {
            def Mesh "Geo"
            {
                int[] faceVertexCounts = [3]
                int[] faceVertexIndices = [0, 1, 2]
                point3f[] points = [(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)]
                color3f[] primvars:displayColor = [(1, 0, 0)]
            }
        }
        "Blue" {
            def Mesh "Geo"
            {
                int[] faceVertexCounts = [3]
                int[] faceVertexIndices = [0, 1, 2]
                point3f[] points = [(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)]
                color3f[] primvars:displayColor = [(0, 0, 1)]
            }
        }
    }
}
```

Both options change only `displayColor`; no `UsdPhysics` data moves, so the
`visual-only` declaration is honest.

### Invalid: a visual-only option changes physics

```usd
#usda 1.0
(
    defaultPrim = "Asset"
    customLayerData = {
        dictionary SimReady_Metadata = {
            dictionary Variants = {
                dictionary Appearance = {
                    dictionary Appearance = {
                        string prim = "/Asset"
                        string variantSetName = "Appearance"
                        string category = "Appearance"
                        string default = "Red"
                        string impactClass = "visual-only"
                    }
                }
            }
        }
    }
)
def Xform "Asset" (
    variants = {
        string Appearance = "Red"
    }
    prepend variantSets = ["Appearance"]
)
{
    variantSet "Appearance" = {
        "Red" {
            def Mesh "Geo"
            {
                int[] faceVertexCounts = [3]
                int[] faceVertexIndices = [0, 1, 2]
                point3f[] points = [(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)]
                color3f[] primvars:displayColor = [(1, 0, 0)]
            }
        }
        "Blue" {
            def Mesh "Geo" (
                prepend apiSchemas = ["PhysicsCollisionAPI"]
            )
            {
                int[] faceVertexCounts = [3]
                int[] faceVertexIndices = [0, 1, 2]
                point3f[] points = [(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)]
                color3f[] primvars:displayColor = [(0, 0, 1)]
            }
        }
    }
}
```

`Blue` adds a collider while the set is declared `visual-only`, so re-selecting it
silently changes simulation data. Declare `simulation-affecting`, or keep the
option free of physics.

## How to comply

Keep `visual-only` options limited to visual data, and keep
`simulation-affecting` options limited to their declared domain with envelope and
mass held invariant. Author the honest class in `AV.001` metadata.

## Related requirements and references

`AV.001` owns the declaration; `AV.005`/`AV.006` own the envelopes; `AV.009`
owns authored mass invariance. This generalizes the physics-isolation intent of
`RV.011` to the impact-class contract.
