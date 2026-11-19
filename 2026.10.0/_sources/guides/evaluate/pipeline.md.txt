# Pipeline and Stages

Unlike single-command [schema validation](../validate_workflow.md), evaluating is a pipeline. A run
moves each asset through four stages: plan, run, stamp, and report. You start the pipeline with a
`simready-evaluate` command; flags such as `--plan-only` and `--no-stamp` control which stages run and what
is written. Refer to [Next Steps](#next-steps) to set up the tool and read results.

## Plan

The planner discovers eligible tests from the resolved profile targets supplied
by the caller. It writes a plan for each target that lists the work to run; the
asset does not declare one exclusive profile.

To produce the plan without running it, use `simready-evaluate --plan-only`. To list
the tests available for selection, use `simready-evaluate --list-tests`.

## Run

The runner launches the engine and executes the planned tests against the asset.
For each test, it records the outcome, captures screenshots, and collects the
engine logs, so a failure can be understood after the run.

## Stamp

After tests execute, the stamper copies the root USD into the run's `results/`
mirror and writes an evaluation receipt to that copy and its sibling
`.simready/assets/<asset-key>/validation.json`. The asset key hashes the complete
USD filename, including its extension, so sibling assets cannot overwrite one
another's evidence. Legacy directory-level receipts remain readable when no
asset-owned receipt exists. The source asset is never modified. This receipt is
distinct from static schema-validation results: it records runtime outcomes.
The USD mirror stores it under
`customLayerData["SimReady_Metadata"]["runtime_testing"]`, grouped by feature
under `tested_features`. Refer to
[Reading Reports](reading-reports.md#the-runtime-stamp) for the receipt structure.
Refer to [Verify a Clean Run](reading-reports.md#verify-a-clean-run). To run without writing the receipt, use
`simready-evaluate --no-stamp`.

## Report

The reporter aggregates per-test results into `<run>/index.html`,
`<run>/run_summary.json`, and
`<run>/report/test_results_index.json`. Evaluate prints the resolved fresh run
directory; an existing requested output directory is never cleared. Refer to
[Next Steps](#next-steps) to interpret these files.

## Next Steps

- [Running Tests](running.md): set up `simready-evaluate`, configure the engine, and run tests
- [Reading Reports](reading-reports.md): interpret results, exit codes, and [Verify a Clean Run](reading-reports.md#verify-a-clean-run)
