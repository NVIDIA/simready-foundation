# Authoring SimReady Foundation runtime tests

This document defines the Foundation-specific contract for tests in
`simready.foundation.tier_core.runtime_tests`. Framework APIs such as `@test`, `RunContext`,
engine sessions, and media capture are owned by the installed
`simready-evaluate` package. Verify those APIs against the installed code and
its `write-test-pack` skill before changing a test.

## Ownership and discovery

Public identities are declared in the test-root `benchmark-provider.json`, not
derived from internal folders. Core uses
`simready.foundation.tier_core.runtime_tests`, Newton uses
`simready.foundation.tier_newton.runtime_tests`, and Sensors uses
`simready.foundation.sensors.runtime_tests`. This is a public namespace, not a
Python module to import. New `runtime_tests` bindings and CLI selectors use
`<namespace>:<test-name>`. Existing suite prefixes remain explicit aliases;
the change does not alter feature requirements or test behavior. Keep this JSON
in the built wheel and preserve distinct import packages across tiers.
Evaluate packs without the declaration retain their legacy basename identity.
The alternate `evaluate-provider.json` declaration is accepted; dual declarations
must agree after normalization. Regular packages can infer omitted import
ownership from physical ancestry; namespace packages require `import_package`.
Provider aliases do not restore the removed Benchmark Python SDK. Current tier
code requires its declared Evaluate dependencies; an unchanged old tier importing
`simready_benchmark` needs its matching Benchmark environment.

A runtime test belongs in this package when it provides behavioral evidence for
a feature owned by the core Foundation tier. The tier's `simready.tier`
descriptor exposes this importable package through `runtime_tests_path`.
Resolving that descriptor must only compute paths; it must not import this
package, Kit, Isaac Sim, or `pxr`.

Use a different ownership model when appropriate:

- A test for another tier belongs in that tier's own importable test package.
- An independent published test-only wheel registers an importable package in
  the `simready.evaluate.tests` entry-point group.
- An unpublished development package can be added with `--tests-path`; the path
  must name the package directory containing `__init__.py`.

Installed tier tests, independent entry-point packs, and explicit development
paths are additive. Do not create another `runtime_tests` container between a
tier wheel and its importable package.

### Engine-specific procedures split across tiers

A test belongs to the tier that owns its bound feature contracts. For
Foundation 2, the owning manifests' `runtime_tests` entries are authoritative;
keep `@test(features=...)` claims consistent with those contracts rather than
treating the decorator as a substitute for a binding. Core FET003/FET004 and
driven-joint procedures execute PhysX and declare only Core-owned features.
Newton owns its FET003/FET004 and
driven-joint procedures, registrations, defaults, scene setup, motion adapters,
and verdict logic in `simready.foundation.tier_newton.runtime_tests`. Newton registrations
retain their suffixed test names (for example `ground_drop_newton`).

Do not import or re-decorate a Core test coroutine or its metadata in Newton.
Do not leave unused Newton verdict or actuation branches inside the PhysX-only
Core procedures. Engine-neutral utilities may be reused where they contain no
test verdict, scene policy, or engine-specific defaults; that dependency must be
declared by the consuming tier.

Core's shared engine integration remains where unchanged Core-owned contracts
require it. Grasp `FET005_Grasp.0-1-0` and gripper
`FET028_Gripper.Isaac.0-1-0` remain in Core (legacy aliases
`FET_005_STANDARD` and `FET_028_ISAAC`). The existing scene/robot handles,
scene-init guards, and temporary-articulation helpers retain legacy and
experimental Newton paths; this does not declare published Newton gripper
coverage. The Isaac gripper contract routes to PhysX. These helpers are not
unused copies of Newton-owned FET003/FET004 procedures. PhysX FET004 also
retains loose-joint articulation wrapping to avoid unstable maximal-coordinate
drives. Removing the Newton-owned tests must not remove these required paths.

Core FET003/FET004/FET022/FET028 procedures reject an accidental non-PhysX invocation as a
test/engine setup mismatch before accessing the scene; the asset is not
evaluated by that misrouted test. Do not convert this error into an asset failure.
Select a Newton-owned procedure only where it exists; Core's published gripper
close/lift bindings have no Newton counterpart.

## Package layout

Each FET family has a package named `fet###_<topic>`. Keep independently
reportable tests in separate modules, and place engine-neutral calculation or
discovery helpers outside the async test coroutine so they can be unit tested
without launching Kit.

```text
simready/foundation/tier_core/runtime_tests/
  fet003_physics/
    __init__.py
    ground_drop.py
    ground_stability.py
    slope_drop.py
  docs/
    fet003-physics.md
    fet003/
      ground-drop.md
      ground-stability.md
      slope-drop.md
```

Shared articulation helpers live in `articulation_phases/`. Reuse the suite's
scene, context, cleanup, configuration, and test helpers rather than creating a
parallel framework.

Discovery directly scans every non-underscore Python file, including helpers
without decorators, under a synthetic top-level module name. Use qualified
absolute imports in scanned files and their coroutines. Pure helpers whose
names begin with an underscore are skipped by the scanner and can use
relative imports when imported through their real package. Full source and
installed-wheel discovery are required checks; ordinary package import alone
does not validate the direct-file import context. Public provider namespaces
are not necessarily importable Python package names.
A selected root that disappears or cannot be enumerated, including an
unreadable subdirectory, also fails discovery rather than silently omitting
tests. Exact-file dispatch needs the advertised root set to remain available.
Restore provider access before interpreting the inventory as complete.

## Registration contract

Decorate an `async def` coroutine with the public `@test` decorator. The current
registration contract requires:

- `features`: one or more dictionaries with a canonical Foundation feature ID
  and decorator version constraint. For a Foundation 2 dotted ID, its contract
  version is already part of the ID; use `version="*"` as in the current
  registrations. Legacy catalogs use a separate semantic version constraint;
- `name`: a unique stable test identifier;
- `description`: an actionable plain-text statement of the tested behavior;
- `expected_video`: plain-text visual cues for a passing recording;
- `version`: the semantic version of the runtime-test contract.

Optional metadata includes `engine`, `config_defaults`, `max_duration`, and
`enabled`. The current decorator has no `requirement` argument. Describe the
requirement or behavioral promise in the registration text and matching
Foundation documentation instead.

Use exact current dotted IDs, such as `FET003_RigidBody.PhysX.0-4-0` and
`FET003_RigidBody.Newton.0-1-0`. Confirm them against the owning tier's
feature manifests and profile selectors. The final segment is the contract's
opaque version token, not the independently versioned runtime-test procedure.
Underscore IDs such as `FET_003_PHYSX` are published legacy aliases, not new
Foundation 2 identities. Do not invent compatibility aliases.

### Feature binding and provider identity

The decorator advertises executable metadata. For Foundation 2, the owning
feature manifest's `runtime_tests` entries are the feature-to-test bindings.
A current Foundation 2 registration advertises the exact dotted contract:

```python
@test(
    features=[{"id": "FET004_Multibody.PhysX.0-4-0", "version": "*"}],
    name="joint_movement",
    # ...
)
```

The owning manifest must also bind
`simready.foundation.tier_core.runtime_tests:joint_movement`. Copying a
decorator alone does not add a Foundation 2 runtime obligation. New or changed
published bindings require the normal contract-versioning review.

For comparison, a **legacy-catalog compatibility** registration uses the
historical identity and separate version constraint:

```python
@test(
    features=[{"id": "FET_004_PHYSX", "version": ">=0.1.0"}],
    name="joint_movement",
    # ...
)
```

For a legacy catalog, Evaluate matches the decorator's feature ID and version
constraint against the selected profile, asset validation, or explicit
`--features` filter. For Foundation 2, it uses the manifest's exact
`<provider>:<test-name>` entries for planning, reports, and stamps. Keep test
names stable and update the manifest bindings when a provider package changes.

Core owns `simready.foundation.tier_core.runtime_tests`; Sensors owns
`simready.foundation.sensors.runtime_tests`; Newton owns
`simready.foundation.tier_newton.runtime_tests`. Their wheels must not install the same
top-level test package. Historically, Benchmark `2026.9.0-dev1` introduced
Foundation 2 manifest-owned bindings. For current Evaluate installations, use the tier's
`evaluate` extra and its declared metadata requirements. Core and Newton
currently require Evaluate[kit] `>=2026.9.0rc2,<2026.11` and engine-kit
`>=2026.9.0rc3,<2026.11`, admitting compatible prerelease and stable updates
within this API generation. When using unpublished local wheels,
install the built tier wheels together rather than resolving their dependencies
against older published tiers.

Keep runtime compatibility at the behavior boundary. Robot setup verifies the
actual room handle's composed floor collision and visibility before physics,
including on older supported Kit wheels. Visual encoding scopes optional
warning/timing isolation to one context and restores its callbacks afterwards;
it leaves engine encoding, media validation, cancellation and worker retirement
unchanged. These safeguards do not change asset criteria or require equal wheel
version labels. Older reporters retain raw pivot skips; newer assessment-aware
reporters can present the same completed-advisory metric explicitly.

Family labels such as `FET001` are derived grouping and filter names. They do
not replace exact dotted contract IDs such as
`FET001_MinimalPlaceableVisual.1-0-1`, and a single family may contain
tests for several runtime variants. Audits that verify feature attribution must
resolve each manifest's provider-qualified `runtime_tests` bindings to enabled
registrations and check the advertised decorator claims against the catalog.
Do not infer the manifest ID from a `fet###_<topic>` package name, a
`fet###-<family>.md` filename, or a `FET###` documentation heading.

Provider identity controls discovery, not feature ownership. The core tier
advertises the `simready.foundation.tier_core.runtime_tests` import package through its tier
descriptor. An independent test-only wheel advertises its package through the
`simready.evaluate.tests` entry-point group, and an unpublished package is
added with `--tests-path`. In all three cases, keep `name` unique and stable so
users can select the exact test with `--tests`.

Bump the test version whenever verdict logic, observable behavior, or evidence
semantics change. Test versions are executable contract data. Declared engine
version constraints are metadata, not an enforced scheduling gate; required
native capabilities must be checked at execution, preserving setup errors.
Keep both declarations in the documentation and parity tests. Do not copy a
Evaluate wheel release number into examples unless it is a real compatibility
floor enforced by package metadata.

## Configuration and outcomes

Put tunable thresholds and time budgets in `config_defaults`. Avoid hidden
asset-specific exceptions. A test should produce the same verdict from the
same asset, engine, configuration, and initial state.

Validate verdict-critical configuration before a phase discovers/commands
joints or advances its evaluated simulation. Require finite real numeric
thresholds in their documented domains, whole-number counts and actual
booleans for policy flags; do not coerce a string/bool or silently clamp an
invalid value into a permissive criterion. NaN/infinity can make comparisons
false and fabricate a PASS. Valid zero tolerances remain exactness policies
where supported. Invalid configuration is an execution/configuration error,
not an asset FAIL or applicability skip. Add regressions that prove rejection
before excitation as well as valid boundary-value behavior. Phase-owned
`config_validation` helpers cover the robot procedures; unknown or inactive
compatibility keys are not new behavioral obligations.

Use outcome methods deliberately:

- `ctx.fail(...)` records a tested contract violation.
- `ctx.skip(...)` records established absence of applicable behavior. It is
  not a substitute for reporting a backend mismatch, failed scene import,
  unavailable required runtime API, or a test setup exception as an incomplete
  execution/error;
- `ctx.precheck_failure(...)` is for an asset/runtime precondition discovered
  before the behavioral phases begin. It records fail or skip according to the
  asset's validation claim and raises `PrecheckAborted` to unwind the test.

`fail()` and `skip()` do not terminate the coroutine. Return explicitly after
them unless continued stepping is intentional evidence collection. Preserve
setup/import exceptions for the runner to report as errors; they do not prove
an asset defect or successful coverage. Use `ctx.step(...)` between meaningful
or long phases so progress remains visible.

Before a clean applicability skip, publish `assessment_applicability` through
`ctx.add_metric` with `status: not_applicable`, a stable `reason_code`,
and the actual skip `reason`. The marker does not override failed or
interrupted execution. Missing required inputs, setup, readback, solver or
backend support supply NO VERDICT through the execution-error path. Legacy or
unmarked skips supply NO VERDICT until their applicability is established.
Do not assign into `ctx.metrics`, which can be a copy. Falling/sliding
applicability markers require an active, enabled FixedJoint owned by the asset
and connecting its rigid body to the world/static frame; ambiguous legacy
anchor skips remain unmarked.

Absence-based applicability requires a complete concrete composition of the
full owned asset, including sibling controller subtrees and instance proxies.
The population mask must include the full asset subtree. Unloaded, undefined
or abstract owned content and failed inventory queries leave applicability
unknown. Any stage composition error also conservatively withholds proof;
it does not attribute an outside-asset error to the asset or create asset FAIL.
A proxy-aware composition inventory alone does not establish that a legacy
detector inspected proxy controls. Cached
passive or standalone classifications from partial discovery cannot supply
that proof. When source inspection is unqualified, withhold the N/A marker and
retain the original skip; the test remains Could not assess. This qualification
does not change load state, physical eligibility, commands or response criteria.

Qualify the producer's actual inspected dependencies as well as its owned root.
Semantic absence proof includes authored direct/collection bindings, collection
sources, resolved materials and visited ancestry outside the asset. A bound
source not inspected by the strip, including a subset material reached through
an inherited or collection binding, cannot supply positive absence evidence.
World/static-anchor proof qualifies resolved
joint endpoints and their rigid-body ancestry, including external endpoints.
Missing, masked, unloaded, undefined, abstract or unresolved required sources
withhold the marker. Mimic absence checks raw active authored coupling
independently of the mapped selection; an empty selection cannot erase active
authored followers omitted by joint mapping. Preserve the original unmarked
skip and its cause; qualification
neither loads those dependencies nor adds stripping or physics behavior.

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
    "within the resolved runtime comparison ceiling plus "
    "tolerance_percent. This response does not by itself prove "
    "authored hard-cap enforcement."
),
expected_video=(
    "Each joint moves alone, accelerates smoothly, and returns without a "
    "visible snap while the base remains fixed."
),
```

## Evidence and cleanup

For independent-hand configuration and optional scoped PhysX contact reporting,
see [Configured hand trials](fet028/hand-trial-controls.md). Preserve default
qualification separately from configured trials, validate held as well as
closing coordinates, and treat actual native cleanup failures as runtime health.

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

Review source docstrings and report-facing `description`/`expected_video` too.
Compare their claims against the actual predicates: all trials versus any trial,
observed measurements and units, proxy limitations, nominal versus live time,
wall-clock budgets, and evidence actually emitted. Inspect description builders
with both defaults and representative overrides. The metadata and link checks
below do not establish that a prose PASS guarantee is true; include an independent
semantic comparison after test changes, without changing criteria to match prose.

These files are physically colocated with the suite but published at the stable
logical path `guides/evaluate/tests`. Author cross-reference links for that
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
simready-evaluate --foundations-path <path-to-simready-foundations> --list-tests

# Clean environment with the built tier wheel installed
simready-evaluate --show-config
simready-evaluate --list-tests
```

For changed behavior, also run a scoped plan and the supported runtime engines.
Inspect JSON results and media rather than treating process completion alone as
a behavioral pass.
