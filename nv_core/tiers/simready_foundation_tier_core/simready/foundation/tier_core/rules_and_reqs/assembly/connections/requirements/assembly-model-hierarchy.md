# assembly-model-hierarchy

| Code     | CN.012 |
|----------|--------|
| Validator| AssemblyModelHierarchyChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The assembly default prim must have `kind = "assembly"`. Each composed-in child asset root must have `kind = "component"` or `kind = "assembly"`, and every prim between the default prim and a child asset root that carries a model kind must be `group` or `assembly`, so the model hierarchy is contiguous.

## Description

USD model hierarchy is contiguous: a prim is a model only when every ancestor is a `group` or `assembly` model. A `component` is a terminal model and has no model descendants.

An assembly stage therefore has this shape:

- The default prim is `assembly`.
- Each child asset root, the topmost prim on a branch that introduces a reference or payload arc (`CN.010`), is `component` or `assembly`. A nested assembly is an `assembly` child.
- Each assembly-local prim above a child asset root is `group` or `assembly`. A compound body (`CN.011`) is `group`.
- No prim inside a `component` carries a model kind. Internal structure such as links uses no kind or `subcomponent`.

Child assets keep the kind they are published with. Attachment semantics do not depend on kind: mate sites, connections, and mate bodies are found by traversal (`MC.001`, `CN.001`, `MC.003`).

## Why is it required?

- Model traversal, model-level selection, and catalog tooling stop at the first prim that breaks the model hierarchy.
- An `assembly` root over `component` and `assembly` children lets an assembly be referenced into a larger assembly without kind edits.

## Examples

```usd
# Valid: assembly root, component children
def Xform "UR10_Robotiq_2F85" (
    kind = "assembly"
)
{
    def Xform "Arm" (
        prepend references = @../../ur10/simready_usd/ur10.usd@</ur10>
    )
    {
    }

    def Xform "Gripper" (
        prepend references = @../../Robotiq/2F-85/simready_usd/2F-85.usda@</Robotiq_2F_85>
    )
    {
    }
}
```

```usd
# Valid: nested assemblies under a group compound body
def Xform "IndustrialPlasticPallet_Stack_B01" (
    kind = "assembly"
)
{
    def Xform "CompoundBody" (
        kind = "group"
    )
    {
        def Xform "Stack_0" (
            prepend references = @../../industrialplasticpallet_stack_a01/simready_usd/industrialplasticpallet_stack_a01.usda@
        )
        {
        }
    }
}
```

```usd
# Invalid: default prim is a component
def Xform "UR10_Robotiq_2F85" (
    kind = "component"
)
{
}
```

```usd
# Invalid: group model inside a component asset
def Xform "Robotiq_2F_85" (
    kind = "component"
)
{
    def Xform "base_link" (
        kind = "group"
    )
    {
    }
}
```

## How to comply

1. Set `kind = "assembly"` on the assembly default prim.
2. Publish each child asset with a `component` or `assembly` root.
3. Set `kind = "group"` on each assembly-local prim that holds child assets, including the compound body.
4. Clear model kinds inside a `component`, or use `subcomponent`.

## Related Requirements

- [assembly-child-references](assembly-child-references.md)
- [compound-body](compound-body.md)
- [assembly-type](assembly-type.md)

## For More Information

- [Kinds](https://openusd.org/dev/api/kind_page_front.html)
- [Model Hierarchy](https://openusd.org/release/glossary.html#usdglossary-modelhierarchy)
