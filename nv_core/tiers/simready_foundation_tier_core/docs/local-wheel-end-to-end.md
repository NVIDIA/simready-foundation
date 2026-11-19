# Local-wheel end-to-end Evaluate setup

Use this workflow to test unpublished Evaluate and Foundation tier changes
without installing either project from a package index. It installs the locally
built wheels into a Evaluate/validation host, configures pip Isaac Sim in a
separate Python 3.12 environment, verifies entry-point discovery, creates a
plan, and runs one real Isaac Sim test.

The virtual environment and working directory must be outside both source
checkouts. This prevents Evaluate's developer source-tree fallbacks from
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
$WorkRoot = "<path-to-isolated-evaluate-workspace>"
$Venv = Join-Path $WorkRoot ".venv"
$IsaacVenv = Join-Path $WorkRoot "isaac-env"
$EnginesToml = Join-Path $WorkRoot "engines.toml"
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

Select the two Evaluate wheels under `$ExplorerRepo\_build\packages\dist`
and the Core tier wheel under `$FoundationsRepo\nv_core\tiers\_build\dist`.
Those builds can also produce other configured project/tier wheels. A filtered
Explorer `python_package` build clears its whole generated staging/dist tree
and regenerates only the selected wheels; do not expect unrelated wheel files
to remain. Installed environments are not uninstalled by that packaging cleanup.

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

$EvaluateWheel = (Get-ChildItem $ExplorerDist -Filter "simready_evaluate-*.whl" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
$EngineWheel = (Get-ChildItem $ExplorerDist -Filter "simready_evaluate_engine_kit-*.whl" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
$CoreTierWheel = (Get-ChildItem $FoundationDist -Filter "simready_foundation_tier_core-*.whl" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
@(
  $EvaluateWheel,
  $EngineWheel,
  $CoreTierWheel
) | ForEach-Object {
  if (-not $_ -or -not (Test-Path -LiteralPath $_ -PathType Leaf)) {
    throw "A required local wheel was not found."
  }
  Write-Host "Using local wheel: $_"
}
```

Install the Foundation dependency graph through the core tier's `evaluate`
extra. Passing the wheel paths directly is important: `--find-links` alone may
select a package-index copy when the local wheel has the same version.

```powershell
& "$Venv\Scripts\python.exe" -m pip install --force-reinstall `
  $EvaluateWheel `
  $EngineWheel `
  "$CoreTierWheel[evaluate]"
```

Installing all three local wheels in one resolver transaction verifies the same
dependency contract that the published extra uses without temporarily pulling
an older Evaluate build from the package index. Once these versions are
published, `pip install simready-foundation-tier-core[evaluate]` replaces the
entire local-wheel section.
Resolve the selected Evaluate and Kit wheels against their independently
declared compatible dependency ranges; equal version labels are not required.
The Core tier has its own version; inspect the actual interpreter, CLI/module locations and
any `PYTHONPATH` or editable/source overrides before claiming wheel qualification.

Verify the environment:

```powershell
& "$Venv\Scripts\python.exe" -m pip check
& "$Venv\Scripts\python.exe" -m pip show `
  simready-evaluate `
  simready.evaluate.engine-kit `
  simready-foundation-tier-core
```

## Set up Isaac in a separate environment

Keep Evaluate, the tier and validation dependencies in `$Venv`. Pip Isaac
brings `usd-exchange`, while Evaluate uses `usd-core`; both own `pxr` files.
Do not install them together. With a configured pip-Isaac interpreter, `--setup`
verifies its prepared runtime without installing or repairing either environment.
Without that configuration, legacy active-environment installation is refused
beside `usd-core`. If an environment was already mixed, recreate it; uninstalling
one overlapping USD distribution can remove the other's files.

The SDK-only setup below supports headless CLI execution. Manual Script Editor
execution and the additional prepared-runtime `--setup` check need runtime
preparation; follow **Prepare Isaac for Script Editor execution** in
`$ExplorerRepo/source/libraries/evaluate/docs/install.md` for that workflow.

```powershell
py -3.12 -m venv $IsaacVenv
& "$IsaacVenv\Scripts\python.exe" -m pip install "isaacsim[all,extscache]" --extra-index-url https://pypi.nvidia.com
& "$IsaacVenv\Scripts\python.exe" -m pip check
& "$IsaacVenv\Scripts\python.exe" -m pip show isaacsim
```

Select a release compatible with the engine plugin/providers; add an exact
version pin when qualifying a particular release. The first install is large.
If it is interrupted, rerun that pip command through the same Isaac Python,
not Evaluate's host setup command.

Save the following as `$EnginesToml` (UTF-8 without a BOM). Replace the paths
with the absolute `$IsaacVenv` paths using forward slashes, and the version
with that environment's `pip show isaacsim` result:

```toml
[kit.isaac_sim]
executable_path = "<absolute-isaac-env>/Scripts/isaacsim.exe"
python_executable = "<absolute-isaac-env>/Scripts/python.exe"
version = "<installed-isaac-version>"
tags = ["isaac", "kit"]
runtime = "PhysX"

[kit.isaac_sim_newton]
executable_path = "<absolute-isaac-env>/Scripts/isaacsim.exe"
python_executable = "<absolute-isaac-env>/Scripts/python.exe"
version = "<installed-isaac-version>"
tags = ["isaac", "kit"]
runtime = "Newton"
experience = "isaacsim.exp.full.newton"
```

This engine configuration does not install Newton's tier/provider. For Newton
tests, also select a compatible local Newton tier wheel and install its
`[evaluate]` extra with the intended local Core/Evaluate/Kit wheels in one
resolver transaction. A configured Newton engine does not add Newton
close/lift gripper coverage.

## Verify the installed providers

Run from `$WorkRoot`, not either checkout, and pass the same explicit engine
configuration to diagnostics, planning and execution:

```powershell
Set-Location $WorkRoot
& "$Venv\Scripts\python.exe" -m pip check
& "$Venv\Scripts\simready-evaluate.exe" --engines-toml $EnginesToml --show-config
& "$Venv\Scripts\simready-evaluate.exe" --engines-toml $EnginesToml --list-tests
```

Expected configuration evidence:

- catalogs come from installed `simready.tier` packages;
- the Core tier advertises its runtime-test directory through `simready.tier`;
- no `--sr-specs`, `--project-config`, or `--tests-path` is required;
- effective test paths are under the host venv's `site-packages`;
- the configured launchers point to the separate Isaac environment.

Check `python_executable`, runtime, capability tags and experience in the TOML
itself; `--show-config` does not print all of them. Discovery and `pip check`
do not prove native execution. Read catalog-binding warnings too: a usable
listing can include available siblings of an incomplete historical contract.

## Alternative: use the source checkout directly

To test unpublished tier and runtime-test changes without building or
installing the Foundation tier wheel, point the Evaluate wheel at the
Foundation checkout. This mode intentionally validates source discovery; it is
separate from the wheel-only verification above.
Keep the selected checkout and provider installations unchanged until Evaluate
exits. Editing, rebasing or reinstalling them during a run can remove the saved
plan's exact test revision. A native `test_discovery` error means the test body
did not run, not that the asset failed. Preserve the loader cause and engine log;
if the provider revision changed, create a fresh plan in a stable environment
rather than substituting another test version.

```powershell
Set-Location $WorkRoot
& "$Venv\Scripts\simready-evaluate.exe" `
  --engines-toml $EnginesToml `
  --foundations-path $FoundationsRepo `
  --show-config

& "$Venv\Scripts\simready-evaluate.exe" `
  --engines-toml $EnginesToml `
  --foundations-path $FoundationsRepo `
  --list-tests
```

`--foundations-path` resolves
`sample_content/project_config.toml`, the catalogs under `nv_core/tiers`, and
every direct tier-owned runtime-test package, including Core's
`simready.foundation.tier_core.runtime_tests` and Newton's `simready.foundation.tier_newton.runtime_tests`. It cannot be
combined with `--project-config`. Pip-installed test packs remain additive; omit
`--foundations-path` to return to installed-tier catalog discovery.

## Verify additional tier and test-pack wheels

Additional providers use the same descriptor contract; no Evaluate code or
configuration change is required. Install another tier wheel into the
environment, then rerun discovery:

```powershell
$PartnerTierDist = "<path-to-partner-tier-dist>"
$PartnerTierWheel = (Get-ChildItem $PartnerTierDist -Filter "partner_tier-*.whl" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
& "$Venv\Scripts\python.exe" -m pip install $PartnerTierWheel

& "$Venv\Scripts\simready-evaluate.exe" --engines-toml $EnginesToml --show-config
& "$Venv\Scripts\simready-evaluate.exe" --engines-toml $EnginesToml --list-tests
```

`--show-config` lists every installed `simready.tier` provider and independent
`simready.evaluate.tests` provider. `--list-tests` includes tests contributed
by every tier and test-only pack. For unpublished tests that are not packaged
in a wheel, use one or more additive source directories:

```powershell
$TestPackOne = "<path-to-first-test-package>"
$TestPackTwo = "<path-to-second-test-package>"
& "$Venv\Scripts\simready-evaluate.exe" `
  --engines-toml $EnginesToml `
  --list-tests `
  --tests-path $TestPackOne $TestPackTwo
```

Installed test packs remain active when `--tests-path` is present. The explicit
paths override only other path configuration sources, such as
`SIMREADY_EVALUATE_TESTS_PATH` and `[tests].paths` in `engines.toml`.

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
& "$Venv\Scripts\simready-evaluate.exe" `
  --engines-toml $EnginesToml `
  --assets $Asset `
  --features FET001_MinimalPlaceableVisual `
  --tests simready.foundation.tier_core.runtime_tests:presence `
  --runtime isaac_sim `
  --output-dir $PlanOutput `
  --plan-only
```

Then run the same test with active Isaac/PhysX simulation:

```powershell
& "$Venv\Scripts\simready-evaluate.exe" `
  --engines-toml $EnginesToml `
  --assets $Asset `
  --features FET001_MinimalPlaceableVisual `
  --tests simready.foundation.tier_core.runtime_tests:presence `
  --runtime isaac_sim `
  --output-dir $RunOutput
```

On completion, Evaluate prints the selected output directory and exact HTML
report path. Open that printed `index.html` and inspect `run_summary.json` in
the same run directory. Do not reconstruct the path from `$RunOutput`: if that
requested directory already contains data, Evaluate allocates a fresh owned
child directory rather than deleting or overwriting it.

This forced presence run is an installation smoke test, not static or complete
asset conformance. Inspect its saved plan, native result/provider/version and
actual engine logs before declaring the local build qualified. An all-PASS
filtered run cannot certify excluded work or unavailable required bindings.

The explicit `engines.toml` is required for this isolated layout, not only for
advanced overrides. It replaces automatic active-environment Isaac discovery;
standalone launchers, other experiences and remote workers use the same
configuration mechanism.
