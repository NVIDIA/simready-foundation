# Pipeline and Stages

Unlike single-command [schema validation](../validate_workflow.md), benchmarking is a pipeline. A run
moves each asset through four stages: plan, run, stamp, and report. You start the pipeline with a
`simready-benchmark` command; flags such as `--plan-only` and `--no-stamp` control which stages run and what
is written. Refer to [Next Steps](#next-steps) to set up the tool and read results.

## Plan

The planner discovers which tests are eligible for an asset from the [features and profiles](overview.md#relationship-to-features-and-profiles) that the asset declares. It then writes a plan that lists the work to run.

To produce the plan without running it, use `simready-benchmark --plan-only`. To list
the tests available for selection, use `simready-benchmark --list-tests`.

## Run

The runner launches the engine and executes the planned tests against the asset.
For each test, it records the outcome, captures screenshots, and collects the
engine logs, so a failure can be understood after the run.

## Stamp

After tests execute, the stamper copies the root USD into the run's `results/`
mirror and writes a benchmark receipt to that copy and its sibling
`.simready/validation.json`. The source asset is never modified. This receipt is
distinct from static schema-validation results: it records runtime outcomes.
The USD mirror stores it under
`customLayerData["SimReady_Metadata"]["runtime_testing"]`, grouped by feature
under `tested_features`. Refer to
[Reading Reports](reading-reports.md#the-runtime-stamp) for the receipt structure.
Refer to [Verify a Clean Run](reading-reports.md#verify-a-clean-run). To run without writing the receipt, use
`simready-benchmark --no-stamp`.

## Report

The reporter aggregates per-test results into `<run>/index.html`,
`<run>/run_summary.json`, and
`<run>/report/test_results_index.json`. Benchmark prints the resolved fresh run
directory; an existing requested output directory is never cleared. Refer to
[Next Steps](#next-steps) to interpret these files.

## Next Steps

- [Running Tests](running.md): set up `simready-benchmark`, configure the engine, and run tests
- [Reading Reports](reading-reports.md): interpret results, exit codes, and [Verify a Clean Run](reading-reports.md#verify-a-clean-run)
