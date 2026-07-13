---
name: simready-foundation-add-profile
description: "Use for adding SimReady profile versions with feature bundles, docs, indexes, and validation notes."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - profile
    - specification
---


# SimReady Add Profile

## Purpose
Use this skill to add a brand-new profile under `nv_core/sr_specs/docs/profiles/`. A profile is a named, versioned bundle of exact feature IDs and versions for a target asset class or runtime.

Do not use this skill for a new version of an existing profile. Use `simready-foundation-update-profile` for that.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/guides.md`
- `nv_core/sr_specs/docs/guides/profiles/profiles.md`
- `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`
- `nv_core/sr_specs/docs/profiles/profiles.toml`
- `nv_core/sr_specs/docs/profiles/profiles.md`
- nearby profile markdown files for the same asset class or runtime
- `nv_core/sr_specs/docs/features/feature-dependency-graph.md`

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `profile_name` | New profile name, such as `Prop-Robotics-Neutral`. Use title-case words separated by hyphens. |
| `profile_version` | Initial version, usually `1.0.0` unless the user states otherwise. |
| `target_asset_class` | Prop, robot body, scene, material library, or another concrete class. |
| `target_runtime` | Neutral OpenUSD, PhysX, Isaac, or another runtime target. |
| `feature_bundle` | Exact feature IDs and versions. |
| `profile_markdown_name` | Markdown file path under `docs/profiles/`. |
| `adapter_plan` | Required adapters from related profiles, or `none`. |
| `validation_strategy` | Example assets, validator command, runtime test, or documented gap. |

## Instructions

Use this checklist when changing the repository:

1. Confirm the profile name is new in `profiles.toml`.
2. Choose a feature bundle from exact existing feature JSON manifests. Do not reference a feature version that does not exist.
3. Check feature dependencies. Avoid duplicating dependencies unless existing profiles do so intentionally for clarity.
4. Add a new `[Profile-Name]` table to `profiles.toml` with the initial version and ordered feature list.
5. Create a profile markdown page under `nv_core/sr_specs/docs/profiles/`:
   - purpose and target asset class
   - target runtime/environment
   - exact feature list and versions
   - authoring requirements and known conditional features
   - validation and runtime-test guidance
   - references to feature docs and related profiles
6. Update `nv_core/sr_specs/docs/profiles/profiles.md` with the new profile row and toctree entry if the index uses one.
7. Add feature adapter notes when this profile is expected to be an upgrade or conversion target from another profile.
8. When the new profile differs from an existing related profile, identify every feature difference and whether a direct adapter path exists or is intentionally blocked.
9. When validation tooling is available, run `workspace validate` or the equivalent `simready-validate` command against a representative asset.
10. Validate consistency:
   - TOML parses
   - every referenced feature ID/version exists in `docs/features/*.json`
   - profile markdown and `profiles.toml` feature lists agree
   - `profiles.md` includes the new profile

## Examples

Example request:

```text
Create a new prop-factory-neutral SimReady profile similar to prop-robotics-neutral.
```

Expected result summary:

```text
changed_files: new docs, manifests, indexes, or validation scaffolding
validation: focused static checks and any relevant docs/build checks
remaining_gaps: requirement, validator, adapter, profile, or runtime-test follow-up
```

## Policies

- `profiles.toml` is the machine-readable source of truth.
- Keep the initial feature bundle focused. Do not add features that are merely nice to have.
- A feature may be conditionally applicable only when the profile docs and validator behavior make that condition clear.
- If new features are needed, create them with `simready-foundation-add-feature` before referencing them.
- If the new profile supersedes or branches from another profile, document migration/adapters instead of rewriting the old profile.

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
| `profile_name` | New profile. |
| `profile_version` | Initial version. |
| `profiles_toml` | TOML path changed. |
| `profile_markdown` | Profile docs path. |
| `features` | Exact feature IDs and versions. |
| `adapters` | Adapter plan or none. |
| `validation` | Checks run and remaining gaps. |
| `next_step` | Feature creation, adapter work, runtime test, or review. |
