# Local-wheel end-to-end Benchmark setup

Use this workflow to test unpublished Benchmark and Foundation tier changes
without installing either project from a package index. It installs the locally
built wheels, lets Benchmark set up pip Isaac Sim, verifies entry-point
discovery, creates a plan, and runs one real Isaac Sim test.

The virtual environment and working directory must be outside both source
checkouts. This prevents Benchmark's developer source-tree fallbacks from
making a wheel-only test appear to work.

## Prerequisites

- Windows PowerShell
- Python 3.12
- Access to every package index required by the selected dependencies, through
  normal `pip` configuration
- Local checkouts of `simready-explorer` and `simready_foundations`
- Enough free disk space for the Isaac Sim Python packages and extension cache

Set the checkout and isolated-workspace paths:

```powershell
$ExplorerRepo = "<path-to-simready-explorer>"
$FoundationsRepo = "<path-to-simready-foundations>"
$WorkRoot = "<path-to-isolated-benchmark-workspace>"
$Venv = Join-Path $WorkRoot ".venv"
```

## Build the local wheels

```powershell
Push-Location $ExplorerRepo
.\repo.bat build
Pop-Location

Push-Location $FoundationsRepo
.\repo.bat build_tiers
Pop-Location
```

The builds produce two Benchmark wheels under
`$ExplorerRepo\_build\packages\dist` and one core Foundation tier wheel under
`$FoundationsRepo\nv_core\tiers\_build\dist`.

## Create a clean environment

```powershell
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
py -3.12 -m venv $Venv
& "$Venv\Scripts\python.exe" -m pip install --upgrade pip
```

## Install the locally built wheels

Resolve wheel paths rather than embedding package versions in commands:

```powershell
$ExplorerDist = Join-Path $ExplorerRepo "_build\packages\dist"
$FoundationDist = Join-Path $FoundationsRepo "nv_core\tiers\_build\dist"

$BenchmarkWheel = (Get-ChildItem $ExplorerDist -Filter "simready_benchmark-*.whl" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
$EngineWheel = (Get-ChildItem $ExplorerDist -Filter "simready_benchmark_engine_kit-*.whl" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
$CoreTierWheel = (Get-ChildItem $FoundationDist -Filter "simready_foundation_tier_core-*.whl" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
@(
  $BenchmarkWheel,
  $EngineWheel,
  $CoreTierWheel
) | ForEach-Object {
  if (-not $_) { throw "A required local wheel was not found." }
  Write-Host "Using local wheel: $_"
}
```

Install the Foundation dependency graph through the core tier's `benchmark`
extra. Passing the wheel paths directly is important: `--find-links` alone may
select a package-index copy when the local wheel has the same version.

```powershell
& "$Venv\Scripts\python.exe" -m pip install `
  $BenchmarkWheel `
  $EngineWheel `
  "$CoreTierWheel[benchmark]"
```

Installing all three local wheels in one resolver transaction verifies the same
dependency contract that the published extra uses without temporarily pulling
an older Benchmark build from the package index. Once these versions are
published, `pip install simready-foundation-tier-core[benchmark]` replaces the
entire local-wheel section.

Verify the environment:

```powershell
& "$Venv\Scripts\python.exe" -m pip check
& "$Venv\Scripts\python.exe" -m pip show `
  simready-benchmark `
  simready-benchmark-engine-kit `
  simready-foundation-tier-core
```

## Set up and verify the installed providers

Run setup from `$WorkRoot`, not either checkout. Setup verifies the installed
tier catalogs and bundled runtime tests, then installs or repairs Isaac Sim in the
active environment. This is the Isaac installation step; no separate Isaac pip
command is required. Setup does not clone Foundation or create `engines.toml`.

```powershell
Set-Location $WorkRoot
& "$Venv\Scripts\simready-benchmark.exe" --setup --install-isaac
& "$Venv\Scripts\python.exe" -m pip show isaacsim
& "$Venv\Scripts\simready-benchmark.exe" --show-config
& "$Venv\Scripts\simready-benchmark.exe" --list-tests
```

The first Isaac Sim install is large and may be quiet for several minutes. If
the network interrupts it, rerun the setup command. The installer raises its
pip timeout and retry count for the large download.

Expected configuration evidence:

- specification catalogs come from installed `simready.tier` packages;
- the core tier advertises its runtime-test directory through `simready.tier`;
- no `--sr-specs`, `--project-config`, or `--tests-path` argument is required;
- no `engines.toml` is needed for pip Isaac;
- `isaac_sim` and `isaac_sim_newton` resolve to the active environment's
  `isaacsim` launcher;
- the effective test directory is under this virtual environment's
  `site-packages` directory.

## Alternative: use the source checkout directly

To test unpublished tier and runtime-test changes without building or
installing the Foundation tier wheel, point the Benchmark wheel at the
Foundation checkout. This mode intentionally validates source discovery; it is
separate from the wheel-only verification above.

```powershell
Set-Location $WorkRoot
& "$Venv\Scripts\simready-benchmark.exe" `
  --foundations-path $FoundationsRepo `
  --show-config

& "$Venv\Scripts\simready-benchmark.exe" `
  --foundations-path $FoundationsRepo `
  --list-tests
```

`--foundations-path` resolves
`sample_content/project_config.toml`, the catalogs under `nv_core/tiers`, and
the core tier's top-level `simready_benchmark_kit_suite` package. It cannot be
combined with `--project-config`. Pip-installed test packs remain additive; omit
`--foundations-path` to return to installed-tier catalog discovery.

## Verify additional tier and test-pack wheels

Additional providers use the same descriptor contract; no Benchmark code or
configuration change is required. Install another tier wheel into the
environment, then rerun discovery:

```powershell
$PartnerTierDist = "<path-to-partner-tier-dist>"
$PartnerTierWheel = (Get-ChildItem $PartnerTierDist -Filter "partner_tier-*.whl" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
& "$Venv\Scripts\python.exe" -m pip install $PartnerTierWheel

& "$Venv\Scripts\simready-benchmark.exe" --show-config
& "$Venv\Scripts\simready-benchmark.exe" --list-tests
```

`--show-config` lists every installed `simready.tier` provider and independent
`simready_benchmark.tests` provider. `--list-tests` includes tests contributed
by every tier and test-only pack. For unpublished tests that are not packaged
in a wheel, use one or more additive source directories:

```powershell
$TestPackOne = "<path-to-first-test-package>"
$TestPackTwo = "<path-to-second-test-package>"
& "$Venv\Scripts\simready-benchmark.exe" `
  --list-tests `
  --tests-path $TestPackOne $TestPackTwo
```

Installed test packs remain active when `--tests-path` is present. The explicit
paths override only other path configuration sources, such as
`SIMREADY_BENCHMARK_TESTS_PATH` and `[tests].paths` in `engines.toml`.

## Plan and run a real test

Set an asset owned by the user or test workspace. The asset does not need to be
inside a Foundation checkout:

```powershell
$Asset = "<path-to-asset.usd>"
$PlanOutput = Join-Path $WorkRoot "presence-plan"
$RunOutput = Join-Path $WorkRoot "presence-run"
```

First validate planning without launching Isaac Sim:

```powershell
& "$Venv\Scripts\simready-benchmark.exe" `
  --assets $Asset `
  --features FET_001_STANDARD `
  --tests presence `
  --runtime isaac_sim `
  --output-dir $PlanOutput `
  --plan-only
```

Then run the same test with active Isaac/PhysX simulation:

```powershell
& "$Venv\Scripts\simready-benchmark.exe" `
  --assets $Asset `
  --features FET_001_STANDARD `
  --tests presence `
  --runtime isaac_sim `
  --output-dir $RunOutput
```

On completion, Benchmark prints the selected output directory and exact HTML
report path. Open that printed `index.html` and inspect `run_summary.json` in
the same run directory. Do not reconstruct the path from `$RunOutput`: if that
requested directory already contains data, Benchmark allocates a fresh owned
child directory rather than deleting or overwriting it.

Use `--engines-toml FILE` only for an advanced override, such as a standalone
Isaac executable, a custom Kit experience, or remote worker configuration. A
present explicit file replaces automatic local Isaac engine discovery.
