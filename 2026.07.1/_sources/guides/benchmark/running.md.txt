# Running Tests

This page walks through installing the `simready-benchmark` tool, configuring an
engine, and running tests against an asset. The installed-tier workflow does not
require a SimReady Foundation clone: the tier supplies both specifications and
runtime tests, while its optional Benchmark extra supplies execution dependencies.

## Prerequisites

Before you install, confirm the following:

| Requirement | Minimum |
|---|---|
| Python | 3.12 |
| Virtual environment | A dedicated venv for `simready-benchmark` and its dependencies |

## Install

Create and activate a virtual environment:

````{tab-set}
```{tab-item} Windows (PowerShell)
python -m venv .venv
.venv\Scripts\activate
```

```{tab-item} Linux
python -m venv .venv
source .venv/bin/activate
```
````

Install the core tier with its optional `benchmark` extra. The command respects
the package index and mirror already configured for `pip`:

```bash
pip install "simready-foundation-tier-core[benchmark]==2026.7.1" "simready-validate>=2026.7.0.dev1"
```

The extra installs `simready-benchmark[kit]>=2026.6.6`; the runtime-test modules
already ship in the tier. The validator is installed explicitly so Benchmark's
static validation gate uses the 7.1-compatible library. Benchmark discovers
both specification catalogs and the runtime-test directory through
`simready.tier`, so neither `--sr-specs` nor `--tests-path` is required for
published content. See the [Foundation 7.1 library set](../foundation_pypi.md#foundation-71-library-set)
for the complete compatibility matrix.

Use `--tests-path` only to add an unpublished test package during development.
Explicit paths are loaded in addition to installed test providers.

## Set Up the Engine

Validate installed providers and install pip Isaac Sim into the active Python
3.12 environment when it is not already present:

```bash
simready-benchmark --setup --install-isaac
simready-benchmark --show-config
simready-benchmark --list-tests
```

`--setup` validates installed tier and runtime-test providers and detects the
pip Isaac launcher. It does not create configuration files or persist a source
checkout. Use `--setup --no-install-isaac` when setup should diagnose only.

For an existing standalone Isaac Sim installation, create `engines.toml` in
the working directory or user configuration directory and point it at the
launcher:

```toml
[kit.isaac_sim]
executable_path = "PATH_TO_ISAAC_LAUNCHER"
tags = ["isaac", "kit"]

[kit.isaac_sim_newton]
executable_path = "PATH_TO_ISAAC_LAUNCHER"
tags = ["isaac", "kit"]
experience = "isaacsim.exp.full.newton"
```

The standalone launcher is `isaac-sim.bat` on Windows or `isaac-sim.sh` on
Linux. `--engines-toml FILE` selects an explicit configuration for one command.
An explicit file replaces automatic local pip-Isaac discovery.

## Use a Foundation Source Checkout

Use a checkout without rebuilding its tier wheel by passing the checkout root:

```bash
simready-benchmark --foundations-path PATH_TO_FOUNDATIONS --show-config
simready-benchmark --foundations-path PATH_TO_FOUNDATIONS --list-tests
```

`--foundations-path` selects the checkout's project configuration, tier
catalogs, and tier-owned runtime tests. It cannot be combined with
`--project-config`.

To make a checkout persistent, set its project configuration in the user
`engines.toml` instead of repeating the flag:

```toml
[paths]
project_config = "PATH_TO_FOUNDATIONS/sample_content/project_config.toml"
```

The `SIMREADY_PROJECT_CONFIG` environment variable provides the same override.

Discovery inputs have distinct purposes:

| Flag | Effect |
|---|---|
| `--foundations-path <DIR>` | Use one Foundation source checkout for catalogs, project configuration, and tier-owned tests. |
| `--project-config <FILE>` | Use an explicit project configuration; mutually exclusive with `--foundations-path`. |
| `--tests-path <DIR> [...]` | Add one or more trusted unpublished test packages. Installed providers remain active. |
| `--engines-toml <FILE>` | Use one explicit engine configuration for this command. |

## Run

Run the tests against an asset by path:

```bash
simready-benchmark --assets path/to/asset.usd
```

By default, the stamp stage copies the root USD into the run's `results/`
mirror and writes the benchmark receipt to that copy and its sibling
`.simready/validation.json`. It never modifies the source asset. Specify
`--no-stamp` to skip this step. Refer to
[The Runtime Stamp](reading-reports.md#the-runtime-stamp) for the output contract.

To force a specific feature's tests to run, regardless of the asset's validation status, add `--features`:

```bash
simready-benchmark --assets path/to/asset.usd --features FET_003_STANDARD
```

To list the tests available before a run, use `simready-benchmark --list-tests`.
By default, the requested output location is `_testing/` at the configured
project root. Benchmark never clears an existing directory: it allocates a
fresh `benchmark_testing`, `benchmark_testing_1`, and so on beneath an existing
location and prints the resolved path. `--output-dir DIR` requests a different
location. Refer to [Pipeline and Stages](pipeline.md) for stage flow and flags
such as `--plan-only` and `--no-stamp`, and to [Reading Reports](reading-reports.md)
for the output contract.

## Next Steps

- [Pipeline and Stages](pipeline.md): plan, run, stamp, and report stages
- [Reading Reports](reading-reports.md): interpret results, exit codes, and [verify a clean run](reading-reports.md#verify-a-clean-run)
