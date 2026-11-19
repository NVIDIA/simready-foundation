---
name: simready-foundation-add-runtime-test
description: "Use for adding or updating SimReady Foundation runtime tests in a tier-owned Evaluate test package, wiring the package through the tier descriptor and wheel, and keeping feature/profile documentation and test registration synchronized. Delegates generic Evaluate mechanics and independent test-pack packaging to the installed simready-evaluate skills."
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
importable `<test-package>` and executed through the `simready-evaluate` plan,
run, stamp, and report pipeline. The core tier currently uses
`simready.foundation.tier_core.runtime_tests`; other tiers may publish a different import
package and must declare it through their descriptor's `runtime_tests_path`.

This skill is deliberately scoped to the Foundation-repository wiring. The
generic mechanics of authoring, packaging, running, and reporting evaluation
tests are owned by the `simready-evaluate` library's own agent skills; do not
duplicate them here. Use those skills for the test-authoring and pipeline
mechanics, and use this skill for how a test is placed into this repository and
kept in sync with the Foundation docs, feature manifests, and profiles.

Do not hand-edit generated plans, result JSON, or report artifacts. Change the
Python test source, its documentation, and focused tests instead.

## Delegate Mechanics to the simready-evaluate Library Skills

The external `simready-evaluate` library ships its own agent skills that are the
source of truth for the framework mechanics. Locate them with
`simready-evaluate --skills-path`, then read and follow the relevant one:

- `write-test-pack` - the `@test` decorator, required metadata (`features`,
  `name`, `description`, `expected_video`, `version`, `engine`,
  `config_defaults`, `max_duration`), `RunContext` usage, media roles,
  config-driven tests, and packaging/discovery through the
  `simready.evaluate.tests` entry-point group.
- `run-tests` - plan, run, and report a suite against a profile.
- `diagnose-failures` - read a report and propose a scoped re-run.

Treat the installed library skills as authoritative for API names and flags;
they match the installed framework version. This skill only adds what those
skills do not know: the Foundation repository's layout, docs, and spec bindings.

## What This Skill Owns (Foundation-Specific)

- Deciding whether the test belongs to a Foundation tier. A test that proves a
  tier-owned feature should ship with that tier. An independent OEM or
  experimental test pack that does not own the feature should use the
  Evaluate `write-test-pack` skill and either an independent wheel or an
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
- Keeping registrations synchronized with the owning feature manifest and
  profile selectors. Foundation 2 manifests own the exact
  `runtime_tests = ["<provider>:<test-name>"]` bindings; decorator metadata alone
  does not add an obligation. Foundation 1 instead matches legacy decorator
  feature IDs and semantic version constraints. Follow the owning suite
  guidance below for the current registration and provider identities.
  The current `@test` decorator has no `requirement` argument, so document the
  behavioral contract in the test description and matching Foundation docs.
- Updating the matching documentation under the owning `<test-package>/docs/`
  directory and any feature/profile acceptance text that promises this runtime
  evidence. Resolve the published destination from the owning tier's
  `docs-sources.json`: Core uses `guides/evaluate/tests/`, Newton uses
  `guides/evaluate/newton-tests/`, and Sensors uses
  `guides/evaluate/sensor-tests/`. Use that destination when checking relative
  links; do not assume every suite publishes beneath Core's URL.

## Owning Suite Guidance

Read the maintained guide for the test package selected by the tier descriptor:

- Core (`simready.foundation.tier_core.runtime_tests`): [authoring.md](../../nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/runtime_tests/docs/authoring.md).
- Newton (`simready.foundation.tier_newton.runtime_tests`): [runtime-tests.md](../../nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/runtime_tests/docs/runtime-tests.md).
- Sensors (`simready.foundation.sensors.runtime_tests`): [tests.md](../../nv_core/tiers/simready_foundation_tier_sensors/simready/foundation/sensors/runtime_tests/docs/tests.md).

Also read the matching feature/procedure pages, neighboring registrations,
`benchmark-provider.json`, and selected contract metadata for that suite.
For another tier, follow its declared authoring guide or maintained suite
landing page. Verify the selected paths exist; do not assume every suite has
`docs/authoring.md` or create a duplicate guide to satisfy that filename.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/evaluate/evaluate.md`
- `nv_core/sr_specs/docs/guides/evaluate/overview.md`
- `nv_core/sr_specs/docs/guides/evaluate/pipeline.md`
- `nv_core/sr_specs/docs/guides/evaluate/running.md`
- `nv_core/sr_specs/docs/guides/evaluate/reading-reports.md`
- `nv_core/tiers/<tier-directory>/<test-package>/docs/tests.md` (or the landing page
  declared by that test package)
- the owning suite guide selected above and its matching procedure/metadata
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
| `feature_or_profile` | Feature/profile requiring runtime evidence. For a Foundations 2 contract, the exact dotted feature ID or the resolved profile target. |
| `asset_scope` | Representative assets and the validation/feature selection that makes the test applicable. |
| `ownership` | Tier-owned feature evidence, independent published pack, or unpublished development pack. |
| `test_identifier` | Unique `@test` name and semantic test version. |
| `test_module` | Python module in the matching FET package. |
| `engine` | Required Kit/Isaac engine tags and supported version range. |
| `test_config` | Defaults exposed through `config_defaults`, including thresholds and timeouts. |
| `expected_artifacts` | Metrics, logs, images, video, result JSON, and HTML report evidence. |

## Instructions

Use this checklist when changing the repository. It covers the Foundation-specific
wiring only; follow the `simready-evaluate` library skills (see above) for the
`@test` authoring, packaging, and pipeline mechanics.

1. Decide whether runtime evidence is required by the feature/profile or only
   useful as supplementary confidence. For a Foundations 2 contract, first
   decide whether it is a runtime FET, a source FET, or a capability: runtime
   evidence is mandatory for a derived FET, a testless FET is valid only as the
   source of a tested derivative, and any other static-only bundle belongs in a
   `CAP` capability instead.
2. Read the matching feature manifest and feature documentation, then confirm
   the exact contract is selectable from the relevant profiles. Foundation 2
   uses the manifest's exact provider-qualified `runtime_tests` selectors.
   Advertise its full dotted contract ID in the decorator, including the opaque
   contract version token, and retain the required decorator feature
   `version="*"` field as in current registrations. This field is distinct
   from the test procedure's own semantic `version`. For Foundation 1
   compatibility, use the existing legacy ID and semantic version constraint.
   Never register a profile wildcard selector or invent a compatibility alias.
   Identify the runtime promise for documentation, but do not pass an
   unsupported `requirement` keyword to `@test`.
3. Read the `simready-evaluate` `write-test-pack` skill (via
   `simready-evaluate --skills-path`) and follow it for the `@test` authoring
   mechanics, decorator metadata, `RunContext` usage, and config defaults. Do not
   restate those mechanics here.
4. Choose the ownership model:
   - For a tier-owned feature, resolve `<test-package>` from the tier
     descriptor's `runtime_tests_path`, add the test to
     `nv_core/tiers/<tier-directory>/<test-package>/fet###_*`, and keep it in the same
     wheel as that tier.
   - For an independent published pack, follow the Evaluate skill and register
     the wheel under `simready.evaluate.tests`.
   - For an unpublished pack, point `--tests-path` at the importable package
     directory. Explicit paths are additive to installed tier and independent
     providers.
5. For a tier-owned test, inspect neighboring modules and add each independently
   reportable test in its own Python file. Reuse the suite's scene, context,
   cleanup, configuration, and unit-test patterns. Do not recreate a separate
   `nv_core/runtime_tests` or `nv_core/testing_tools` provider tree.
   Discovery also directly scans non-underscore helper files under a synthetic
   top-level module name. Use qualified absolute imports in scanned files and
   their coroutines; pure underscore-prefixed helpers may use relative imports
   when imported through the real package. Follow the Evaluate packaging
   reference and verify full source and installed-wheel discovery, not only
   normal package imports. A helper with no decorator can still break planning.
   Selected-root disappearance or directory enumeration/access errors fail
   discovery; a surviving subset is not a usable complete provider inventory.
   Restore access before accepting scan or exact-file dispatch results.
   For robot arrival tests, follow the Evaluate skill's velocity-aware timing
   guidance and the owning suite's documented policy: qualified hint units,
   shared slowest-joint ramp, bounded response/hold and execution budgets.
   Use required live ramp starts rather than missed previous goals, and handle
   SDK unlimited sentinels before command/ceiling arithmetic. Follow the test's
   documented eligibility without inventing stops or ratings; make omitted
   prerequisites and subset coverage visible, not a vacuous PASS.
   Keep Newton's procedure/defaults/timing locally owned rather than importing
   Core policy. A velocity-limit excitation has a sampled-speed criterion,
   not an arrival deadline; record helper acknowledgment without claiming
   physical enforcement. Bump the test procedure version for observable
   changes and update its owning guide; public bindings need no rewrite when
   their provider/test identity is unchanged.
   Keep independent feature obligations independently reportable: current
   ground-drop verdicts do not substitute for separately bound sampled stability.
   Qualify complete post-proximity hold windows, minimum observations and deadlines
   before reporting rest; freeze rest/deadline acceptance before recording tails.
   Required overlap checks may still invalidate the result during that tail.
   A budget that cannot finish the required observation opportunity is incomplete
   execution, not measured asset non-settling. Preserve required feature coverage
   and document nullable window proxies without claiming native velocity/contact.
6. Confirm the owning tier's `pyproject.toml` includes both its `simready`
   package and `<test-package>`, and that the tier descriptor's
   `runtime_tests_path` resolves directly to that importable package directory.
   Set the `evaluate` extra and isolated test requirements to the minimum
   compatible Evaluate/Kit builds that provide every required measurement and
   cleanup API. A missing retirement callback is not optional recording
   compatibility; keep those execution requirements out of validation-only
   base dependencies and verify the declared minimum, not only the latest pair.
   For the core tier, `<test-package>` is currently
   `simready.foundation.tier_core.runtime_tests`. Descriptor import must remain
   dependency-light and must not import tests, Kit, Isaac, or `pxr`.
7. Keep the decorator's `features` metadata and the selected contract aligned.
   For Foundation 2, bind the exact public `<provider>:<test-name>` identity in
   the owning feature manifest's `runtime_tests`; the public provider namespace
   comes from the package's canonical `benchmark-provider.json`; `import_package`
   separately names the actual Python package, including namespace ancestors.
   Core/Newton/Sensors preserve the old flat suite names as provider aliases.
   `evaluate-provider.json` is also accepted; dual normalized declarations must
   agree. Regular packages may infer omitted import ownership from physical
   ancestry; namespace packages require explicit `import_package`. These aliases
   do not supply Python import shims or restore the removed Benchmark SDK. Old
   SDK-importing tier code needs its matching Benchmark environment; current
   code requires its declared Evaluate dependencies. Readability of historical
   evidence does not establish freshness, current source or native qualification.
   Follow the owning suite guidance above for provider identities and
   existing examples. Never edit published feature/profile versions in place:
   a changed binding requires a new contract version and the normal profile
   review. Foundation 1 compatibility continues to use decorator ID/version
   matching. The tier descriptor or independent entry point discovers the
   package but does not replace Foundation 2 manifest ownership.
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

- Protect unrelated local work: before editing shared repository files (spec markdown, requirement/feature JSON, profile TOML, validators, skills, or docs), check `git status` for unrelated in-progress changes and scope edits to the requested task. Never revert, overwrite, discard, stash, or commit a user's uncommitted or unrelated changes; if a file you must edit already carries pending unrelated edits, surface it and confirm before proceeding.
- Keep secrets out of the repo and evidence: never write user-provided tokens, credentials, API keys, or other secrets into files, source, logs, validation or evaluation reports, commit messages, or bug/Jira/Confluence attachments, and do not echo them in full; read them from environment variables or an existing credential store and redact them from any output you preserve.
- Generated plans, result JSON, media, and report folders are artifacts, not source of truth.
- Runtime tests should be reproducible from the repository, installed Evaluate
  packages, engine configuration, asset path, and command line.
- Tier-owned tests ship in the tier wheel and are advertised only through the
  tier descriptor. Independent test-only wheels use `simready.evaluate.tests`.
- Foundation 2 manifests own exact runtime-test bindings; Foundation 1 uses
  decorator feature ID/version matching. Keep registration, provider metadata,
  selected contracts and profile selectors synchronized without rewriting
  published versions.
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
