# Proposal: Split the Benchmark Suite by Owning Tier

- **Status:** Executed on `dev/sboochoon/tier_newton` (Option B). See §11 for what
  was done and two recon-driven corrections to §5/§6. Still pending: a
  benchmark-engineer runtime pass (engine->tier routing, §8.2) — none of this was
  runtime-validated (no Isaac Sim / Kit / Newton in the authoring environment).
- **Scope owner:** SimReady Foundation + the `simready-benchmark` library maintainer
- **Related:** `nv_core/tiers/simready_foundation_tier_core/simready_benchmark_kit_suite`,
  `simready-benchmark`, `simready-benchmark-engine-kit`,
  `proposals/tier-newton-extraction-proposal.md`

## 1. Summary and goal

The tier-newton extraction moved Newton **requirements, validators, and
features** into `simready-foundation-tier-newton`. The one remaining Newton
surface still in `tier-core` is the **runtime benchmark suite**
(`simready_benchmark_kit_suite`), which contains Newton-specific behavior.

Goal: make each tier own the benchmark tests for the engines it owns.
`tier-core` keeps the tests exercising its engines (Standard / PhysX / MuJoCo);
`tier-newton` gets the tests exercising Newton. Concretely, an engine-parametrized
file like `fet003_physics/ground_drop.py` would exist in **both** tiers — the core
copy tests the FET-003 drop under Standard/PhysX/MuJoCo, and the newton copy tests
it under Newton. The newton copy reuses the shared, engine-neutral scaffolding by
**importing it directly from the core suite** — a deliberate, one-directional
`tier-newton -> tier-core` dependency at the benchmark layer (never the reverse).

## 2. How the benchmark suite works today

- **One suite in tier-core.** `simready_benchmark_kit_suite` ships in the
  `tier-core` wheel and is discovered through the tier descriptor's
  `runtime_tests_path`. Its `__init__.py`: *"Tests are discovered from the owning
  tier's runtime_tests_path descriptor field."*
- **Tests are feature-keyed.** Each test is an `async def` decorated with the
  `@test` decorator (owned by the `simready-benchmark` package), declaring
  `features` (canonical Foundation feature ID + semver) and a unique `name`.
- **Engine-parametrized execution.** Tests run under whichever physics engine the
  run configures. `simready-benchmark-engine-kit` provides the engine abstraction
  (`active_physics_engine()`, `physics_utils`, `fabric_utils`, `force_display`).
  `engine_guard.py` holds *"engine-aware guards shared across the physics test
  families"* — it branches on the active engine and handles Newton's stricter
  scene-init behavior. A single test can map the active engine to the feature it
  reports (e.g. `grasp_and_lift.py` maps `"newton" -> "FET_003_NEWTON"`).
- **Shared scaffolding lives in the core suite.** Scene setup, phases, discovery,
  and assertions are shared modules in the suite (e.g. `fet005_grasp/grasp_scene.py`,
  `grasp_phases.py`, `fet004_multibody/joint_discovery.py`, and the
  `articulation_phases/` helpers). Authoring guidance: *"Reuse the suite's scene,
  context, cleanup, configuration, and test helpers"* and keep engine-neutral
  helpers outside the async coroutine.
- **Newton helpers are imported by core tests.** `fet004_multibody/newton_drive.py`
  and `fet005_grasp/newton_articulation.py` are Newton-specific helpers, imported
  at module top by core test families (`joint_movement.py`, `grasp_and_lift.py`,
  `grasp_robot.py`, `grasp_scene.py`) and invoked behind
  `active_physics_engine() == "newton"` guards. Two unit tests
  (`tests/runtime_tests/unit/test_fet004_newton_drives.py`,
  `test_newton_articulation.py`) exercise those helpers.

## 3. The library already supports per-tier tests (discovery is solved)

`docs/authoring.md` is explicit:

> A test for another tier belongs in that tier's own importable test package.
> ... Installed tier tests, independent entry-point packs, and explicit
> development paths are additive.

So a `tier-newton` benchmark package, exposed via that tier's `runtime_tests_path`
(or registered through the `simready_benchmark.tests` entry-point group), is
discovered additively alongside the core suite. **Discovery is not the blocker.**

## 4. The real problems to solve

1. **Shared-scaffolding placement (the crux) — decision: Option B.** Splitting
   `ground_drop.py` into a core copy and a newton copy means the shared,
   engine-neutral body (scene, phases, discovery, assertions) must be reachable by
   both. **Chosen approach:** keep that shared scaffolding in the **core** benchmark
   suite (`simready_benchmark_kit_suite`) and have the newton tests **import it from
   core** — a deliberate, one-directional `tier-newton -> tier-core` dependency at
   the benchmark layer. The considered options were:
   - **A: promote shared scaffolding into a shared base library** —
     `simready-benchmark-engine-kit` or a new `simready-benchmark-core` package.
     Rejected: it over-disaggregates the suite (a third package to own/version) for
     little benefit given newton is an extension of core.
   - **B (chosen): leave shared scaffolding in the core suite; newton imports it** —
     a one-directional `tier-newton -> tier-core` benchmark import edge. This is
     acceptable because newton is already a downstream extension of core; the one
     hard rule is that the edge must stay one-directional, which requires removing
     today's `tier-core -> newton` edge (see problem 2).
   - **C: duplicate scaffolding into both tiers** — high divergence risk. Rejected.
2. **Remove the current `tier_core -> newton` code edge (required for Option B).**
   Today core test families top-level-import `newton_drive` / `newton_articulation`.
   After the split those Newton helpers live in `tier-newton`, so core's tests must
   **stop importing them** — otherwise the split would create a `tier-core ->
   tier-newton` edge that, combined with the new `tier-newton -> tier-core` import,
   forms a cycle. Because the calls are already engine-gated
   (`active_physics_engine() == "newton"`), the core copies simply drop the Newton
   path entirely (they only run under core engines); the Newton path becomes the
   newton-tier copy. This is what keeps the dependency strictly one-directional.
3. **Engine -> tier routing.** Today one test runs under any configured engine.
   After the split, the harness must run the **core** copy for Standard/PhysX/MuJoCo
   runs and the **newton** copy for Newton runs, keying on the test's declared
   `features` (feature IDs are already engine-specific: `FET_003_STANDARD/PHYSX/
   MUJOCO` vs `FET_003_NEWTON`). Confirm the `simready-benchmark` run/plan model
   selects tests by feature/engine this way.

## 5. Proposed design

- **Ownership by feature ID.** A benchmark test lives in the tier that owns the
  feature it declares in `@test(features=...)`. Core-engine tests
  (`FET_*_STANDARD/PHYSX/MUJOCO`) stay in `tier-core`; Newton tests
  (`FET_*_NEWTON`) move to a new `tier-newton` benchmark package.
- **Per-FET split of engine-parametrized files.** For each engine-parametrized
  test (see inventory), produce a core copy (core engines only, Newton path
  removed) and a newton copy (Newton only) in the respective tier suites.
- **Shared scaffolding stays in core; newton imports it.** The engine-neutral
  scene/phase/discovery/assertion helpers and `engine_guard` remain in the core
  suite (`simready_benchmark_kit_suite`). Newton tests import them from there, e.g.
  `from simready_benchmark_kit_suite.fet005_grasp.grasp_scene import ...`. Keep
  engine-specific helpers with their engine's tier (`newton_drive`,
  `newton_articulation` -> `tier-newton`).
- **`tier-newton` benchmark package.** Add a newton benchmark test package with the
  Newton test families + the two Newton helpers, expose it via the tier
  descriptor's `runtime_tests_path` (the field exists on all tier descriptors;
  core/sensors/aif set it, newton currently leaves it unset), and ship it in the
  wheel. It **requires `tier-core` installed** (for the shared-scaffolding imports),
  which is the normal deployment.
- **Dependency direction (one-way).** `tier-newton` benchmark -> `tier-core`
  benchmark only. There is **no `tier-core` -> `tier-newton` edge** once core's test
  copies drop the Newton path (problem 2). `tier-core` remains buildable and
  runnable without `tier-newton`.

## 6. Inventory (engine-parametrized vs engine-agnostic)

Engine-parametrized families (need a core/newton split):

- `fet003_physics` (`ground_drop`, `ground_stability`, `slope_drop`)
- `fet004_multibody` (`joint_movement` + the `newton_drive` helper)
- `fet005_grasp` (`grasp_and_lift`, `grasp_robot`, `grasp_scene`, `phase_grasping`,
  + the `newton_articulation` helper)
- `fet022_driven_joints` (drive-gain, effort-limit, full-range-sweep, IK,
  mimic-joint, multi-joint, state-accuracy, velocity-limit)
- `fet028_gripper` (`gripper_close_lift`)
- `articulation_phases/` (shared physics phase helpers used across the above)

Engine-agnostic families (stay in `tier-core`, no Newton variant):

- `fet001_visual` (`pivot`), `fet006_materials`, `fet010_standard`,
  `fet011_semantics`.

Newton-specific units to move with the Newton tests:
`fet004_multibody/newton_drive.py`, `fet005_grasp/newton_articulation.py`, and
their two unit tests.

## 7. Worked example — `fet003_physics/ground_drop.py`

- **Shared scaffolding (stays in core):** the drop scene builder, settle/measure
  phases, and the drop-distance/stability assertions remain in
  `simready_benchmark_kit_suite/fet003_physics/` (core) as engine-neutral helpers.
- **`tier-core` copy:** `@test(features=[FET_003_STANDARD, FET_003_PHYSX,
  FET_003_MUJOCO], name="fet003-ground-drop")`, runs the shared drop scenario
  under the active core engine; no Newton import or branch.
- **`tier-newton` copy:** in the newton benchmark package,
  `@test(features=[FET_003_NEWTON], name="fet003-ground-drop-newton")`, imports the
  shared drop scaffolding and `engine_guard` from `simready_benchmark_kit_suite`
  (core) and runs the scenario under Newton with the Newton scene-init checks.

## 8. Open decisions (need the benchmark engineer)

1. **Core suite as an import surface for newton.** Option B makes the core benchmark
   suite a de-facto public API that newton imports. Confirm the shared modules
   newton needs (scene/phase/discovery/assertion helpers, `engine_guard`) are stable
   to import from `simready_benchmark_kit_suite`, and decide whether to mark them as
   an intentional cross-tier API (vs private). `engine_guard` stays in core (it
   references Newton only by engine-name string, no `tier-newton` import).
2. **Engine -> tier routing:** does the `simready-benchmark` plan/run model select
   the right tier's test per engine purely from `@test(features=...)`, or is extra
   routing needed?
3. **`tier-newton` test packaging:** tier `runtime_tests_path` vs a
   `simready_benchmark.tests` entry-point pack — which is preferred for a tier?
4. **Naming/`name` uniqueness** across tiers (e.g. suffix `-newton`) and whether
   report/plan tooling assumes a single suite.
5. **Docs:** per-tier `docs/` benchmark pages (each tier documents its own tests).

## 9. Risks

- **Divergence** between core and newton copies of a scenario — mitigated by
  keeping all engine-neutral logic in the shared core-suite modules and making the
  tier copies thin engine-bound entry points that import them.
- **Dependency direction** — Option B is only safe if the edge is strictly
  `tier-newton -> tier-core`. Core's suite must never import the newton suite/tier;
  otherwise a `tier-core -> tier-newton` edge reappears and creates a cycle. A CI
  check that greps Core's suite for `simready_benchmark_newton_suite` / `tier_newton`
  imports guards this. (Note: `newton_drive` / `newton_articulation` are Core-local
  helpers and are *not* the guard target — see §11 Correction A.)
- **Core suite becomes a cross-tier import surface** — newton depends on core's
  shared modules staying importable/stable; treat them as an intentional API.
- **Library-capability assumptions** — the routing/discovery model must be
  confirmed against the installed `simready-benchmark` before executing.
- **Unit-test placement** — the two Newton unit tests stay in Core with the
  helpers they exercise (see §11 Correction A); they are not relocated.

## 10. Phased roadmap

0. **Confirm library model (gate).** With the benchmark engineer, confirm per-tier
   test discovery + engine/feature routing, and that a one-directional
   `tier-newton -> tier-core` benchmark import is acceptable.
1. **Keep the core suite free of any `tier-newton` import.** Split the
   engine-parametrized core tests so the core copies declare only their
   Standard/PhysX/MuJoCo features; the shared engine-neutral scaffolding — including
   the `newton_drive` / `newton_articulation` USD-authoring helpers, which are
   Core-local, not cross-tier (see §11 Correction A) — stays where it is in the core
   suite (no behavior change for core engines). Add a CI grep guard against
   `tier-core -> tier-newton` / `simready_benchmark_newton_suite` imports.
2. **Scaffold the `tier-newton` benchmark package** + `runtime_tests_path` +
   wheel packaging; declare its dependency on `tier-core` for the shared imports.
3. **Split one family end-to-end** (e.g. `fet003_physics`) as the pilot: core copy
   (core engines, Newton removed) + newton copy (Newton) that imports the shared
   scaffolding from the core suite; verify a Newton run selects the newton copy and
   a PhysX run selects the core copy.
4. **Split the remaining families that declare a Newton feature** (`fet004`,
   `fet022`). Per §11 Correction B, `fet005` and `fet028` declare no Newton feature
   and do not split; per Correction A the `newton_drive` / `newton_articulation`
   helpers and their unit tests stay in Core.
5. **Docs + validation:** per-tier benchmark docs; run the full suite under each
   engine with both tiers installed and confirm parity with today's results.

## 11. Execution notes (what was actually done)

Executed on `dev/sboochoon/tier_newton`. Recon of the real suite overturned two
assumptions baked into §5/§6, so the executed shape differs from the draft in two
important ways. Neither weakens Option B; both make it cleaner.

**Correction A — the Newton USD-authoring helpers stay in Core (they are not
moved).** §5/§6 assumed `newton_drive` / `newton_articulation` move to the newton
tier. In practice each is engine-neutral USD-authoring scaffolding consumed by a
*shared body that stays in Core*:

- `newton_drive` is used only by `fet004/joint_movement`, whose body is
  engine-parametrized (it picks the PhysX or Newton drive path per joint-type at
  runtime via `active_physics_engine()`, interleaved throughout a ~2600-line
  function). That body cannot be bisected into a "Core path" and a "Newton path"
  without duplicating almost the whole function. So the body stays whole in Core
  and both tier copies import it; `newton_drive` therefore must stay importable by
  Core and stays in the Core suite. Moving it would either force that duplication
  or create a `tier-core -> tier-newton` import (a cycle with the benchmark edge).
- `newton_articulation` is used only by the `fet005` grasp helpers, and the single
  grasp test (`grasp_and_lift`) declares **only `FET_005_STANDARD`** — there is no
  `FET_005_NEWTON`. By the §5 ownership-by-feature-ID rule that test is Core-owned
  and does not split, so its private helper `newton_articulation` (and its unit
  test) stay in Core too.

The key invariant Option B needs is still satisfied: there is **no `tier-core ->
tier-newton` edge**. `newton_drive` / `newton_articulation` are *intra-Core*
helpers, not cross-tier. The CI guard should therefore grep Core's suite for
imports of `simready_benchmark_newton_suite` / `tier_newton` (there are none), not
for `newton_drive` / `newton_articulation` (which are legitimately Core-local).

**Correction B — `fet005` and `fet028` do not split.** `grasp_and_lift`
(`FET_005_STANDARD`) and the `fet028` gripper tests (`FET_028_ISAAC`) declare no
Newton feature; they run under Newton via the same engine-parametrized mechanism
and stay entirely in Core. Only families that *declare* a Newton feature split:
`fet003` (`FET_003_NEWTON`), `fet022` (`FET_022_NEWTON`), and `fet004`
(`FET_004_NEWTON` + `FET_004_ROBOT_NEWTON`).

**What was created / changed:**

- New Core-owned top-level package name would collide across wheels, so the newton
  benchmark package is a distinct top-level package:
  `simready_benchmark_newton_suite`, shipped by the `tier-newton` wheel and
  discovered through `runtime_tests_path` (added to `tier_newton/_tier.py`, which
  gained the same `_owned_package_directory` resolver Core uses).
- `tier_newton/pyproject.toml`: added a `benchmark` optional-dependency extra that
  pulls `simready-foundation-tier-core` (plus `simready-benchmark[kit]`,
  `usd-core`). The tier's core `dependencies` still name no tier — validation stays
  independent; the one-directional `tier-newton -> tier-core` edge is confined to
  the benchmark extra.
- Shared-body pattern: each split Core test file now exposes an engine-neutral
  `run_<name>(ctx)` coroutine plus a `<NAME>_KWARGS` dict of decorator metadata;
  the Core `@test` decorates it with the Core engine features (Newton removed), and
  the newton copy in `simready_benchmark_newton_suite` imports `run_<name>` +
  `<NAME>_KWARGS` and re-decorates with the Newton feature(s) and a `_newton`
  suffixed `name`. Split: `fet003` (3), `fet022` (9), `fet004/joint_movement` (1)
  = 13 newton copies, all importing one-way from `simready_benchmark_kit_suite`.
- Verified: `py_compile` passes for every changed/created file; the Core suite
  contains zero imports of the newton suite/tier (only doc comments reference it).

**Not yet done (needs a runtime environment / the benchmark engineer):**

- Engine->tier routing (§8.2): confirm a Newton run selects the `_newton` copies
  and a PhysX/MuJoCo run selects the Core copies purely from `@test(features=...)`,
  and that test `name` uniqueness across tiers is handled by plan/report tooling.
- A full suite run under each engine with both tiers installed, confirming parity
  with today's results. None of the above was runtime-validated here.
- Per-FET doc feature-table sync (`simready_benchmark_kit_suite/docs/**`) to drop
  the Newton feature from Core test rows and document the newton copies.
