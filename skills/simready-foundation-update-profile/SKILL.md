---
name: simready-foundation-update-profile
description: "Use for updating SimReady profile versions, feature bundles, docs, and adapter notes."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - profile
    - maintenance
---


# SimReady Update Profile

## Purpose
Use this skill to change an existing profile. Profile versions are immutable, so the normal operation is to add a new version under the existing profile table in `profiles.toml` and update documentation to describe the new version.

Edit an existing profile version in place only for a clear typo, comment correction, markdown-only clarification, or unpublished draft content that the user explicitly says may be changed in place.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/guides.md`
- `nv_core/sr_specs/docs/guides/profiles/profiles.md`
- `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`
- `nv_core/sr_specs/docs/profiles/profiles.toml`
- target profile markdown
- `nv_core/sr_specs/docs/profiles/profiles.md`
- selected feature JSON manifests
- `nv_core/sr_specs/docs/features/feature-dependency-graph.md`

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `profile_name` | Existing profile table name. |
| `base_version` | Existing version to copy from. |
| `new_version` | New semantic version for changed feature bundle. |
| `feature_changes` | Added, removed, or changed exact feature IDs/versions. |
| `reason` | Runtime, validation, asset class, or dependency reason for the update. |
| `adapter_plan` | Required adapters or migration notes from old to new profile. |

## Instructions

Use this checklist when changing the repository:

1. Classify the change.
   - Editorial changes may edit docs or comments in place.
   - Feature bundle changes require a new profile version.
2. Confirm the profile and base version exist in `profiles.toml`.
3. Confirm every new feature ID/version exists as a JSON manifest before referencing it.
4. Add the new profile version by copying the base version feature list and applying the requested changes.
5. Preserve old profile versions exactly unless the user explicitly requested an editorial fix.
6. Update the target profile markdown:
   - add or update the version block
   - document changed feature versions
   - describe migration and adapter implications
   - keep authoring guidance synchronized with the new feature list
7. Update `nv_core/sr_specs/docs/profiles/profiles.md` so the profile summary lists the available versions and current feature bundle accurately.
8. Update adapter docs or create adapter work items when assets are expected to upgrade between profile versions.
9. When the new profile version differs from another source/target profile, identify every feature difference and whether a direct adapter path exists or is intentionally blocked.
10. When validation tooling is available, run `workspace validate` or the equivalent `simready-validate` command against a representative asset.
11. Validate consistency:
   - TOML parses
   - old version still exists
   - new version exists and contains exact feature versions
   - profile markdown agrees with TOML
   - profile index agrees with TOML
   - all feature references resolve to JSON manifests

## Versioning Rules

- Patch: non-contract metadata or documentation fix.
- Minor: backward-compatible added feature or feature-version bump.
- Major: removed feature, incompatible feature-version change, target runtime change, or changed required authored data.

When a profile adopts a new feature version created in the same change, include both the feature update and profile update in the final summary.

## Examples

Example request:

```text
Update prop-robotics-neutral to include a conditional optional feature note.
```

Expected result summary:

```text
changed_files: updated docs, manifests, indexes, validators, or adapters
validation: focused checks for the changed contract
remaining_gaps: downstream feature, profile, adapter, or runtime-test follow-up
```

## Policies

- Treat `profiles.toml` as source of truth.
- Do not silently make a feature optional by changing prose only; machine-readable profile behavior must match.
- Do not update only markdown when validators consume TOML.
- Do not reference feature versions that do not exist.
- Keep old versions available for existing assets.

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
| `profile_name` | Profile changed. |
| `base_version` | Existing version used as source. |
| `new_version` | Version added, or `in-place editorial fix`. |
| `features_added` | Feature IDs/versions added. |
| `features_removed` | Feature IDs removed. |
| `features_changed` | Feature version changes. |
| `docs_changed` | Markdown/index paths changed. |
| `adapter_plan` | Migration/adapters required. |
| `validation` | Checks run and remaining gaps. |
