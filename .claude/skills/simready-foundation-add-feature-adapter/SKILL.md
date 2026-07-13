---
name: simready-foundation-add-feature-adapter
description: "Use for adding SimReady feature adapters that mutate USD assets between exact feature or profile versions."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - adapter
    - usd
---


# SimReady Add Feature Adapter

## Purpose
Use this skill to add a direct asset mutation path between feature versions or profile feature bundles. Feature adapters live under `nv_core/cip_specs/asset_handler_modules/` and modify an output USD stage so an asset can move from an input feature/profile contract to a target one.

Use this after feature/profile differences are known. If no USD mutation is needed, document that no adapter is required.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`
- source and target feature manifests
- source and target profile versions, if this is profile-driven
- existing adapters in the relevant asset handler module

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `input_feature_id` | Source feature ID. |
| `input_feature_version` | Source feature version. |
| `output_feature_id` | Target feature ID. |
| `output_feature_version` | Target feature version. |
| `profile_path` | Optional source/target profile upgrade path. |
| `mutation` | Exact USD data changes required. |
| `module_path` | Asset handler module directory. |
| `test_assets` | Assets that pass input and should pass output after mutation. |

## Instructions

Use this checklist when changing the repository:

1. Compare source and target manifests. Identify only the requirements that differ.
2. Decide whether a direct adapter is necessary. For profile transformations, every feature difference must have a direct adapter path or a documented blocker. If target requirements are documentation-only or already satisfied by source assets, document no-op behavior.
3. Choose or create the asset handler module path.
4. Add a Python adapter file with `@feature_adapter` metadata using exact feature IDs and versions.
5. Implement `modify_stage(input_stage, output_stage)`:
   - read source stage only when needed
   - mutate output stage deterministically
   - preserve unrelated authored data
   - save output stage when complete
6. Use native USD schemas and existing helper patterns from neighboring adapters.
7. Add focused tests or manual validation notes:
   - input validates against source feature/profile
   - output validates against target feature/profile
   - mutation is idempotent or safely repeatable where practical
8. Update adapter indexes, imports, or registration files if the repo requires them.
9. If the adapter is needed for a new profile version, update the profile docs or migration notes.

## Examples

Example request:

```text
Add a feature adapter that mutates assets from one exact SimReady feature/profile version to another.
```

Expected result summary:

```text
changed_files: new docs, manifests, indexes, or validation scaffolding
validation: focused static checks and any relevant docs/build checks
remaining_gaps: requirement, validator, adapter, profile, or runtime-test follow-up
```

## Policies

- Do not use adapters to hide invalid source assets; adapters should bridge defined feature differences.
- Do not mutate source stages in place.
- Do not invent property values that need user intent or prediction unless the adapter contract explicitly defines defaults.
- Keep profile upgrade paths direct: every changed feature needs a clear adapter path or a documented blocker.

## Limitations

- Do not mutate published feature or profile versions in place.
- Do not invent requirement IDs or validator behavior when the contract is ambiguous; record the question.
- Do not skip index, manifest, validation, or downstream follow-up notes.

## Troubleshooting

- Error: the new concept overlaps an existing artifact. Solution: update the existing capability, requirement, feature, profile, or adapter instead.
- Error: names or IDs conflict. Solution: re-check naming conventions and nearby indexes before editing further.
- Error: validation strategy is unclear. Solution: document deferred validation and the exact follow-up skill.

## Resources

- `assets/openai.yaml` preserves optional UI metadata for clients that read skill display hints. It is not required for the workflow.

## Summary Format

Report:

| Field | Meaning |
|---|---|
| `adapter_name` | Adapter identifier. |
| `adapter_path` | Python file path. |
| `input_feature` | Source feature ID/version. |
| `output_feature` | Target feature ID/version. |
| `mutation_summary` | USD opinions changed. |
| `profile_upgrade` | Profile path supported, if any. |
| `validation` | Tests/assets run and remaining gaps. |
