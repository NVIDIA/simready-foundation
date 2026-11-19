---
name: simready-foundation-update-profile
description: "Add a new Foundations 2 profile version with wildcard feature/capability selectors, optionality, resolution review, docs, and adapter notes."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags: [simready, profile, maintenance]
---

# SimReady Update Profile

## Purpose

Change an existing profile by adding a new version in its tier-owned TOML.
Published versions are immutable. Editorial prose fixes may be made in place
only when they do not change selector resolution or validation policy.

## Prerequisites

Read `AGENTS.md`, the profile/feature/adapter guides, target TOML/markdown,
shared indexes/graphs, and complete installed feature/capability catalogs.

## Workflow

1. Copy the base profile to a new version.
2. Apply exact/wildcard feature selector and capability selector changes.
   Capability selectors must begin with `CAP`; move any static-only FET
   selection to the capability list.
3. Apply `optional=true` in TOML for conditional features and capabilities.
4. Resolve old and new versions against the same catalog and diff exact
   matches. A required unmatched selector is an error.
5. Review wildcard breadth and overlapping required/optional selectors;
   required wins.
6. Update profile docs with selectors, reviewed resolved bundle, migration,
   and adapter implications.
7. Update the shared profile index.
8. Identify direct adapters for every required runtime-tested feature difference and
   profile adapters for authored capability differences.
9. Validate representative assets independently against the new profile and
   other compatible profiles. Profile selection is caller-supplied and
   repeatable, not an exclusive asset stamp.
10. Parse TOML and run strict contract/dependency/adapter checks.

## Compatibility

Do not rewrite published Foundations 1 exact-pin versions. Add a Foundations 2
profile version once its consumer can resolve dotted selectors, or use
`simready.foundation.contracts` during transition.

## Summary

Report profile/base/new versions, selector changes, optionality changes,
before/after resolved IDs, adapter plan, docs, multi-profile validation, and
remaining gaps.
