# SimReady Foundation Newton Tier

The `simready-foundation-tier-newton` distribution contains the Newton runtime
physics features, the `NEWTON.*` requirements those features reference, and the
validator rules that enforce them (rigid bodies, multibody, driven joints, and
base articulation for the Newton solver).

## Independence

The validation package is independent of Core Python code: base dependencies
name no Core tier, and its few validator helpers are local. Full profile
validation still needs the Core requirements referenced by Newton feature
contracts. Newton owns its Evaluate runtime helpers and does not install Core.
Installing Core automatically installs this tier for its required Newton
profile contracts.

Install validation support. For full validation of the Newton gates in a
robot/prop profile, install both tiers together:

```bash
pip install simready-validate simready-foundation-tier-core simready-foundation-tier-newton
```

Installing this tier alone is supported at the package level, but its features
cannot be fully validated without Core, because they reference Core requirement
codes.

## Contents

### Capabilities

- **`physics_bodies/base_articulation`** — `NEWTON.BA.001` (Newton articulation root config)
- **`physics_bodies/physics_driven_joints`** — `NEWTON.DJ.001-003` (Newton joint drive API, joint attributes, mimic API)
- **`physics_bodies/physics_materials`** — `NEWTON.MAT.001` (Newton material attributes)
- **`physics_bodies/physics_rigid_bodies`** — `NEWTON.COL.001/002`, `NEWTON.MAS.001` (Newton collider API, SDF attributes, mass attributes)

### Feature families

Canonical feature catalogs use `FET003_RigidBody.Newton`,
`FET004_Multibody.Newton`, `FET004_Multibody.RobotNewton`, and
`FET022_DrivenJoints.Newton` families. Core/runtime and articulation gates are
capabilities: `CAP000_Core.Newton` and `CAP024_BaseArticulation.Newton`.
Use the installed catalog's exact versioned identity; legacy `FET_###_*` IDs
are compatibility/display aliases, not new contract identities.

## Layout

```text
simready_foundation_tier_newton/
|-- pyproject.toml
|-- README.md
|-- docs-sources.json
|-- simready/foundation/tier_newton/runtime_tests/   # Newton-owned Evaluate runtime implementation
`-- simready/foundation/tier_newton/
    |-- __init__.py, _plugin.py, _tier.py
    |-- rules_and_reqs/
    |-- features/
    |-- profiles/
    `-- skills/            # conform skills for this tier's features
```

The shared Hatch build hook generates
`simready/foundation/tier_newton/requirements/` from the capability Markdown and
adds those enums to the wheel.

## Skills

This tier is the source of truth for the conform skills of the features it owns
(`simready-foundation-conform-fet-*-newton`), under
`simready/foundation/tier_newton/skills/`. They ship in the wheel and are
exposed through the tier descriptor's `skills_path`, so a consumer that
enumerates installed tiers can discover them (the same pattern the external
`simready-validate` / `simready-evaluate` / `simready-package` libraries use for
their bundled skills). For monorepo development the repository root `skills/`
tree aggregates them via symlinks, so root-based agent discovery
(`.claude` / `.codex` / `.agents`) still sees every skill.

## Evaluate suite

This tier ships `simready.foundation.tier_newton.runtime_tests`, discovered through
`runtime_tests_path`. Its canonical provider is
`simready.foundation.tier_newton.runtime_tests`, also the Python import package.
The former flat name remains a provider alias; Python code uses the namespaced
import. Public `_newton` test names and feature bindings are
unchanged.

Newton owns the FET003 ground/slope procedures, FET004 multibody procedure, and
all nine FET022 phases, including their decorators, configuration defaults,
verdicts, scene setup, actuator/tensor backend, and motion-evidence adapter.
Core `run_*` functions and Core `*_KWARGS` metadata are not imported.
Independent changes can now be reviewed by the Newton test owner without
changing Core/PhysX verdicts. Do not keep copying later solver-specific Core
changes into this implementation.

Newton owns `placement_compat` for presenting an asset and
`articulation_phases.error_utils` for diagnostics. Its optional Evaluate
dependencies supply the runner and engine:

```bash
python -m pip install "simready-foundation-tier-newton[evaluate]"
```

FET022 evaluates the asset's authored control configuration; FET004's
constraint-movement probe uses explicitly test-owned temporary drive/force
setup. Diagnostic histories do not decide pass/fail, never change controls,
and are optional when the installed runner does not implement recording.
Times are nominal observed-step estimates and capture ticks are excluded.
Missing readbacks stay null/partial, not fabricated measurements.

Newton close/lift gripper contracts are **not** introduced. Core's published
Isaac sphere/cube gripper bindings remain unchanged; these are not proof of
Newton gripper conformance. A separately owned, versioned Newton gripper
contract and phase implementation remain a follow-up. Neutral compatibility
helpers remain in Core where still used, but its active FET028
close/lift procedure is PhysX-only and has no Newton execution branch.
`ground_stability_newton` 3.0.2 is enabled as an independent sampled-settling
procedure alongside `ground_drop_newton` 4.0.2. A drop PASS alone does not satisfy
a feature requiring stability. Existing public bindings are unchanged; create a
fresh plan to discover the qualified procedure. Other unavailable experimental
bindings remain honest coverage gaps, not implied support.

See the bundled [Newton runtime-test and motion-evidence guide](simready/foundation/tier_newton/runtime_tests/docs/runtime-tests.md)
for observation sources, clocks, partial evidence and the qualified distinction
between a velocity comparison ceiling and an actuator effort-speed envelope.
It also describes test-owned ramp materials, the downhill-only exit allowance,
the multibody probe's any-one-joint aggregate, and setup/coverage limitations.
Shared stop/commit and contact-capacity behavior belongs to the matching
Evaluate version's public **Kit Plugin → API → PhysicsHandle** and **Kit Plugin
Concepts** documentation. Locate the installed **diagnose-failures** skill using
`simready-evaluate --skills-path`; an execution error is not an asset defect.

## Discovery

The wheel advertises two entry points:

- `usd_validation_nvidia` (`simready-validate-newton`) -> `simready.foundation.tier_newton:SimReadyPlugin`
  lets the validator discover rules and requirements.
- `simready.tier` (`newton`) -> `simready.foundation.tier_newton:tier` lets
  validation and Evaluate discover the tier's requirement module, catalogs, and
  profile sources.

## Build

From the repository root:

```bash
./repo.sh build_tiers
```

On Windows use `repo.bat build_tiers`. Wheels are written to
`nv_core/tiers/_build/dist/`.
