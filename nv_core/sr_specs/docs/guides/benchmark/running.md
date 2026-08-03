# Running Tests

This page walks through installing the `simready-benchmark` tool, configuring an
engine, and running tests against an asset. You do not need a SimReady Foundation
clone before you start; the configure step acquires one by default. If you
already have a SimReady Foundation clone, for example, this repository, refer to
[Configure the Engine](#configure-the-engine) for flags that point the wizard at
your existing clone.

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

Install the framework and the NVIDIA Kit and NVIDIA Isaac Sim engine plugin from the public NVIDIA PyPI index. The `[kit]` extra brings the engine plugin (`simready-benchmark-engine-kit`), which is required to run tests in the engine:

```bash
pip install simready-benchmark[kit] --extra-index-url https://pypi.nvidia.com
```

The FET test families themselves are part of the SimReady Foundation, so there is nothing else to install. The next step points the framework at the foundation, and the tests are discovered from there.

## Configure the Engine

Run the setup wizard once to record an engine and write the configuration:

```bash
simready-benchmark --init-engines-toml
```

The wizard acquires the SimReady Foundation, which contains the FET test families, detects or installs Isaac Sim, and writes a complete `engines.toml`. The framework discovers the FET test families from the foundation automatically. Confirm the result with:

```bash
simready-benchmark --show-config
```

If you already have a SimReady Foundation clone and an Isaac Sim install, for
example, when working from this repository, pass their paths to the wizard so it
skips cloning the foundation and downloading Isaac Sim:

```bash
simready-benchmark --init-engines-toml --foundations-path PATH_TO_FOUNDATIONS --no-clone-foundations --executable-path PATH_TO_ISAAC_LAUNCHER --no-install-isaac
```

The Isaac Sim launcher is `isaac-sim.bat` on Windows or `isaac-sim.sh` on Linux. The relevant flags are:

| Flag | Effect |
|---|---|
| `--foundations-path <DIR>` | Use an existing SimReady Foundation clone instead of cloning. |
| `--no-clone-foundations` | Do not clone SimReady Foundation. |
| `--executable-path <PATH>` | Use a specific Isaac Sim launcher and skip detection and installation. |
| `--no-install-isaac` | Do not install Isaac Sim. |

## Run

Run the tests against an asset by path:

```bash
simready-benchmark --assets path/to/asset.usd
```

By default, the stamp stage also writes a benchmark receipt into the
asset. Specify `--no-stamp` to skip it. Refer to
[The Runtime Stamp](reading-reports.md#the-runtime-stamp) for what is written.

To force a specific feature's tests to run, regardless of the asset's validation status, add `--features`:

```bash
simready-benchmark --assets path/to/asset.usd --features FET003
```

To list the tests available before a run, use `simready-benchmark --list-tests`.
By default, results land under `_testing/` at the project root configured for
`simready-benchmark`. Refer to [Pipeline and Stages](pipeline.md) for
stage flow and flags such as `--plan-only` and `--no-stamp`. Refer to
[Next Steps](#next-steps) to interpret results.

## Next Steps

- [Pipeline and Stages](pipeline.md): plan, run, stamp, and report stages
- [Reading Reports](reading-reports.md): interpret results, exit codes, and [verify a clean pass](reading-reports.md#verify-a-clean-pass)
