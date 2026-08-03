# test-prim-exists

| Code     | EX.003 |
|----------|--------|
| Tags     | {tag}`essential` |

## Summary

The default prim must have a child prim named `TestBlob`.

## Description

This example requirement shows the simplest generated-requirement
validator pattern: check for a specific prim and report the generated
requirement enum when it is absent. The validator registers and reports
`cap.ExampleRequirements.EX_003`.

## Example

```usd
# Valid: TestBlob is a direct child of the default prim
def Xform "Asset"
{
    def Xform "TestBlob"
    {
    }
}
```

## How to comply

Author a prim named `TestBlob` directly below the stage default prim.
