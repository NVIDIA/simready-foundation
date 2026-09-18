---
orphan: true
---

# Feature: `FET_###_<RUNTIME>`

<!--
Copy this template when creating or revising a feature markdown page. Replace
all placeholder values before publishing. The final feature page should have a
matching JSON manifest with the same feature name, semantic version,
dependencies, and requirement IDs. For physics runtime features, the JSON
manifest also carries a `runtime` field naming the USD physics variant set the
validator enables for that feature (`PhysX`, `Newton`, or `MuJoCo`); omit it for
`STANDARD`, `ISAAC`, MDL, and packaging features. See the Runtime Variant Field
section in `guides/features/features.md`.
-->

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_###_<RUNTIME>` |
| Runtime                 | `STANDARD`, `NEWTON`, `PHYSX`, `ISAAC`, or another approved runtime token |
| Proprietary Techs       | `None` for `STANDARD`, or `<Runtime/Technology>` |
| Latest Version          | `0.1.0` |

Use `STANDARD` for OpenUSD features that do not require additional
runtime-specific attributes, schemas, or behavior. Use runtime tokens such as
`NEWTON` or `PHYSX` when the feature depends on runtime-specific schemas,
attributes, validators, or behavior.

## Description

Describe the runtime promise this feature makes. State what an asset can do
when it satisfies the feature, why that behavior matters, and what type of
assets the feature applies to.

Keep this section focused on asset behavior rather than implementation detail.
Use concrete language such as "the asset can be placed," "the asset can be
simulated as a rigid body," or "the robot can be imported with driven joints."

## Dependency Graph

Use a short sentence when there are no dependencies:

This feature has no dependencies and no other features depend on it directly.

Use a Mermaid graph when dependencies exist:

```{mermaid}
flowchart LR
    FET###A["FET_###_STANDARD\n1"]
    FET###B["FET_###_<RUNTIME>\n1"]

    FET###B --> FET###A

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET###B current
    class FET###A other
```

## Use Cases

Products or workflows that consume this feature:

- `<Product or workflow>`
- `<Product or workflow>`

If there are no known consumers yet, write:

- None documented.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

```markdown
- **[`<Profile Name>`](../profiles/<profile-file>.md)** (`v<profile-version>`) - `<Why this profile uses the feature>`
```

If no profile consumes this version yet, write:

- None documented.

#### Feature Dependencies

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | `[<Dependency Display Name>](<relative-path-to-feature-section>)` (`<FEATURE_NAME>@<version>`) |

If this version has no dependencies, write:

None.

#### Requirement List

```markdown
* Capability: [`<Capability Group>/<Capability Name>`](../capabilities/<capability-path>/<capability-page>.md)
    * Requirements:
        * [`<Requirement Display Name>`](../capabilities/<capability-path>/requirements/<requirement-page>.md)
            * `<REQ.ID>` | Version `<version>`
            * [Rule | Implementation](../capabilities/<capability-path>/validation.py)
```

Add one capability block for each capability used by the feature. The IDs listed
here must match the feature JSON manifest exactly after dependency resolution.

</details>

## Pipelines

List the authoring, conversion, validation, or runtime pipelines that support
this feature.

Source file type:

- `.<extension>`
  - Via `<tool, converter, or workflow>`

Validation or runtime pipeline:

- `<Pipeline name>` - `<What it proves or produces>`

If there are no supported pipelines yet, write:

- None.

## Samples

List sample assets or reference materials that demonstrate the feature.

```markdown
- [`<sample asset path>`](../../../../sample_content/<path-to-sample>.usd)
```

If there are no samples yet, write:

- None.

## Benchmarks

List automated runtime tests, benchmark suites, or manual validation evidence
that prove the feature behavior.

```markdown
- Suite: [`<Benchmark Suite Name>`](../guides/benchmark/tests/<suite-file>.md)
  - Tests:
    - [`<test-name>`](../guides/benchmark/tests/<feature-folder>/<test-file>.md)
```

If there are no benchmarks yet, write:

- None.

## Adapters

List direct feature adapters that convert assets into or out of this feature.
Include only adapters that exist or are explicitly planned. Do not list every
possible source or target feature.

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `<SOURCE_FEATURE_NAME>@<version>` | `<TARGET_FEATURE_NAME>@<version>` | `<adapter module or path>` | `<Done/Draft/Planned>` | `<What the adapter changes>` |

If there are no adapters for this feature, write:

None.
