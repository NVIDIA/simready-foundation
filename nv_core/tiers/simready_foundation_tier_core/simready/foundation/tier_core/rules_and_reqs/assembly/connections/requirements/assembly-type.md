# assembly-type

| Code     | CN.008 |
|----------|--------|
| Validator| AssemblyTypeChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The assembly default prim must author `simready:mate:assemblyType` with exactly one value drawn from the closed list `robot`, `pallet_stack`. A missing attribute or an unrecognized token fails.

## Description

`assemblyType` is the classification of the assembly as a whole, in the same spirit as `mechanical:kind` on a mate site (`MC.007`) and `isaac:robotType` on an Isaac robot root. It is a single token, not a list.

The attribute belongs on the **assembly default prim**, not on the `Connections` Scope and not on a connection prim. It classifies the artifact a catalog indexes.

A nested assembly keeps its own `assemblyType` on its root. The outer default prim's token classifies the whole result.

The token names the assembly, not a sub-classification of it. An arm plus gripper is `robot`; that it is specifically a manipulator is already carried by `isaac:robotType`.

### Closed list

| Token | Applies to |
|---|---|
| `robot` | A robot body with one or more tools, grippers, or sensors attached at mechanical mate sites. |
| `pallet_stack` | Interlocking or nesting props aggregated into a stack held by composition. |

The list is closed: an unrecognized token fails rather than warning. A consumer that branches on `assemblyType` must be able to treat an unknown value as an error rather than silently falling through.

The list may grow. Adding a token is a new version of `CAP027_Connections` and an edit to this page, not an asset-side extension. Prefer reusing an existing token over coining a near-duplicate: `pallet_stack` and `pallets` would split the same search.

`assemblyType` is informational with respect to physics. No other requirement branches on it, and realization behavior is decided by `CN.006` from the mate bodies. The two must not become competing switches: a `pallet_stack` may legitimately contain a `jointed` connection, and a `robot` may contain `compound` ones.

## Why is it required?

- Catalog and search tooling needs one tag per assembly to filter on, without parsing the connection graph.
- A closed list keeps the tag decidable for consumers that dispatch on it.
- Requiring the tag rather than accepting its absence means every shipped assembly is classifiable.

## Examples

```usd
# Valid: robot assembly
def Xform "UR10_Robotiq_2F85" (
    kind = "assembly"
    prepend apiSchemas = ["IsaacRobotAPI"]
)
{
    uniform token simready:mate:assemblyType = "robot"
    custom uniform token isaac:robotType = "Manipulator"
}
```

```usd
# Valid: compound prop assembly
def Xform "IndustrialPlasticPallet_Stack_A01" (
    kind = "assembly"
)
{
    uniform token simready:mate:assemblyType = "pallet_stack"
}
```

```usd
# Invalid: attribute omitted
def Xform "IndustrialPlasticPallet_Stack_A01" (
    kind = "assembly"
)
{
}
```

```usd
# Invalid: unrecognized token
def Xform "IndustrialPlasticPallet_Stack_A01" (
    kind = "assembly"
)
{
    uniform token simready:mate:assemblyType = "pallets"
}
```

```usd
# Invalid: authored on the Connections Scope instead of the default prim
def Xform "IndustrialPlasticPallet_Stack_A01" (
    kind = "assembly"
)
{
    def Scope "Connections"
    {
        uniform token simready:mate:assemblyType = "pallet_stack"
    }
}
```

## How to comply

1. Author `uniform token simready:mate:assemblyType` on the assembly default prim. Leave the token that a nested assembly authors on its own root.
2. Use the token from the closed list that names the assembly class.
3. To introduce a genuinely new assembly class, add the token to this page and publish a new `CAP027_Connections` version.

## Related Requirements

- [mechanical-kind](../../mates/requirements/mechanical-kind.md)
- [mate-realization](mate-realization.md)
