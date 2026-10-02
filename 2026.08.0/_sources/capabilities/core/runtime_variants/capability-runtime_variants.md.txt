# Runtime Variants

**Capability:** Runtime Variants (RV)

```{include} /capabilities/_includes/badges/runtime_variants.md
```

## Overview

The Runtime Variants capability defines how a neutral SimReady asset exposes
runtime-specific physics behavior through USD variant sets that layer in runtime
payloads. The base (neutral) asset stays unchanged when the runtime variants are
disabled, and each supported runtime (PhysX, Newton, or MuJoCo) is opted into
by selecting its variant, which non-destructively prepends a runtime payload
layer.

## Summary

This capability captures the structural contract for runtime physics variants:
which variant set an asset root must expose for a given runtime, where that
runtime's payload layer lives on disk, and how the variant is documented in
SimReady metadata. Requirements are grouped per runtime so a feature can adopt
only the runtimes it targets, mirroring the neutral/PhysX/Newton/MuJoCo feature
expansion pattern at the asset-composition level.

Each runtime has three requirements: a variant-set rule, a payload-location
rule, and a metadata rule.

| Runtime | Variant set | Payload | Metadata |
|---------|-------------|---------|----------|
| PhysX  | RV.001 | RV.002 | RV.003 |
| Newton | RV.004 | RV.005 | RV.006 |
| MuJoCo | RV.007 | RV.008 | RV.009 |

Two cross-runtime rules govern how the variants compose so a selected runtime
gets a clean, isolated physics stage:

| Rule | Scope |
|------|-------|
| RV.010 | Variant-section purity: `Enabled` composes only its payload arc, `Disabled` is empty. |
| RV.011 | Runtime physics isolation: the composed stage for a selected runtime carries only that runtime + neutral data. See the [runtime physics isolation matrix](runtime-physics-isolation-matrix.md). |

For an authoring-oriented overview of PhysX + Newton + MuJoCo on one asset, see
[Multiple Physics Solvers](../../../guides/multiphysics_solvers.md).

## Requirements

```{toctree}
:maxdepth: 1
:hidden:

requirements
requirements/physx-variant-set
requirements/physx-runtime-payload
requirements/physx-variant-metadata
requirements/newton-variant-set
requirements/newton-runtime-payload
requirements/newton-variant-metadata
requirements/mujoco-variant-set
requirements/mujoco-runtime-payload
requirements/mujoco-variant-metadata
requirements/runtime-variant-section-purity
requirements/runtime-physics-isolation
```

```{toctree}
:maxdepth: 1
:hidden:

Runtime Physics Isolation Matrix <runtime-physics-isolation-matrix>
```

<!-- RUNTIME_VARIANTS_REQUIREMENTS_LIST_END -->
