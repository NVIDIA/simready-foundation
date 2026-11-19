# Feature Adapters Documentation Guide

## Purpose

A feature adapter mutates an asset from one exact runtime-tested feature contract to
another. In Foundations 2, adapter endpoints are exact dotted feature IDs:

```text
<name>[.<runtime>].<version>
```

## What is a Feature Adapter?

A **Feature Adapter** is a mechanism that mutates an asset with a particular profile into a new profile. For this to work, there must be a direct path for all the features that are different from profile A to profile B.

### Key Concepts

- **Profile Transformation**: Converts assets between different feature profiles
- **Feature Mutation**: Modifies asset properties to meet new feature requirements
- **Direct Path Requirement**: All feature differences must have defined transformation logic
- **Asset Handler Modules**: Tier-owned modules bundled in the tier wheel and
  exposed through the `simready.feature_adapters` package-entry-point group.

### How Feature Adapters Work

1. **Input Profile**: Asset starts with one set of features (e.g., `FET003_RigidBody.0-2-0`)
2. **Transformation Logic**: Adapter applies specific mutations to the asset
3. **Output Profile**: Asset now conforms to new features (e.g., `FET003_RigidBody.PhysX.0-4-0`)
4. **Validation**: Asset can now be validated against the new feature set

### Standalone Robotics-Prop multiphysics upgrade

The repository includes a fail-closed adapter path for
`Prop-Robotics-Physx@1.0.0` to `Robotics-Prop@3.1.0` with the optional PhysX,
Newton, and MuJoCo feature chains selected. It is usable when the external
`workspace upgrade` / `omni.cip` runtime is unavailable.

The implementation ships as the standalone `simready-multiphysics-upgrade`
distribution in `nv_core/cip_specs/multiphysics_upgrade`. Once it is installed,
use its console script:

```powershell
simready-multiphysics-upgrade --plan `
  path/to/source/simready_physx_usd/sm_asset_01.usda

simready-multiphysics-upgrade `
  --output path/to/staged/robotics_prop_3_1 `
  --report path/to/upgrade_report.json `
  path/to/source/simready_physx_usd/sm_asset_01.usda
```

The historical module path still works from a checkout, and CIP keeps loading
its adapter registrations from `asset_handler_modules`:

```powershell
$env:PYTHONPATH = "nv_core/cip_specs"
python -m asset_handler_modules.multiphysics_upgrade.runner `
  --plan `
  path/to/source/simready_physx_usd/sm_asset_01.usda
```

Profile and feature data comes from an installed
`simready-foundation-tier-core`, from `SIMREADY_TIER_CORE_ROOT`, or from a
repository checkout, in that order.

Pass the root USD path (CIP-style). Package-level copy/promote uses that file's
parent directory. The runner reads the source and target profile TOMLs, verifies
that every selected target feature has an exact adapter edge, validates the
source, applies the adapters to a temporary package, checks neutral/runtime
isolation, validates the target, and promotes the output only after all gates
pass. It never edits the source package. Use `--skip-validation` only when
explicitly accepting an inspection-only run because `simready-validate` cannot
be loaded.

These adapters deliberately refuse ambiguous mesh, collider, mass, joint, or
articulation repairs. Resolve the reported requirement failure with the matching
feature conformance workflow rather than making the adapter invent asset intent.


Wildcard selectors belong to profiles and must never be adapter endpoints.

## Features and capabilities

Features differ from capabilities by carrying the additional requirements,
adapters, and runtime-test evidence needed to produce and prove runtime
behavior. A testless source may remain a FET so derived feature endpoints have
a stable source; other contracts without runtime tests use `CAP` IDs and are
not adapter endpoints. Runtime feature JSON definitions list adapter references:

```json
{
  "id": "FET004_Multibody.PhysX.2-0-4",
  "source_feature": "FET004_Multibody.0-2-0",
  "additional_requirements": ["PHYSX.COL.001"],
  "adapters": ["neutral_to_physx:collider_neutral_to_prop_physx"],
  "runtime_tests": ["FET004:joint-movement"]
}
```

## Adapter metadata

Adapters carry the complete source and target IDs:

```python
@feature_adapter(
    name="multibody_openusd_to_physx",
    input_feature="FET004_Multibody.2-0-2",
    output_feature="FET004_Multibody.PhysX.2-0-4",
)
def modify_stage(input_stage, output_stage):
    ...
```

## Where adapters live

Adapters are tier-owned: the asset handler modules are bundled in the tier wheel
and exposed through the `simready.feature_adapters` package-entry-point group.

The decorator is intentionally Kit-free. It records the feature mapping and
callback in the provider package; derivation consumers load providers lazily from
`simready.feature_adapters`. Do not add filesystem adapter paths to
`config.json` or import adapters from validation entry points.

## Workflow

1. Resolve the source and target profiles against the same installed catalog.
2. Compare required resolved feature IDs.
3. Identify exact runtime-tested feature differences.
4. Confirm an adapter can safely author the target data from existing asset
   intent; do not fabricate geometry or semantics.
5. Implement one direct exact-ID path per mutation.
6. Validate the output against the exact target feature.
7. Run the target feature's runtime tests.
8. Record blocked paths when source data is insufficient.

## Profile adapters

Profiles can also select requirement-only capabilities. When a source/target
profile difference is only a static check over existing data, no mutation path
is needed. When capability conformance requires authored changes not owned by a
runtime-tested feature, use an explicit profile adapter and document the mutation.

## Multi-profile assets

An adapter does not replace an asset's profile. Assets have no exclusive
profile binding. After mutation, validate the output independently against all
profiles requested by the producer or consumer and keep separate evidence for
each result.

## Validation checklist

- Source and target are exact dotted IDs, never wildcards.
- Both feature definitions exist.
- The target feature names the adapter.
- Every target additional requirement is addressed or explicitly blocked.
- Static and runtime validation evidence is preserved.
- Existing published adapter paths remain available.
