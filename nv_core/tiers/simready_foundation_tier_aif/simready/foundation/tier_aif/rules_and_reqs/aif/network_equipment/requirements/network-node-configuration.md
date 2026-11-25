# network-node-configuration

| Code | NET.002 |
|---|---|
| Validator | {oav-validator-latest-link}`net-002` |
| Compatibility | {compatibility}`AIF` |
| Tags | {tag}`essential` |

## Summary

This requirement applies only to `network-equipment` in AIF 0.3.

The default prim must author `aif:spec:cpuAllocation`, `aif:spec:memory_MB`, and
`aif:spec:storage_GB` as strictly positive USD `int` values in the Properties
sublayer. Memory uses MB and storage uses GB; no source schema default is set.
CPU allocation has no agreed unit, so this contract checks a positive integer
only. Consumer-specific allocation limits and MB/GB byte-base interpretation
remain review decisions.

When authored, `aif:spec:osImage` must be a non-empty USD `string`. Its identifier
is opaque and preserved verbatim; the offline check does not resolve or execute
an image. The composed values must satisfy the same type/value rules as their
Properties-layer definitions. Allocation and image values configure a node
before simulation starts and imply no runtime support or image availability.

## How to comply

Author the values described above and validate with `AIF-Entity@0.3.0`.
