# SimReady Foundation Benchmark Kit Suite

This package contains the runtime tests owned by the SimReady Foundation core
tier. The tests are inert Python definitions until `simready-benchmark`
discovers the tier's lightweight `simready.tier` descriptor and imports this
package in a compatible Kit or Isaac Sim runtime.

The tier wheel ships its validation catalogs and this runtime-test package
together. An installed tier advertises the package through `runtime_tests_path`;
independent test-only distributions use the separate
`simready_benchmark.tests` entry-point group.

## Shipped test families

| Family | Enabled runtime coverage |
|---|---|
| FET001 | Presence, normals, culling, lighting response, and pivot placement |
| FET003 | Ground and slope drop behavior for Standard, PhysX, and Newton rigid bodies |
| FET004 | Multibody joint movement for Standard, PhysX, Newton, and legacy robot variants |
| FET005 | Parallel-jaw grasp, lift, hold, shake, and release |
| FET011 | Labelled and stripped semantic-segmentation evidence |
| FET022 | Driven-joint behavior for PhysX and Isaac features |
| FET028 | Isaac gripper close, lift, shake, and release with sphere and cube payloads |

Family labels such as `FET001` are reporting and CLI-filter groups, not feature
manifest IDs. A family can exercise one or more canonical feature variants. For
example, the `FET001` family maps to `FET_001_STANDARD`, while `FET003` maps to
the Standard, PhysX, and Newton variants of that feature. There is intentionally
no feature manifest whose ID is only `FET001`.

The `features` argument on each enabled `@test` decorator is the executable
mapping to the owning feature manifests. Automation must resolve those exact
canonical IDs and version constraints rather than deriving a manifest name from
the family label, package directory, documentation filename, or heading.

The enabled decorators are the executable source of truth. See the
[Benchmark reference](docs/tests.md) for the per-family and per-test contract,
and [Experimental and disabled tests](docs/experimental.md) for implementations
that are intentionally not advertised as shipped coverage.

## Discovery and local verification

With the tier installed:

```bash
python -m pip install "simready-foundation-tier-core[benchmark]"
simready-benchmark --show-config
simready-benchmark --list-tests
```

From a Foundation source checkout, the checkout supplies both tier catalogs and
runtime tests:

```bash
simready-benchmark --foundations-path <path-to-simready-foundations> --list-tests
simready-benchmark --foundations-path <path-to-simready-foundations> \
  --assets <path-to-asset.usd> --plan-only
```

Use `--tests-path` only for an additional unpublished test package. It is not
required for this suite when the tier is installed or `--foundations-path` is
used.

## Source layout

```text
simready_benchmark_kit_suite/
  fet001_visual/ ... fet028_gripper/   enabled and experimental test modules
  articulation_phases/                shared articulation behavior
  docs/                                authoritative family/test documentation
  README.md                            this package overview
```

Contributor rules, documentation requirements, and focused verification steps
are in [Authoring runtime tests](docs/authoring.md).
