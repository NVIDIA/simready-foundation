---
name: simready-foundation-add-runtime-test
description: "Use for adding SimReady runtime tests, runner expectations, batch/job/report notes, and validation evidence."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - runtime-testing
    - validation
---


# SimReady Add Runtime Test

## Purpose
Use this skill when static validators are not enough to prove a feature or profile works in a runtime. Runtime tests use the `workspace runtime_tests` pipeline: batch maker, job runner, and report generator.

Do not hand-edit generated job JSON. Add or update the source test/search configuration that generates it.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/runtime_testing/runtime_testing.md`
- `nv_core/sr_specs/docs/guides/runtime_testing/runtime_tests_overview.md`
- `nv_core/sr_specs/docs/guides/runtime_testing/job_runner_deep_dive.md`
- `nv_core/sr_specs/docs/guides/runtime_testing/runners_info.md`
- `nv_core/sr_specs/docs/guides/runtime_testing/cicd_usage.md`
- relevant feature/profile docs that need runtime evidence

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `runtime_goal` | Behavior to prove, such as drop/settle, articulation motion, rendering, or importability. |
| `feature_or_profile` | Feature/profile requiring runtime evidence. |
| `asset_scope` | Asset search pattern, modified assets list, or manual assets. |
| `test_identifier` | Existing or new test definition name. |
| `search_function` | Existing or new search function that returns assets for the test. |
| `test_definition` | TOML source with `TestInfo`, `RunnerTags`, and `TestConfig` sections. |
| `runner` | Kit/Isaac/runtime runner requirement. |
| `expected_artifacts` | Logs, screenshots, metrics, XML, JSON, or HTML report. |

## Instructions

Use this checklist when changing the repository:

1. Decide whether runtime evidence is required by the feature/profile or only useful as supplementary confidence.
2. Locate existing runtime test definitions and search functions for similar behavior.
3. Add or update source test/search configuration, not generated batch job files.
4. For search functions, keep the file and function name aligned and return `AssetData` from the provided search context.
5. For test definitions, include the guide-required TOML sections:
   - `[TestInfo]` with name, description, version, search function, and optional feature IDs/versions
   - `[RunnerTags]` with runner config and script/class fields only when the run mode requires them
   - `[TestConfig]` for test-specific settings
6. Ensure runner assumptions are documented in `local_run/runners_info.toml` guidance or the relevant docs. Do not hard-code user-specific runner paths into committed specs.
7. Document how to run:
   - `workspace runtime_tests batch_maker`
   - `workspace runtime_tests job_runner`
   - `workspace runtime_tests report_generator`
8. Record expected outputs under `_testing/batch_jobs/`, `_testing/job_outputs/`, and `_testing/index.html`.
9. Add expected pass/fail signals and artifacts to the feature/profile docs when runtime testing is part of the acceptance strategy.
10. Run the narrowest available runtime test when the local Kit/runtime environment exists; otherwise report the blocked runtime dependency.
11. Preserve report paths and summarize runtime evidence.

## Examples

Example request:

```text
Add a runtime test proving a SimReady factory asset connection point imports and aligns correctly in Kit.
```

Expected result summary:

```text
changed_files: new docs, manifests, indexes, or validation scaffolding
validation: focused static checks and any relevant docs/build checks
remaining_gaps: requirement, validator, adapter, profile, or runtime-test follow-up
```

## Policies

- Generated job JSON and output folders are artifacts, not source of truth.
- Runtime tests should be reproducible from project root, test definitions, search functions, and runner config.
- Keep user/CI-owned runner paths out of source-controlled docs unless intentionally templated.
- If runtime cannot run locally, still add clear commands and expected artifacts.

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
| `runtime_goal` | Behavior being tested. |
| `feature_or_profile` | Spec surface covered. |
| `test_sources` | Test/search files changed. |
| `runner_requirements` | Kit/Isaac/runtime assumptions. |
| `commands` | Batch/job/report commands. |
| `artifacts` | Expected or produced reports. |
| `validation` | Runtime test result or blocker. |
