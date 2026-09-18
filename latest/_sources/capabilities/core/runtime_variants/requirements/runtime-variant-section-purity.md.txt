# runtime-variant-section-purity

| Code     | RV.010 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Each physics runtime variant set must isolate all runtime data in its payload: the `Enabled` option may compose the runtime only through the `prepend payload` arc and must author no inline prim overrides, and the `Disabled` option must be empty.

## Description

The physics runtime variant sets (`PhysX`, `Newton`, `MuJoCo`) exist to switch a self-contained runtime payload on or off. All runtime-specific data must live in the runtime payload layer under `runnables/physics/`, not inline in the variant edit on the asset root.

For every physics runtime variant set on the stage `defaultPrim`:

- The `Enabled` option must contain exactly one composition arc, the `prepend payload` required by the payload requirement (`RV.002` / `RV.005` / `RV.008`), and no other opinions: no inline `over`/`def` child prim specs, no authored properties, and no additional references, inherits, specializes, or variant sets.
- The `Disabled` option must be empty: no payload, no child prim specs, and no authored properties.

Inline opinions inside a variant edit compose more strongly than a payload (USD LIVRPS strength order places local variant opinions above payload opinions). An override authored in one runtime's variant section can therefore leak into the composed result of a *different* selected runtime, silently overriding that runtime's payload. Keeping variant sections empty except for the payload arc removes this entire class of cross-runtime leaks.

## Why is it required?

- Prevents variant-authored opinions from outranking and corrupting another runtime's composed payload.
- Guarantees each runnable payload is the single source of truth for its runtime's data.
- Keeps the asset root free of runtime-specific schemas and attributes.
- Makes the variant contract predictable: `Enabled` means exactly "compose this runtime payload."

## Examples

```usd
# Valid: Enabled composes only the payload; Disabled is empty
    variantSet "PhysX" = {
        "Disabled" {
        }
        "Enabled" (
            prepend payload = @../runnables/physics/physx.usd@
        ) {
        }
    }
```

```usd
# Invalid: inline override inside a variant section (leaks across runtimes)
    variantSet "PhysX" = {
        "Disabled" {
            over "Geometry"
            {
                over "collision_mesh"
                {
                    custom token physics:approximation = "convexDecomposition"
                }
            }
        }
        "Enabled" (
            prepend payload = @../runnables/physics/physx.usd@
        ) {
        }
    }
```

## How to comply

- Move every runtime-specific override out of the variant sections and into the runtime payload layer under `runnables/physics/`.
- Keep each `Enabled` option limited to its `prepend payload` arc.
- Keep each `Disabled` option empty.

## Related Requirements

- [physx-runtime-payload](physx-runtime-payload) (RV.002)
- [newton-runtime-payload](newton-runtime-payload) (RV.005)
- [mujoco-runtime-payload](mujoco-runtime-payload) (RV.008)
- [runtime-physics-isolation](runtime-physics-isolation) (RV.011)

## For More Information

- [USD Variant Selection](https://openusd.org/release/glossary.html#usdglossary-variantselection)
- [USD Value Resolution / LIVRPS](https://openusd.org/release/glossary.html#usdglossary-livrpsstrengthordering)
