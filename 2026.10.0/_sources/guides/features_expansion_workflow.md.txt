# Adding or Expanding a Feature

Use the [Feature Authoring Guide](features/features.md) as the source of truth.
This page summarizes the end-to-end acceptance path.

## Workflow

1. State the runtime behavior and concrete success criteria.
2. Reuse existing capability requirements where possible.
3. Add and validate any genuinely new atomic requirements.
4. Choose one dotted `<name>[.<runtime>].<version>` feature ID.
5. Create matching JSON and markdown without separate identity fields.
6. Declare additional requirements, runtime tests, and exact adapter
   references. A testless source can remain a FET when tested derived features
   name it; otherwise create a `CAP` capability.
7. Add exact dependencies when the contract builds on another feature.
8. Add a new immutable profile version using exact or wildcard selectors.
9. Mark feature or capability selectors optional only when absence is valid.
10. Validate known-good and known-bad assets against every affected profile.

## Feature expansion

A runtime-specific feature may replace a base requirement when its technology
supports a valid pattern that the base validator would reject. The expanded
feature must carry the complete intended requirement set, with the rejected
base rule removed and the runtime-specific rule added.

```json
{
  "id": "FET004_Multibody.PhysX.2-0-4",
  "source_feature": "FET004_Multibody.0-2-0",
  "additional_requirements": ["COL.001"],
  "runtime_tests": ["FET004:joint-movement"],
  "adapters": ["neutral_to_physx:collider_neutral_to_prop_physx"]
}
```

The feature ID is the sole identity. Dependencies and adapter endpoints are
exact dotted IDs; they never use profile wildcards.

## Profile adoption

```toml
[Robot-Body]
"2.0.0" = {features = [
    {selector = "FET004.*", optional = true},
    {selector = "FET004.PhysX.*"},
], capabilities = [
    {selector = "CAP024*"},
]}
```

Resolve selectors against the catalog before validation. Required matches win
over optional matches. Unmatched required selectors fail resolution; unmatched
optional selectors create no obligation.

The caller may validate one asset against several profile targets. Keep each
result separate and do not infer one exclusive profile from asset metadata.

Published feature and profile versions are immutable. Add new IDs and profile
versions rather than rewriting published manifests or TOMLs in place.
