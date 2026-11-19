# simready-multiphysics-upgrade

Standalone distribution of the SimReady multiphysics upgrade pipeline. It turns
a neutral prop package into a package that carries isolated PhysX, Newton, and
MuJoCo runtime payloads, then composes the Isaac Sim interface layer over the
result.

The package depends on `pxr` for stage mutation and on
the transformer bundled in `simready-foundation-tier-core` for Isaac composition.
Isaac conversion requires Python 3.12 and the `isaac` extra. The base package
supports Python 3.11–3.13, the range of the tier core it depends on. It requires no
Omniverse Kit runtime, no `omni.cip`, and no repository checkout.

## Install

```bash
pip install "simready-multiphysics-upgrade[isaac]"
```

For a source checkout:

```bash
cd nv_core/cip_specs/multiphysics_upgrade
python -m pip install -e ".[usd,test,isaac]"
```

## Python API

The offline wheelhouse builder uses the tier-core project (including its
bundled transformer), resolves its Isaac dependencies, and targets Python 3.12
(`cp312`). Run the builder and smoke test with that interpreter.

```python
from simready.multiphysics_upgrade import run_neutral_to_runtimes

result = run_neutral_to_runtimes(
    "C:/assets/sm_prop_01/staging/sm_prop_01.usd",
    "C:/assets/sm_prop_01/simready_usd",
    replace_existing=True,
    report_path="C:/assets/sm_prop_01/.diagnostics/report.json",
    diagnostics_dir="C:/assets/sm_prop_01/.diagnostics",
)
if not result.ok:
    for error in result.errors:
        print(error.stage, error.code, error.detail)
```

The source package is never modified. Work happens in a staging directory next
to the destination; the destination is replaced only after the whole pipeline
succeeds, and a pre-existing destination is restored if promotion fails.

## Authored joint drives

The converter preserves static standard USD drives on matching joint types:
`PhysicsDriveAPI:angular` on revolute joints and `PhysicsDriveAPI:linear` on
prismatic joints. It accepts force or acceleration drives with finite targets,
nonnegative finite stiffness/damping, and nonnegative effort limits (including
positive infinity for unlimited effort). Schema fallback values are supported.

Other axes/joint types, time-sampled drive values, malformed API tokens, and
invalid values still require explicit handling. Runtime-specific mimics,
actuators, articulation settings, and scene APIs retain their existing blockers.
Preserving USD drive data does not establish equivalent actuation in every
runtime; the converter does not synthesize MuJoCo actuators.

## JSON sidecar

Host applications that cannot import USD in-process (for example the SimReady
Blender add-on running on Blender's Python 3.13) invoke the one-shot sidecar in
a Python 3.12 interpreter for Isaac conversion. It reads one JSON request on stdin and writes one
JSON response on stdout; diagnostics go to stderr.

```bash
echo '{"protocol_version": 1, "op": "neutral_to_runtimes", "source_usd": "staging/sm_prop_01.usd", "output_folder": "simready_usd", "replace_existing": true}' | simready-multiphysics-sidecar
```

`{"op": "ping"}` reports the protocol version, package version, and interpreter
version without touching any asset.

Exit codes: `0` success, `1` transformation failure, `2` malformed or
unsupported request.

## Offline wheelhouse

Host applications install from a self-contained wheelhouse instead of reaching
the network:

```bash
python tools/build_wheelhouse.py --output _build/wheelhouse
python tools/verify_wheelhouse.py _build/wheelhouse
python tools/wheelhouse_smoke_test.py _build/wheelhouse
```

One bundle carries every SimReady sidecar, so the build also includes the
sibling [`simready-metadata-conform`](../metadata_conform/README.md)
distribution. Both sidecars share `usd-core` and one install target; shipping
two wheelhouses would duplicate the largest wheels and give a host two install
states to keep in sync.

The build produces `wheels/`, `licenses/`, and a `wheelhouse.json` manifest that
records distribution versions, target interpreter and platform, license
artifacts, and SHA-256 hashes. Third-party pins live in
`tools/requirements-runtime.txt`.

Each sidecar is listed in the manifest's `sidecars` array by a stable `name`:

```json
"sidecars": [
  {"name": "multiphysics", "module": "simready.multiphysics_upgrade.sidecar",
   "protocol_version": 1, "distribution": "simready-multiphysics-upgrade"},
  {"name": "metadata", "module": "simready.metadata_conform.sidecar",
   "protocol_version": 1, "distribution": "simready-metadata-conform"}
]
```

The original top-level `sidecar_module` and `protocol_version` keys are kept,
pointing at multiphysics, so a host built against the single-sidecar manifest
still resolves. `verify_wheelhouse.py` fails the bundle when the two disagree.

`build_wheelhouse.py` runs the smoke test by default; pass `--skip-smoke-test`
on hosts that cannot install the target platform's wheels, and rely on
`verify_wheelhouse.py` there. The smoke test installs with
`pip install --no-index --find-links`, then chains both sidecars over a fixture
in subprocesses whose only import path is the install target, so a build that
secretly depends on a repository checkout fails.

### Shipping the wheelhouse in the Blender add-on

The SimReady Blender add-on bundles this wheelhouse so prop upgrades and
metadata conformance work with no network. Stage a fresh build into the add-on
repository with:

```bash
cd path/to/simready-blender-addons
python tools/scripts/stage_multiphysics_wheelhouse.py \
    --source path/to/simready_foundations/nv_core/cip_specs/multiphysics_upgrade/_build/wheelhouse
```

Staging verifies the source bundle before replacing the existing one, and the
add-on's own packaging gate (`tools/scripts/verify_bundled_wheelhouse.py`, run
by both its build and validate jobs) fails the release ZIP when a wheel, hash,
license artifact, sidecar entry, or protocol version is missing or mismatched.
Bumping `PROTOCOL_VERSION` in either package's `protocol.py` therefore requires
the matching bump in the add-on's `multiphysics/runtime.py` or
`metadata/runtime.py`.

## Profile-aware upgrade runner

The `simready-multiphysics-upgrade` console script runs the profile-to-profile
edge sequence and needs Foundation tier data. It resolves that data from an
installed `simready-foundation-tier-core`, from `SIMREADY_TIER_CORE_ROOT`, or
from a repository checkout, in that order.

```bash
simready-multiphysics-upgrade --plan path/to/source.usda
simready-multiphysics-upgrade --output path/to/staged --report report.json path/to/source.usda
```

## Tests

```bash
python -m pytest tests -q
```
