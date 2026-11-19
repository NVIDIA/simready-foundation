---
name: simready-foundation-add-feature
description: "Add a runtime-tested Foundations 2 SimReady feature with a dotted name.runtime.version ID, CAP dependencies, requirements, tests, adapters, indexes, and profile follow-up."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags: [simready, feature, specification]
---

# SimReady Add Feature

## Purpose

Add a brand-new feature under its owning tier. Use
`simready-foundation-update-feature` when an existing feature contract changes.

## Prerequisites

Read `AGENTS.md`, the feature/profile/adapter guides, `feature-template.md`, the
shared feature index and dependency graph, neighboring feature definitions,
and every selected requirement/validator.

## Inputs

- `id`: exact `<name>[.<runtime>].<version>` ID, for example
  `FET004_Multibody.PhysX.2-0-4`.
- `runtime_promise`: concrete asset behavior.
- `capabilities`: exact `CAP`-prefixed static contracts.
- `requirements`: static requirement IDs local to this runtime feature.
- `dependencies`: exact dotted feature IDs; never wildcards.
- `additional_requirements`: requirements added by the runtime implementation.
- `adapters`: exact adapter modules/entry points.
- `runtime_tests`: executable evaluation evidence.
- `profile_targets`: profile selectors/versions expected to adopt the feature.

## Contract rules

- Feature identity exists only in `id`; do not add separate identity fields
  named `name`, `runtime`, or `version`.
- The ID has two segments for neutral contracts or three for runtime variants.
- Published IDs are immutable.
- Every runtime feature must declare non-empty `additional_requirements`,
  `adapters`, and `runtime_tests`.
- A testless FET must be `source=true` and have tested derived FETs; every
  other static contract is a `CAP` capability.
- Dependencies and adapter endpoints are exact IDs.
- Profile wildcards are selectors and are not feature or adapter identities.

## Workflow

1. Define the runtime promise before selecting requirements.
2. Confirm the feature name/runtime/version does not already exist.
3. Prefer existing CAP-prefixed capability requirements and validators.
4. Create strict JSON using the dotted ID and create matching markdown from
   `feature-template.md`.
5. For a runtime feature, add additional requirements, adapters, runtime tests,
   and a conform skill. For a source FET, add `source=true` and confirm tested
   derived FETs name it. Otherwise create/update a capability instead.
6. Keep docs and JSON requirement/dependency/adapter/test lists synchronized.
7. Update the shared feature index and dependency graph. When the new contract
   carries a Foundations 1 `legacy_identity`, add its `(id, version)` -> dotted
   ID mapping to the owning tier's `catalog-map.json`. Regenerate the shared
   `features.md`/`capabilities.md` hubs with
   `nv_core/tiers/_tooling/migrate_foundations2_catalog.py --write-hubs` instead
   of hand-editing them.
8. Resolve every affected profile selector against the complete installed
   catalog and review wildcard matches.
9. Use add/update-profile for profile adoption; never mutate a published
   profile version.
10. Run strict contract, JSON, requirement, dependency, docs, adapter, and
    runtime checks available in the workspace.

## Compatibility

Do not rewrite published Foundations 1 manifests in place. New Foundations 2
content uses dotted IDs. If a legacy loader is still required, expose an alias
or compatibility view without making that alias a second identity.

## Summary

Report the dotted ID, owning tier, requirements, additional requirements,
dependencies, adapters, runtime tests, affected profile selectors, changed
files, validation run, and remaining blockers.
