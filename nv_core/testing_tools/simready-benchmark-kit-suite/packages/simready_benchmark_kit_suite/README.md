# simready-benchmark-kit-suite

Built-in FET test suite (FET001-FET022) targeting the Kit engine plugin.
Includes visual, physics, multibody, grasp, and driven-joint validations.

Registered via the `simready_benchmark.tests` entry-point group; the
`simready-benchmark` CLI auto-discovers tests defined here once the wheel is
installed.

## Install

```
pip install simready-benchmark-kit-suite
# Equivalent to: pip install simready-benchmark[kit-suite]
```

Runtime dependencies pulled in by pip:

- `simready-benchmark` — the framework core
- `usd-core>=23.5` — provides the `pxr` module that the test phases
  import at module load. Inside Kit / Isaac Sim, `pxr` comes from the
  runtime; outside Kit (running unit tests, listing tests on a CI
  machine without Kit installed, static analysis) `usd-core` from
  PyPI supplies the same `pxr` module. `usd-core` is the headless
  USD distribution — no GPU / Hydra renderers — so it doesn't bloat
  installs that already have Kit available.

## What's inside

| Group | Description |
|---|---|
| FET001 | Visual validation (presence, normals, culling, lighting) |
| FET003 | Physics ground/slope drop, stability |
| FET004 | Multibody / joint discovery + movement |
| FET005 | Grasp + lift |
| FET022 | Driven joints (full-range sweep, velocity limit, mimic, multi-joint) |

## Adding new tests

### Test descriptions

Every `@test(...)` call must include `description` and `expected_video`
kwargs (both non-empty plain-text strings). They surface in `result.json`
and the HTML report so reviewers know what each test verifies and what a
passing run looks like in the captured video — without reading the source.
See `CONTRIBUTING.md` for the authoring style guide.

## Documentation

https://docs.omniverse.nvidia.com/simready

## License

Apache-2.0.
