# SimReady Foundation Core Tier

The `simready-foundation-tier-core` distribution contains the core SimReady
profiles, features, requirements, validator rules, and tier-owned Benchmark
runtime tests. It has no dependency on another Foundation tier.

Install validation support:

```bash
pip install simready-validate simready-foundation-tier-core
```

Install the optional Benchmark framework and Kit engine dependencies needed to
execute this tier's bundled runtime tests:

```bash
pip install "simready-foundation-tier-core[benchmark]"
```

The runtime-test modules are inert until Benchmark discovers their path through
the tier's `simready.tier` descriptor. Validator-only installs therefore do not
pull Benchmark, Kit, or Isaac dependencies. During development,
`--foundations-path <checkout>` selects the catalogs and tests from a Foundation
source checkout; `--tests-path` adds a separate unpublished test package.

## Contents

The tier owns the core, hierarchy, visualization, physics-bodies, Isaac Sim,
non-visual sensor, packaging, and semantic-label capability groups, together
with their features and profiles. Isaac content briefly shipped in a separate
tier and is currently consolidated here.

## Layout

```text
simready_foundation_tier_core/
|-- pyproject.toml
|-- README.md
|-- simready/foundation/tier_core/
|   |-- __init__.py, _plugin.py, _tier.py
|   |-- capabilities/
|   |-- features/
|   `-- profiles/
|-- simready_benchmark_kit_suite/
|   |-- README.md
|   |-- docs/
|   `-- fet*/ and shared runtime helpers
`-- tests/runtime_tests/unit/
```

The committed tier package ships as-is. The shared Hatch build hook generates
`simready/foundation/tier_core/requirements/` from the capability Markdown and
adds those enums to the wheel. Runtime-test documentation is colocated with the
test package and assembled into the public Foundation guide from that single
source.

## Discovery

The wheel advertises two entry points:

- `usd_validation_nvidia` -> `simready.foundation.tier_core:SimReadyPlugin`
  lets the validator discover rules and requirements.
- `simready.tier` -> `simready.foundation.tier_core:tier` lets validation and
  Benchmark discover the tier's requirement module, catalogs, profile sources,
  and optional runtime-test package.

The tier-owned tests do not use the `simready_benchmark.tests` entry-point group;
that group is reserved for independent test-only distributions.

## Build

From the repository root:

```bash
./repo.sh build_tiers
```

On Windows use `repo.bat build_tiers`. Wheels are written to
`nv_core/tiers/_build/dist/`.

See `docs/local-wheel-end-to-end.md` for the isolated local-wheel workflow and
`simready_benchmark_kit_suite/docs/authoring.md` for runtime-test authoring.
