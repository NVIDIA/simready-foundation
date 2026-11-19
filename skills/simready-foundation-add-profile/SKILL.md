---
name: simready-foundation-add-profile
description: "Add a Foundations 2 profile with wildcard feature/capability selectors, optional flags, multi-profile validation notes, docs, and adapter analysis."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags: [simready, profile, specification]
---

# SimReady Add Profile

## Purpose

Add a new named profile in its own tier-owned TOML file. Use
`simready-foundation-update-profile` for a new version of an existing profile.

## Prerequisites

Read `AGENTS.md`, the profile/feature/adapter guides, all installed tier
feature/capability catalogs, related profiles, the shared profile index, and
the feature dependency graph.

## Inputs

- profile name/version, asset class, and consumer/runtime intent;
- feature selectors and capability selectors;
- required/optional policy per selector;
- adapter plan and representative multi-profile validation targets.

## Workflow

1. Confirm the profile name is new.
2. Choose exact or wildcard feature selectors over dotted IDs.
3. Add capability selectors for requirement-only contracts.
4. Store `optional=true` on feature or capability selector entries when
   absence/non-applicability is allowed.
5. Resolve against the complete installed tier catalog. Required unmatched
   selectors are errors; optional unmatched selectors are permitted.
6. Inspect every wildcard match. Required wins if required and optional
   selectors overlap.
7. Create profile docs showing both selectors and the reviewed resolved bundle.
8. Compare with related profiles and document exact adapter paths/blockers.
9. Update the shared profile index.
10. Validate representative assets independently against this profile and any
    other compatible profiles. Do not stamp an exclusive profile on the asset.

## TOML example

```toml
[Robot]
"2" = {features = [
    {selector = "FET004.*", optional = true},
    {selector = "FET004.PhysX.*"},
], capabilities = [
    {selector = "CAP006*", optional = true},
]}
```

## Summary

Report profile/version, feature/capability selectors, optional selectors,
resolved matches, adapter plan, multi-profile evidence, changed files,
validation, and gaps.
