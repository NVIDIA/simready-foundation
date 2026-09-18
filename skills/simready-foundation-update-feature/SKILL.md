---
name: simready-foundation-update-feature
description: "Use for updating existing SimReady features with new integer feature versions, FET runtime feature names, feature-template.md sections, requirement changes, manifests, docs, conform-skill alignment, and profile notes."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - feature
    - maintenance
---


# SimReady Update Feature

## Purpose
Use this skill when an existing feature changes. The default path is additive: create a new integer feature version and keep the old version available. Edit an existing feature version in place only for clear editorial fixes, broken links, typos, or unpublished draft content that the user explicitly says may be changed in place.

Existing feature markdown should continue to follow `nv_core/sr_specs/docs/guides/features/feature-template.md`. When adding a new version block to an existing feature page, include only what changed from the previous version plus enough context to keep requirements, dependencies, samples, benchmarks, adapters, and validation evidence clear.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/guides.md`
- `nv_core/sr_specs/docs/guides/features/features.md`
- `nv_core/sr_specs/docs/guides/profiles/profiles.md`
- `nv_core/sr_specs/docs/guides/features/feature-template.md`
- current feature markdown
- all JSON manifests for the feature name being changed
- validators and requirement docs named by the affected manifests
- profiles that currently consume the feature/version

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `feature_name` | Existing feature name / manifest `id`, such as `FET_003_PHYSX`. |
| `current_version` | Integer feature version being changed or used as the base. |
| `new_version` | Required integer feature version for behavior, requirement, dependency, or validation changes. |
| `change_type` | Editorial, requirement change, dependency change, tech expansion, validation change, or documentation-only clarification. |
| `reason` | Runtime behavior or validation problem being addressed. |
| `profile_targets` | Profiles that should adopt the new feature version, if any. |
| `conform_skill_impact` | Existing conform skill to update, new conform skill to add, or rationale for no change. |

## Naming And Version Rules

- Feature names must use `FET_###_<RUNTIME>`, such as `FET_003_STANDARD`, `FET_003_PHYSX`, or `FET_003_NEWTON`.
- Feature versions use dotted semantic versions. Do not use bare integer feature versions.
- JSON manifest filenames must match `FET_###_<RUNTIME>-<semantic-version>.json`.
- Feature markdown filenames must match `FET_###_<RUNTIME>.md`.
- Matching conform skill folders use lowercase runtime suffixes, such as `skills/simready-foundation-conform-fet-003-physx/`.
- If a feature page has multiple versions, the latest version section should document only changes from the previous version unless full restatement is needed for clarity.

## Instructions

Use this checklist when changing the repository:

1. Classify the change.
   - Editorial fixes may edit existing markdown/manifests only when they do not change the contract.
   - Contract changes require a new integer feature version.
2. Locate all existing manifests with the same `id`. Confirm the current version exists and choose the next semantic version unless the user or profile migration explicitly names another version.
3. Copy the prior manifest to `FET_###_<RUNTIME>-<new-version>.json` and update only the intended fields: `version`, `display_name`, `dependencies`, `runtime`, and `requirements`.
   - keep dependency versions exact semantic values
   - keep dependencies minimal and avoid circular dependency chains
   - preserve the `runtime` field on physics runtime features (variant-set name to Enable: `PhysX`, `Newton`, or `MuJoCo`); do not add it to `STANDARD`, `ISAAC`, MDL, or packaging features. See the Runtime Variant Field section in `guides/features/features.md`.
   - when a technology-specific feature replaces a base requirement, keep the replacement requirement list explicit
4. Update or add feature markdown for the new version:
   - preserve old version documentation
   - preserve the `feature-template.md` top-level sections: Feature, Description, Dependency Graph, Use Cases, Requirements, Pipelines, Samples, Benchmarks, and Adapters
   - document changes, migration notes, and validation impact
   - link updated requirement docs and validators
   - keep the markdown requirement list synchronized with the new JSON manifest
   - do not leave template placeholders or bracket text in published feature docs
5. Update requirement docs or validators when the feature change adds or changes objective rules.
6. Update `nv_core/sr_specs/docs/shared/features/features.md` when latest-version text, version links, support matrix, or toctree references change.
7. Update `feature-dependency-graph.md` when dependencies change.
8. Update the matching conform skill when the feature contract, requirements, validator behavior, repair policy, or blocked cases change:
   - preserve support for older feature versions when those versions remain published
   - add version-specific guidance when repair behavior differs by version
   - update source-of-truth manifest paths, requirement IDs, validation commands, and summary fields
   - document any new required model/tool capability, such as vision, CAD/source data, runtime simulation, or material identity
   - if no conform skill exists and the updated feature can fail asset validation, create one using the `simready-foundation-conform-fet-###-<runtime>` naming pattern
9. If profiles should consume the new feature, hand off to `simready-foundation-update-profile` and create new profile versions. Do not mutate old profile versions in place.
10. Validate consistency:
   - old manifest remains present
   - new manifest parses and uses the same feature name with the new semantic version
   - all dependency feature names and semantic versions exist
   - all requirement IDs exist or are added in the same change
   - feature markdown keeps the canonical template sections
   - consuming profiles reference exact feature versions
   - the matching conform skill is updated, added, or explicitly documented as not applicable

## Versioning Rules

- In-place editorial fix: typo, broken link, formatting correction, or unpublished draft cleanup that does not change the feature contract.
- New semantic version: any requirement change, dependency change, authored-data change, validation behavior change, runtime behavior change, sample/benchmark evidence change that alters the contract, or profile adoption change that needs a new feature pin.
- Next version: bump the highest existing semantic version (increment the patch or minor component as appropriate for the change).

When uncertain, prefer a new version and call out the uncertainty.

## Feature Expansion Rules

Use feature expansion when a technology-specific rule replaces a base rule. In that case:

- start from the base feature requirement list
- remove the conflicting base requirement
- add the technology-specific requirement
- keep the tech-specific manifest explicit
- update profiles to choose either base or tech feature, not both conflicting rules

## Examples

Example request:

```text
Update an existing SimReady feature and add a new version when the contract changes.
```

Expected result summary:

```text
changed_files: updated docs, manifests, indexes, validators, or adapters
validation: focused checks for the changed contract
remaining_gaps: downstream feature, profile, adapter, or runtime-test follow-up
```

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
| `feature_name` | Feature changed, such as `FET_003_PHYSX`. |
| `old_version` | Integer version used as the base. |
| `new_version` | Integer version added, or `in-place editorial fix`. |
| `manifests_changed` | JSON paths changed. |
| `docs_changed` | Markdown/index paths changed. |
| `requirements_changed` | Requirement IDs added, removed, or preserved. |
| `profiles_to_update` | Profile versions that should adopt the change. |
| `conform_skill` | Conform skill changed, added, or intentionally not changed. |
| `validation` | Checks run and remaining gaps. |
