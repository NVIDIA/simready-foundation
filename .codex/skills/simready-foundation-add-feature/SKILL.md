---
name: simready-foundation-add-feature
description: "Use for adding new SimReady feature markdown pages and matching JSON manifests from nv_core/sr_specs/docs/guides/features/feature-template.md, including FET runtime naming, integer feature versions, requirement mapping, validation strategy, index entries, and optional profile or conform-skill follow-up."
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
Use this skill to add a brand-new SimReady feature under the owning package in
`nv_core/tiers/`. A feature is a versioned runtime/use-case contract made from
exact requirement IDs and optional feature dependencies.

Use `nv_core/sr_specs/docs/guides/features/feature-template.md` as the canonical markdown structure for new feature pages.

Do not use this skill for a new version of an existing feature. Use `simready-foundation-update-feature` for that.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/guides.md`
- `nv_core/sr_specs/docs/guides/features/features.md`
- `nv_core/sr_specs/docs/guides/naming_conventions.md`
- `nv_core/sr_specs/docs/guides/features/feature-template.md`
- `nv_core/sr_specs/docs/shared/features/features.md`
- existing neighboring feature markdown and JSON files for the same domain

If the feature will be added to a profile, also read `nv_core/sr_specs/docs/guides/profiles/profiles.md` and the target profile markdown/TOML entries.

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `feature_number` | Numeric ID such as `025`. If absent, inspect existing feature IDs and propose the next appropriate number. |
| `owning_tier` | Tier package that owns the feature manifest and narrative page. |
| `runtime` | Uppercase runtime suffix such as `STANDARD`, `NEWTON`, `PHYSX`, or `ISAAC`. Use `STANDARD` only for OpenUSD-standard behavior with no runtime-specific schemas or attributes. |
| `feature_name` | Exact feature name such as `FET_025_STANDARD`, `FET_025_NEWTON`, or `FET_025_PHYSX`; use the `FET_###_<RUNTIME>` pattern for new feature work. |
| `version` | Semantic feature version, usually `0.1.0` for a new feature unless the user states otherwise. |
| `display_name` | Human-readable feature name. |
| `runtime_promise` | Concrete asset behavior the feature guarantees. |
| `requirements` | Existing requirement IDs or new requirement docs/validators needed by the feature. |
| `dependencies` | Exact feature names and semantic versions this feature depends on. |
| `use_cases` | Runtime, authoring, or validation scenarios the feature supports. |
| `pipelines` | Authoring, conversion, validation, or runtime pipelines relevant to the feature. |
| `samples` | Representative assets or explicit `None` when no sample exists yet. |
| `benchmarks` | Runtime tests, benchmark suites, or validation evidence, or explicit `None` when absent. |
| `adapters` | Feature/profile adapters that convert to or from this feature, or explicit `None`. |
| `profile_targets` | Optional profiles and versions that should adopt the feature. |
| `validation_strategy` | Automated validator, runtime test, manual test, or documented gap. |
| `conform_skill_plan` | New conform skill name, existing conform skill to update, or documented reason no conform skill can safely repair the feature. |

## Naming Rules

- Feature names must use `FET_###_<RUNTIME>`.
- Runtime suffixes are uppercase and should describe the runtime contract: `STANDARD`, `NEWTON`, `PHYSX`, `ISAAC`, or another explicit runtime.
- Use `STANDARD` for OpenUSD features that do not require additional runtime-specific attributes, schemas, or behavior.
- Do not use older compact names or base-neutral suffix names for new feature work.
- Feature versions use dotted semantic versions such as `0.1.0`. Do not write bare integer feature versions in new feature markdown or manifests.
- Markdown filenames should be easy to match to the exact feature name.
- JSON manifest filenames should include the exact feature name and semantic version, such as `FET_025_STANDARD-0.1.0.json`.
- Matching conform skill folders use lowercase runtime suffixes, such as `skills/simready-foundation-conform-fet-025-standard/`.

## Instructions

Use this checklist when changing the repository:

1. Inspect existing feature numbers, names, filenames, and runtime suffixes. Avoid reusing an ID or inventing a new suffix when an existing suffix matches.
2. Define the runtime promise in asset terms before choosing requirements.
3. Prefer existing requirements and validators. Add new requirement docs or validators only when the feature needs a new testable rule.
4. Create the feature markdown page under the owning tier's `features/` directory from `feature-template.md`:
   - preserve these top-level sections: Feature, Description, Dependency Graph, Use Cases, Requirements, Pipelines, Samples, Benchmarks, and Adapters
   - replace every template placeholder with concrete content
   - if a section has no content yet, write `None` plus a short reason or follow-up instead of leaving placeholder text
   - describe the runtime use case in asset terms
   - list properties, dependencies, profiles, and requirements
   - link each requirement doc and validator implementation when available
   - document testing, samples, manual review, known gaps, and adapter status
5. Create the JSON manifest under the same tier's `features/` directory:
   - use a filename that clearly matches the `FET_###_<RUNTIME>` feature name and semantic version
   - include `id`, `version`, `display_name`, `path`, and `requirements`
   - include `dependencies` only when the feature actually depends on other features
   - use exact semantic dependency versions
   - for a physics runtime feature (e.g. `_PHYSX`, `_NEWTON`, `_MUJOCO`), include a `runtime` field whose value is the exact USD physics variant-set name to Enable (`PhysX`, `Newton`, or `MuJoCo`); the standalone validator uses it to compose that variant before checking the feature's runtime-specific requirements. Omit `runtime` for `STANDARD`, `ISAAC`, MDL, and packaging features (validated on the neutral base). See the Runtime Variant Field section in `guides/features/features.md`.
   - avoid circular dependencies
   - keep requirements explicit when feature expansion replaces a base requirement
6. Keep the markdown requirements section and JSON requirements list synchronized.
7. Update `nv_core/sr_specs/docs/shared/features/features.md` with the new feature row and toctree entry.
8. Update `nv_core/sr_specs/docs/shared/features/feature-dependency-graph.md` when the feature has dependencies or affects common dependency diagrams.
9. Add a conform skill for the new feature when the feature can produce asset-level validation failures:
   - create `skills/simready-foundation-conform-fet-###-<runtime>/SKILL.md`
   - include source-of-truth feature/requirement/validator paths
   - define what the skill may repair automatically and what it must block on
   - call out required model/tool capabilities, such as vision, CAD/source data, runtime simulation, or material identity
   - update `assets/openai.yaml` so the skill is discoverable
   - if the feature is metadata-only, advisory-only, or cannot be repaired safely, document the reason in the feature summary and validation handoff
10. If profile adoption is requested, hand off to `simready-foundation-add-profile` or `simready-foundation-update-profile`; do not silently mutate an existing profile version.
11. Validate consistency:
   - JSON parses
   - manifest `id` and `version` match the requested feature name and semantic version
   - every dependency feature/version exists
   - every requirement ID is documented or intentionally new in the same change
   - markdown contains all required template sections
   - no placeholder bracket text or template instructional text remains in the new feature
   - no semantic feature version remains in the new feature files
   - feature markdown and index links resolve by path/name
   - the matching conform skill exists or the no-conform-skill rationale is documented

## Examples

Example request:

```text
Add a new SimReady Foundation feature FET_025_STANDARD for factory connection points and wire it into feature docs and manifests.
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
- Treat the per-profile TOML files in `profiles/` as profile source of truth; feature docs should mention profile usage but not replace the TOML.
- Feature authoring and asset repair should evolve together. A new feature that introduces required authored USD data should normally ship with a conform skill for repairing or clearly blocking on that feature.
- Samples, benchmarks, and adapters should point to real assets, real evidence, or real modules. If they are missing, document the gap plainly.
- Runtime-specific feature docs must avoid placeholder requirements. If the runtime schema or runtime behavior is unknown, stop and report the exact missing source needed.

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
| `feature_name` | New `FET_###_<RUNTIME>` feature name. |
| `version` | New integer feature version. |
| `feature_markdown` | Feature documentation path. |
| `feature_manifest` | JSON manifest path. |
| `requirements` | Requirement IDs included. |
| `dependencies` | Feature dependencies included. |
| `samples` | Sample assets added or referenced, or `none`. |
| `benchmarks` | Benchmarks added or referenced, or `none`. |
| `adapters` | Adapter paths added or referenced, or `none`. |
| `profiles_updated` | Profiles changed, or `none`. |
| `conform_skill` | New/updated conform skill path, or documented rationale for none. |
| `validation` | Checks run and remaining gaps. |
| `next_step` | Profile adoption, validator work, runtime test, or review. |
