# Reading Reports

This page describes where a run writes its output, how to read outcomes and exit
codes, and the benchmark receipt written into each source USD asset.

## Output Layout

By default, a run writes output under `_testing/` at the project root that
`simready-benchmark` is configured to use, typically your SimReady Foundation clone.
You can override the output directory in engine configuration.

Top-level reports and artifacts under `_testing/` belong to the run. The
benchmark receipt is written into each source USD asset and travels with
that asset after the run output is deleted or archived. The subsections below
cover run output first, then the asset receipt.

### Run Output Under `_testing/`

Every run produces the same top-level folder layout. The following subsections
describe how that layout is populated for different command patterns.

```text
_testing/
├── index.html                          the HTML report
├── test_results.json                   pass/fail summary per test
├── report/
│   └── test_results_index.json         grouped index into per-asset artifacts
├── batch_jobs/
│   └── local_test_<platform>.json      job plan for the current run
└── job_outputs/
    └── <runner>/<job_id>/<asset_id>/   per-asset artifacts (XML, screenshots, logs)
```

Open `index.html` to view per-test outcomes, screenshots, and stamping status from
the run. Folder names under `job_outputs/` (runner prefix, job ID, asset ID) depend
on runner configuration and how tests are batched. Refer to
`report/test_results_index.json` for the paths used in the current report.

#### Single Asset, Single Command

This is the default case: one asset on one `simready-benchmark` command.

```bash
simready-benchmark --assets path/to/asset.usd
```

One pipeline run writes one job plan, one set of reports, and one artifact folder.
`index.html` and `test_results.json` describe that asset only. Artifacts land
under a single folder such as `job_outputs/<runner_name>/job_00001/asset_0000/`.

#### Multiple Assets, Single Command

When you specify more than one asset on a single `simready-benchmark` command, one pipeline
run writes one job plan and one set of reports. The plan in
`batch_jobs/local_test_<platform>.json` schedules every asset on the command line.
After tests execute, `index.html` and `test_results.json` aggregate pass/fail outcomes
for all of them. Under `job_outputs/`, each asset gets its own folder, typically as siblings under
the same job:

```text
job_outputs/
└── <runner_name>/
    └── job_00001/
        ├── asset_0000/                 first asset (test_results.xml, logs, …)
        └── asset_0001/                 second asset
```

The exact IDs can differ; treat the index JSON as the source of truth for paths.

#### Multiple Assets, Multiple Commands

Each `simready-benchmark` invocation runs the full pipeline again. The example below uses
two successive commands with one asset each:

```bash
simready-benchmark --assets path/to/apple.usd
simready-benchmark --assets path/to/orange.usd
```

Each run writes the same `batch_jobs/local_test_<platform>.json` filename, so
`index.html` and `test_results.json` reflect the latest command's asset in the
typical case. The `keep_outputs` flag controls what is cleaned under `_testing/`
between runs.

- **If you specify `keep_outputs`**, `simready-benchmark` keeps prior files under
  `batch_jobs/` and `report/` instead of clearing those folders. Each run
  writes a new job plan, refreshes `index.html` and `test_results.json`, and
  replaces artifacts in the current runner's folder under `job_outputs/`. The
  latest pass/fail results are in those top-level reports; extra files from
  earlier runs might remain on disk:

  ```text
  _testing/
  ├── index.html                          latest asset (orange)
  ├── test_results.json
  ├── report/
  │   ├── test_results_index_prior.json   existing report from an earlier session
  │   ├── test_results_index_apple.json   from the apple command
  │   └── test_results_index.json         from the orange command (latest)
  ├── batch_jobs/
  │   ├── local_test_<platform>.json      overwritten each run (same platform)
  │   └── local_test_<other_platform>.json   other platform (unchanged by this run)
  └── job_outputs/
      └── <runner_name>/
          └── job_00001/
              └── asset_0000/             same path each run; contents replaced
  ```

  Use `index.html` or `test_results.json` for the latest command. Older files under
  `report/` or `batch_jobs/` might not match those reports.

- **If you do not specify `keep_outputs`** (the default), the plan stage clears
  `batch_jobs/` before writing a new job file. The run stage clears all of
  `job_outputs/`. The report stage regenerates `index.html` and
  `test_results.json` and removes and recreates `report/`. Only the latest
  command's plan and artifacts remain:

  ```text
  _testing/
  ├── index.html                          latest asset (orange)
  ├── test_results.json
  ├── report/
  │   └── test_results_index.json
  ├── batch_jobs/
  │   └── local_test_<platform>.json
  └── job_outputs/
      └── <runner_name>/
          └── job_00001/
              └── asset_0000/
  ```

  `index.html` and `test_results.json` reflect the latest command only. No output
  from earlier commands remains under `_testing/`.

To reset `_testing/` completely (for example, when using `keep_outputs`), remove
the folder before the next run.

#### Asset Plan, Artifacts, and Reports

When troubleshooting or reporting a problem, trace one asset across the job plan,
its artifact folder, and the JSON report. The plan assigns paths, tests write XML
and other files into those folders, and the report stage reads the XML and fills in
pass/fail fields.

**Plan** (`batch_jobs/local_test_<platform>.json`): each job lists its assets and
output folder names. A multi-asset run uses sibling folders such as `asset_0000` and
`asset_0001`:

```json
"job_output_dir": "<runner_name>/job_00001",
"assets": [
  {
    "asset": "assets/apple.usd",
    "asset_output_dir": "asset_0000",
    "matched_features": [{ "id": "FET001", "version": "1.0" }]
  },
  {
    "asset": "assets/orange.usd",
    "asset_output_dir": "asset_0001",
    "matched_features": [{ "id": "FET001", "version": "1.0" }]
  }
]
```

**Artifacts** (`job_outputs/<runner_name>/job_00001/asset_0000/`): the test run
writes results here. The report generator looks for `test_results.xml` or
`report.xml`; other files (screenshots, videos, logs) depend on the test:

```text
job_outputs/<runner_name>/job_00001/asset_0000/
├── test_results.xml          pass/fail source for the report
└── …                         other artifacts the test produced
```

**Report** (`test_results.json`): one object per asset path, with a `tests` array
built from the XML in each artifact folder. The `output_folder` field points back
to that folder:

```json
{
  "asset_path": "assets/apple.usd",
  "tests": [
    {
      "test_name": "FET001 Visual Pivot",
      "test_passed": true,
      "output_folder": "job_outputs/<runner_name>/job_00001/asset_0000",
      "features": [{ "id": "FET001", "version": "1.0" }]
    }
  ]
}
```

Refer to [Verify a Clean Pass](#verify-a-clean-pass) for how to read `test_passed`.

### Runtime Stamp on the Asset

The durable output of a run is also written into each source USD asset. Unlike
`_testing/`, that receipt travels with the asset. Refer to
[The Runtime Stamp](#the-runtime-stamp).

## Outcomes and Exit Codes

Each test ends in a pass or a fail outcome, aggregated in both reports. The
`simready-benchmark` command returns an exit code that a pipeline can gate on. For
pass-or-fail gating, treat only exit code `0` as success.

| Exit Code | Meaning |
|---|---|
| `0` | Clean pass. |
| `1` | Failures or a runtime error. |
| `2` | Command-line usage error. |
| `3` | Missing plan or results. |
| `4` | Setup not ready. |
| `130` | Interrupted with Ctrl-C. |

## Verify a Clean Pass

A benchmark run **passes** when every planned test for the asset records
`test_passed: true`. A test with Kit warnings can still pass; only explicit
failures or missing results count against the run. Use the checks below in
order. For CI, the exit code alone is enough. For a local run, open the HTML
report to inspect failures, screenshots, and warnings.

1. **Check the command exit code.** After `simready-benchmark` finishes, confirm
   the shell reports exit code `0`. Any other code means the run did not pass
   cleanly. Refer to [Outcomes and Exit Codes](#outcomes-and-exit-codes) for
   the full table.

   ```bash
   simready-benchmark --assets path/to/asset.usd
   echo Exit code: $?
   ```

   On Windows PowerShell, use `$LASTEXITCODE` instead of `$?`.

2. **Review the HTML report.** Open `_testing/index.html`. One HTML report covers
   every asset in the run. When the run lists more assets than fit on one page,
   open the additional pages under `_testing/report/` (for example,
   `assets_page_2.html`). On each page, every
   asset appears as its own section with an entry for each test planned for that
   asset. At the top, the summary cards show counts for the run: **Passed**,
   **Failed**, and **Not Tested**. A clean pass has **Failed** and **Not Tested**
   both at `0`. A feature that did not pass static validation appears in the amber
   **validation failed** state and runs no benchmark. A validation-failed
   feature does not by itself turn its asset red, so an asset can still show a
   passing verdict while one of its features is amber. Confirm that no feature
   shows the validation-failed state. Kit warning indicators can appear without
   failing the run. Scroll to your asset and confirm every listed test shows a
   pass outcome. Open a failing test to read the error message, screenshots, and
   engine logs.

3. **Confirm in JSON (optional).** For automation or scripting, read
   `_testing/test_results.json`. Each asset has a `tests` array with one entry for
   every test in the plan for that asset. Every entry must have `"test_passed":
   true`. A planned test that produced no XML still appears as an entry with
   `"test_passed": false`. `_testing/report/test_results_index.json` groups the
   same tests with paths to per-test artifact folders (XML results, videos, logs).

4. **Confirm the runtime stamp (optional).** If you did not specify
   `--no-stamp`, the stamp stage writes a receipt into the source USD asset before
   the command exits. Open the asset in a USD viewer and inspect
   `customLayerData["SimReady_Metadata"]["runtime_testing"]`. For each feature
   exercised in the run, find its entry under the run's timestamp in
   `tested_features` and confirm `"passed": true`. Refer to
   [Interpreting Multiple Timestamps](#interpreting-multiple-timestamps) when
   earlier runs left older entries in the file. If stamping failed but the tests
   themselves passed, the reports and exit code still reflect the test outcome;
   fix the stamp problem and re-run with stamping enabled before relying on the receipt downstream.

## The Runtime Stamp

The benchmark **receipt** is the durable result of a completed
`simready-benchmark` run. In the stamp stage, after tests execute, the stamper builds
it from `_testing/test_results.json` and writes it into each tested asset's
`customLayerData` (unless you specify `--no-stamp`). Downstream pipelines read
this metadata to confirm which features passed benchmarking without
re-running the engine.

The receipt is stored under
`customLayerData["SimReady_Metadata"]["runtime_testing"]`. It is distinct from
the schema-validation stamp written by `simready-validate` under
`SimReady_Metadata.validation` (refer to the [SimReady Validation Workflow](../validate_workflow.md)).

### Structure

The receipt is grouped by feature under `tested_features`. Each successful stamp
run adds one ISO timestamp key (taken from `test_results.json` metadata). Under
that key, each feature entry includes:

| Field | Meaning |
|---|---|
| `passed` | `true` only when every test listed for that feature passed |
| `version` | Feature version recorded for this run (highest semver seen among its tests) |
| `tests` | Map of test definition files to per-test `{ "passed": … }` results |

Example (one feature, one run):

```text
"runtime_testing" = {
    "tested_features" = {
        "2026-06-10T14:30:00.123456" = {
            "FET001" = {
                "passed" = true
                "version" = "1.0"
                "tests" = {
                    "fet001_visual.toml" = { "passed" = true }
                }
            }
        }
    }
}
```

Re-running benchmarks on a later date appends a new timestamp entry. Earlier
entries remain, so the asset preserves a history of benchmark outcomes.

### Interpreting Multiple Timestamps

Each stamp run adds one timestamp key. Older keys are not removed. To determine
the **current** benchmark status for a feature, use the **newest timestamp
that includes that feature**, not an older entry from a previous run.

1. List the timestamp keys under `tested_features`.
2. Sort them chronologically (ISO-8601 strings sort in run order when the format
   is consistent).
3. From newest to oldest, find the first timestamp that contains the feature ID.
4. Read that feature entry's `passed` flag. A feature passes only when `passed`
   is `true` and every test listed under it passed.

**Examples:** The scenarios below apply the rule above.

**Pass, then fail.** Run 1 stamps `FET001` with `passed: true`. After an asset
change, run 2 stamps `FET001` with `passed: false`. The current status for
`FET001` is **failed**. The earlier pass remains in the file as history but does
not override the newer result.

**Pass, then pass again.** The newest entry wins; current status is **passed**.

**Fail, then pass.** Run 1 stamps `FET001` with `passed: false`. After a fix,
run 2 stamps `FET001` with `passed: true`. The current status for `FET001` is
**passed**. The earlier failure remains in the file as history but does not
override the newer result.

**Fail, then fail again.** The newest entry wins; current status is **failed**.

**Feature not in the latest run.** Each timestamp lists only the features
exercised in that run. If the newest stamp run tested a different feature set,
a feature omitted from that run keeps the status recorded under its own most
recent timestamp until it is tested again.

Example with two runs on the same feature:

```text
"tested_features" = {
    "2026-06-01T10:00:00" = {
        "FET001" = { "passed" = true  ... }
    }
    "2026-06-10T14:30:00" = {
        "FET001" = { "passed" = false ... }
    }
}
```

Current status for `FET001`: **failed** (use `2026-06-10T14:30:00`, not the
June 1 entry).

Example with two runs on different features:

```text
"tested_features" = {
    "2026-06-01T10:00:00" = {
        "FET001" = { "passed" = true  ... }
    }
    "2026-06-10T14:30:00" = {
        "FET002" = { "passed" = false ... }
    }
}
```

The newest stamp run lists only `FET002`, not `FET001`. Current status for
`FET001` is **passed** (its newest entry is `2026-06-01T10:00:00`). Current
status for `FET002` is **failed** (use `2026-06-10T14:30:00`).

### Who Reads It

Downstream tools treat a feature as runtime-validated only when `passed` is
`true` for that feature and for every test listed under it, using the per-feature
rule in [Interpreting Multiple Timestamps](#interpreting-multiple-timestamps).

`simready-benchmark` does not read this receipt to plan or execute tests. Test
selection comes from the asset's declared features and profiles. The receipt is
written for pipelines, catalogs, and other tools that consume the asset after
testing.

Stamping runs as a separate step after the tests finish. Although it is unlikely,
the stamper can fail to write the receipt even when every test passed
(for example, if the USD file is not writable or the USD library is unavailable).
In that case, `_testing/index.html` and `test_results.json` still reflect the
test outcome, and per-test `stamping` fields in the report show the error. Fix
the stamp problem and re-run with stamping enabled before relying on the receipt
downstream.

## Related Pages

- [SimReady Benchmark Overview](overview.md): concepts and test families
- [Pipeline and Stages](pipeline.md): plan, run, stamp, and report stages
- [Running Tests](running.md): install and run `simready-benchmark`
