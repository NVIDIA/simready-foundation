---
name: simready-foundation-add-runtime-test
description: "Use for adding or updating SimReady Foundation runtime tests in a tier-owned Benchmark test package, wiring the package through the tier descriptor and wheel, and keeping feature/profile documentation and test registration synchronized. Delegates generic Benchmark mechanics and independent test-pack packaging to the installed simready-benchmark skills."
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
Use this skill when static validators are not enough to prove that a feature or
profile works in a runtime, and the runtime evidence must live in the SimReady
Foundation repository. Runtime tests are authored in the owning tier's
importable `<test-package>` and executed through the `simready-benchmark` plan,
run, stamp, and report pipeline. The core tier currently uses
`simready_benchmark_kit_suite`; other tiers may publish a different import
package and must declare it through their descriptor's `runtime_tests_path`.

This skill is deliberately scoped to the Foundation-repository wiring. The
generic mechanics of authoring, packaging, running, and reporting benchmark
tests are owned by the `simready-benchmark` library's own agent skills; do not
duplicate them here. Use those skills for the test-authoring and pipeline
mechanics, and use this skill for how a test is placed into this repository and
kept in sync with the Foundation docs, feature manifests, and profiles.

Do not hand-edit generated plans, result JSON, or report artifacts. Change the
Python test source, its documentation, and focused tests instead.

## Delegate Mechanics to the simready-benchmark Library Skills

The external `simready-benchmark` library ships its own agent skills that are the
source of truth for the framework mechanics. Locate them with
`simready-benchmark --skills-path`, then read and follow the relevant one:

- `write-test-pack` - the `@test` decorator, required metadata (`features`,
  `name`, `description`, `expected_video`, `version`, `engine`,
  `config_defaults`, `max_duration`), `RunContext` usage, media roles,
  config-driven tests, and packaging/discovery through the
  `simready_benchmark.tests` entry-point group.
- `run-tests` - plan, run, and report a suite against a profile.
- `diagnose-failures` - read a report and propose a scoped re-run.

Treat the installed library skills as authoritative for API names and flags;
they match the installed framework version. This skill only adds what those
skills do not know: the Foundation repository's layout, docs, and spec bindings.

## What This Skill Owns (Foundation-Specific)

- Deciding whether the test belongs to a Foundation tier. A test that proves a
  tier-owned feature should ship with that tier. An independent OEM or
  experimental test pack that does not own the feature should use the
  Benchmark `write-test-pack` skill and either an independent wheel or an
  explicit development path.
- Placing a tier-owned test directly under
  `nv_core/tiers/<tier-directory>/<test-package>/fet###_*` and focused unit
  tests under `nv_core/tiers/<tier-directory>/tests/runtime_tests/unit/`. The
  package name comes from
  the owning tier descriptor; it is not globally fixed.
- Keeping the tier wheel's package list and its `simready.tier` descriptor's
  `runtime_tests_path` synchronized. The descriptor points directly at the
  importable test package directory; it does not point at a `runtime_tests`
  container.
- Keeping the canonical `FET_###_<RUNTIME>` decorator entry and semantic
  version constraint synchronized with the owning feature manifest and profile
  TOMLs. The decorator is the executable feature-to-test binding; feature
  manifests do not carry a separate `runtime_tests` selector. The current
  `@test` decorator has no `requirement` argument, so document the requirement
  or behavioral contract in the test description and matching Foundation docs.
- Updating the matching documentation under the owning `<test-package>/docs/`
  directory and any feature/profile acceptance text that promises this runtime
  evidence. The documentation assembler publishes the tier-declared source at
  the stable `guides/benchmark/tests/` URL.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/benchmark/benchmark.md`
- `nv_core/sr_specs/docs/guides/benchmark/overview.md`
- `nv_core/sr_specs/docs/guides/benchmark/pipeline.md`
- `nv_core/sr_specs/docs/guides/benchmark/running.md`
- `nv_core/sr_specs/docs/guides/benchmark/reading-reports.md`
- `nv_core/tiers/<tier-directory>/<test-package>/docs/tests.md` (or the landing page
  declared by that test package)
- `nv_core/tiers/<tier-directory>/<test-package>/docs/authoring.md`
- `nv_core/tiers/<tier-directory>/pyproject.toml`
- `nv_core/tiers/<tier-directory>/simready/foundation/<tier-module>/_tier.py`
- `nv_core/tiers/<tier-directory>/<test-package>/`
- `nv_core/tiers/<tier-directory>/tests/runtime_tests/unit/`
- relevant feature/profile docs that need runtime evidence
- the neighboring runtime tests for the same feature family

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `runtime_goal` | Behavior to prove, such as drop/settle, articulation motion, rendering, or importability. |
| `feature_or_profile` | Feature/profile requiring runtime evidence. |
| `asset_scope` | Representative assets and the validation/feature selection that makes the test applicable. |
| `ownership` | Tier-owned feature evidence, independent published pack, or unpublished development pack. |
| `test_identifier` | Unique `@test` name and semantic test version. |
| `test_module` | Python module in the matching FET package. |
| `engine` | Required Kit/Isaac engine tags and supported version range. |
| `test_config` | Defaults exposed through `config_defaults`, including thresholds and timeouts. |
| `expected_artifacts` | Metrics, logs, images, video, result JSON, and HTML report evidence. |

## Instructions

Use this checklist when changing the repository. It covers the Foundation-specific
wiring only; follow the `simready-benchmark` library skills (see above) for the
`@test` authoring, packaging, and pipeline mechanics.

1. Decide whether runtime evidence is required by the feature/profile or only useful as supplementary confidence.
2. Read the matching feature manifest and feature documentation. Identify the
   canonical `FET_###_<RUNTIME>` decorator entry and semantic version
   constraint, then confirm the same feature version is selectable from the
   relevant profile TOMLs. The decorator is the executable feature-to-test
   binding; do not add a separate `runtime_tests` selector to the feature
   manifest. Identify the requirement or runtime promise it proves for
   documentation, but do not pass a `requirement` keyword to `@test`; that
   keyword is not part of the current API.
3. Read the `simready-benchmark` `write-test-pack` skill (via
   `simready-benchmark --skills-path`) and follow it for the `@test` authoring
   mechanics, decorator metadata, `RunContext` usage, and config defaults. Do not
   restate those mechanics here.
4. Choose the ownership model:
   - For a tier-owned feature, resolve `<test-package>` from the tier
     descriptor's `runtime_tests_path`, add the test to
     `nv_core/tiers/<tier-directory>/<test-package>/fet###_*`, and keep it in the same
     wheel as that tier.
   - For an independent published pack, follow the Benchmark skill and register
     the wheel under `simready_benchmark.tests`.
   - For an unpublished pack, point `--tests-path` at the importable package
     directory. Explicit paths are additive to installed tier and independent
     providers.
5. For a tier-owned test, inspect neighboring modules and add each independently
   reportable test in its own Python file. Reuse the suite's scene, context,
   cleanup, configuration, and unit-test patterns. Do not recreate a separate
   `nv_core/runtime_tests` or `nv_core/testing_tools` provider tree.
6. Confirm the owning tier's `pyproject.toml` includes both its `simready`
   package and `<test-package>`, and that the tier descriptor's
   `runtime_tests_path` resolves directly to that importable package directory.
   For the core tier, `<test-package>` is currently
   `simready_benchmark_kit_suite`. Descriptor import must remain
   dependency-light and must not import tests, Kit, Isaac, or `pxr`.
7. Bind the test to this repository's specs with the canonical Foundation
   feature ID and semantic version constraint in the decorator's `features`
   list. Confirm that ID/version against the owning feature manifest and
   relevant profile TOMLs. Provider identity is a discovery concern handled by
   the tier descriptor, `simready_benchmark.tests` entry point, or
   `--tests-path`; do not author provider/test selectors in feature manifests.
   Keep pure calculation and discovery logic outside the coroutine and add
   focused unit tests; add registration/metadata coverage when changing
   mappings or report behavior.
8. Update the matching page under the owning suite's `docs/` directory and any
   feature/profile acceptance text that promises this runtime evidence. Keep
   the suite index/toctree and the tier's declarative documentation-source
   mapping synchronized. Do not create a second copy under `sr_specs/docs`.
9. Validate both delivery paths that changed:
   - Source checkout: use `--foundations-path <repo>` or point `--tests-path`
     directly at the test package while developing, then run `--list-tests`.
   - Tier wheel: build and install the tier wheel in a clean environment and run
     `--show-config` plus `--list-tests` without `--tests-path`.
   Then run a scoped `--plan-only` and `--no-stamp` execution. Inspect the
   report/media and summarize the pass/fail/skip signal. If Kit/Isaac is
   unavailable, report a blocked runtime check rather than claiming a pass.

## Examples

Example request:

```text
Add a runtime test proving a SimReady factory asset connection point imports and aligns correctly in Kit.
```

Expected result summary:

```text
changed_files: new docs, manifests, indexes, or validation scaffolding
validation: discovery, plan-only, focused unit checks, and runtime evidence when available
remaining_gaps: requirement, validator, adapter, profile, or runtime-test follow-up
```

## Policies

- Generated plans, result JSON, media, and report folders are artifacts, not source of truth.
- Runtime tests should be reproducible from the repository, installed Benchmark
  packages, engine configuration, asset path, and command line.
- Tier-owned tests ship in the tier wheel and are advertised only through the
  tier descriptor. Independent test-only wheels use `simready_benchmark.tests`.
- The decorator's canonical feature ID and semantic version constraint own the
  executable feature-to-test binding. Keep them synchronized with the tier's
  feature manifests and profile TOMLs.
- `--tests-path` must point at the importable package directory containing
  `__init__.py`, not at the repository root.
- Keep user/CI-owned executable paths and credentials out of committed tests and docs.
- Do not change an asset merely to make a runtime test pass unless the task
  explicitly includes asset conformance.
- If the runtime cannot run locally, still add clear commands, expected signals,
  and focused non-runtime validation.

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
| `test_sources` | Test implementation, unit tests, and documentation changed. |
| `engine_requirements` | Kit/Isaac/runtime assumptions. |
| `commands` | Discovery, plan-only, focused unit, and runtime commands. |
| `artifacts` | Expected or produced result/report evidence. |
| `validation` | Runtime test result or blocker. |
