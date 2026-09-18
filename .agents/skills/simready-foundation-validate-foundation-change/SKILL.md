---
name: simready-foundation-validate-foundation-change
description: "Use for auditing SimReady requirement, validator, feature, profile, adapter, test, and skill consistency."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - validation
    - audit
---


# SimReady Validate Foundation Change

## Purpose
Use this skill after changing SimReady requirements, capabilities, validators, features, profiles, adapters, runtime tests, or related skills. It is a consistency audit, not a repair skill. Repair findings with the targeted add/update skills.

## Prerequisites
Before validating, read:

- `AGENTS.md`
- the changed files
- relevant guides for the changed surface
- affected feature manifests and profiles
- `nv_core/sr_specs/docs/guides/benchmark/benchmark.md` and its linked pages
  when runtime evidence or `_testing/` artifacts are involved

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `changed_files` | Git diff or explicit file list. |
| `change_type` | Requirement, capability, validator, feature, profile, adapter, runtime test, or skill change. |
| `target_feature_profile` | Affected `FET_###_<RUNTIME>` feature names, semantic feature versions, profile names, and profile versions. |
| `available_tools` | `simready-validate`, USD/PXR, OAV, Kit runtime, or docs-only. |

## Instructions

Use this checklist when changing the repository:

1. Inspect the diff and classify touched surfaces.
2. Requirement/capability checks:
   - every requirement doc has a unique code
   - every requirement doc is indexed by its capability
   - capability overview and `requirements.md` agree
   - custom names follow naming conventions
3. Validator checks:
   - validators register documented requirement IDs
   - failure messages are requirement-specific
   - docs and validator behavior agree
   - imports/registration paths are updated
4. Feature checks:
   - JSON manifests parse
   - feature names use `FET_###_<RUNTIME>`
   - feature versions are dotted semantic versions; do not reintroduce the
     reverted bare-integer version experiment
   - JSON manifest filenames match `FET_###_<RUNTIME>-<semantic-version>.json`
   - feature markdown filenames match `FET_###_<RUNTIME>.md`
   - `id`, `version`, `display_name`, `path`, `dependencies`, and `requirements` are present as expected
   - every requirement ID exists
   - every dependency feature/version exists
   - dependency versions are exact and dependency chains are not circular
   - feature expansion removes conflicting base requirements instead of stacking mutually exclusive rules
   - feature markdown keeps the canonical `feature-template.md` sections: Feature, Description, Dependency Graph, Use Cases, Requirements, Pipelines, Samples, Benchmarks, and Adapters
   - feature markdown documents the same semantic versions and requirements as the JSON manifests
   - `features/features.md` and dependency graph are updated when needed
   - new or contract-changing features have a matching `skills/simready-foundation-conform-fet-###-<runtime>` skill, or the change documents why no asset-repair skill is safe/applicable
5. Profile checks:
   - the per-profile TOML files in `profiles/` parse
   - existing profile versions are preserved unless explicitly editorial
   - every referenced feature name/semantic feature version exists
   - profile markdown and `profiles.md` agree with TOML
6. Adapter checks:
   - adapter metadata references existing feature names and semantic feature versions
   - every changed profile feature difference has an adapter path or documented blocker
7. Runtime test checks:
   - Python test sources changed, not generated plans, result JSON, or reports
   - tier-owned tests live under
     `nv_core/tiers/<tier>/<test-package>/`, where `<test-package>` is the
     importable package declared by that tier's descriptor; retired
     `nv_core/runtime_tests` and `nv_core/testing_tools` trees are not recreated
   - the tier wheel includes the test package and its descriptor's
     `runtime_tests_path` points directly to that importable directory
   - independent test-only wheels use `simready_benchmark.tests`; unpublished
     development packs remain discoverable through `--tests-path`
   - each independently reportable test has its own module and `@test` registration
   - feature mappings, name/version, engine requirements, configuration defaults,
     `description`, and `expected_video` are complete; do not add the removed
     `requirement` decorator keyword
   - focused unit and registration tests cover non-runtime behavior
   - engine assumptions and reproduction commands are documented
   - expected pass/fail/skip signals and report artifacts are clear
8. Skill/layout checks:
   - `skills` is source of truth
   - `.codex/skills` and `.claude/skills` remain compatibility links/placeholders
   - skill folder name, `SKILL.md` name, and `assets/openai.yaml` prompt token align
   - conform skill source-of-truth feature manifests, requirement IDs, validators, repair policy, blocked cases, and summary fields align with the changed feature contract
9. Run available validation commands:
   - JSON/TOML parse checks
   - targeted Python syntax/import checks
   - `simready-validate` when installed
   - USD/PXR or runtime tests when available and relevant
10. Report findings ordered by severity with file paths and next repair skill.

## Examples

Example request:

```text
Validate a SimReady Foundation change that adds a feature, profile, validator, and conform skill.
```

Expected result summary:

```text
findings: file paths and contract drift found
validation: checks reviewed or rerun
next_step: targeted add/update/conform skill for each repair
```

## Policies

- Do not hide unavailable tooling. State exactly which checks could not run.
- Do not treat docs-only validation as equivalent to runtime validation.
- Prefer targeted findings over broad style advice.
- If profile markdown and TOML disagree, TOML is the machine-readable source of truth.
- If a published version was mutated in place, flag it unless the change is clearly editorial.

## Limitations

- This skill audits consistency; make repairs only when the user asks for them.
- Do not treat missing runtime evidence as passing; record the validation gap.
- Do not collapse versioned SimReady artifacts into mutable in-place edits.

## Troubleshooting

- Error: a referenced artifact is missing. Solution: report the missing path and the upstream index or manifest that points to it.
- Error: docs and validators disagree. Solution: identify which contract is authoritative before recommending a repair.
- Error: runtime evidence is absent. Solution: mark it as a validation gap rather than a pass.

## Resources

- `assets/openai.yaml` preserves optional UI metadata for clients that read skill display hints. It is not required for the workflow.

## Summary Format

Report:

| Field | Meaning |
|---|---|
| `change_type` | Surfaces checked. |
| `files_checked` | Important files inspected. |
| `commands_run` | Validation commands and results. |
| `findings` | Bugs or consistency gaps ordered by severity. |
| `blocked_checks` | Tooling or environment gaps. |
| `recommended_repairs` | Targeted skills or files to fix next. |
| `overall_status` | Pass, pass with warnings, blocked, or fail. |
