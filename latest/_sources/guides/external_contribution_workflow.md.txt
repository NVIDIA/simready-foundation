# External Contribution Workflow

This guide connects the repository's tier, requirement, feature, profile,
sample-content, and Evaluate documentation into one contribution path. It is
for an external developer proposing specification behavior against
[`NVIDIA/simready-foundation`](https://github.com/NVIDIA/simready-foundation).

```{important}
Start with a GitHub issue to agree on scope, tier ownership, and branch access.
A maintainer can create an upstream working branch and arrange access, or
coordinate a fork. Public branches support specification development; a
maintainer confirms the review route before submission. Run local checks and
retain evidence because contributor branches have no guaranteed hosted CI.
```

GitHub calls the final review object a **pull request (PR)**. It is equivalent
to a merge request (MR) in systems that use that term.

## What the workflow must prove

Each stage closes a different risk. Do not start with a profile and fill in the
lower layers afterward: implement the contract from the atomic rule upward.

| Step | Question answered | Required evidence |
|---|---|---|
| 0. Make branch | Is the work isolated and based on current upstream? | Agreed upstream branch or fork, clean LFS checkout, linked issue |
| 1. Determine tier | Does this belong in an existing tier, or is a new tier needed? | Tier decision and dependency/portability rationale |
| 2. Define contract | Is the behavior documented, testable, and selectable? | Requirement docs, validator rules, feature manifest/docs, profile pin/docs |
| 3. Sample content | Does a real asset demonstrate the contract? | Licensed, portable LFS asset that passes the intended static gate |
| 4. Evaluate | Does the promised behavior work in a runtime? | Discovered test, plan, result JSON, logs/media, HTML report |
| 5. Make PR/MR | Can reviewers reproduce and assess the complete change? | Focused diff, commands/results, limitations, issue link |

Static validation and runtime evaluation are complementary. A validator proves
that the required USD data is authored; an evaluation proves that the resulting
asset behaves as promised in the target runtime.

## Before you begin

Read the current
[`CONTRIBUTING.md`](https://github.com/NVIDIA/simready-foundation/blob/main/CONTRIBUTING.md),
open an issue
describing the use case, and get agreement on scope and tier ownership. Include:

- the asset class and runtime behavior;
- the gap in existing requirements, features, and profiles;
- whether the proposal is runtime-neutral or runtime/vendor/domain-specific;
- the sample asset and runtime that can provide end-to-end evidence;
- any schema, package, or license dependencies.

Install Git LFS before cloning because USD files and images are LFS-managed.
Use Python 3.12 in a dedicated virtual environment for the complete validation
and Evaluate workflow. See the repository
[`README.md`](https://github.com/NVIDIA/simready-foundation/blob/main/README.md)
for platform-specific setup.

## Working with an AI agent

An agent can inspect the repository, implement the specification surfaces,
author or repair staged USD content, run available checks, and prepare review
material. It cannot decide ambiguous asset intent, tier ownership, or acceptance
policy for the maintainers. It also must not claim that static checks prove
runtime behavior.

Start every agent task with these instructions:

```text
Read AGENTS.md and the complete SKILL.md for every applicable SimReady skill
before editing. Inspect the current tier, neighboring artifacts, and published
versions first. Preserve unrelated work and published capability, feature, and
profile versions. Run the narrowest relevant checks, state unavailable
tools or blocked runtime evidence explicitly, and report changed files,
commands, results, and remaining gaps.
```

Use the task-specific skill rather than asking the agent to improvise the
repository workflow. Repo-local skills live under `skills/`:

| Work | Skill |
|---|---|
| Add or update a capability | `simready-foundation-add-capability` or `simready-foundation-update-capability` |
| Add or update a requirement | `simready-foundation-add-requirement` or `simready-foundation-update-requirement` |
| Add or update a validator | `simready-foundation-add-validator` or `simready-foundation-update-validator` |
| Add or update a feature | `simready-foundation-add-feature` or `simready-foundation-update-feature` |
| Add or update a profile | `simready-foundation-add-profile` or `simready-foundation-update-profile` |
| Add or update an adapter | `simready-foundation-add-feature-adapter` or `simready-foundation-update-feature-adapter` |
| Add runtime evidence | `simready-foundation-add-runtime-test`, followed by the installed Evaluate skills |
| Audit the complete change | `simready-foundation-validate-foundation-change` |

When validating, evaluating, or packaging an asset, have the agent discover
and follow the skills bundled with `simready-validate`, `simready-evaluate`, or
`simready-package`. For example,
`simready-evaluate --skills-path` locates the Evaluate skills matching the
installed CLI. Repo-local skills own Foundation source layout and contract
wiring; library skills own the corresponding tool mechanics.

## 0. Make a branch

A public reader can create a local branch or fork. Creating or pushing an
upstream branch requires repository Write access, subject to repository rules.
If you need upstream access, open a contribution-branch issue using the format
in [CONTRIBUTING.md](https://github.com/NVIDIA/simready-foundation/blob/main/CONTRIBUTING.md).
The maintainer creates the branch, records its work owner, arranges access, and
confirms the base and review target. Work ownership in an issue is separate from
GitHub permissions.

For a maintainer-created upstream branch, clone the public repository and track
the confirmed branch (replace `<assigned-branch>`):

```bash
git clone https://github.com/NVIDIA/simready-foundation.git
cd simready-foundation
git fetch origin
git switch --track origin/<assigned-branch>
git lfs pull
git lfs ls-files
```

If the maintainer coordinates a fork instead, replace `<user>` and
`<issue>-<topic>` below:

```bash
git clone https://github.com/<user>/simready-foundation.git
cd simready-foundation
git remote add upstream https://github.com/NVIDIA/simready-foundation.git
git fetch upstream
git switch -c <issue>-<topic> upstream/main
git lfs pull
git lfs ls-files
```

Use one branch for one coherent contract change. Before editing, record the
baseline checks that pass in your environment. Do not commit generated build
trees, Evaluate run directories, virtual environments, or installed
dependencies.

### Agent instructions

An agent may inspect remotes and create the local topic branch. Creating a
remote fork, pushing, or opening a PR must be covered by the user's
authorization and the maintainer-confirmed contribution route. A suitable instruction is:

```text
Inspect the current branch, remotes, worktree changes, and Git LFS setup. Do
not discard or overwrite existing work. Create local branch <issue>-<topic>
from the agreed upstream ref, verify LFS materialization, and report the exact
base commit. Do not push or open a pull request.
```

**Gate:** the branch is based on the intended upstream ref, LFS objects are
materialized rather than pointer text, and the proposal has a tracking issue.

## 1. Determine whether you need a new tier

A tier is the ownership and distribution boundary for requirements, rules,
features, profiles, and any runtime tests. First determine whether the proposal
fits an existing tier. Do not create a new tier merely because the proposal
adds a capability, feature, or profile.

Use these questions with the tier maintainers:

1. Does an existing tier already own this domain and its requirement namespace?
2. Is the behavior consistent with that tier's portability claim?
3. Can the proposal depend on existing requirements and features without
   changing their meaning?
4. Can the owning tier distribute the required validators, dependencies,
   samples, and runtime tests?

If the answer is yes, place the work in that existing tier and continue to
step 2:

- Use the **core tier** for behavior that is broadly agreed across runtimes and
  vendors.
- Use an existing runtime-, vendor-, or domain-specific tier for a narrower
  contract that falls within that tier's ownership. Such content can still be
  production quality; its portability claim is simply narrower.

If no existing tier is an appropriate owner, define a new tier. Prefer a
separate downstream tier for organization-specific or independently
distributed behavior. A downstream tier may depend on and reference upstream
Foundation content without modifying or redefining it. Add a new tier to this
repository only when the maintainers accept its ownership, distribution, and
review model.

When a new tier is required, follow
[SimReady Foundation PyPI Packages](foundation_pypi.md#creating-your-own-tier).
At minimum, define its package name and owner, upstream dependencies,
portability claim, versioning policy, `pyproject.toml`,
`usd_validation_nvidia` and `simready.tier` entry points, dependency-light tier
descriptor, package initializers, and rules_and_reqs/capabilities/features/
profiles directories.
For an in-repository tier, add it to `nv_core/tiers/pyproject.toml`; do not
modify the shared builder merely to enumerate it.

If the new tier owns runtime tests, place its importable test package in
`simready/foundation/<tier-module>/runtime_tests/`, alongside `features/` and
`profiles/`. Its wheel must include that package, and its descriptor must expose
that directory through `runtime_tests_path`. The descriptor must not import
Kit, Isaac Sim, `pxr`, or the tests merely to resolve its content paths.

Document the decision in the issue or design note:

```text
Owner: <tier/package>
Decision: <use existing tier or create new tier>
Upstream dependencies: <tiers and versions>
Portability claim: <cross-runtime or scoped runtime/domain>
Why an existing tier is sufficient, or why none is appropriate: <rationale>
```

### Agent instructions

Ask the agent to determine whether a new tier is necessary before scaffolding
files:

```text
Evaluate the proposed <behavior> against the existing tiers, requirements,
features, profiles, and runtime-test providers. First determine whether it fits
an existing tier; prefer that tier when its ownership and portability claim
match. If none fits, explain why and recommend a separate downstream tier or a
new in-repository tier. Cite the repository files that support the decision and
identify package dependencies, entry points, portability claims, and review
owners. Do not create a new tier until ownership is confirmed.
```

If the choice changes the public portability claim or conflicts with existing
contracts, the agent must stop with the alternatives and request the maintainer
decision. Once ownership is confirmed, instruct it to scaffold only the agreed
tier. If that is a new tier, have it verify both entry-point groups from a
built wheel.

**Gate:** maintainers agree that the proposal belongs in the selected existing
tier or that a new tier is necessary. Package dependencies are one-way, and the
proposal does not redefine an upstream requirement.

## 2. Define the requirement, rule, feature, profile, and docs

Implement this layer bottom-up. Reuse an existing requirement or feature when
it already expresses the behavior. Published capability, feature, and profile
versions are immutable; contract changes require new versions.

For an in-repository tier, the relevant source layout is:

```text
nv_core/tiers/<tier-directory>/
├── pyproject.toml
├── simready/foundation/<tier-module>/
│   ├── rules_and_reqs/<domain>/<requirement-group>/
│   │   ├── requirements/<requirement>.md
│   │   ├── requirements.md
│   │   └── validation.py
│   ├── capabilities/       # Dotted CAP JSON definitions and docs
│   ├── features/           # Dotted FET JSON definitions and docs
│   ├── profiles/           # Selector TOMLs and authoring docs
│   └── runtime_tests/      # Importable Evaluate test procedures
└── tests/
    └── runtime_tests/unit/ # Focused tests for the runtime procedures
```

### 2.1 Requirement and validation rule

A requirement is one atomic, testable statement. Add it beneath the owning
requirement group's `requirements/` directory under `rules_and_reqs/` and
register it in that group's
`requirements.md`. Use a unique, stable code in the capability's namespace.
The requirement page must explain the rule, why it matters, passing and failing
examples, how to comply, related requirements, and authoritative references.

Add or update the requirement group's `validation.py` so the requirement has an
executable rule with requirement-specific failure messages. Update the package
`__init__.py` registration path when needed. Test at least:

- a passing asset;
- a failing asset that isolates this rule;
- edge cases and not-applicable behavior;
- rule discovery/registration.

Do not invent custom USD properties when OpenUSD already represents the
concept with schemas, APIs, relationships, metadata, or composition arcs.

### 2.2 Capabilities, features, and contract documentation

Publish reusable static requirement bundles as CAP definitions under
`capabilities/`. Runtime-tested contracts belong under `features/`. Both use a
single dotted identity, `<name>[.<runtime>].<version>`, for example:

```text
capabilities/CAP007_NonVisualMaterials.0-2-0.json
capabilities/CAP007_NonVisualMaterials.md
features/FET004_Multibody.PhysX.0-4-0.json
features/FET004_Multibody.PhysX.md
```

Neutral contracts omit the runtime segment; runtime-specific contracts keep it.
The `id` is the only identity field; do not duplicate `name`, `runtime`, or
`version`. Preserve the version token exactly, including leading zeroes. A
contract change creates a new version; published definitions stay immutable.

Runtime-tested FETs declare executable `runtime_tests`,
`additional_requirements`, and `adapters`. A testless FET has `source=true` and
must be named by at least one tested derived FET through `source_feature`.
Other static contracts are capabilities. `source_feature` records provenance;
it does not inherit requirements. Use `dependencies` when the whole source
contract must validate, and `capabilities` for required static contracts.

Dependencies are exact IDs and must resolve without cycles. Keep matching
markdown alongside the JSON and follow [Features](features/features.md) and
[the feature template](features/feature-template.md). Register new definitions
in the shared indexes and dependency graph. For the relocated catalog, use the
[catalog migration tooling](foundations2-layout-migration.md) to regenerate hubs
and links; do not hand-edit `catalog-map.json`.

A technology-specific expansion may replace a conflicting base requirement;
it must not silently stack mutually exclusive rules. If moving between exact
feature contracts requires USD mutation, add a direct
[feature adapter](feature_adapters/feature_adapters.md) and validate its output.

### 2.3 Profile and profile documentation

A profile selects features and capabilities for an asset class or target runtime.
Add a new profile in its own tier-owned TOML file unless the tier deliberately
uses an established catalog file. Add a new table entry for a new version; do
not rewrite a published entry. Keep the profile markdown and the shared profile
index synchronized with the TOML, which is the machine-readable source of
truth.

Selectors may be exact dotted IDs or one-to-three-segment wildcards, with
optional selectors in either the feature or capability list. Resolve them
against all installed tiers, sort and deduplicate matches, and let a required
path win over an optional path. An unmatched required selector is an error;
an unmatched optional selector creates no obligation. Validate each requested
profile/version independently; do not infer one exclusive profile from asset
metadata. See [Profiles](profiles/profiles.md).

Document required versus optional contracts,
expected asset type, runtime assumptions, validation commands, migration or
adapter paths, and sample and evaluation evidence.

### 2.4 Run contract checks

Build the tiers to exercise requirement-enum generation and wheel packaging.
The builder requires `uv` on `PATH`. Install `uv`, then run this command from
the repository root:

```bash
python nv_core/tiers/_tooling/build_tiers.py
```

The wheels are written to `nv_core/tiers/_build/dist/`. Install the newly
built wheel in a clean environment, then prove entry-point discovery and run
static validation against the new profile:

```bash
python -c "from importlib.metadata import entry_points; print([ep.name for ep in entry_points(group='simready.tier')])"
simready-validate --profile <Profile-Name> --version <profile-version> path/to/sample.usd
```

During source development, use the local paths or project configuration
documented by [SimReady Validation Workflow](validate_workflow.md). A wheel-only
test is still required because it catches missing package data and entry-point
wiring that a source checkout can hide.

### Agent instructions

Give the agent the accepted behavior, owner, IDs or ID namespace, intended
versioning impact, and success evidence. Then let it route each surface to the
matching add/update skill. For example:

```text
Implement the accepted <behavior> in tier <tier>. Use the applicable
simready-foundation add/update skills for the capability or requirement,
validator, feature, profile, and adapter. Work bottom-up from the atomic
requirement. Preserve published versions and add new versions when behavior
changes. Use dotted Foundations 2 IDs and profile selectors. Keep JSON/TOML
and markdown synchronized, update indexes and dependency documentation, add focused pass/fail/edge/discovery tests, build the
tier wheel, and validate <sample> against <Profile>@<version>. Finish with the
simready-foundation-validate-foundation-change audit and report any blocked
checks rather than weakening the contract.
```

If the feature can cause asset-level validation failures, also instruct the
agent to add or update the exact
`simready-foundation-conform-fet-###-<runtime>` skill. If automatic repair would
be unsafe or subjective, it should document the blocked case instead. In
particular, FET005 grasp-line repair requires visual evidence; the
agent must not guess a grasp region.

**Gate:** requirement docs and rule behavior agree; manifests and TOML parse;
all IDs and exact versions resolve; registration works from the built wheel;
the intended sample passes and the negative fixture fails for the expected
requirement.

## 3. Add sample content

Put a minimal, representative OpenUSD asset under the appropriate domain in
`sample_content/`. Prefer a small asset that makes the new behavior obvious and
keeps runtime results reproducible. Follow the neighboring asset layout rather
than creating a second convention.

The sample must:

- have a clear license and redistribution provenance;
- use relative, portable composition and texture paths;
- include all referenced layers and resources needed for the test;
- contain values derived from the asset rather than fabricated to pass;
- validate against the exact proposed profile/version;
- be linked from the feature and profile documentation;
- avoid unrelated production content or sensitive metadata.

USD files, images, and many source formats are tracked by Git LFS. Confirm that
new binary content is LFS-managed and inspect the staged diff for accidental
pointer or generated files:

```bash
git check-attr filter -- path/to/sample.usd path/to/thumbnail.png
git lfs status
git diff --check
```

Keep small known-bad fixtures with focused validator tests when practical; do
not present a deliberately invalid asset as a reference sample. Record the
static validation command and output summary used to qualify the sample.

### Agent instructions

Provide the source asset, output directory, exact target feature/profile, and
license/provenance facts. Do not ask the agent to fabricate missing physical or
semantic values merely to make validation pass:

```text
Create a staged reference sample for <Feature or Profile>@<version> from
<source asset>; never silently edit the source. Read and apply the exact
conform-fet skills in dependency order, derive physical and provenance values
from the asset, preserve relative dependencies, and stop on any value that
cannot be derived. Run the simready-validate library skill against the staged
root USD, confirm Git LFS coverage, and return the output paths, validation
report, provenance, and any blocked requirement.
```

For a brand-new sample authored directly in the contribution branch, replace
the staging instruction with an explicit destination and still require the
agent to preserve any supplied source. A vision-capable agent must inspect
render or viewport evidence for visual-semantic authoring such as grasp lines.

**Gate:** a fresh clone can resolve every dependency, the sample has reviewable
provenance, and static validation produces the expected result.

## 4. Add and run the evaluation

Add runtime evidence when the feature promises behavior that static inspection
cannot prove. A tier-owned test belongs in
`simready/foundation/<tier-module>/runtime_tests/`, the importable package named
by that tier's `runtime_tests_path`, with focused unit tests under the tier's
`tests/runtime_tests/unit/` tree. An independent or experimental test pack
should use Evaluate's independent-provider or `--tests-path` workflow instead
of being placed in an unrelated Foundation tier.

Before authoring, run `simready-evaluate --skills-path` and follow the
installed framework's `write-test-pack` skill; its API and CLI match the
installed version. Bind the test to the exact dotted FET contract through the
catalog's `runtime_tests` mapping and the provider's test metadata. Follow the
installed API for any family/version metadata; inspect `--list-tests` to verify
the effective binding. Do not add generated plans, result JSON, media, or
reports as test source, and do not hand-edit them.

Validate discovery and planning from the checkout. Replace
`EXACT_AVAILABLE_FEATURE_ID` with an ID reported by the installed inventory:

```bash
simready-evaluate --foundations-path . --show-config
simready-evaluate --foundations-path . --list-tests
simready-evaluate --foundations-path . --assets path/to/sample.usd --features EXACT_AVAILABLE_FEATURE_ID --plan-only
```

Then run the focused test in the supported engine without stamping the source:

```bash
simready-evaluate --foundations-path . --assets path/to/sample.usd --features EXACT_AVAILABLE_FEATURE_ID --no-stamp
```

Repeat discovery and at least a plan-only check from the clean environment
containing the built tier wheel, without `--foundations-path` or
`--tests-path`. This proves that published discovery works.

Review the resolved run directory, especially `run_summary.json`,
`report/test_results_index.json`, engine logs, captured media, and
`index.html`. Document engine/version, exact command, configuration/thresholds,
result, and artifact location. If the required runtime is unavailable, mark the
runtime check as blocked; unit tests and a successful plan are not a substitute
for behavioral evidence.

### Agent instructions

Require the repository-specific runtime-test skill and the installed Evaluate
skills in the same task:

```text
Add runtime evidence for <Feature>@<version> using
simready-foundation-add-runtime-test for repository placement and wiring.
Discover the installed simready-evaluate skills and follow write-test-pack for
the test API, run-tests for execution, and diagnose-failures if needed. Bind
the test to the canonical feature ID/version, add focused unit and registration
tests, update the tier-owned test docs, verify source and built-wheel discovery,
run plan-only, then execute with --no-stamp. Report engine/version, config,
pass/fail/skip result, metrics, logs/media, and report paths. Do not edit or
commit generated plans or reports as source.
```

If the runtime is unavailable, the agent should complete source, registration,
unit, discovery, and plan checks that do not need it, then report the runtime
execution as blocked and give the exact reproduction command.

**Gate:** the test is discoverable from both source and wheel, maps to the
correct feature version, plans only for applicable assets, runs reproducibly,
and its report demonstrates the feature's promised behavior.

## 5. Make the PR/MR

Record the branch, commit, design, and evidence in the coordinating issue.
Follow the maintainer-confirmed review route in
[CONTRIBUTING.md](https://github.com/NVIDIA/simready-foundation/blob/main/CONTRIBUTING.md).
A working branch is a place to develop the proposal; acceptance into main or a
release still requires Foundation review. The public mirror and internal
integration repository may have different branch names and acceptance steps.

Sync with the agreed base without rewriting another contributor's commits.
For a fork, `upstream` names NVIDIA's public repository; for an upstream branch,
`origin` names it. Confirm the correct remote and base before merging changes:

```bash
git fetch <base-remote>
git merge <base-remote>/<agreed-base>
git push origin <working-branch>
```

Open a draft pull request when the maintainer confirms its target and review
route. A maintainer coordinates integration and public-mirror publication.

The PR description should contain:

- the problem statement and linked issue;
- the tier choice and portability rationale;
- the requirement, capability, feature, and profile IDs/versions added or changed;
- the sample's license/provenance and expected static result;
- exact build, unit-test, validation, and Evaluate commands with outcomes;
- links or attachments for the Evaluate report and essential media;
- adapter/migration impact and compatibility notes;
- blocked checks, environmental limitations, and follow-up work.

### Agent instructions

An agent may perform the final audit and draft the PR before it has authority to
publish anything:

```text
Audit this branch with simready-foundation-validate-foundation-change. Review
the full diff for contract drift, generated artifacts, LFS mistakes, secrets,
and in-place edits to published versions. Run the available focused tests and
strict docs build. Draft a GitHub pull-request title and body containing the
issue, tier rationale, contract IDs/versions, sample provenance, exact commands
and results, evaluation evidence, compatibility impact, and blocked checks. Do
not push or open the pull request.
```

Push or open the PR when the user's authorization and the maintainer-confirmed
route cover that action. Resolve an ambiguous repository, base, head, or review
route before publication. Existing authorization does not need to be requested
again.

Keep generated Evaluate output out of the commit unless a specific docs page
intentionally uses a small reviewed artifact as evidence. Review the complete
diff, confirm that no published capability/feature/profile version changed, and run a
strict docs build:

```bash
python build_docs.py --strict
git diff --check
```

Request review from the owners of every affected tier and runtime. A change is
ready to merge only when its machine-readable contract, prose, static rule,
sample, runtime evidence, and packaging/discovery behavior tell the same story.

## Final review checklist

- [ ] Tracking issue and maintainer-approved scope exist.
- [ ] Tier ownership and upstream dependencies are explicit.
- [ ] Requirement ID is unique, indexed, documented, and registered to a rule.
- [ ] Passing, failing, edge, and discovery tests cover the validator.
- [ ] Capability/feature JSON and markdown agree on exact dotted IDs and immutable versions.
- [ ] Profile TOML and markdown agree; required and optional selectors resolve correctly.
- [ ] Required adapters or migration blockers are documented.
- [ ] Sample content is portable, licensed, LFS-managed, and statically valid.
- [ ] Runtime test is tier-owned or independently packaged as intended.
- [ ] Evaluate discovery, plan, run, and report evidence are recorded.
- [ ] Built-wheel discovery succeeds in a clean environment.
- [ ] Strict documentation build and diff checks pass.
- [ ] Maintainer-confirmed branch access and review route are recorded in the issue.

## Related guides

- [SimReady Foundation Tiers](tiers.md)
- [SimReady Foundation PyPI Packages](foundation_pypi.md)
- [SimReady Acceptance Workflow](acceptance_workflow.md)
- [Features](features/features.md)
- [Profiles](profiles/profiles.md)
- [SimReady Validation Workflow](validate_workflow.md)
- [SimReady Evaluate](evaluate/evaluate.md)
