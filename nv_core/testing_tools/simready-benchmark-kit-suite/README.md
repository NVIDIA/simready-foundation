# simready-benchmark-kit-suite

Built-in FET test suite (FET001-FET022) for the
[SimReady Benchmark](https://docs.omniverse.nvidia.com/simready),
targeting the Kit / Isaac Sim engine. Registers against the framework's
`simready_benchmark.tests` entry-point group; the framework's CLI auto-discovers
this suite once it is installed.

## Install

For end users:

```bash
# Default: pulls the framework + Kit plugin + this suite together
pip install simready-benchmark[kit-suite]

# Or install just this wheel against an existing framework install
pip install simready-benchmark-kit-suite
```

This wheel depends on:

- `simready-benchmark>=2026.6.0` — the framework core
- `usd-core>=23.5` — provides the `pxr` module that the test phases
  import at module load. Inside Kit / Isaac Sim, `pxr` comes from the
  runtime; outside Kit (running unit tests, listing tests on a CI
  machine without Kit installed, static analysis) `usd-core` from PyPI
  supplies the same `pxr` module. `usd-core` is the headless USD
  distribution — no GPU / Hydra renderers — so it doesn't bloat installs
  that already have Kit available.

pip resolves both dependencies automatically when installing from PyPI.

## What's inside

| Group | Description |
|---|---|
| FET001 | Visual validation (presence, normals, culling, lighting) |
| FET003 | Physics ground/slope drop, stability |
| FET004 | Multibody / joint discovery + movement |
| FET005 | Grasp + lift |
| FET022 | Driven joints (full-range sweep, velocity limit, mimic, multi-joint, IK, Jacobian) |

After installing, list the registered tests with the framework's CLI:

```bash
simready-benchmark --list-tests
```

## Contributing

To work on this suite from a local clone, install editable:

```bash
py install.py
```

`install.py` performs an editable install of the suite wheel and verifies
the entry point registered. The framework (`simready-benchmark>=2026.6.0`) must
already be available -- pip pulls it from PyPI if it isn't already in
site-packages.

Run the utility-test suite (pure Python, no Kit required):

```bash
pytest
```

## Adding new tests

The test-author guide lives in the framework's documentation, including
the `@test` decorator reference, packaging your own test pack, and
publishing it to PyPI:

- [Writing Tests](https://docs.omniverse.nvidia.com/simready/kit-tests/writing-tests/)
- [Kit Tests Concepts](https://docs.omniverse.nvidia.com/simready/kit-tests/concepts/)

The short version: write `@test`-decorated async functions, register the
package via the `simready_benchmark.tests` entry-point group in your own
`pyproject.toml`, build a wheel, publish to PyPI. The framework picks up
your tests alongside this suite automatically.

## Discovering this suite without pip-installing

If you cannot install from PyPI (air-gapped CI, pre-release bootstrap),
the framework's CLI accepts a `--tests-path` flag, a `SIMREADY_BENCHMARK_TESTS_PATH`
env var, or a `[tests].paths` list in `engines.toml` pointing at this
package's source directory. See the framework's
[Getting Started](https://docs.omniverse.nvidia.com/simready/getting-started/)
guide for the full lookup-order semantics.

## License

Apache-2.0.
