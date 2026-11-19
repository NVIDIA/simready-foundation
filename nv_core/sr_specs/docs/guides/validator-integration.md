# Foundations 2 Validator Integration

This document is the handoff contract for the companion `simready-validate`
implementation maintained with SimReady Explorer. The Foundation owns parsing
and resolution semantics; the validator owns USD execution and reporting.

## Release 2026.10 compatibility

The Foundation API below defines the integration contract.
`simready-validate` 2026.10.0rc1 uses a separate resolver that requires a version
or wildcard segment. Its two-segment `<name>.<version>` form selects neutral
versions, except `<name>.*`, which selects all runtimes and versions. Custom
profiles for that release use explicit forms such as
`FET004.*.*`, `FET004.PhysX.*`, and `CAP000_Core.0-2-0`. The broader bare-name
and runtime shorthand described in the loader contract is supported by the
Foundation reference resolver, but is not supported consistently by Validate
rc1. See {ref}`selector compatibility <validate-rc1-selectors>`
for equivalent forms and runtime-scope differences.

Qualify custom selectors against the installed validator as well as the
Foundation resolver. A required selector rejected during profile registration
can skip the profile before asset validation starts. Resolver parity requires
companion-validator changes; explicit profile examples provide a release
compatibility path.

## Foundation API

The core tier exports two dependency-light modules:

- `simready.foundation.contracts`: CAP-prefixed capability definitions, dotted
  feature IDs, wildcard selectors, dependency expansion, and multi-profile
  resolution.
- `simready.foundation.validation`: required/optional requirement merging,
  runtime evidence, and validator execution plans.

The validator should consume `ValidationPlan` rather than reimplement selector
semantics.

Installed tiers expose `capability_contracts_path`, `feature_contracts_path`,
and `profile_contracts_path` for Foundations 2. Prefer those paths when present;
use `features_path` and `profiles_path` only as the Foundations 1 fallback.

The validator loads or builds the `CapabilityDefinition` catalog from its
registered capability/rule inventory and passes that mapping into profile
resolution. Every catalog ID begins with `CAP`; its requirement tuple is the
static contract executed by the validator.

## Loader changes

The validator loader needs these Foundations 2 behaviors:

1. Parse feature `id` as `<name>[.<runtime>].<version>` and reject separate
   `name`, `runtime`, or `version` identity fields.
   Neutral FET and CAP IDs omit `OpenUSD`; accept earlier explicit neutral IDs
   and normalize them to the short spelling. Preserve `OpenUSD` in the parsed
   runtime for base-composition selection.
2. Index features by the complete dotted ID. Do not require the final segment
   to be semantic-version compatible.
   A SemVer-keyed `(id, version)` registry cannot be the Foundations 2 source of
   truth; use a full-ID catalog or a private compatibility projection that is
   never exposed as feature identity.
3. Require non-empty `runtime_tests`, `additional_requirements`, and `adapters`
   on runtime FETs. Permit a testless FET only when `source=true` and at least
   one tested derived FET names it; migrate other static-only definitions to
   `CAP`-prefixed capabilities.
4. Parse capability IDs/dependencies with the `CAP` prefix and reject legacy
   unprefixed capability selectors in Foundations 2 profiles.
5. Merge feature `requirements` and `additional_requirements` with requirements
   from referenced capabilities while retaining `runtime_tests` and `adapters`
   as separate evidence.
6. Load all feature and capability definitions before profiles.
7. Parse profile feature and capability selectors, including wildcard segments
   and `optional = true`.
   Two-segment selectors match a runtime or a neutral version; a bare name or
   family selects every runtime and version. Three-segment selectors match
   runtime and version explicitly.
8. Resolve selectors deterministically against the complete cross-tier catalog.
9. Validate source-feature relationships, but expand only exact feature
   dependencies, feature-to-capability references, capability dependencies,
   and compatibility capability-to-feature edges. `source_feature` classifies
   the family; it does not inherit source requirements. Required wins over
   optional.
10. Fail an unmatched required selector; permit an unmatched optional selector.
11. Derive runtime grouping from `FeatureId.runtime`, not a manifest `runtime`
   field.

The existing Foundations 1 loader remains as a compatibility path for published
split-ID/version manifests and exact-pin TOMLs.

## API changes

Add a multi-target request without breaking the current scalar API:

```python
targets = [
    ProfileTarget("Robot-Body", "2.0.0"),
    ProfileTarget("Marketplace-Delivery", "2.0.0"),
]

results = validate_asset_profiles(asset_path, targets)
```

The returned collection has one independent result per `(profile, version)`.
An asset failing one target must still be evaluated against later targets.

Keep the current single-profile function as a compatibility wrapper that calls
the multi-target API with one target. Foundations 2 validation does not infer a
target from asset metadata when the caller supplies none; clients must make the
selection explicit.

Feature summaries and `get_available_profiles()` should expose the complete
dotted feature ID, resolved selector provenance, and optional state. They should
not synthesize or return a separate feature `version` field.

## CLI changes

Make profile targets repeatable and unambiguous:

```text
simready-validate \
  --profile Robot-Body@2.0.0 \
  --profile Marketplace-Delivery@2.0.0 \
  asset.usd
```

Legacy `--profile NAME --version VERSION` remains accepted for one target.
Reports and exit status aggregate all requested targets, while console output
and JSON preserve separate results.

## Result and stamping changes

- Do not key persisted JSON only by asset path; that overwrites results for the
  same asset/profile combination. Nest results by asset and profile target or
  use a composite key.
- Preserve optional failures as non-blocking evidence on the feature or
  capability that selected them.
- Report FET runtime tests separately from CAP/static requirement failures.
- If validation evidence is stamped into USD, store a map/history keyed by
  profile target. Do not stamp one exclusive `profile` as asset identity.

## Runtime and adapter handoff

`ValidationPlan.feature_evidence` lists runtime tests and adapter references per
resolved feature. `runnable_evidence` remains a compatibility alias. Static
validation may pass before runtime evidence is
available; the result model should distinguish static pass, runtime pass/fail,
and not-run.

Adapters always use exact dotted source and target feature IDs. Wildcards are a
profile authoring convenience and never reach adapter dispatch.

## Cross-repository acceptance tests

- Load the packaged Foundations 2 JSON/TOML fixtures from the core tier tests.
- Reject an orphan testless FET and reject a capability without a `CAP` prefix.
- Confirm `FET004.*` expands across PhysX and Newton.
- Confirm `FET004.PhysX.*` narrows the match.
- Confirm a shared requirement is mandatory when any source is mandatory.
- Confirm a feature-required capability and its dependencies are resolved with
  propagated optionality.
- Confirm a testless source FET is accepted only when a tested derived FET names
  it, without implicitly adding its requirements to the derived contract.
- Load all generated tier projections and resolve every projected profile.
- Confirm optional feature and capability failures are non-blocking.
- Confirm one asset produces two independently addressable profile results.
- Confirm Foundations 1 feature/profile files still load unchanged.

## SimReady Explorer implementation map

The companion `simready-explorer` repository contains a
partial Foundations 2 implementation. The remaining integration should be
made in these validator surfaces:

- `source/libraries/validate/src/validate/impl/tiers.py`: prefer each tier's
  `capability_contracts_path`, `feature_contracts_path`, and
  `profile_contracts_path`, falling back to the Foundations 1 paths only when
  the new descriptors are absent.
- `source/libraries/validate/src/validate/impl/loader.py`: load the complete CAP
  and FET catalogs before registration; defer source-FET validation until that
  catalog is complete. In particular, `_load_and_register_feature()` must not
  reject every dotted FET with an empty `runtime_tests` list. It may accept one
  only when `source=true` and at least one runtime-tested FET declares that
  exact ID in `source_feature`.
- `source/libraries/validate/src/validate/contracts.py`: keep selector and
  dependency semantics synchronized with the Foundation-owned resolver. Do not
  expand `source_feature` as a dependency.
- `source/libraries/validate/src/validate/api.py`: use the resolved profile
  target as the result/stamp key and preserve an independent result for every
  target in a multi-profile request.
- `source/libraries/validate/tests/test_contracts.py`, `test_loader.py`, and
  `test_api.py`: import the Foundation fixtures and add the source-FET case to
  the existing dotted-ID, wildcard, and multi-profile coverage.
- `electron_client/backend/source/feature_docs.py`: feature-document discovery
  must match dotted filenames (`FET*.json`) and capability files
  (`CAP*.json`); the legacy `FET_*.json` glob alone is not a complete
  Foundations 2 catalog.

This repository does not write into the Explorer checkout. The generated tier
catalogs and the fixtures under the core tier tests are the cross-repository
handoff inputs.
