# semantic-label-material

| Code     | SL.MAT.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`sl-mat-001` |
| Compatibility | {compatibility}`nvidia-omniverse`  |
| Tags     | {tag}`correctness` |

## Summary

Visual material prims must be labeled with a non-empty `SemanticsLabelsAPI:material` label.

## Description

For ground-truth material segmentation, every visual `Material` prim must carry semantic labels under the `material` taxonomy: the `SemanticsLabelsAPI:material` schema applied with at least one authored value in `semantics:labels:material` (for example `"metal"`, `"plastic"`, `"wood"`).

This is an NVIDIA convention layered on top of the taxonomy-agnostic object labeling (SL.001): object/class labels describe *what an object is*, while the `material` taxonomy describes *what it is made of*. The two coexist via the OpenUSD `SemanticsLabelsAPI` "Multiple Apply" schema design.

### Which materials this applies to

A physics material is a `Material` prim as well, so the prim type alone cannot say whether a
label is expected. Material segmentation describes what a sensor sees, so the requirement
applies to the materials the asset actually renders with. A material is in scope when all
three of the following hold:

1. **It is bound by renderable geometry.** The binding resolves from a `Gprim` — or one of its
   `materialBind` `GeomSubsets` — whose computed purpose is `default` or `render`. `proxy` and
   `guide` geometry does not count, and instanced geometry does: the binding is resolved
   through instance proxies so material bindings inside an `instanceable` reference are seen.
2. **The binding is a render-purpose binding.** `material:binding` and its `full` / `preview`
   purposes are consulted; `material:binding:physics` is not.
3. **It resolves a shading network.** A render terminal (`outputs:surface`,
   `outputs:displacement` or `outputs:volume`, in the universal context or a
   render-context-qualified form such as `outputs:mdl:surface`) connects to a shading node. A
   material whose terminal is authored but left unconnected is still in scope when a `Shader`
   sits in its namespace; the missing connection is a visual-material defect reported by the
   [Visual Materials](../../visualization/materials/capability-materials.md) capability.

A physics material fails (2) and (3), so it is never asked for a material label. A material
library that nothing renders with fails (1) and is likewise out of scope.

## Examples

```usd
# Valid: the object carries a class label, and its Material carries a material label
def Xform "Car" (
    prepend apiSchemas = ["SemanticsLabelsAPI:class"]
)
{
    token[] semantics:labels:class = ["car", "vehicle"]

    def Mesh "Body" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {
        rel material:binding = </Car/Materials/Metal>
        rel material:binding:physics = </Car/PhysicsMaterials/Steel>
    }

    def Scope "Materials" {
        def Material "Metal" (
            prepend apiSchemas = ["SemanticsLabelsAPI:material"]
        )
        {
            token outputs:surface.connect = </Car/Materials/Metal/Shader.outputs:surface>
            token[] semantics:labels:material = ["metal", "shiny"]

            def Shader "Shader" {
                uniform token info:id = "UsdPreviewSurface"
                token outputs:surface
            }
        }
    }

    # Valid: a physics material is out of scope. It has no render terminal and is bound
    # through the physics purpose, so no material label is expected on it.
    def Scope "PhysicsMaterials" {
        def Material "Steel" (
            prepend apiSchemas = ["PhysicsMaterialAPI"]
        )
        {
            float physics:dynamicFriction = 0.6
            float physics:staticFriction = 0.8
        }
    }
}

# Invalid: a rendered Material prim has no SemanticsLabelsAPI:material label
def Material "Metal" {
    token outputs:surface.connect = </Metal/Shader.outputs:surface>

    def Shader "Shader" {
        uniform token info:id = "UsdPreviewSurface"
        token outputs:surface
    }
}
```

For assets intended to ship alongside NVIDIA Omniverse asset libraries, the
material *values* use the Wikidata Q-code taxonomy instead of free text. The
instance name stays `material` (that is what this requirement keys on), while the
class label uses the `wikidata_qcode` instance. Annotate each opaque code with a
comment, since a reader cannot tell at a glance that `Q11426` means "metal":

```usd
# Valid (NVIDIA Q-code values): the class uses wikidata_qcode; the material values are Q-codes
def Xform "Car" (
    prepend apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]
)
{
    token[] semantics:labels:wikidata_qcode = ["Q1420"]  # Q1420 = motor car

    def Scope "Materials" {
        def Material "Metal" (
            prepend apiSchemas = ["SemanticsLabelsAPI:material"]
        )
        {
            token[] semantics:labels:material = ["Q11426", "Q663"]  # Q11426 = metal, Q663 = aluminium
        }
    }
}
```

The Q-code format rule (SL.QCODE.001) only checks the `wikidata_qcode` instance, so
Q-code values authored under the `material` instance are not format-validated —
the comment is what keeps them legible. See
[Semantic Label QCode Valid (SL.QCODE.001)](semantic-label-qcode-valid.md).

## Why is it required?

- Enables material-segmentation ground truth for perception/ML training
- Separates "what an object is" (class) from "what it is made of" (material)
- Keeps material semantics consistent across NVIDIA Omniverse asset libraries

## How to comply

1. Apply `SemanticsLabelsAPI:material` to each visual `Material` prim.
2. Author at least one value in `semantics:labels:material` describing the material type.
3. Leave physics materials unlabeled. If a physics material is reported, it is bound in the
   render slot (`material:binding` rather than `material:binding:physics`) or carries a
   shading network; fix the binding instead of adding a label.

## For More Information

- [Semantic Labels Capability](../capability-semantic_labels.md)
- [Semantic Label Capability Requirement](semantic-label-capability.md)
- [Semantic Label QCode Valid Requirement](semantic-label-qcode-valid.md)
