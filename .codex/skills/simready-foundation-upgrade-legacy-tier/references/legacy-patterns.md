# Legacy Tier Patterns and Migration Decisions

Read this reference in upgrade mode or whenever inventory finds old FET IDs, split ID/version records, AIF/DSX code, legacy adapter endpoints, or stamped asset metadata.

## Pattern Map

| Legacy evidence | Interpretation | Foundations 2 action |
|---|---|---|
| `FET001_BASE_NEUTRAL`, `FET003_BASE_PHYSX`, or similar compact IDs | Pre-underscore feature identity; runtime may be encoded in the suffix | Map the exact manifest/version pair using runtime-test evidence. Do not mechanically derive the target ID. |
| `FET_004_PHYSX` plus a separate semantic version | Foundations 1 split identity | Map the exact pair to one dotted ID and preserve the original version text in `catalog-map.json`. |
| Requirements but no runtime test | Static validation bundle | Project to a `CAP` identity unless it qualifies as a source FET. |
| Testless base/standard contract named by tested derived contracts | Provenance/source contract | Keep as a FET only with `source=true` and verified tested derivatives. |
| Feature dependency dictionary/list | Relationship whose target kind is not yet known | Classify every target first, then translate to FET dependencies or CAP selections. |
| Profile feature pin | Published profile obligation | Preserve the old profile; generate a new exact or intentional wildcard selector in a new profile version/projection. |
| Runtime-test TOML/Python registration | Runtime evidence | Bind the executable test to the exact dotted FET ID and retain a legacy alias if old runners still emit it. |
| Adapter source/target pair | Mutation route | Add exact dotted endpoints; retain published legacy routes. Wildcards are not adapter endpoints. |
| Feature data in USD metadata, reports, or workspace cache | Persisted compatibility surface | Add a reader/migration path or regenerate derived state. Do not edit caches as authoring source. |
| `source_feature` | Provenance/classification edge | Do not inherit requirements. Add a dependency separately when the source must validate. |

## Identity Rules

- A Foundations 2 FET has one public identity field: `id`.
- A FET ID has exactly `<name>[.<runtime>].<version>`.
- The version token is opaque. Preserve leading zeroes and punctuation allowed by the active parser.
- Do not duplicate `name`, `runtime`, or `version` beside the dotted ID in a new manifest.
- A CAP is a static reusable requirement contract and must use a `CAP` prefix.
- Allocate IDs from the owning tier's documented range; do not assume another tier's unused-looking number is available.
- Use the catalog map to preserve lossless legacy identity, not the new public ID format.

## Classification Evidence

Runtime evidence must identify all of the following:

1. the exact legacy contract/version it proves;
2. the named runtime;
3. an executable test entry point or evaluation registration;
4. success/failure evidence attributable to that exact contract;
5. additional static requirements and exact adapter routes required by the runnable contract.

Documentation that calls something “runnable,” a runtime-like suffix, or validator-only code is not runtime-test evidence.

## AIF/DSX Guidance

Inventory these domains explicitly when present:

- electrical authored data and connectivity;
- thermal authored data and material/ boundary properties;
- network nodes, ports, and connection points;
- domain validators and requirement registries;
- solvers, simulators, runner scripts, and result schemas;
- profiles or presets consumed by downstream applications.

Apply the normal CAP/FET test:

- authored-data shape, naming, schema, units, connectivity, and static consistency belong in CAPs;
- behavioral simulation promises belong in FETs only when an exact runtime runner proves them;
- a validator is not a runtime test merely because it executes Python;
- preserve stable requirement IDs when semantics are unchanged;
- make Core or other tier dependencies explicit and verify load order against the complete catalog.

If an AIF runner exists but cannot be tied to an exact published contract, record the item as `runtime-evidence-unresolved`; do not create a speculative FET.

## Tier Definition and Expansion Checklist

For a new or expanded tier, establish:

- unique filesystem slug, Python package, distribution name, and entry-point key;
- owner, purpose, support state, and release/version policy;
- CAP, FET, profile, and requirement namespaces/ranges;
- allowed upstream tiers and cycle policy;
- capability docs, stable requirement IDs, and validator registration;
- runtime-test and adapter ownership for each runnable FET;
- source versus generated catalog roots;
- validator/plugin and SimReady tier discovery entry points;
- installed-wheel tests and representative sample content;
- docs aggregation and workspace/build registration.

When expanding, never reuse an existing identity for changed behavior. Add new immutable contracts and profile versions.

## Compatibility Checklist

Before removing any compatibility alias or reader, search for:

- feature IDs and profile versions in Python, JSON, TOML, Markdown, USD/USDA, logs, and reports;
- adapter registry keys and upgrade graph edges;
- evaluation/test family names and emitted result IDs;
- asset stamps and custom metadata;
- workspace caches and generated plans;
- CLI flags, Python imports, package entry points, and docs examples;
- consumer repositories and installed validator versions.

Generated artifacts may be deleted/regenerated by their owning workflow, but published source and persisted asset metadata require an explicit compatibility decision.
