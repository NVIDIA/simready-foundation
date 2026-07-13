# SimReady Foundation Tests

## Overview

This directory contains the SimReady Foundation test suite, which runs the AIF validators end-to-end against `.usda` fixture assets. Each test feeds an asset to `ValidationEngine`, runs one rule (or a rule set) in isolation, and asserts the expected outcome.

The suite uses a two-layer design:

- **Domain-agnostic infrastructure** at the root of `tests/` (`conftest.py`, `_harness.py`, `check_rule.py`) is shared by every domain.
- **Domain-specific tests and fixtures** live in subfolders (currently just `aif/`). Adding a new domain (robotics, etc.) means adding a folder, not editing the shared infrastructure.

## Quick start

From the repository root, one command runs every test suite:

```powershell
python run_tests.py
```

`run_tests.py` creates a dedicated virtual environment under `_build/test-venvs/`, installs each suite's dependencies from its `requirements.txt`, and runs it. You only need a Python 3.11 or 3.12 interpreter on PATH; on Windows use `py -3.12 run_tests.py` if 3.12 is not your default. GitLab CI invokes the launcher the same way a developer does.

If the dependency install fails because `simready-validate` cannot be found, the package index that hosts it is not configured in your environment. Set `PIP_EXTRA_INDEX_URL` to that index and re-run.

The sections below cover the manual virtual-environment workflow, which you need for targeted runs and for spot-checking individual rules.

## Prerequisites

- **Python 3.12** installed and on PATH. Python 3.13+ may work but is untested; Python 3.10 and earlier will fail at import time because the validator uses `tomllib` from the 3.11+ standard library.
- **Microsoft Visual C++ Redistributable 2015-2022 (x64)** on Windows. Required because USD's C++ extensions link against the MSVC runtime. Download from https://aka.ms/vs/17/release/vc_redist.x64.exe.
- **Network access** to the package registry from which you install `simready-validate` (see setup steps below).

## First-time setup

The [Quick start](#quick-start) launcher does this automatically. Set the environment up by hand when you want targeted runs, spot-checks, or an activated venv to work in.

These steps create a fresh Python virtual environment and install everything the tests need.

```powershell
cd nv_core/sr_specs

# Create a Python 3.12 venv. `py -3.12` is the Windows launcher; on macOS/Linux use
# `python3.12 -m venv .venv` or whatever name your distro uses for Python 3.12.
py -3.12 -m venv .venv

# Activate. PowerShell users may need to run `Set-ExecutionPolicy -ExecutionPolicy
# RemoteSigned -Scope CurrentUser` once if the activation script is blocked.
.\.venv\Scripts\Activate.ps1

# Verify the venv is on Python 3.12.
python --version
```

Then install the test suite's dependencies:

```powershell
pip install -r tests/requirements.txt
```

[tests/requirements.txt](requirements.txt) pins the three packages the test suite needs:

- **`simready-validate`** is the validator CLI and its `ValidationEngine` API.
- **`numpy`** is a foundations-side runtime requirement, not a dependency of the `simready-validate` wheel. It is intentionally not pulled in transitively (the validator itself does not use numpy and pinning it via the wheel would risk version conflicts in downstream environments), but the foundations capabilities under `docs/capabilities/visualization/materials/` import numpy at load time, so the test bootstrap needs it.
- **`pytest`** is the test framework. It is not a runtime concern of `simready-validate`, so it lives here rather than in the validator wheel.

If you are doing broader foundations development (packaging samples, etc.), the more comprehensive [nv_core/package_sample/requirements.txt](../../package_sample/requirements.txt) also covers the test deps and adds packaging tooling.

## Running the tests

From `nv_core/sr_specs/` with the venv activated:

```powershell
pytest tests\ -v
```

You should see one line per parametrized test case ending with `PASSED`, followed by a summary like:

```
============================= 23 passed in 1.18s ==============================
```

Useful variations:

| Command | What it does |
|---|---|
| `pytest tests\ -v` | One line per test with PASS/FAIL |
| `pytest tests\ -v -x` | Stop at the first failure |
| `pytest tests\ -v --tb=long` | Show full tracebacks on failures |
| `pytest tests\ -v -s --log-cli-level=INFO` | Show validator loader logs during setup |

## What to expect

- **Total tests:** 23 (16 negative variants + 4 CP edge cases + 3 clean baselines for AIF).
- **Runtime:** about 1 to 3 seconds end-to-end after the one-time bootstrap.
- **First-run cost:** the very first run takes a few extra seconds because the validator codegen generates and injects requirement enums into `omni.capabilities`. Subsequent runs reuse the venv.
- **Successful run ends with** `N passed in X.XXs`. Anything other than "all passed" means either a real regression in the validators, or a fixture that drifted out of sync with the spec.

## Layout

```
tests/
|-- README.md               (this file)
|-- conftest.py             session-wide bootstrap that runs the validator's
|                           codegen pipeline once at pytest import time.
|                           Populates the RequirementsRegistry that the harness
|                           queries. No test module should need to bootstrap
|                           the validator itself.
|-- _harness.py             two shared assertion helpers used by every domain:
|                             - assert_rule_fires(asset, code): run a single
|                               rule and assert it reports a FAILURE.
|                             - assert_no_failures(asset, codes): run a rule
|                               set and assert zero failures.
|                           Both helpers translate spec codes (like "AM.002")
|                           into rule classes via the registry, so test files
|                           never need to import checker classes directly.
|-- check_rule.py           standalone CLI for spot-checking one asset against
|                           one rule. Not part of the pytest suite.
`-- aif/                    AIF-domain tests, fixtures, and expectation matrix
    |-- README.md           fixture details + per-fixture pass/fail outcomes
    |-- test_aif.py         manifest (NEGATIVE_FIXTURES, CLEAN_FIXTURES) and
    |                       the two parametrized pytest functions that iterate
    |                       it and delegate to the harness helpers.
    `-- fixtures/           USDA assets used by the tests
        |-- Generic_CDU/    compliant CDU baseline
        |-- gb300/          compliant compute-rack baseline
        `-- variants/       deliberately-broken assets paired with the rule
                            that should catch each break
```

## Spot-checking one asset against one rule

`check_rule.py` is a developer convenience for running a single rule against any USD file on disk, without going through pytest. Useful when you want to see what the validator says about a specific asset and rule combination.

```powershell
python -m tests.check_rule <asset.usda> <CODE>
```

Example:

```powershell
python -m tests.check_rule tests\aif\fixtures\variants\am_fail_no_assetClass.usda AM.002
```

Expected output:

```
========================================================================
Asset:       <full path>
Requirement: AM.002
========================================================================
RESULT: AM.002 FIRED (1 failure issue(s))
  [1] Missing required attribute: aif:core:assetClass.
```

`FIRED` means the rule caught a problem on the asset (the expected outcome on a broken fixture, a warning sign on a clean asset). `did not fire` means the asset passed under that rule.

Exit code 0 indicates the script ran cleanly; non-zero means a usage error (missing asset, unknown rule code, etc.). The exit code does not encode the validation outcome itself.

## Adding new tests

### Adding a fixture to an existing domain

1. Drop the new `.usda` file (and any `_Properties.usda` sublayer) into `tests/<domain>/fixtures/variants/`.
2. Add one line to that domain's manifest. For AIF, edit `tests/aif/test_aif.py`:
   - For a deliberately-broken fixture: add an entry to `NEGATIVE_FIXTURES` mapping the path to the rule code it should trigger.
   - For a compliant baseline: add an entry to `CLEAN_FIXTURES` mapping the path to the list of rule codes it must pass under.
3. Update the domain's `README.md` so the expectation matrix matches reality.
4. Run `pytest tests\ -v` to confirm the new case behaves as expected.

### Adding a new domain

1. Create `tests/<newdomain>/` with an `__init__.py`.
2. Copy `tests/aif/test_aif.py` as a starting point and replace `NEGATIVE_FIXTURES` and `CLEAN_FIXTURES` with the new domain's rule codes and fixtures. The harness resolves codes to rule classes via `RequirementsRegistry`, so the test file only needs to know the spec codes (like `"AM.002"`) that the new domain's `@register_requirements` decorators registered.
3. Drop fixtures into `tests/<newdomain>/fixtures/`.
4. Add a `tests/<newdomain>/README.md` documenting the fixtures.
5. No changes needed to `conftest.py` or `_harness.py`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ImportError: DLL load failed while importing _tf` | Missing or outdated MSVC runtime | Install the VC++ Redistributable (see prerequisites) |
| `ModuleNotFoundError: No module named 'tomllib'` | Venv created with Python 3.10 or earlier | Delete `.venv` and recreate with `py -3.12 -m venv .venv` |
| `ModuleNotFoundError: No module named 'numpy'` | numpy is a foundations-side requirement, not bundled with `simready-validate` | `pip install numpy` |
| `cannot be loaded because running scripts is disabled` | PowerShell execution policy | Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` once |
| Tests collect 0 items | Wrong working directory | Run from `nv_core/sr_specs/`, not from anywhere else |
| `Could not find a version that satisfies simready-validate` | Package index not configured (it is not on public PyPI), or no network access | Set `PIP_EXTRA_INDEX_URL` to the index that hosts `simready-validate` and re-run; confirm network access |
| `ImportError: cannot import name 'ValidationEngine'` | Stale `omniverse-asset-validator` install | `pip install --upgrade --force-reinstall omniverse-asset-validator` |

## See also

- [aif/README.md](aif/README.md) for the AIF fixture expectation matrix and per-fixture details.
- The repository root `README.md` for higher-level SimReady Foundation documentation.
