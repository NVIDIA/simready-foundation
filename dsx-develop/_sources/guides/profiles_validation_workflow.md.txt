# Profiles Validation Workflow

This guide describes how a caller resolves and validates one asset against one
or more Foundations 2 profiles. For authoring details, see
[Profiles](profiles/profiles.md).

## Core model

A profile is a named, immutable version containing selectors over features and
capabilities:

```text
Profile selectors
    -> resolved feature IDs and capability IDs
    -> requirements
    -> static CAP rules and FET runtime tests
    -> one independent result for that profile target
```

Features use one dotted identity:

```text
<name>[.<runtime>].<version>
FET004_Multibody.PhysX.2-0-4
```

Runtime feature variants have tests, additional requirements, and exact adapter
references. A testless source stays a FET when tested variants derive from it;
other static-only contracts use `CAP`-prefixed capability IDs.

## 1. Author a profile version

Create one TOML file per profile under the owning tier's `profiles/` directory.
Each selector entry names its selector and, optionally, `optional = true`:

```toml
[Prop-Robotics]
"4.0.0" = {features = [
    {selector = "FET001.*.*"},
    {selector = "FET004.PhysX.*"},
    {selector = "FET004.AnimGraph.*", optional = true},
], capabilities = [
    {selector = "CAP000_Core.*.*"},
    {selector = "CAP007_NonVisualMaterials.*.*", optional = true},
]}
```

Published profile versions are immutable. Add a new profile version when a
selector, optional flag, or capability selection changes.

## 2. Resolve selectors

Resolve the profile against the complete feature and capability catalogs before
opening the asset:

1. Expand each selector using case-insensitive segment matching.
2. Use explicit runtime and version segments for all-runtime wildcard selections.
   For neutral contracts, use `<name>.<version>`.
3. Let a required match override an optional match for the same item.
4. Sort and deduplicate resolved IDs for deterministic output.
5. Fail an unmatched required selector.
6. Allow an unmatched optional selector and create no obligation for it.
7. Add capabilities required by selected features, propagating optionality;
   required wins over optional.

`FET004.*.*` selects the full `FET004` feature family across runtime and version.
`FET004.PhysX.*` selects only PhysX members. Use an exact versioned selector
when reproducibility requires one contract.

The example uses forms accepted by `simready-validate` 2026.10.0rc1. That release
requires an explicit version or wildcard and does not implement all shorthand
accepted by the Foundation reference resolver. See
{ref}`Validate 2026.10.0rc1 compatibility <validate-rc1-selectors>`
for neutral/runtime selection, migration examples, and profile-registration
failures.

## 3. Validate one asset against multiple profiles

The caller supplies every `(profile, version)` target. Do not infer one
exclusive profile from USD metadata.

```python
from simready.foundation.contracts import ProfileTarget
from simready.foundation.validation import validate_profiles

targets = [
    ProfileTarget("Prop-Robotics", "4.0.0"),
    ProfileTarget("Marketplace-Delivery", "2.0.0"),
]

results = validate_profiles(
    "asset.usda",
    targets,
    profiles=profile_catalog,
    features=feature_catalog,
    capabilities=capability_catalog,
    validate_one=run_validation_plan,
)
```

Each result is independent and keyed by its profile target. A failure against
one target must not suppress validation against the others.

## 4. Interpret required and optional results

- Required features and capabilities contribute mandatory requirements.
- Optional selections contribute requirements only for catalog items that
  resolve.
- Failures contributed only by optional selectors are reported as non-blocking
  evidence. A shared requirement is blocking when any required selector adds it.
- Feature runtime tests execute after its static requirements are satisfied.
- Adapter references describe supported mutation paths and are never expanded
  from profile wildcards.

## Authoring checklist

- Define the target asset behavior and runtime.
- Confirm every required selector matches the intended catalog.
- Review wildcard expansions for accidental future breadth.
- Mark features and capabilities optional only when absence is acceptable.
- Document the resolved contract and runtime evidence strategy.
- Validate a known-good and known-bad asset.
- Exercise at least two profile targets against the same asset.
- Preserve every published profile version.

The reference parser and resolver live in
`nv_core/tiers/simready_foundation_tier_core/simready/foundation/contracts.py`.
