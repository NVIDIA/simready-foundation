# Features Documentation Guide

## Foundations 2 model

Foundations 2 separates static and runtime contracts:

- A **capability** is a reusable static requirement bundle outside a runtime
  feature family. Its canonical ID begins with `CAP`, for example
  `CAP007_NonVisualMaterials.0-2-0`.
- A **feature** belongs to a runtime behavior family. Runtime-tested variants
  include tests, additional runtime requirements, and adapters. A testless
  source remains a FET when tested derived features name it.

A contract without runtime tests is a feature only when it is the source of
tested derived FETs. Move any orphan static contract to a `CAP` definition and
update profiles to select that capability.

Feature identity is one opaque dotted ID:

```text
<name>[.<runtime>].<version>
```

For example:

```text
FET004_Multibody.PhysX.2-0-2
FET004_Multibody.PhysX.2-0-4
FET004_Multibody.Newton.0-0-2
```

The components are:

- **name** — stable FET-prefixed feature name, such as
  `FET004_Multibody`;
- **runtime** — runtime or implementation contract, such as `PhysX`,
  `Newton`, or `AnimGraph`;
- **version** — an opaque version token compared exactly.

Neutral features and capabilities omit the runtime segment:
`FET004_Multibody.0-2-0` and `CAP000_Core.0-2-0`.
Runtime variants retain it, for example `FET004_Multibody.PhysX.0-4-0`.
The parser accepts earlier explicit OpenUSD spellings and serializes them to
the neutral spelling. Consumers still receive `OpenUSD` as the parsed runtime.

A physics runtime segment (`PhysX`, `Newton`, or `MuJoCo`) is also the name of
the USD variant set that `simready-validate` enables on the asset's default prim
before checking that contract's requirements, matching the variant sets defined
by the Runtime Variants capability (`RV.*`). Contracts with a neutral runtime
such as `OpenUSD` are validated against the base composition with every physics
variant disabled.

Do not duplicate identity in separate `name`, `runtime`, or `version` fields.

## Capability definition

Static requirements belong in a capability JSON definition:

```json
{
  "id": "CAP007_NonVisualMaterials.0-2-0",
  "requirements": [
    "NVM.001",
    "NVM.002"
  ]
}
```

Capability IDs and exact dependencies begin with `CAP` and are
`<name>[.<runtime>].<version>`, the same shape as a feature ID. Capability
selectors follow the same rules as feature selectors, so `CAP007_NonVisualMaterials.*`
selects every runtime and version of that capability and `CAP007.*` selects the
whole CAP family.

## Source feature definition

A source remains a FET when tested variants derive from it:

```json
{
  "id": "FET004_Multibody.0-2-0",
  "source": true,
  "requirements": ["JT.001", "JT.002", "RB.MB.001"]
}
```

A source with no direct tests is valid only if at least one tested feature
names it through `source_feature`.

## Feature definition

A runtime-tested feature references its static capabilities and adds the
runtime-specific contract:

```json
{
  "id": "FET004_Multibody.PhysX.2-0-4",
  "source_feature": "FET004_Multibody.0-2-0",
  "additional_requirements": [
    "PHYSX.COL.001",
    "PHYSX.COL.002"
  ],
  "adapters": [
    "neutral_to_physx:collider_neutral_to_prop_physx"
  ],
  "runtime_tests": [
    "FET004:joint-movement"
  ]
}
```

Every runtime-tested Foundations 2 FET definition has non-empty `runtime_tests`,
`additional_requirements`, and `adapters`. `runnable` is derived from runtime
evidence. Testless source FETs do not declare runtime-only fields.

`requirements` remains available for static checks local to one runtime
contract. Reusable static bundles should live in CAP definitions. The resolved
requirement set is the union of feature requirements, additional requirements,
and requirements from resolved capabilities.

## Dependencies

Use `source_feature` for the exact source FET, `dependencies` for other exact
feature dependencies, and `capabilities` for exact static dependencies:

```json
{
  "id": "FET022_DrivenJoints.PhysX.0-0-2",
  "source_feature": "FET022_DrivenJoints.0-2-0",
  "dependencies": ["FET004_Multibody.PhysX.0-4-0"],
  "additional_requirements": ["PHYSX.DRIVE.001"],
  "adapters": ["physx_drives:add_drives"],
  "runtime_tests": ["FET022:joint-motion"]
}
```

Dependencies are exact IDs, never wildcards. Keep both graphs minimal and
acyclic. `source_feature` is classification/provenance, not requirement
inheritance; list the source in `dependencies` only when its whole contract
must also validate. A capability required by a selected feature inherits that
feature's optional state; any required path makes it required.

## Profile selection

Profiles select runtime features and static capabilities independently:

| Selector | Meaning |
|---|---|
| `FET004.*.*` | Every member of FET family 004 across runtimes and versions. |
| `FET004.PhysX.*` | Every PhysX member of FET family 004. |
| `FET004_Multibody.PhysX.2-0-4` | One exact feature. |
| `CAP007*.*.*` | Matching static capability contracts across runtimes and versions. |

For family selectors, `FET004` matches a name beginning `FET004_`, such as
`FET004_Multibody`. See [Profiles](../profiles/profiles.md) for deterministic
expansion, optional selectors, and multi-profile validation. Its
{ref}`Validate 2026.10.0rc1 compatibility <validate-rc1-selectors>`
section lists explicit selector forms for the release validator.

## Conversion rule for existing content

When reviewing an existing feature:

1. Confirm it has executable runtime tests mapped to the exact feature ID.
2. If it does, publish a dotted FET definition with tests and adapters.
3. If it is the source family contract for tested derived FETs, publish it as a
   `source=true` FET and link each derived definition with `source_feature`.
4. Otherwise create a `CAP` definition containing its static requirement
   contract.
5. Replace new-profile FET selectors/pins for that contract with capability
   selectors.
6. Update runtime-tested features that reuse a separate static contract to reference
   the new capability.

## Authoring workflow

1. State the runtime promise and concrete runtime success signal.
2. Identify the source FET and any separate CAP-prefixed static contracts.
3. Choose a stable FET name, runtime, and exact version token.
4. Add only runtime-specific requirements to the feature.
5. Add exact feature and capability dependencies.
6. Add direct adapters and executable runtime tests.
7. Create matching JSON and markdown from
   [feature-template.md](feature-template.md).
8. Update the shared feature/capability indexes and dependency graph.
9. Resolve affected profile selectors against the complete installed catalog.
10. Do not publish a derived FET while runtime evidence is missing; convert it
    to CAP unless it is itself a source for tested derivatives.

## Versioning and compatibility

Published dotted IDs are immutable. Any requirement, dependency, adapter,
runtime-test, or behavior change creates a new version segment. Keep older
definitions available while profiles or evidence reference them.

The version is what an asset claims conformance to, so changing what a published
version asks for changes the meaning of every asset already stamped with it, and
changes it silently: nothing about the asset moved and nothing about the version
moved, only the answer. `nv_core/sr_specs/tests/validate_feature_versions.py`
enforces this in CI by comparing every feature and capability manifest against
the default branch, matched by dotted ID.

### Recording a Necessary Edit

Some edits to a published version genuinely cannot be deferred to a new version -
typically when the version names a requirement no rule implements, which makes
the loader drop every profile that lists the feature. Record such an edit in its
own TOML file under
`nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/known_edits/`,
named after the contract it edits, creating that directory if it does not exist:

```toml
# known_edits/FET006_Materials.MDL.0-1-0.toml
[edit]
feature = "FET006_Materials.MDL.0-1-0"
requirements = ["VM.BIND.002", "VM.MAT.001", "VM.MDL.001", "VM.TEX.001", "VM.TEX.002"]
reason = "VM.MDL.002 is implemented by no rule, so this version unregisters its own feature."
```

All three fields are required. `feature` is the full dotted ID of a feature or
capability, which already carries the version. `requirements` is the complete requirement list the
edit produces, in manifest order, and the manifest is accepted only while it
matches that list exactly. Binding the record to the content rather than to a diff
has two consequences worth knowing:

- The record reads the same before and after the edit merges. It does not need
  removing in a follow-up commit, and it will not start failing CI once it lands.
- It does not pre-authorize a later, different edit to the same version. A second
  edit is a second decision, made by updating `requirements` in the record.

Records stay in the tree once the edit merges, in the same way `known_deletions`
records stay after sample content is removed. A merged record is inert: the
manifest now agrees with the default branch, so the comparison has nothing left
to accept. Deleting a spent record is safe and breaks nothing, but it is not
required and nothing asks for it, so there is no follow-up chore to forget.

Do not reach for a record in place of a version bump.

The reference implementation is `simready.foundation.contracts`.

## Validation checklist

- Capability IDs and selectors begin with `CAP`.
- Testless FETs are sources with tested derivatives; other static-only
  contracts are capabilities.
- Every feature ID uses `name[.runtime].version` and an FET-prefixed name.
- Every runtime feature has tests, additional requirements, and adapters.
- Every requirement and exact dependency exists.
- Capability and feature JSON agree with their documentation.
- Required profile selectors match at least one catalog item.
- Required wins over optional across direct and dependency paths.
- Published feature and capability versions remain unchanged.
