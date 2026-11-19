---
orphan: true
---

# Feature: `<name>[.<runtime>].<version>`

| Property | Value |
|---|---|
| Feature ID | `<name>[.<runtime>].<version>` |
| Runtime tests | `<suite:test>` |
| Latest ID | `<name>[.<runtime>].<version>` |

The feature ID is the only identity. Do not add separate feature-name,
runtime, or version identity fields. A contract without runtime tests is a FET
only when it is a `source=true` contract with tested derived FETs; otherwise it
is a `CAP`-prefixed capability.

## Description

Describe the runtime promise in concrete asset terms. State what an asset can
do when it satisfies this feature, why that matters, and which asset classes
the feature applies to.

## Dependency Graph

List the exact source FET, other dotted feature IDs, and exact `CAP`-prefixed
capability IDs. Use a Mermaid graph when dependencies exist. Dependencies must
not use wildcards.

## Use Cases

- `<Product or workflow>`

Write `None documented.` when no consumer is known.

## Requirements

### `<name>[.<runtime>].<version>`

#### Capability contracts

List the exact `CAP`-prefixed capabilities this feature requires and link their
requirement pages and validators.

#### Additional runtime requirements

List requirements added by this runtime contract. The capability and direct
requirement lists must match the JSON definition exactly.

## Pipelines

List authoring, conversion, validation, and runtime pipelines that support the
feature. Write `None.` when there are no supported pipelines.

## Samples

Link representative assets. Write `None.` when no sample exists.

## Evaluates

Link every runtime test that proves the behavior. A source-only FET instead
links the tested derived FETs that justify its classification. If derived
evidence is blocked, keep the draft out of the published FET catalog.

## Adapters

Runtime-tested features must list direct adapters that can author or convert
into the contract. Source-only FETs list their tested derived endpoints instead:

| From feature | To feature | Adapter | Status | Notes |
|---|---|---|---|---|
| `<exact dotted ID>` | `<exact dotted ID>` | `<module:function>` | `<Done/Draft/Blocked>` | `<mutation>` |

Do not use wildcard selectors in adapter endpoints.

## Profile selectors

List profiles whose selectors currently resolve to this feature. Note whether
the selector is required or optional. Because wildcard expansion depends on
the installed catalog, record the selector as well as the profile version.
