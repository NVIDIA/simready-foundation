# undefined-prims

| Code     | HI.010 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`hi-010` |
| Compatibility | {compatibility}`hierarchy-usd`  |
| Tags     | {tag}`essential` |

## Summary

Assets must not contain undefined prims (overs)

## Description

USD assets should not contain undefined prims, also known as "overs". An undefined prim is one that exists in the stage but has no actual definition - it only provides property opinions or metadata overrides. These overs can indicate broken references, incomplete asset composition, or cleanup issues from asset processing pipelines. While there are some legitimate use cases for overs (which are whitelisted), their presence generally indicates an issue that should be resolved.

## Why is it required?

- Indicates potential broken references or missing files
- Suggests incomplete or corrupted asset composition
- Can cause unexpected behavior in asset loading and rendering
- May result from failed asset processing or cleanup steps
- Reduces asset clarity and maintainability
- Can lead to confusion about the asset's actual structure

## Examples

```usd
# Valid: All prims are properly defined
#usda 1.0
(
    defaultPrim = "Chair"
)

def Xform "Chair"
{
    def Mesh "Seat"
    {
        # Properly defined mesh with geometry
    }
    
    def Mesh "Backrest"
    {
        # Properly defined mesh with geometry
    }
}

# Invalid: Contains undefined prim (over)
#usda 1.0
(
    defaultPrim = "Chair"
)

def Xform "Chair" (
    references = @./chair_base.usd@  # This reference might be broken
)
{
    over "Seat"  # This over has no definition - NOT ALLOWED
    {
        # Only property overrides, no actual definition
        float3 xformOp:translate = (0, 0.5, 0)
    }
}

# Invalid: Over of non-existent prim
#usda 1.0
(
    defaultPrim = "Chair"
)

def Xform "Chair"
{
    over "NonexistentPrim"  # This prim is not defined anywhere - NOT ALLOWED
    {
        float3 xformOp:translate = (0, 0, 0)
    }
}
```

## Whitelisted Scenarios

Some overs are allowed in specific scenarios:

1. **Broken References**: Overs inside prims with broken references or missing payloads are temporarily allowed, as they may become valid once the reference is fixed

## How to comply

- Ensure all prims have proper definitions (use `def` instead of `over`)
- Fix or remove broken references and payloads
- Clean up unused or orphaned prims from asset processing
- Verify that all referenced files exist and are accessible
- Use proper USD composition to override properties on defined prims
- Test assets in isolation to catch undefined prim issues
- Review asset structure after automated processing tools

## Common Causes

- Broken or missing reference files
- Incomplete asset export from DCC tools
- Failed asset processing or cleanup steps
- Manually edited USD files with incorrect syntax
- Remnants from asset reorganization or refactoring

## For More Information

- [USD Glossary - Over](https://openusd.org/release/glossary.html#usdglossary-over)
- [USD Composition Arcs](https://openusd.org/release/glossary.html#composition-arcs)
- [USD Best Practices - Asset Structure](https://openusd.org/release/tut_usd_best_practices.html)

