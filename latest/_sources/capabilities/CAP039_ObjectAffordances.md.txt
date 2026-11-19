# Capability: `CAP039_ObjectAffordances`

| Property | Value |
|---|---|
| Exact ID | `CAP039_ObjectAffordances.0-1-0` |
| Runtime | OpenUSD |
| Version token | `0-1-0` |

## Contract

Assets declare interactions through `SemanticsLabelsAPI:affordance` and qualitative
states through `SemanticsLabelsAPI:affordance_state`. AFF.001 checks nine affordance
tokens and AFF.002 checks twelve state tokens. Each taxonomy is opt-in per prim;
prims without applicable interactions do not author empty labels.

| Requirement | Documentation | Implementation |
|---|---|---|
| AFF.001 | [Affordance vocabulary](../rules_and_reqs/physics_bodies/object_affordances/requirements/object-affordance-valid.md) | `ObjectAffordancesCapabilityChecker` |
| AFF.002 | [State vocabulary](../rules_and_reqs/physics_bodies/object_affordances/requirements/object-affordance-state-valid.md) | `ObjectAffordancesCapabilityChecker` |

## Dependencies

`FET011_SemanticLabels.0-2-0` supplies generic semantic-label checks, including
SL.001. Wikidata labels and custom taxonomies may coexist with the two SimReady
taxonomies. AFF.001 and AFF.002 check vocabulary membership only. A state token does
not require its corresponding affordance token to be co-authored.

## Validation

`ObjectAffordancesCapabilityChecker` checks composed values at default time and every
authored time sample. Diagnostics identify the prim, property, invalid token and
sample time. The [capability overview](../rules_and_reqs/physics_bodies/object_affordances/capability-object_affordances.md)
defines the vocabulary and scope.

Callers may select the capability directly or through their own profile. Profile
adoption is deferred while the vocabulary stabilizes; no shipped profile selects it.

## Authoring and scope

Apply the native OpenUSD schema instances and author canonical lowercase tokens for
the intended interaction. Unknown tokens require author intent to correct. No USD
data conversion, adapter or dedicated conform skill is required.

This offline gate does not wire joints or drives, infer actuation thresholds, simulate
interactions, or validate physical state transitions. Those belong to separate
affordance-mechanism contracts. No runtime test is required by this capability.

## Fixtures and samples

Five semantic fixtures in `tests/fixtures/object_affordances` illustrate microwave
oven, light switch, filing cabinet, ball valve and padlock authoring. Validator tests
cover all nine affordance and twelve state tokens, invalid values, time samples,
composition, custom taxonomies and semantic-label coexistence.

These fixtures are not production assets or evidence of full asset-profile conformance.
Promotion of the five actual asset samples requires separate review and approval.
