---
name: simready-foundation-update-feature
description: "Update a runtime-tested Foundations 2 dotted feature contract while preserving published IDs and coordinating CAP dependencies, adapters, tests, docs, and profiles."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags: [simready, feature, maintenance]
---

# SimReady Update Feature

## Purpose

Change an existing feature. Contract changes create a new exact dotted ID by
changing the version segment; published IDs remain available.

## Prerequisites

Read `AGENTS.md`, the feature/profile/adapter guides, `feature-template.md`, all
definitions/docs for the feature name, selected requirement validators,
adapters, runtime tests, conform skills, and profiles whose selectors match it.

## Inputs

- current exact dotted ID and new exact dotted ID;
- change type and runtime reason;
- CAP dependencies and additional requirement changes;
- dependency, adapter, runtime-test, conform-skill, and profile impact.

## Workflow

1. Classify editorial versus contract-changing work.
2. For a contract change, copy to a new dotted ID; do not edit the published
   definition in place.
3. Keep identity only in `id` (`<name>[.<runtime>].<version>`).
4. Update exact dependencies and avoid cycles.
5. Keep additional requirements, adapters, and runtime tests aligned. A
   testless FET is valid only as a source with tested derived FETs; convert
   other static-only behavior to a `CAP` capability and update new profile
   versions accordingly.
6. Update docs, shared indexes, dependency graphs, validators, adapters, tests,
   and conform skills as required. When a new dotted ID carries a Foundations 1
   `legacy_identity`, add its `(id, version)` -> dotted ID mapping to the owning
   tier's `catalog-map.json`. Regenerate the shared `features.md`/
   `capabilities.md` hubs with
   `nv_core/tiers/_tooling/migrate_foundations2_catalog.py --write-hubs` instead
   of hand-editing them.
7. Resolve all profile wildcards before and after the new feature is added.
   Adding a matching ID may change a profile without editing its TOML.
8. Add new profile versions only when selector/optionality policy changes;
   preserve older versions.
9. Run strict contract and downstream validation.

## Compatibility

Published Foundations 1 split-ID manifests and adapters stay immutable. Use
compatibility aliases during migration; do not treat an alias as a second
feature identity.

## Summary

Report old/new dotted IDs, requirements, CAP/feature dependencies, runtime additions,
adapters/tests, wildcard profiles whose resolution changed, exact profile
versions changed, conform skill impact, validation, and gaps.
