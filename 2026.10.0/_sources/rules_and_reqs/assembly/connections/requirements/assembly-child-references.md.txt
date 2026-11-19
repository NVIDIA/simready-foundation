# assembly-child-references

| Code     | CN.010 |
|----------|--------|
| Validator| AssemblyChildReferencesChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Each connected mate site must arrive on the assembly stage through a reference or payload arc to a separately published asset. Parts authored inline in the assembly's own root layer fail.

## Description

An assembly is an aggregation of separately published, separately validated assets. A child asset may be a `component` or another assembly (`CN.012`). This requirement verifies that the assembled parts are composed in rather than duplicated.

Walk from each connected mate site toward the assembly default prim. At least one prim on that path must introduce a `references` or `payload` composition arc. The site itself may be the prim carrying the arc. The assembly default prim is excluded: an arc there would make the whole stage a reference to something else, not an assembly of parts.

Both the socket site and the plug site of every connection are checked, including compound connections. A compound satisfies this the same way a jointed pairing does, because each demoted part is still referenced from its own published asset. The compound body itself carries no arc, which is what `CN.011` requires of it, so the arc is always found on a part below it.

The arc target is not required to be a distinct asset. A stack of identical parts references one asset repeatedly, and each reference introduces an independent subtree.

### Relationship to packaging

`FET_031_STANDARD` (`AA.001`) requires asset references to resolve inside the package source folder. An assembly packaged for distribution must therefore bring its child assets inside its own source, or declare them as package dependencies. Dependency declaration is tracked separately and is not specified by this requirement.

## Why is it required?

- An asset validated on its own carries its requirement conformance into the assembly only if the assembly composes it rather than copying it.
- Inlined geometry cannot be swapped, re-versioned, or revalidated as its own asset.
- Reference and payload arcs are what let an assembly be nested inside a larger assembly.

## Examples

```usd
# Valid: both parts referenced from published assets
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
# Valid: compound stack, one asset referenced twice under the compound body.
# The compound body itself carries no arc (CN.011).
def Xform "CompoundBody" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
    kind = "group"
)
{
    float physics:mass = 57

    def Xform "Pallet_0" (
        prepend references = @../../industrialplasticpallet_a01/simready_usd/industrialplasticpallet_a01.usd@</RootNode>
    )
    {
        bool physics:rigidBodyEnabled = false
    }

    def Xform "Pallet_1" (
        prepend references = @../../industrialplasticpallet_a01/simready_usd/industrialplasticpallet_a01.usd@</RootNode>
    )
    {
        bool physics:rigidBodyEnabled = false
    }
}
```

```usd
# Valid: two published stack assemblies referenced as children
def Xform "CompoundBody" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
    kind = "group"
)
{
    float physics:mass = 171

    def Xform "Stack_0" (
        prepend references = @../../industrialplasticpallet_stack_a01/simready_usd/industrialplasticpallet_stack_a01.usda@
    )
    {
    }

    def Xform "Stack_1" (
        prepend references = @../../industrialplasticpallet_stack_a01/simready_usd/industrialplasticpallet_stack_a01.usda@
    )
    {
    }
}
```

```usd
# Invalid: gripper geometry and mate site authored inline
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
        prepend apiSchemas = ["PhysicsRigidBodyAPI"]
    )
    {
        def Xform "tool_plug_01"
        {
            uniform token simready:mate:domain = "mechanical"
            uniform token simready:mate:role = "Plug"
        }
    }
}
```

## How to comply

1. Publish each assembled part as its own asset, either a `component` or an assembly.
2. Compose each part onto the assembly stage with `references` or `payload`.
3. Apply assembly-local edits as overs on the referenced subtree rather than re-authoring the part.

## Related Requirements

- [connection-targets-resolve](connection-targets-resolve.md)
- [mate-realization](mate-realization.md)
- [compound-body](compound-body.md)
- [assembly-model-hierarchy](assembly-model-hierarchy.md)
- [anchored-asset-paths](../../../core/atomic_asset/requirements/anchored-asset-paths.md)

## For More Information

- [USD Composition Arcs](https://openusd.org/dev/api/_usd__page__value_clips.html)
- [References](https://openusd.org/dev/api/class_usd_references.html)
- [Payloads](https://openusd.org/dev/api/class_usd_payloads.html)
