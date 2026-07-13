# package_sample — publish a SimReady-Foundation-conformant asset package

This sample takes you from "I have a folder of USD files on disk" to "I have a
package that conforms to the SimReady Foundation standard and is ready to
publish". The single entry point is `create_simready_package.py`; it drives
three phases in order — pre-validation, build, and post-validation — and
exits non-zero if any phase fails.

```
source folder ──► create_simready_package.py ──► published package
   (USDs)        (pre-validate ─► build ─► post-validate)
```

| Phase             | What it does                                                       |
|-------------------|--------------------------------------------------------------------|
| Pre-validation    | Verify the source folder; optionally write `.metadata/` (BOM, conformance, OpenUSD root layers). |
| Create            | Build the package (WRAPP); verify and register conformance metadata in the package definition. |
| Post-validation   | Run the `Package` profile over the finished package; optionally write evidence metadata. |

The three phases are also exposed as a small Python API under
`sr_pkg_sample/` if you want to wire the workflow into your own
tooling instead of shelling out to the script — call
`sr_pkg_sample.pre_validate`, `sr_pkg_sample.create_package`, and
`sr_pkg_sample.post_validate` directly. See
[Advanced: integrate via Python API](#advanced-integrate-via-python-api).

A lightweight, WRAPP-less alternative to the full build is available
via `--no-wrapp` — it stamps a minimal package definition (required
fields only, no BOM) directly into the source folder. See
[Lightweight: no-BOM, no-WRAPP package](#lightweight-no-bom-no-wrapp-package).

---

## Quick Start

Run everything from this directory
(`simready_foundations/nv_core/package_sample/`). The detailed
sections that follow expand on each step.

1. **Download the WRAPP wheel** from NGC at
   <https://catalog.ngc.nvidia.com/orgs/nvidia/teams/omniverse/resources/wrapp_clt/files?version=2.2.0>
   (free NGC account; file name is
   `omni_wrapp_minimal-2.2.0-py3-none-any.whl`).

2. **Bootstrap the venv** — this creates `.venv/` next to this README
   and installs `simready-validate` (with all its dependencies) and
   WRAPP:

   ```bash
   ./setup_venv.sh --wrapp-wheel /path/to/omni_wrapp_minimal-2.2.0-py3-none-any.whl
   ```

   ```bash
   source .venv/bin/activate
   ```

3. **Build and validate a package** end-to-end. Replace the values
   below with your asset name, version, license, source folder,
   root USD, and target repo:

   ```bash
   python create_simready_package.py apple_a01 1.0.0 Apache-2.0 \
       ~/my_asset/simready_usd ~/my_repo \
       --root-usd sm_apple_a01_01.usd
   ```

The script exits `0` only if pre-validation, the build, and
post-validation all pass. The published package lands at
`~/my_repo/.packages/apple_a01/1.0.0/`, with
`com.nvidia.simready.packaging.json` as its definition file.

---

## Prerequisites

- **Python 3.10+** on your PATH.
- **Network access to <https://pypi.nvidia.com/>.** The setup script passes
  `--extra-index-url https://pypi.nvidia.com/` to pip so it can resolve
  `simready-validate` and its dependencies. No VPN or special credentials
  are required — the index is publicly browsable.
- **The WRAPP wheel (`omni-wrapp-minimal`).** This sample uses WRAPP as
  the underlying packaging tool for the create phase. (The SimReady
  Foundation standard does not mandate WRAPP — any tool that produces
  the expected layout and metadata works — but this sample is wired to
  it.) Download it from
  <https://catalog.ngc.nvidia.com/orgs/nvidia/teams/omniverse/resources/wrapp_clt/files?version=2.2.0>
  (free NGC account) and pass it to `setup_venv.sh` via
  `--wrapp-wheel <path>`. The script installs it with the `[local]`
  extra automatically.

### WRAPP extras

`setup_venv.sh` installs WRAPP with the `[local]` extra only — enough
for this sample's file-based repos. Other backends ship as extras on
the same wheel: `nucleus`, `s3`, `azure`, `storage-api`. See the WRAPP
docs for what each one enables.

To add one, rerun pip inside the activated venv with the extras you
want, e.g. to layer S3 on top of the default local install:

```bash
source .venv/bin/activate
pip install --extra-index-url https://pypi.nvidia.com/ \
    "/path/to/omni_wrapp_minimal-2.2.0-py3-none-any.whl[local,s3]"
```

Each backend has its own authentication mechanism (environment
variables, credential files, interactive browser flows, etc.). See
[Supported Storage Systems — Authentication](https://docs.omniverse.nvidia.com/kit/docs/omni-wrapp/latest/storage.html#authentication)
in the WRAPP documentation for the full details.

## Setup

From this directory (`simready_foundations/nv_core/package_sample/`), run:

```bash
./setup_venv.sh --wrapp-wheel /path/to/omni_wrapp_minimal-2.2.0-py3-none-any.whl
```

This creates `.venv/` right here inside `package_sample/` and installs:

- `simready-validate` (pulls in `omniverse-asset-validator`,
  `omniverse-usd-profiles`, `numpy`, etc. as declared dependencies),
- `omni-wrapp-minimal` with the `[local]` extra,
- `pytest` + `pytest-asyncio` for the integration tests.

All packages except WRAPP are resolved from <https://pypi.nvidia.com/>
(no VPN or special credentials required).

Activate the venv before running anything:

```bash
cd simready_foundations/nv_core/package_sample
source .venv/bin/activate
```

Pass `--recreate` to `setup_venv.sh` to wipe `.venv/` first.

### Development: alternative package sources

For development workflows — testing against locally built wheels or
resolving packages from a private index — `setup_venv.sh` accepts
additional flags:

- `--extra-index <url>` — add an additional PyPI-compatible package index
  for dependency resolution (repeatable). The default index
  (`https://pypi.nvidia.com/`) is always included; each `--extra-index`
  is appended as an extra `--extra-index-url` to every `pip install`
  invocation. Use this when packages are hosted on a private or
  organisation-internal index. When the index hosts WRAPP, this replaces
  the need for a `--wrapp-wheel` argument.
- `--simready-validate-wheel <path>` — install `simready-validate` from a
  local wheel instead of resolving it from the indexes.
- `--asset-validator-wheel <path>` — install `omniverse-asset-validator`
  from a local wheel, overriding the version pulled in as a dependency
  of `simready-validate`.
- `--wrapp-wheel <path>` — install WRAPP from a local wheel instead of
  resolving it from the indexes.

Examples:

```bash
# Resolve all packages (including WRAPP) from a private index
./setup_venv.sh --extra-index https://my-pypi.example.com/simple

# Local wheels for simready-validate and the asset validator,
# WRAPP from the NGC download
./setup_venv.sh \
    --wrapp-wheel /path/to/omni_wrapp_minimal-2.2.0-py3-none-any.whl \
    --simready-validate-wheel /path/to/simready_validate-X.Y.Z-py3-none-any.whl \
    --asset-validator-wheel /path/to/omniverse_asset_validator-X.Y.Z-py3-none-any.whl
```

---

## Usage

### Default flow: build a package end-to-end

The "source folder" is the self-contained directory that holds
everything your asset needs: if you think of your asset as a root USD
stage, the folder must contain that stage **and every file it
references**, directly or transitively. Anything referenced from
outside the folder won't make it into the package.

```bash
python create_simready_package.py <name> <version> <license> <source> <repo>
```

Parameters:

- `<name>` — package name, e.g. `apple_a01`. Lowercase, no spaces.
- `<version>` — package version, e.g. `1.0.0`.
- `<license>` — [SPDX identifier](https://spdx.org/licenses/) for the
  license that applies to the asset you are publishing. Common choices
  include `Apache-2.0`, `MIT`, `CC-BY-4.0`, `CC-BY-NC-4.0`, or a
  `LicenseRef-<your-license>` expression for a proprietary or bespoke
  license.
- `<source>` — folder of USD files to publish.
- `<repo>` — the WRAPP repository to publish into. A local directory
  path (e.g. `~/my_repo`) works for a personal repo; a `file://` URL
  is also accepted.

Typical use (the `--root-usd` flag identifies the entry-point USD
inside `<source>`):

```bash
python create_simready_package.py apple_a01 1.0.0 Apache-2.0 \
    ~/my_asset/simready_usd ~/my_repo \
    --root-usd sm_apple_a01_01.usd
```

All three phases run by default. The script exits `0` only if every
phase that ran exited `0`; otherwise it exits with the non-zero exit
code of the first phase to fail.

### Skip a phase

If you've already done one phase by hand, pass the matching opt-out
flag to skip it:

- `--skip-pre-validation` — go straight to the build (use after a
  separate pre-validation run).
- `--skip-post-validation` — stop after the build (use when you'll
  validate the published package later).

```bash
python create_simready_package.py apple_a01 1.0.0 MIT \
    ~/my_asset/simready_usd ~/my_repo \
    --skip-post-validation
```

### Run a single phase

Two `--only-*` modes run a single phase against the matching input.
They are mutually exclusive with each other and with the default flow
(positional arguments are rejected):

- `--only-pre-validation --source <folder>` — pre-flight a candidate
  source folder. The headline check is
  [AA.001 — anchored-asset-paths](../sr_specs/docs/capabilities/core/atomic_asset/requirements/anchored-asset-paths.md):
  every reference in every USD has to be written as a relative path
  (e.g. `./materials/wood.mdl`), not an absolute path or a search-path
  token. Useful while iterating on a folder before you're ready to
  build.
- `--only-post-validation --package-def <path-to-com.nvidia.simready.packaging.json>`
  — run the SimReady `Package` profile against an already-built
  package definition. Useful for re-checking a package you (or
  someone else) published earlier.

```bash
python create_simready_package.py --only-pre-validation \
    --source ~/my_asset/simready_usd \
    --root-usd sm_apple_a01_01.usd

python create_simready_package.py --only-post-validation \
    --package-def ~/my_repo/.packages/apple_a01/1.0.0/com.nvidia.simready.packaging.json
```

### Conformance metadata flags

These flags control the `.metadata/` artefacts that the packaging
workflow produces:

- `--write-metadata` — during pre-validation, write `.metadata/`
  files (BOM, `root_usds.json`, conformance JSONs with
  `content_hash`).  **Enabled implicitly** in the default full flow
  so the create step can verify and register them.  Use explicitly
  with `--only-pre-validation` to produce `.metadata/` without
  running the create step.
- `--write-evidence` — during post-validation, write a conformance
  evidence JSON into `.metadata/` for each validated profile.
  **Enabled implicitly** in the default full flow.  Use explicitly
  with `--only-post-validation` to capture post-validation results.
  Evidence files are **not** covered by `package_hash` (they are
  post-creation artefacts).
- `--profile PROFILE` — validation profile to use (repeatable).
  Defaults to `Package-Candidate` for pre-validation, `Package` for
  post-validation.
- `--root-usd PATH` — relative path of a root USD file inside
  `<source>` (repeatable).  Required unless
  `.metadata/com.nvidia.simready.root_usds.json` already exists from
  a prior run.  If the source folder intentionally contains no USD
  files, pass `--no-usd-files` instead.
- `--no-usd-files` — allow pre-validation to succeed when no root USD
  files are found.  Use this for source folders that intentionally
  contain no USD content.  Without this flag, an empty source folder
  is treated as a usage error.

### Lightweight: no-BOM, no-WRAPP package

If you don't need a full BOM-bearing package — for example, while
prototyping, or in environments where you can't install the WRAPP
wheel — pass `--no-wrapp` to swap the build phase for a minimal
alternative. Instead of producing a WRAPP package, the script writes
a single `com.nvidia.simready.packaging.json` straight into your
`<source>` folder containing only the three fields the SimReady
packaging standard marks as required (`format_version`, `package_id`,
`license`). No BOM, no `.metadata/` folder, no file hashes.

The `<source>` folder *is* the package in this mode, so the `<repo>`
positional argument is dropped:

```bash
python create_simready_package.py apple_a01 1.0.0 Apache-2.0 \
    ~/my_asset/simready_usd \
    --no-wrapp
```

Pre-validation still runs by default, and so does post-validation —
but the resulting package will FAIL post-validation features that
look for a BOM (e.g. `FET032_PACKAGING_INTROSPECTION`). That's
expected. If you want a clean exit code in this mode, also pass
`--skip-post-validation`.

This path is also the only way to use the script when the WRAPP
wheel is not available: `import wrapp` is loaded lazily, so
`--no-wrapp` (and the `--only-*` validation modes) keep working even
if `setup_venv.sh` was never given a `--wrapp-wheel`.

---

## Advanced: integrate via Python API

The `sr_pkg_sample/` package exposes two top-level async workflow
functions that mirror the CLI — call them from your own tooling
instead of shelling out to `create_simready_package.py`:

```python
import asyncio
import simready.validate as sv

from sr_pkg_sample import (
    FOUNDATIONS_DOCS_DIR,
    PackagingError,
    ValidationFailed,
    create_simready_package,
)
from sr_pkg_sample._asset_validator_kit_shim import install_kit_shim

# One-time setup (once per process).
install_kit_shim()
sv.initialize(
    rules_and_requirements_paths=[FOUNDATIONS_DOCS_DIR / "capabilities"],
    features_paths=[FOUNDATIONS_DOCS_DIR / "features"],
    profiles_paths=[FOUNDATIONS_DOCS_DIR / "profiles" / "profiles.toml"],
)

async def main():
    try:
        created = await create_simready_package(
            "apple_a01", "1.0.0", "MIT",
            "~/my_asset/simready_usd", "~/my_repo",
        )
        print(f"Package definition: {created.pkg_def_url}")
    except ValidationFailed as exc:
        print(f"validation failed: {exc.failures}")
    except PackagingError as exc:
        print(f"packaging failed: {exc}")

asyncio.run(main())
```

For the WRAPP-free alternative, swap in
`create_simready_package_no_wrapp` (same signature minus `repo`).

Both functions return a `CreatedPackage` on success and raise a
`PackagingError` subclass on failure:

| Exception | When it is raised |
|---|---|
| `UsageError` | Caller-supplied input is wrong (path missing, mismatched `.wrapp` marker, ...). |
| `ValidationFailed` | Validation completed but features failed. `failures` carries the sorted list of failing feature IDs. |
| `BuildFailed` | The create step's underlying build failed (WRAPP / I/O error). The original exception is reachable via `__cause__`. |

**Key function signatures** (all are `async`):

```python
await create_simready_package(name, version, license_id, source, repo,
    *, profiles=None, root_usds=None,
    skip_pre_validation=False, skip_post_validation=False) -> CreatedPackage

await create_simready_package_no_wrapp(name, version, license_id, source,
    *, profiles=None, root_usds=None,
    skip_pre_validation=False, skip_post_validation=False) -> CreatedPackage
```

The individual phase functions (`pre_validate`, `create_package`,
`post_validate`) are also importable from `sr_pkg_sample/` if you need
finer-grained control.

Each function prints the same `PASS` / `FAIL` lines on stdout that the
script does — capture them with `contextlib.redirect_stdout` if you
want to surface the per-feature summary in your own UI.

Swap `create_package` for `sr_pkg_sample.create_package_definition(name,
version, license, source)` to use the WRAPP-less, no-BOM build path
described above. It has the same signature minus the `repo`
argument, returns a `CreatedPackage` whose `bom_url` is `None`, and
raises the same `PackagingError` subclasses on failure.

---

## Tests

Integration tests live under `tests/`. The per-phase tests drive the
public `sr_pkg_sample.*` async API directly via `pytest-asyncio` and
`pytest.capsys`; the end-to-end tests go through `subprocess.run` so
they cover the script's CLI surface (argument parsing, `--only-*`,
`--skip-*`).

```bash
cd simready_foundations/nv_core/package_sample
source .venv/bin/activate
pytest tests/ -v
```

The create-step tests are marked `skip` if the WRAPP wheel hasn't been
installed into the venv, so the rest of the suite still runs without
NGC access.
