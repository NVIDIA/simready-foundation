# Base Articulation

This capability enables articulation root configuration for robots, including
runtime-specific articulation settings where required.

## Summary

An articulation is a single actor comprising a set of links (each of which behaves like a rigid body) connected together with special joints. Every articulation has a tree-like structure - so there can be no loops or breaks.

The Newton tier contributes the Newton-solver articulation-root requirement for
this capability; the base articulation-root requirements are owned by the Core
tier.

# Implementation

{doc}`Full Requirements List <requirements>`

```{toctree}
:maxdepth: 1
:hidden:

requirements
```
