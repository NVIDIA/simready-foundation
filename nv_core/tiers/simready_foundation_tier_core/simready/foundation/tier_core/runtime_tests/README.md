# SimReady Foundation Evaluate Kit Suite

This package contains the runtime tests owned by the SimReady Foundation core
tier. `simready-evaluate` discovers the tier's lightweight `simready.tier`
descriptor and imports its lightweight registrations during host discovery.
Executing a registered procedure requires a compatible Kit or Isaac Sim runtime.

The tier wheel ships its validation catalogs and this runtime-test package
together. An installed tier advertises the package through `runtime_tests_path`;
independent test-only distributions use the separate
`simready.evaluate.tests` entry-point group.

## Shipped test families

| Family | Enabled runtime coverage |
|---|---|
| FET001 | Presence, normals, culling, lighting response, and pivot placement |
| FET003 | Core PhysX ground drop, independently assessed sampled ground stability, and slope drop bound to OpenUSD and PhysX rigid-body contracts |
| FET004 | Core PhysX joint movement bound to OpenUSD, PhysX, and deprecated RobotPhysX compatibility contracts |
| FET005 | Parallel-jaw grasp, lift, hold, shake, and release |
| FET006 | Bound-material pixel coverage with requested UsdPreviewSurface, MDL, or OpenPBR render contexts; the same runs are FET009's material-coverage evidence |
| FET008 | Authored object-facing preservation and front-camera response |
| FET010 | Display-color and opacity response under a scoped diagnostic material |
| FET011 | Labelled and stripped semantic-segmentation evidence |
| FET012 | Whether the asset's 3D Gaussian Splat visual renders in RTX |
| FET022 | Driven-joint behavior for PhysX and Isaac features |
| FET028 | Isaac gripper close, lift, shake, and release with sphere and cube payloads |

Newton drop, multibody and driven-joint procedures are owned by the separate
`simready-foundation-tier-newton` package. Its public provider is
`simready.foundation.tier_newton.runtime_tests`; its Python import package is
also `simready.foundation.tier_newton.runtime_tests`. The old flat suite names
remain provider aliases; Python code uses the namespaced imports. This Core package does not
advertise or execute those Newton procedures.

Family labels such as `FET001` are reporting and CLI-filter groups, not feature
manifest IDs. A family can exercise one or more canonical feature variants. For
example, the `FET001` family maps to `FET001_MinimalPlaceableVisual`,
while `FET003` maps to the OpenUSD and PhysX variants of `FET003_RigidBody`
here and to `FET003_RigidBody.Newton` in the Newton tier's suite. There is intentionally
no feature manifest whose ID is only `FET001`.
Foundation 2 contracts use exact dotted IDs, for example
`FET001_MinimalPlaceableVisual.1-0-1` or
`FET003_RigidBody.PhysX.0-2-0`; old `FET_001_STANDARD` names are not the current
contract identity.

Enabled decorators define discoverable procedures and required feature metadata.
For Foundation 2, the selected feature manifest's `runtime_tests` array owns the
exact provider-qualified test bindings; decorator metadata does not override
that manifest. Foundation 1 catalogs use the decorator's feature ownership.
Automation must resolve the selected exact contract and test provider rather
than derive a manifest name from a family label, package directory, documentation
filename, or heading. Discovery alone is not proof that a contract schedules a
procedure or has complete coverage.

See the [Evaluate reference](docs/tests.md) for the per-family and per-test contract,
and [Experimental and disabled tests](docs/experimental.md) for implementations
that are intentionally not advertised as shipped coverage.

## Discovery and local verification

With the tier installed:

```bash
python -m pip install "simready-foundation-tier-core[evaluate]"
simready-evaluate --show-config
simready-evaluate --list-tests
```

From a Foundation source checkout, the checkout supplies both tier catalogs and
runtime tests:

```bash
simready-evaluate --foundations-path <path-to-simready-foundations> --list-tests
simready-evaluate --foundations-path <path-to-simready-foundations> \
  --assets <path-to-asset.usd> --plan-only
```

Use `--tests-path` only for an additional unpublished test package. It is not
required for this suite when the tier is installed or `--foundations-path` is
used.

## Source layout

```text
simready/foundation/tier_core/runtime_tests/
  fet001_visual/ ... fet028_gripper/   enabled and experimental test modules
  articulation_phases/                Core-owned articulation procedures/helpers
  docs/                                authoritative family/test documentation
  README.md                            this package overview
```

Contributor rules, documentation requirements, and focused verification steps
are in [Authoring runtime tests](docs/authoring.md).
