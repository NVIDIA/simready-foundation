# Capability: `CAP1000_TemplateSmoke.Template`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP1000_TemplateSmoke.Template` |
| Runtime                 | `Template` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0` |

## Description

Example smoke feature for the additive template tier. An asset that satisfies
this capability declares a stage `defaultPrim`, which tooling needs to resolve the
asset root.

Replace this capability when cloning the template into a real tier: choose a real
`FET_###_<RUNTIME>` ID, rename the markdown/JSON files, and point at your own
requirements.

## Dependency Graph

This capability has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this capability:

- Demonstrating that an additive tier can register a feature and validator.
- None documented beyond the template smoke check.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

No profile selects this version.

#### Dependencies

None.

#### Requirement List

* Capability: [Template/Smoke](../rules_and_reqs/template/smoke/capability-smoke.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `TMP.001` | [TMP.001](../rules_and_reqs/template/smoke/requirements/default-prim.md) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies `FET_1000_TEMPLATE` via the template tier plugin.
- Example adapter `standard_to_template_smoke` can ensure `defaultPrim`.

## Samples

- None.

## Evaluates

- None.

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `CAP000_Core.0-1-0` | `FET_1000_TEMPLATE@0.1.0` | `standard_to_template_smoke` | Done | Ensures `defaultPrim` (`TMP.001`). Docstring shows how to import an external package such as `isaacsim.asset.transformer`. |
