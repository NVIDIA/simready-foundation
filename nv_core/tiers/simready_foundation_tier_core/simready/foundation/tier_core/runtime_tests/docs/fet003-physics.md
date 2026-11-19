# FET003 Physics

Rigid-body dynamics: sampled drop, overlap, downhill-motion, and settling checks.

## Overview

This family runs PhysX drops on flat and tilted ground. It checks sampled
bounding-box proximity, allowed overlap/separation, downhill displacement, and
settling against configured limits. These are diagnostic proxies, not measured
collision contacts or a certification of physical realism.

## What a Passing Family Means

The sampled bounding-box and displacement proxies satisfied this run's
configured limits. A pass does not establish exact contact, collider fidelity,
realistic mass/inertia, continuous stability, or behavior in every physics scene.
Review the per-test evidence, tolerances, and recorded stage scale.
Invalid/non-finite configuration or required setup/cleanup/readback failure
leaves incomplete execution, not a completed physics-response verdict.
Required cleanup preserves original errors and cancellation, attempts remaining
safe restoration and retires an uncertain native context. These gates do not
change valid configured response criteria or authorize asset tuning.

## Tests

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [ground_drop](fet003/ground-drop.md)
  - Drops onto a flat floor and checks bounding-box proximity, allowed overlap,
    independently of the settling verdict.
  - FET003_RigidBody and FET003_RigidBody.PhysX (registered versions)
* - [ground_stability](fet003/ground-stability.md)
  - Uses the same flat-floor fixture and checks a complete sampled center/corner
    settling window after proximity and before the configured deadline.
  - FET003_RigidBody and FET003_RigidBody.PhysX (registered versions)
* - [slope_drop](fet003/slope-drop.md)
  - Checks signed downhill displacement and configured bounding-box ramp/floor
    overlap and separation limits on a finite 45-degree inclined plane.
  - FET003_RigidBody and FET003_RigidBody.PhysX (registered versions)
:::

## Relationship to the Feature

This family validates the runtime behavior described by the
[Standard](../../features/FET003_RigidBody.md),
[PhysX](../../features/FET003_RigidBody.PhysX.md) FET003 features using
PhysX. Newton FET003 features are exercised by separate procedures owned by
`simready.foundation.tier_newton.runtime_tests`, not by these Core procedures.
A drop PASS alone does not satisfy the family: required stability and slope
coverage still contribute their own verdicts. Published feature bindings are
unchanged; regenerate plans to discover the enabled stability procedure.

```{toctree}
:maxdepth: 1
:hidden:

ground_drop <fet003/ground-drop>
ground_stability <fet003/ground-stability>
slope_drop <fet003/slope-drop>
```
