# SimReady Foundation Core Tier

## Purpose

The `simready-foundation-tier-core` distribution contains the core SimReady
profiles, features, requirements, validator rules, and tier-owned Evaluate
runtime tests, Kit-free feature adapters, and the SimReady integration for the
public Isaac Asset Transformer. It installs the Newton tier for the required
Newton contracts in Robot-Body and Robot-Gripper 4.0.0 and supports Python
3.11–3.13. Newton's Evaluate and simulator dependencies remain optional.

It is the baseline tier for general OpenUSD, visualization, physics, robotics,
semantic-label, non-visual-sensor, Isaac Sim, and packaging workflows. See the
[Core tier catalog](../../sr_specs/docs/shared/tiers/core.md) for the complete,
hyperlinked profile and feature inventory.

Install validation support:

```bash
pip install simready-validate
pip install simready-foundation-tier-core
```

Isaac transformation and schema tooling are opt-in. In a Python 3.12
environment, install the public Isaac packages from PyPI with:

```bash
pip install "simready-foundation-tier-core[isaac]"
```

A base core installation, including core installed as another tier's dependency,
does not pull in `isaacsim-asset-isolated` or `isaacsim-robot-schema`.

For uv's handling of the transitive `tinyobjloader` prerelease, see the
[installation guide](../../sr_specs/docs/guides/foundation_pypi.md#using-uv).

The optional Evaluate extra declares the compatible dependency range in
`pyproject.toml`. Install Evaluate and its Kit
engine dependencies to execute this tier's bundled runtime tests:

```bash
pip install "simready-foundation-tier-core[evaluate]"
```

Check the actual resolved `simready-evaluate` and
`simready.evaluate.engine-kit` versions together against the package metadata
for the installed tier. A declared range does not establish wheel availability
or installed provider compatibility.

Use a fresh Python 3.12 environment for Evaluate. Current runtime tests live
under the owning tier namespace; the former flat suite imports are retired.
For an explicitly chosen historical environment, optional manual cleanup of
the retired standalone runtime-test distributions is separate maintenance:

```bash
pip uninstall simready-benchmark-kit-suite simready-foundation-runtime-tests-kit
```

Those retired distributions used the old `simready_benchmark_kit_suite` flat
package. The current Core package is `simready.foundation.tier_core.runtime_tests`;
its old flat name remains a provider alias, not a Python import shim. The old names above are
historical distribution identifiers, not packages to install for Evaluate.

The runtime-test modules are inert until Evaluate discovers their path through
the tier's `simready.tier` descriptor. Validator-only installs therefore do not
pull the optional Isaac packages, Evaluate, or its Kit engine dependencies. During development,
`--foundations-path <checkout>` selects the catalogs and tests from a Foundation
source checkout; `--tests-path` adds a separate unpublished test package.

## Contents

The tier owns the core, hierarchy, visualization, physics-bodies, Isaac Sim,
non-visual sensor, packaging, and semantic-label capability groups, together
with their features and profiles. The Isaac static optimization capabilities
ship separately in `simready-foundation-tier-isaac`. The wheel also carries
tier-owned feature adapters and the profiles, patches, and CLI that integrate
the public Isaac Asset Transformer. Copy
`simready_foundation_tier_template` when you need a new additive tier that
depends on this core package. Core stays standalone-installable because
dependent tiers point *at* it, never the reverse.

The wheel also provides the dependency-light Foundations 2 contract boundary:

- `simready.foundation.contracts` parses CAP-prefixed static contracts, dotted
  runtime-tested feature IDs, and profile selectors, then resolves several
  profile targets.
- `simready.foundation.validation` produces required/optional requirement plans
  and runtime evidence for the validator backend.

The Foundations 2 catalogs live directly in `tier_core/capabilities/`,
`tier_core/features/`, and `tier_core/profiles/`. `catalog-map.json` maps legacy
Foundations 1 identities to their dotted contracts for compatibility; there is
no separate `foundations2/` catalog tree. Published contract versions remain
immutable. After adding or renaming contract pages, regenerate the shared
feature/capability documentation hubs with
`python nv_core/tiers/_tooling/migrate_foundations2_catalog.py --write-hubs`
from the repository root; its other migration modes are not a catalog build step.

## Layout

```text
simready_foundation_tier_core/
|-- pyproject.toml
|-- README.md
|-- simready/foundation/tier_core/
|   |-- __init__.py, _plugin.py, _tier.py
|   |-- rules_and_reqs/
|   |-- capabilities/
|   |-- features/
|   |-- profiles/
|   `-- catalog-map.json       # legacy identity to dotted contract mapping
|-- simready/foundation/tier_core/runtime_tests/
|   |-- README.md
|   |-- docs/
|   `-- fet*/ and shared runtime helpers
|-- tests/runtime_tests/unit/
`-- tools/
    |-- asset_handler_modules/
    `-- isaac_asset_transformer/
```

The committed tier package ships as-is. The shared Hatch build hook generates
`simready/foundation/tier_core/requirements/` from the capability Markdown and
adds those enums to the wheel. Runtime-test documentation is colocated with the
test package and assembled into the public Foundation guide from that single
source.

## Discovery

The wheel advertises three entry points:

- `usd_validation_nvidia` -> `simready.foundation.tier_core:SimReadyPlugin`
  lets the validator discover rules and requirements.
- `simready.tier` -> `simready.foundation.tier_core:tier` lets validation and
  Evaluate discover the tier's requirement module, catalogs, profile sources,
  and optional runtime-test package.
- `simready.feature_adapters` ->
  `simready.foundation.tier_core.asset_handler_modules:get_feature_adapters`
  lets derivation consumers discover the tier's Kit-free feature adapters
  lazily. Adapters that need an optional extra, such as the Isaac composition
  adapters and `[isaac]`, are offered only when that extra is installed.

The tier-owned tests do not use the `simready.evaluate.tests` entry-point group;
that group is reserved for independent test-only distributions.

It also installs the `simready-transform-asset` command for direct access to the
bundled SimReady integration for the public Isaac Asset Transformer.

## Build

From the repository root:

```bash
./repo.sh build_tiers
```

On Windows use `repo.bat build_tiers`. Wheels are written to
`nv_core/tiers/_build/dist/`.

See `docs/local-wheel-end-to-end.md` for the isolated local-wheel workflow and
`simready/foundation/tier_core/runtime_tests/docs/authoring.md` for runtime-test authoring.
