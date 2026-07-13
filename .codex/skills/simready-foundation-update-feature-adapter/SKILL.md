---
name: simready-foundation-update-feature-adapter
description: "Use for updating SimReady feature adapters, USD mutation logic, tests, and source/target metadata."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - adapter
    - maintenance
---


# SimReady Update Feature Adapter

## Purpose
Use this skill when an existing feature adapter no longer matches source/target feature contracts, produces invalid USD, misses a required mutation, or needs new profile-version support.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`
- target adapter file
- source and target feature manifests
- source and target profile versions
- existing adapter tests or validation reports

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `adapter_path` | Existing adapter file. |
| `source_feature` | Input feature ID/version currently supported. |
| `target_feature` | Output feature ID/version currently supported. |
| `bug_or_gap` | Missing mutation, bad metadata, invalid output, non-idempotence, crash, or profile drift. |
| `new_feature_versions` | Updated feature versions if the adapter should support a new path. |
| `test_assets` | Assets or reports that show the problem. |

## Instructions

Use this checklist when changing the repository:

1. Compare adapter metadata with actual source/target manifests and profile versions.
2. Reproduce or inspect the failed upgrade when possible.
3. Determine whether to update the existing adapter or add a new adapter for a new exact version path. Prefer adding a new path when published source/target versions must keep their old behavior.
4. Patch transformation logic narrowly:
   - preserve unrelated data
   - keep output deterministic
   - avoid source-stage mutation
   - save output stage correctly
5. Update metadata only when the supported feature path changes.
6. Update tests or manual validation instructions to cover the corrected path.
7. Update profile migration notes if adapter behavior affects profile upgrades.
8. Confirm every changed feature difference in the profile transformation still has a direct adapter path or documented blocker.
9. Validate source-to-target behavior against the relevant feature/profile requirements when tooling is available.

## Examples

Example request:

```text
Update a SimReady feature adapter for a new exact source and target feature version.
```

Expected result summary:

```text
changed_files: updated docs, manifests, indexes, validators, or adapters
validation: focused checks for the changed contract
remaining_gaps: downstream feature, profile, adapter, or runtime-test follow-up
```

## Policies

- Do not change an adapter to target a different feature version without preserving the old upgrade path when it is still published.
- Prefer adding a new adapter for new feature versions over mutating old behavior.
- Do not add broad catch-all mutation logic that could damage assets outside the adapter contract.
- If a required mutation needs user intent, report a blocked adapter path.

## Limitations

- Do not silently change published contracts; add versions when behavior changes.
- Do not update docs without checking validator, manifest, profile, adapter, and runtime-test impact.
- Do not broaden a change beyond the selected requirement, capability, feature, profile, validator, or adapter.

## Troubleshooting

- Error: the requested change alters a published contract. Solution: create a new version and preserve the old artifact.
- Error: docs and machine-readable manifests diverge. Solution: make the JSON/TOML and markdown agree, then rerun focused checks.
- Error: downstream profile or adapter impact is unclear. Solution: list the affected artifacts before making broad edits.

## Resources

- `assets/openai.yaml` preserves optional UI metadata for clients that read skill display hints. It is not required for the workflow.

## Summary Format

Report:

| Field | Meaning |
|---|---|
| `adapter_path` | Adapter changed. |
| `feature_path` | Input and output feature IDs/versions. |
| `change_type` | Bug fix, new version path, or docs/test update. |
| `mutation_summary` | USD behavior changed. |
| `tests` | Tests/assets run. |
| `profile_followup` | Profile docs or migration notes changed/needed. |
| `validation` | Remaining gaps. |
