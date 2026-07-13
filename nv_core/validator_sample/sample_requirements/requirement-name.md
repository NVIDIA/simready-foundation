# sample-name

| Code     | SAMP.001 |
|----------|-----------|
| Version  | 1.0.0 |
| Validator| {oav-validator-latest-link}`samp-001` |
| Compatibility | {compatibility}`sample` |
| Tags     | {tag}`essential` |

## Summary

The stage must have a default prim named exactly "Foo".

## Description

This sample requirement ensures that the USD stage has a default prim and that its name is "Foo". It is used by the validation sample to illustrate requirement specification and rule implementation.

### Valid USDA

The asset passes SAMP.001 when the stage has a default prim and that prim’s name is "Foo". For example:

```usda
#usda 1.0
def "Foo"
{
}
```

Or with an explicit defaultPrim metadata:

```usda
#usda 1.0
(
    defaultPrim = "Foo"
)
def "Foo"
{
}
```

### Invalid USDA

The asset fails SAMP.001 if:

- **No default prim** — the stage has no default prim set:

```usda
#usda 1.0
def "SomePrim"
{
}
```

- **Default prim has a different name** — the default prim exists but is not named "Foo" (e.g. "Bar", "Root", etc.):

```usda
#usda 1.0
(
    defaultPrim = "Bar"
)
def "Bar"
{
}
```
