# interface-match

| Code     | CN.004 |
|----------|--------|
| Validator| ConnectionDeclarationChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The socket and plug `simready:mate:mechanical:interface` tokens must be equal by exact string comparison.

## Description

No aliasing, case folding, or numeric tolerance. A typo on either asset produces an incompatibility between two assets that can each pass `MC.004` individually.

Validators check string equality, not physical fit.

## Why is it required?

- Compatibility is declared per asset and verified per pairing.
- Exact equality is decidable without a rounding policy.

## Examples

```usd
# Invalid: different tokens
# socket: ISO-9409-1-50-4-M6
# plug:   ISO-9409-1-40-4-M6

# Valid: identical tokens
# socket: ISO-9409-1-50-4-M6
# plug:   ISO-9409-1-50-4-M6
```

## How to comply

1. Copy the published designation onto both sites with the same spelling.
2. Do not encode bolt-circle, thread, or interlock dimensions as separate numeric attributes in this version.

## Related Requirements

- [mechanical-interface](../../mates/requirements/mechanical-interface.md)
