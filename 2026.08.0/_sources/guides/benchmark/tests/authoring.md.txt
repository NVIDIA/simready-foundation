# Authoring SimReady Foundation runtime tests

This document defines the Foundation-specific contract for tests in
`simready_benchmark_kit_suite`. Framework APIs such as `@test`, `RunContext`,
engine sessions, and media capture are owned by the installed
`simready-benchmark` package. Verify those APIs against the installed code and
its `write-test-pack` skill before changing a test.

## Ownership and discovery

A runtime test belongs in this package when it provides behavioral evidence for
a feature owned by the core Foundation tier. The tier's `simready.tier`
descriptor exposes this importable package through `runtime_tests_path`.
Resolving that descriptor must only compute paths; it must not import this
package, Kit, Isaac Sim, or `pxr`.

Use a different ownership model when appropriate:

- A test for another tier belongs in that tier's own importable test package.
- An independent published test-only wheel registers an importable package in
  the `simready_benchmark.tests` entry-point group.
- An unpublished development package can be added with `--tests-path`; the path
  must name the package directory containing `__init__.py`.

Installed tier tests, independent entry-point packs, and explicit development
paths are additive. Do not create another `runtime_tests` container between a
tier wheel and its importable package.

## Package layout

Each FET family has a package named `fet###_<topic>`. Keep independently
reportable tests in separate modules, and place engine-neutral calculation or
discovery helpers outside the async test coroutine so they can be unit tested
without launching Kit.

```text
simready_benchmark_kit_suite/
  fet003_physics/
    __init__.py
    ground_drop.py
    slope_drop.py
  docs/
    fet003-physics.md
    fet003/
      ground-drop.md
      slope-drop.md
```

Shared articulation helpers live in `articulation_phases/`. Reuse the suite's
scene, context, cleanup, configuration, and test helpers rather than creating a
parallel framework.

## Registration contract

Decorate an `async def` coroutine with the public `@test` decorator. The current
registration contract requires:

- `features`: one or more dictionaries with a canonical Foundation feature ID
  and semantic version constraint;
- `name`: a unique stable test identifier;
- `description`: an actionable plain-text statement of the tested behavior;
- `expected_video`: plain-text visual cues for a passing recording;
- `version`: the semantic version of the runtime-test contract.

Optional metadata includes `engine`, `config_defaults`, `max_duration`, and
`enabled`. The current decorator has no `requirement` argument. Describe the
requirement or behavioral promise in the registration text and matching
Foundation documentation instead.

Use canonical IDs such as `FET_003_STANDARD`, `FET_003_PHYSX`, and
`FET_003_NEWTON`. Confirm them against the owning tier's feature manifests and
profile TOMLs. Do not invent compatibility aliases.

### Feature binding and provider identity

The decorator is the executable feature-to-test binding. For example:

```python
@test(
    features=[{"id": "FET_004_PHYSX", "version": ">=0.1.0"}],
    name="joint_movement",
    # ...
)
```

Benchmark matches the decorator's canonical feature ID and version constraint
against the selected profile, asset validation, or explicit `--features`
filter. The owning feature manifest does not carry a separate `runtime_tests`
selector; do not invent one.

Family labels such as `FET001` are derived grouping and filter names. They do
not replace canonical feature IDs such as `FET_001_STANDARD`, and a single
family may contain tests for several runtime variants. Audits that verify
feature attribution must inspect every enabled decorator's `features` list and
confirm that each exact ID has at least one compatible manifest version. Do not
infer the manifest ID from a `fet###_<topic>` package name, a
`fet###-<family>.md` filename, or a `FET###` documentation heading.

Provider identity controls discovery, not feature ownership. The core tier
advertises the `simready_benchmark_kit_suite` import package through its tier
descriptor. An independent test-only wheel advertises its package through the
`simready_benchmark.tests` entry-point group, and an unpublished package is
added with `--tests-path`. In all three cases, keep `name` unique and stable so
users can select the exact test with `--tests`.

Bump the test version whenever verdict logic, observable behavior, or evidence
semantics change. Engine minimum versions and test versions are executable
contract data; keep them in the documentation and parity tests. Do not copy a
Benchmark wheel release number into examples unless it is a real compatibility
floor enforced by package metadata.

## Configuration and outcomes

Put tunable thresholds and time budgets in `config_defaults`. Avoid hidden
asset-specific exceptions. A test should produce the same verdict from the
same asset, engine, configuration, and initial state.

Use outcome methods deliberately:

- `ctx.fail(...)` records a tested contract violation.
- `ctx.skip(...)` records that the runtime cannot honestly execute the test or
  that an explicit prerequisite is not met.
- `ctx.precheck_failure(...)` is for an asset/runtime precondition discovered
  before the behavioral phases begin.

`fail()` and `skip()` do not terminate the coroutine. Return explicitly after
them unless continued stepping is intentional evidence collection. Use
`ctx.step(...)` between meaningful or long phases so progress remains visible.

## Description and expected video

Both fields surface in result data and the HTML report.

- Write `description` in present tense from an asset-author perspective. Name
  the headline metric, threshold, or relevant configurable.
- Write `expected_video` as concrete visual cues a reviewer can verify. Do not
  write vague text such as "the test looks correct."
- Use plain text only; the report renders these fields as escaped paragraphs.

Example:

```python
description=(
    "Drives each non-passive joint and verifies measured velocity stays "
    "within the authored maximum plus velocity_tolerance_percent."
),
expected_video=(
    "Each joint moves alone, accelerates smoothly, and returns without a "
    "visible snap while the base remains fixed."
),
```

## Evidence and cleanup

Capture the smallest evidence set that explains the verdict. Use summary,
error, or worst-case media roles intentionally. A passing video should show the
entire behavior promised by `expected_video`; a failure should remain visible
long enough to diagnose.

Tests may remove only artifacts they created inside their owned output. Never
recursively clean a user-selected parent directory, and never delete source
assets, sibling dependencies, or pre-existing captures.

## Documentation contract

Every enabled registration must be documented exactly once. Add or update:

1. one per-test page under `docs/fet###/` (one page may cover a deliberately
   paired registration when both contracts and versions are identical);
2. the matching `docs/fet###-<family>.md` family page;
3. the visible family table and hidden toctree in `docs/tests.md` when adding a
   new family.

Each per-test page must include registration metadata (`Test name` or
`Test names`, `Feature(s)`, and `Test version`) and these content groups:

- `Summary`;
- `What Pass Guarantees`;
- `What It Checks`;
- execution details (`How It Works` or `Execution Model`);
- remediation (`How to Fix` or `Common Failure Modes`);
- expected evidence (`Expected Result` or `Evidence`).

Document config values as defaults, not immutable behavior. Keep feature IDs,
test versions, engine constraints, supported runtimes, phase order, thresholds,
and pass/fail/skip semantics synchronized with executable code.

These files are physically colocated with the suite but published at the stable
logical path `guides/benchmark/tests`. Author cross-reference links for that
published logical location. The tier root's `docs-sources.json` declares the
mapping; the generic docs assembler validates it and rejects duplicate logical
paths with different content.

Disabled registrations do not appear as shipped per-test coverage. Record them
only in [Experimental and disabled tests](experimental.md), including their
current `enabled=False` status.

## Verification

Run the narrowest checks first:

```bash
python -m pytest \
  nv_core/tiers/simready_foundation_tier_core/tests/runtime_tests/unit/test_benchmark_documentation.py
python -m pytest nv_core/tiers/_tooling/tests/test_assemble_docs.py
python nv_core/tiers/_tooling/assemble_docs.py --output <new-empty-output>
```

Then verify both discovery paths affected by the change:

```bash
# Source checkout
simready-benchmark --foundations-path <path-to-simready-foundations> --list-tests

# Clean environment with the built tier wheel installed
simready-benchmark --show-config
simready-benchmark --list-tests
```

For changed behavior, also run a scoped plan and the supported runtime engines.
Inspect JSON results and media rather than treating process completion alone as
a behavioral pass.
