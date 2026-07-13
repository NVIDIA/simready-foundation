---
name: simready-foundation-add-feature
description: "Use for adding SimReady feature docs, manifests, requirement mappings, validation strategy, and index entries."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - feature
    - specification
---


# SimReady Add Feature

## Purpose
Use this skill to add a brand-new SimReady feature under `nv_core/sr_specs/docs/features/`. A feature is a versioned runtime/use-case contract made from exact requirement IDs and optional feature dependencies.

Do not use this skill for a new version of an existing feature. Use `simready-foundation-update-feature` for that.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/guides.md`
- `nv_core/sr_specs/docs/guides/features/features.md`
- `nv_core/sr_specs/docs/guides/naming_conventions.md`
- `nv_core/sr_specs/docs/features/features.md`
- existing neighboring feature markdown and JSON files for the same domain

If the feature will be added to a profile, also read `nv_core/sr_specs/docs/guides/profiles/profiles.md` and the target profile markdown/TOML entries.

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `feature_number` | Numeric ID such as `025`. If absent, inspect existing feature IDs and propose the next appropriate number. |
| `feature_id` | Exact ID such as `FET025_BASE_NEUTRAL`; must match the variant pattern used by existing JSON manifests. |
| `version` | Initial semantic version, usually `0.1.0` unless the user states otherwise. |
| `display_name` | Human-readable feature name. |
| `runtime_promise` | Concrete asset behavior the feature guarantees. |
| `requirements` | Existing requirement IDs or new requirement docs/validators needed by the feature. |
| `dependencies` | Exact feature IDs and versions this feature depends on. |
| `profile_targets` | Optional profiles and versions that should adopt the feature. |
| `validation_strategy` | Automated validator, runtime test, manual test, or documented gap. |
| `conform_skill_plan` | New conform skill name, existing conform skill to update, or documented reason no conform skill can safely repair the feature. |

## Instructions

Use this checklist when changing the repository:

1. Inspect existing feature numbers, IDs, filenames, and variant suffixes. Avoid reusing an ID or inventing a new suffix when an existing suffix matches.
2. Define the runtime promise in asset terms before choosing requirements.
3. Prefer existing requirements and validators. Add new requirement docs or validators only when the feature needs a new testable rule.
4. Create the JSON manifest under `nv_core/sr_specs/docs/features/`:
   - use the guide filename pattern `FET_###_base_<variant>-<version>-<description>.json`
   - include `id`, `version`, `display_name`, `path`, and `requirements`
   - include `dependencies` only when the feature actually depends on other features
   - use exact dependency versions
   - avoid circular dependencies
   - keep requirements explicit when feature expansion replaces a base requirement
5. Create the feature markdown page under `nv_core/sr_specs/docs/features/`:
   - describe the runtime use case
   - list properties, dependencies, profiles, and requirements
   - link each requirement doc and validator implementation when available
   - document testing, samples, manual review, and known gaps
6. Update `nv_core/sr_specs/docs/features/features.md` with the new feature row and toctree entry.
7. Update `nv_core/sr_specs/docs/features/feature-dependency-graph.md` when the feature has dependencies or affects common dependency diagrams.
8. Add a conform skill for the new feature when the feature can produce asset-level validation failures:
   - create `skills/simready-foundation-conform-fet-###-<feature-name>/SKILL.md`
   - include source-of-truth feature/requirement/validator paths
   - define what the skill may repair automatically and what it must block on
   - call out required model/tool capabilities, such as vision, CAD/source data, runtime simulation, or material identity
   - update `assets/openai.yaml` so the skill is discoverable
   - if the feature is metadata-only, advisory-only, or cannot be repaired safely, document the reason in the feature summary and validation handoff
9. If profile adoption is requested, hand off to `simready-foundation-add-profile` or `simready-foundation-update-profile`; do not silently mutate an existing profile version.
10. Validate consistency:
   - JSON parses
   - manifest `id` and `version` match the requested feature
   - every dependency feature/version exists
   - every requirement ID is documented or intentionally new in the same change
   - feature markdown and index links resolve by path/name
   - the matching conform skill exists or the no-conform-skill rationale is documented

## Examples

Example request:

```text
Add a new SimReady Foundation feature FET025 for factory connection points and wire it into feature docs and manifests.
```

Expected result summary:

```text
changed_files: new docs, manifests, indexes, or validation scaffolding
validation: focused static checks and any relevant docs/build checks
remaining_gaps: requirement, validator, adapter, profile, or runtime-test follow-up
```

## Policies

- Feature versions are immutable once published or used by a profile.
- Keep the feature focused on one runtime promise.
- Do not include requirements just because they are nearby; include only what the feature needs.
- If a technology-specific feature replaces a neutral/base requirement, list the full replacement requirement set explicitly instead of depending on the base feature for conflicting rules.
- Treat `profiles.toml` as profile source of truth; feature docs should mention profile usage but not replace TOML.
- Feature authoring and asset repair should evolve together. A new feature that introduces required authored USD data should normally ship with a conform skill for repairing or clearly blocking on that feature.

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
| `feature_id` | New feature ID. |
| `version` | New feature version. |
| `feature_markdown` | Feature documentation path. |
| `feature_manifest` | JSON manifest path. |
| `requirements` | Requirement IDs included. |
| `dependencies` | Feature dependencies included. |
| `profiles_updated` | Profiles changed, or `none`. |
| `conform_skill` | New/updated conform skill path, or documented rationale for none. |
| `validation` | Checks run and remaining gaps. |
| `next_step` | Profile adoption, validator work, runtime test, or review. |
