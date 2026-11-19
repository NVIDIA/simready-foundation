---
name: simready-foundation-upgrade-legacy-tier
description: Define a new SimReady Foundation tier, expand an existing tier, or upgrade a legacy Foundations 1, pre-underscore, AIF, DSX, or third-party tier to the Foundations 2 CAP/FET/profile contract. Use for tier scaffolding and registration, ownership and ID allocation, static-feature-to-capability realignment, dotted runtime FET migration, profile projection, adapter and runtime-test remapping, validator integration, and compatibility-preserving legacy catalog upgrades.
---

# SimReady Foundation Tier Definition and Upgrade

Use this skill for tier-level work. It supports three modes:

1. **Define** creates and registers a new tier.
2. **Expand** adds capabilities, runtime features, profiles, validators, tests, or adapters to an existing tier without changing published contracts.
3. **Upgrade** projects an older tier or codebase, including AIF/DSX-style catalogs, into Foundations 2 while preserving compatibility inputs.

Do not use this skill for a single isolated requirement, feature, profile, validator, or adapter when the tier structure and catalog model are already correct. Use the corresponding `simready-foundation-add-*` or `simready-foundation-update-*` skill instead.

## Read First

Read the repository's `AGENTS.md` and any nested `AGENTS.md` that governs each target. Then inspect:

- the tier discovery and packaging guide;
- the feature, profile, feature-adapter, and runtime-testing guides;
- the active Foundations 2 parser/resolver and tier descriptor;
- the repository's catalog migration/generation tooling, when present;
- one maintained peer tier and its tests;
- `references/legacy-patterns.md` for upgrade mode or any AIF/DSX/legacy identifiers.

Treat current code and tests as evidence of integration shape, not permission to copy stale identity semantics.

## Establish Inputs and Mode

Before editing, record:

- mode: `define`, `expand`, or `upgrade`;
- tier display name, filesystem/package slug, Python module, and entry-point name;
- owner, purpose, dependency boundary, and allocated CAP/FET/requirement ID ranges;
- authoritative source roots and generated output roots;
- required upstream tiers and whether cross-tier references are permitted;
- runtime-test, adapter, validator, documentation, sample-content, and consumer roots;
- compatibility promises for published IDs, profiles, stamps, caches, and APIs;
- validator checkout/version used for acceptance.

Do not guess ownership, identity ranges, cross-tier dependency policy, or which runtime proves behavior. Stop and request a decision if repository evidence cannot resolve one of these.

## Inventory Before Editing

For `expand` and `upgrade`, run the bundled read-only inventory helper over every relevant source root:

```text
python skills/simready-foundation-upgrade-legacy-tier/assets/scripts/inventory_legacy_tier.py <root> [<root> ...] --output <report.json>
```

The helper inventories likely manifests, profiles, validators, runtime tests, adapters, docs, stamps, caches, and AIF/DSX references. It does not rewrite scanned content. Review the report and follow references outside the tier package; hidden consumers are part of the migration surface.

For `define`, inventory peer tiers and shared registries instead. Confirm that proposed package, entry-point, requirement, CAP, and FET identities do not collide.

## Define a New Tier

1. Copy the maintained tier architecture, not its domain content. Create the package, README, build metadata, license headers, tests, and Python namespace required by the repository.
2. Register both discovery surfaces used by the current stack:
   - validator/plugin discovery for requirements and executable validators;
   - SimReady tier discovery for capability, feature, and profile catalogs.
3. Make the tier descriptor dependency-light. It may compute paths, but must not import USD or validators merely to expose catalog locations.
4. Create source and generated directories according to repository policy. If the repository uses a generator, generated Foundations 2 catalogs must never be hand-edited.
5. Document ID ownership, upstream tier dependencies, public entry points, authoring source, generated output, and release process.
6. Add the smallest meaningful vertical slice: at least one documented capability or runtime feature, its requirements/tests as applicable, and a profile or resolver test that proves discovery. Do not create placeholder FETs without runtime evidence.
7. Add the tier to workspace/build/docs/test registries and verify installed-wheel discovery, not only source-tree imports.

Use `simready-foundation-add-capability`, `simready-foundation-add-requirement`, `simready-foundation-add-validator`, `simready-foundation-add-feature`, and `simready-foundation-add-profile` for the detailed contract files after the tier boundary exists.

## Expand an Existing Tier

1. Preserve every published requirement ID, CAP/FET ID, feature version, profile version, and adapter route.
2. Allocate new identities within the tier's documented range. Resolve collisions before authoring content.
3. Add new static contracts as capabilities. Add a FET only when it represents a runtime-tested contract, or when it is a declared source FET referenced by tested derived FETs.
4. Create new immutable feature/profile versions for contract changes. Do not change an older selector bundle in place.
5. Update generators and source inputs, then regenerate projections. Never patch generated catalog files directly.
6. Add or update validators, runtime tests, adapters, docs, indexes, skills, and consumer integration in the same change when their contracts are affected.
7. Test the complete installed catalog so cross-tier references resolve after all tiers are loaded.

## Upgrade a Legacy Tier or Codebase

### 1. Freeze compatibility input

Identify published manifests, profile TOMLs, requirement IDs, adapter paths, runtime-test registrations, API symbols, and asset stamps. Treat them as immutable compatibility input unless the user explicitly authorizes a breaking release.

### 2. Build an explicit catalog map

Create a deterministic, reviewable mapping for every exact legacy `(id, version)` pair. Record:

- legacy ID and version without normalization loss;
- target kind: `capability` or `feature`;
- exact target ID;
- classification evidence;
- translated dependencies;
- profile selectors that consume it;
- runtime-test and adapter registrations;
- compatibility aliases or readers still required.

Never migrate by global string replacement. Legacy IDs are reused across manifests, code, stamps, and caches with different semantics.

### 3. Classify CAP versus FET

Apply this decision order:

1. A contract with an exact executable runtime-test mapping becomes a dotted FET.
2. A testless contract may remain a FET only when `source=true` and at least one tested derived FET names it as `source_feature`.
3. Every other testless/static contract becomes a `CAP`-prefixed capability.

A runtime FET's dotted ID is its sole identity and has exactly `<name>[.<runtime>].<version>`. Its contract includes non-empty runtime tests, additional requirements, and adapters. Preserve the version token as opaque text, including leading zeroes.

`source_feature` records provenance only. It does not inherit requirements. Add `dependencies` when the source contract must also validate.

### 4. Translate relationships by target kind

- FET-to-FET edges become feature dependencies.
- FET-to-CAP edges become capability selections/dependencies.
- CAP-to-CAP edges remain capability dependencies.
- A legacy static bundle referenced by a runtime contract does not become a FET merely because of that reference.

Reject dangling, cyclic, or ambiguous edges. Resolve selectors against the complete available multi-tier catalog, not a tier in isolation.

### 5. Project profiles

Generate per-profile Foundations 2 selectors. Feature selectors may have one to three segments, with omitted trailing segments meaning `*`. Capability and feature selectors may be optional.

Verify:

- deterministic sorting and deduplication;
- required selection wins over the same optional selection;
- unmatched required selectors fail;
- unmatched optional selectors create no validation obligation;
- the same asset can be validated independently against multiple caller-supplied profiles.

### 6. Update executable integration

- Register runtime tests against exact dotted FET IDs. Preserve legacy aliases during the compatibility window.
- Add exact new adapter endpoints while keeping published legacy routes. Do not use wildcard adapter endpoints.
- Update tier descriptors/loaders to expose Foundations 2 capability, feature, and profile contract roots while preserving legacy fields required by old validators.
- Update validators to load the complete catalog before resolving profiles. If an upstream registry requires semantic versions, keep any conversion private; never expose it as the public opaque version identity.
- Regenerate or compatibly read old stamps/caches. Do not edit caches as if they were authoring source.

## AIF and Other Domain Code

Do not infer feature status from domain names such as electrical, thermal, networks, or connection points. Static authored-data rules and validators are capabilities. Create a FET only when a named runtime and executable behavioral test prove a runtime promise. Preserve stable AIF requirement IDs when their semantics remain valid, and document any cross-tier dependency on Core or another owner.

Read `references/legacy-patterns.md` for examples and migration traps.

## Validation Gates

Run the narrowest relevant checks after each gate and the full acceptance set before handoff:

1. Python, JSON, TOML, and package metadata parse.
2. Tier entry points resolve from an installed wheel in Python 3.12.
3. Requirement and validator registration has no duplicates or missing IDs.
4. Every exact CAP/FET/dependency/profile reference resolves in the complete catalog.
5. Runtime FETs have tests, additional requirements, and adapters; source FETs have tested derived references; other testless contracts are CAPs.
6. Profile wildcard and optional semantics pass focused resolver tests.
7. Catalog generation is deterministic and idempotent; a second run has no diff.
8. Published legacy inputs and compatibility routes still pass legacy tests.
9. The updated validator discovers the tier and validates representative sample content against at least two profiles when the tier exposes them.
10. Docs, indexes, maps, and skill guidance describe the same contract as code.

Use `simready-foundation-validate-foundation-change` for the final cross-surface audit.

## Handoff

Report:

- mode and tier identity;
- source, generated, and compatibility roots;
- CAP/FET/profile counts before and after;
- exact legacy-to-new map location for upgrades;
- registrations, validators, runtime tests, adapters, and consumers changed;
- commands and sample assets used for validation;
- preserved compatibility surfaces;
- unresolved ownership, runtime-evidence, or release blockers.

Do not claim completion if the generated catalog is not reproducible, an exact mapping remains ambiguous, or only source-tree discovery was tested.
