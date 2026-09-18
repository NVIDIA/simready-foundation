# Reading Benchmark Reports

This page describes the current run-output contract, result states, exit codes,
and the optional stamp written to the run's asset mirror.

## Find the Resolved Output Directory

Benchmark creates a fresh directory for every run and prints its resolved path
when the command completes. It never clears an existing requested directory.
When `--output-dir DIR` names a directory that already exists, Benchmark creates
`DIR/benchmark_testing`, then `benchmark_testing_1`, and so on. Use the printed
path rather than assuming that the requested path was used directly.

Each allocated directory contains a `.simready-benchmark-output.json` ownership
marker. Benchmark cleanup is limited to framework-owned artifacts inside that
marked run directory.

## Output Layout

```text
<run>/
|-- .simready-benchmark-output.json
|-- plan.json
|-- run_summary.json
|-- index.html
|-- logs/
|   |-- orchestrator.log
|   `-- <engine-session>.log
|-- state/
|   |-- events.jsonl
|   `-- work_pool.json
|-- report/
|   `-- test_results_index.json
`-- results/
    `-- <asset-relative-path>/
        |-- <asset>.usd
        `-- .simready/
            |-- validation.json
            `-- runtime/<test-name>/<engine>/
                |-- result.json
                `-- <images, videos, logs, or USD recordings>
```

The exact media files depend on the test. Paths in
`report/test_results_index.json` and per-test `result.json` are authoritative.

## Which File to Read

| File | Purpose |
|---|---|
| `index.html` | Human-readable asset, feature, test, engine, media, and diagnostic views. |
| `run_summary.json` | Top-level automation status, readiness, completed work, and failed work. |
| `report/test_results_index.json` | Detailed result rows and paths to per-test evidence. |
| `state/events.jsonl` | Append-only execution events for debugging and integrations. |
| `state/work_pool.json` | Runtime work-item state; use reports for final pass/fail decisions. |
| `results/**/.simready/runtime/**/result.json` | The result and metrics for one asset, test, and engine. |

For CI, gate on the process exit code and retain the complete run directory as
an artifact. For diagnostics, start with `index.html`, then open the failing
row's engine log and per-test evidence.

## Result States

Individual result rows can be `pass`, `fail`, `skipped`, or an execution state
such as `error`, `blocked`, or `incomplete`. A skipped test is not evidence that
the behavior passed; its message explains why the test was not applicable or
could not run. A validation-gated feature can also be reported as not tested
when its static feature contract did not pass.

A clean run has no failed or non-terminal planned work. Do not infer success
from the presence of media or from a completed engine session alone.

## Exit Codes

| Exit code | Meaning |
|---|---|
| `0` | The requested command completed without failed work. |
| `1` | A runtime test, stage, report, stamp, or setup operation failed. |
| `2` | Invalid command-line input or invalid stage input. |
| `3` | A required plan or result contract is missing. |
| `4` | The selected runtime is not ready. |
| `130` | The command was interrupted. |

Treat only exit code `0` as success in automation. Also retain
`run_summary.json` and `report/test_results_index.json` so a failure can be
diagnosed without rerunning the engine.

## Verify a Clean Run

1. Confirm that the process exit code is `0`.
2. Read `run_summary.json`; verify that readiness is `ready`, `failed` is zero,
   and the top-level status is successful.
3. Inspect `report/test_results_index.json`; verify that every planned result
   has the intended terminal state. Treat `skipped` according to the test's
   applicability contract rather than as behavioral proof.
4. Open `index.html` and review videos, images, USD recordings, metrics, and
   engine logs for the rows that matter to the acceptance decision.
5. If stamping was enabled, inspect the mirror USD and sibling
   `.simready/validation.json` described below.

PowerShell exposes the command exit code through `$LASTEXITCODE`; POSIX shells
use `$?`.

## The Runtime Stamp

Stamping is enabled by default and can be disabled with `--no-stamp`. Benchmark
does **not** modify the source asset. It copies the root USD into `results/`
using the asset's relative mirror path, then writes run metadata to that copy
and to its sibling `.simready/validation.json`.

The USD copy receives this nested `customLayerData` shape:

```text
SimReady_Metadata
`-- runtime_testing
    `-- tested_features
        `-- <ISO timestamp>
            `-- FET_001_STANDARD
                |-- passed
                |-- version
                `-- tests
                    `-- <test source or name>
                        `-- passed
```

Feature IDs and versions come from the actual test registration and plan; they
use canonical IDs such as `FET_001_STANDARD` and semantic versions. Re-stamping
the same mirror adds a timestamped sibling and preserves unrelated
`customLayerData`.

The `.simready/validation.json` mirror sidecar carries the corresponding static
validation and runtime-test receipt for consumers that do not read USD
`customLayerData`. It intentionally lives beside the mirror USD. Materials and
textures are not copied merely to make the stamped root USD a standalone asset;
open the original source asset for authoring, and use the mirror as report
evidence.

## Multiple Engines and Assets

One report can contain several assets and several engines. Result identity is
the asset, feature, test, and engine tuple. Use the engine filter in the HTML
report or the engine field in JSON rather than combining rows from different
physics runtimes. The planner may select different feature variants for PhysX,
Newton, or another configured runtime.

## Related Pages

- [SimReady Benchmark Overview](overview.md)
- [Pipeline and Stages](pipeline.md)
- [Running Tests](running.md)
- [Benchmark Test Reference](tests/tests.md)
