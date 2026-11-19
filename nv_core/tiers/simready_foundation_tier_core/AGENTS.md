# SimReady Foundation — Core Tier (AI Context)

Durable context for AI assistants working on the `simready-foundation-tier-core`
package. Written so an agent can work on this tier **standalone** (when this
directory, not the full Foundation monorepo, is the working root). For the full
framework guidance (requirement/capability/feature/profile contract stack,
guides, and workflow), see the repository-root `AGENTS.md`.

## What this tier is

`simready-foundation-tier-core` is the baseline SimReady Foundation tier. It owns
the core, hierarchy, visualization, physics-bodies, Isaac Sim, non-visual sensor,
packaging, and semantic-label capability groups, together with their
requirements, validators, features, and profiles, plus the tier-owned Evaluate
runtime tests. It installs the Newton tier for the required robot profile contracts.

Runtime-specific physics content is split by solver:

- **Standard / PhysX / MuJoCo** requirements, validators, and features live here.
- **Newton** physics requirements, validators, and features live in the separate
  `simready-foundation-tier-newton` package, installed as a base dependency of
  Core. Newton owns its runtime helpers and has no reverse Core dependency or
  Core Python imports. Simulator execution extras remain optional.
  Robot-Body and Robot-Gripper `4.0.0` require the Newton rigid-body, multibody,
  driven-joint, Core, and articulation contracts. Earlier robot versions and
  prop profiles select Newton optionally. Required Newton selectors need both
  tiers installed.
- The runtime-variant scaffolding for all solvers (`RV.*`, including the Newton
  `RV.004`-`RV.006` variant set/payload/metadata and the cross-runtime purity
  `RV.010`-`RV.011`) stays here in the `core/runtime_variants` capability.

## Skills

This tier is the source of truth for the conform skills of the features it owns,
under `simready/foundation/tier_core/skills/` (the
`simready-foundation-conform-fet-*` skills for Standard/PhysX/MuJoCo/Isaac
features). Foundation-authoring skills (`add/update-*`, `validate-foundation-change`,
`create-package`) are **not** here — they live at the repository root because they
are about building the Foundation itself, not conforming assets to this tier.

Skills are discoverable three ways: (1) standalone, via this directory's
`.claude/skills`, `.agents/skills`, `.codex/skills` symlinks; (2) in the
monorepo, aggregated into the repo-root `skills/` tree; (3) for pip consumers,
through the tier descriptor's `skills_path`
(`simready.foundation.tier_core:tier`). Use a skill's `SKILL.md` as the
procedural source of truth before editing an asset.

## Standing rules

- Prefer native OpenUSD patterns over inventing custom properties.
- Derive physical values from the actual asset; never fabricate a value to force a
  pass. Report the single remaining blocker if a value cannot be derived.
- Published feature/requirement versions are immutable; add a new version rather
  than editing a shipped one.
- Work on requested staged output; never silently mutate a source asset. Check
  `git status` for unrelated in-progress changes before editing shared files, and
  never revert, overwrite, discard, stash, or commit a user's uncommitted or
  unrelated changes.
- Keep secrets out of the repository and evidence.
- Core depends on the Newton tier for required robot profile contracts. Keep
  Newton content in `simready-foundation-tier-newton` and avoid reverse Core
  dependencies or cross-tier Python imports.

## Validation

```bash
simready-validate --profile Robot-Body --version 3.0.0 path/to/asset.usd
```
