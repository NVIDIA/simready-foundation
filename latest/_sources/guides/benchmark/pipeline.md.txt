# Pipeline and Stages

Unlike single-command [schema validation](../validate_workflow.md), benchmarking is a pipeline. A run
moves each asset through four stages: plan, run, stamp, and report. You start the pipeline with a
`simready-benchmark` command; flags such as `--plan-only` and `--no-stamp` control which stages run and what
is written. Refer to [Next Steps](#next-steps) to set up the tool and read results.

## Plan

The planner discovers which tests are eligible for an asset from the [features and profiles](overview.md#relationship-to-features-and-profiles) the asset declares. It then writes a plan that lists the work to run.

To produce the plan without running it, use `simready-benchmark --plan-only`. To list
the tests available for selection, use `simready-benchmark --list-tests`.

## Run

The runner launches the engine and executes the planned tests against the asset.
For each test it records the outcome, captures screenshots, and collects the
engine logs, so a failure can be understood after the run.

## Stamp

After tests execute, the stamper writes a benchmark receipt into the asset. This
receipt is distinct from the schema-validation stamp: it records benchmark
outcomes rather than requirement-rule results from schema validation. The receipt
is written into `customLayerData["SimReady_Metadata"]["runtime_testing"]`
on the USD asset, grouped by feature under `tested_features`. Refer to
[Reading Reports](reading-reports.md#the-runtime-stamp) for the receipt structure.
Refer to [Next Steps](#next-steps) to verify a clean pass. To run without writing the receipt, use
`simready-benchmark --no-stamp`.

## Report

The reporter aggregates the per-test results into an HTML report
(`_testing/index.html`) and JSON reports (`_testing/test_results.json` and
`_testing/report/test_results_index.json`). Refer to [Next Steps](#next-steps) to interpret them.

## Next Steps

- [Running Tests](running.md): set up `simready-benchmark`, configure the engine, and run tests
- [Reading Reports](reading-reports.md): interpret results, exit codes, and [verify a clean pass](reading-reports.md#verify-a-clean-pass)
