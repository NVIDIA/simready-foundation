# SimReady Foundation — Newton Tier (AI Context)

This is durable context for AI assistants working on the
`simready-foundation-tier-newton` package. It is written so an agent can
understand and work on this tier **standalone** (when this directory, not the
full Foundation monorepo, is the working root).

## What this tier is

`simready-foundation-tier-newton` is a separately publishable SimReady Foundation
tier that owns the **Newton-solver physics** contracts: the `NEWTON.*`
requirements, their validators, and the Newton runtime features. A tier is a
Python package discovered through the `simready.tier` and `usd_validation_nvidia`
entry points; installed tiers layer additively into the shared validation
registry.

## Independence from the Core tier

This tier's validation code is **package/code independent** of `simready-foundation-tier-core`:

- No `pyproject` dependency on tier core, and **no import of Core Python code**
  in the validation layer. The few shared validator helpers are duplicated locally in
  `simready/foundation/tier_newton/rules_and_reqs/_common.py`.
- Its features reference Core requirement/capability IDs (`RB.*`, `JT.*`, `RV.*`,
  `CAP000_Core`, `CAP024_BaseArticulation`) as **runtime content**, resolved from
  the merged registry **when both tiers are installed**. So this tier is
  independent at the package level, but full validation of its features needs
  Core installed too:

  ```bash
  pip install simready-validate simready-foundation-tier-core simready-foundation-tier-newton
  ```

The Newton runtime-variant scaffolding (`RV.004`-`RV.006`) and cross-runtime
purity/isolation (`RV.010`-`RV.011`) stay in Core's `runtime_variants`
capability; this tier's features reference them.

## What this tier owns

Requirements + validators (in `simready/foundation/tier_newton/rules_and_reqs/physics_bodies/...`):

| Code | Capability | Validator |
|---|---|---|
| `NEWTON.BA.001` | base_articulation | `NewtonArticulationRootConfig` |
| `NEWTON.DJ.001` | physics_driven_joints | `NewtonJointDriveAPIChecker` |
| `NEWTON.DJ.002` | physics_driven_joints | `NewtonJointAttributesChecker` |
| `NEWTON.DJ.003` | physics_driven_joints | `NewtonMimicAPIChecker` |
| `NEWTON.MAT.001` | physics_materials | `NewtonMaterialAttributesChecker` |
| `NEWTON.COL.001` | physics_rigid_bodies | `NewtonColliderAPIChecker` |
| `NEWTON.COL.002` | physics_rigid_bodies | `NewtonSDFAttributesChecker` |
| `NEWTON.MAS.001` | physics_rigid_bodies | `NewtonMassAttributesChecker` |

Features (in `simready/foundation/tier_newton/features/`):
`FET003_RigidBody.Newton`, `FET004_Multibody.Newton`,
`FET004_Multibody.RobotNewton`, and `FET022_DrivenJoints.Newton`.
Capabilities (in `capabilities/`): `CAP000_Core.Newton` and
`CAP024_BaseArticulation.Newton`. Use exact versioned catalog IDs in contracts;
legacy `FET_###_*` labels are compatibility/display aliases only.

## Skills

This tier is the source of truth for the conform skills of the features it owns,
under `simready/foundation/tier_newton/skills/`:

- `simready-foundation-conform-fet-000-newton`
- `simready-foundation-conform-fet-003-newton`
- `simready-foundation-conform-fet-004-newton`
- `simready-foundation-conform-fet-004-robot-newton`
- `simready-foundation-conform-fet-022-newton`
- `simready-foundation-conform-fet-024-newton`

They are discoverable three ways: (1) standalone, via this directory's
`.claude/skills`, `.agents/skills`, `.codex/skills` symlinks; (2) in the
Foundation monorepo, aggregated into the repo-root `skills/` tree; (3) for pip
consumers, through the tier descriptor's `skills_path`
(`simready.foundation.tier_newton:tier`), mirroring how the external
`simready-validate` / `simready-evaluate` / `simready-package` libraries expose
their bundled skills. Use a skill's `SKILL.md` as the procedural source of truth
before editing an asset.

## Evaluate suite

This tier owns `simready.foundation.tier_newton.runtime_tests`, canonically
`simready.foundation.tier_newton.runtime_tests`. Keep the shipped `_newton`
test names and exact versioned dotted feature IDs; aliases are not ownership.

- FET003/FET004/FET022 decorators, defaults, verdicts, scene setup, and Newton
  backend helpers are local. Never import Core `run_*` procedures or `*_KWARGS`.
- Placement and diagnostic helpers are owned locally. Newton has no Core Python
  imports or package dependency, including in its Evaluate extras.
- Core installs Newton for its required profile contracts. Keep the dependency
  direction Core-to-Newton. Do not copy future PhysX phase changes wholesale:
  each solver owner reviews its own behavior and diagnostics.
- Recording is optional. Hooks observe existing commands/readbacks, issue no
  additional commands, add no simulation ticks, preserve null readbacks, and
  label nominal observed-step time and partial evidence honestly. Test/report
  contracts are documented by Evaluate's test-writing guidance.
- Newton close/lift gripper support is an explicit gap, not an implied feature.
  Leave published Core Isaac sphere/cube bindings unchanged. Do not infer Newton
  conformance from Core's legacy experimental grasp/gripper paths.
- Keep disabled experiments disabled unless separately reviewed/versioned.
- Runtime geometry canaries require complete finite live body poses and owned
  geometry and required-cleanup worker retirement through
  the current `evaluate` extra's `simready.evaluate[kit]` and
  `simready.evaluate.engine-kit` requirements, respectively
  `>=2026.9.0rc2,<2026.11` and `>=2026.9.0rc3,<2026.11`. These bounds admit compatible prerelease and stable
  updates within this API generation. Missing required state is
  a setup/runtime error, not an authored
  rest-pose or zero-box fallback. Explicit authored bounds are for setup/reach
  heuristics; optional camera framing is not verdict evidence. Install the tier
  extra to apply both declared compatible requirements.
- Verify composed room-floor collision and visibility in the Newton-owned setup
  before starting physics. The check preserves stronger USD opinions and does
  not depend on a newer Kit bug-fix release or import a new Core helper.

```bash
python -m pip install "simready-foundation-tier-newton[evaluate]"
```

## Standing rules

- Prefer native OpenUSD patterns (schemas, composition arcs, relationships,
  metadata) over inventing custom properties.
- Derive physical values from the actual asset; never fabricate a value to force
  a pass. Report the single remaining blocker if a value cannot be derived.
- Published feature and requirement versions are immutable; adopt new behavior by
  adding a new version, not by editing a shipped one.
- Work on requested staged output; never silently mutate a source asset. Before
  editing shared repository files, check `git status` for unrelated in-progress
  changes and scope edits to the task; never revert, overwrite, discard, stash,
  or commit a user's uncommitted or unrelated changes.
- Keep secrets out of the repository and evidence: never write user-provided
  tokens, credentials, or API keys into files, logs, reports, or commits, and do
  not echo them in full.
- Keep this tier's validation package/code independent of tier core: do not add a `pyproject`
  dependency on it or import its Python modules. If a Newton validator needs a
  helper that also exists in core, duplicate it into `rules_and_reqs/_common.py`.

## Validation

```bash
# With both tiers installed, validate an asset that pins Newton features.
simready-validate --profile Robot-Body --version 2.2.0 path/to/asset.usd
```
