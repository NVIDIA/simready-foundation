# Runtime Tests Overview and CLI

A three-stage pipeline discovers assets, generates batch jobs, runs tests, and builds reports. Preferred entrypoint inside Kit: `workspace runtime_tests`.

- batch_maker.py: Discovers assets via search functions and test definitions; writes job JSON under `_testing/batch_jobs/`.
- job_runner.py: Executes jobs; writes results under `_testing/job_outputs/` (XML, images, logs, artifacts).
- report_generator.py: Builds `test_results.json`, `report/test_results_index.json`, and `index.html` in `_testing/`.

All three are wrapped by `omni.simready.workspace_commands.runtime_tests` for in-Kit invocation.

## Quickstart

- Ensure your SimReady project root is configured in WorkspaceConfiguration.
- Ensure `local_run/runners_info.toml` contains a Kit runner.
- Generate jobs, run, and report:

```
workspace runtime_tests
```

- Open the report:

```
{project_root}/_testing/index.html
```

## Why use runtime tests?

- Pre-check-in validation: Verify assets meet capability/profile expectations before committing (screenshots, metrics, pass/fail).
- Repeatable coverage: Run consistent searches over large libraries to validate many assets across engines/platforms.
- CI-ready outputs: Structured job files, XML results, and deterministic HTML/JSON reports.
- Fast iteration loop: Filter by modified assets, re-run only affected jobs, keep outputs for diffs.

Typical workflows:
- Before check-in: run full workflow, spot-check the HTML, fix issues, re-run quickly.
- Feature/profile changes: adjust test definitions or search filters, regenerate jobs, compare reports.
- Engine updates: re-run existing jobs across updated engines/runners to catch regressions.

## End-to-end usage (preferred)

- Full workflow:

```
workspace runtime_tests [--modified-assets-list FILE]
```

- Sub-commands:

```
workspace runtime_tests batch_maker [ARGS]
workspace runtime_tests job_runner [ARGS]
workspace runtime_tests report_generator [ARGS]
```

Note: `help`, `?`, `-?`, or `/?` are mapped to `--help` for subcommands.

## CLI reference

### batch_maker.py

Generates job JSON files. When used via workspace, `--search-library-path` is auto-injected if discoverable; for direct CLI it is required.

Path specification (choose exactly one method):
- Method 1 (single pathset):
  - `--search-functions-dir PATH`
  - `--test-definitions-dir PATH`
  - `--project-config-file PATH`
- Method 2 (multiple pathsets):
  - `--pathsets-json JSON_ARRAY`
- Method 3 (auto-derive from project root):
  - `--project-root PATH`

Other options:
- `--runner-info PATH` (default: `local_run/runners_info.toml`; if default, path is auto-derived from `--project-root`)
- `--search-library-path PATH` (required for CLI; workspace wrapper auto-discovers)
- `--modified-assets-list FILE` (JSON array of allowed assets)
- `--tests TEST...` (filter to specific tests; search still runs)
- `--manual-assets PATH...` (intersect search results with these assets)
- `--list-tests` (print available test identifiers and exit)
- `--list-tests-format` (control the format of the --list-tests command, default to `text`)
- `--list-tests-path` (optional absolute path location where the output of the --list-tests output is to be written)
- `--output-directory PATH` (defaults to `{project_root}/_testing/batch_jobs` when project root is known)
- `--execution-mode {local|distributed}` (default: `local`)
- `--platforms windows linux` (space-separated list; default auto-detect)
- `--keep-outputs`

Outputs: `{project_root}/_testing/batch_jobs/*.json`

Examples (Kit):

```
# Minimal project-root invocation (workspace)
workspace runtime_tests batch_maker --project-root D:/simready --keep-outputs

# Explicit CLI (advanced) with platforms and modified assets filtering
python batch_maker/batch_maker.py \
  --project-root D:/simready \
  --search-library-path D:/simready/search_library \
  --platforms windows linux \
  --modified-assets-list D:/simready/modified_assets.json

# Select a specific test (search still runs)
workspace runtime_tests batch_maker --project-root D:/simready --tests kit_test/minimal_app

# Select tests and intersect with specific assets
workspace runtime_tests batch_maker --project-root D:/simready \
  --tests kit_test/minimal_app \
  --manual-assets sample_content/common_assets/props_general/obs_orange_a01/obs_orange_a01.usd
```

### job_runner.py

Executes a job file and (optionally) archives results.

Positional:
- `job_file` Path to job JSON.

Options:
- `--timeout INT` (default: 600)
- `--enable-output-timeout`
- `--output-timeout FLOAT` (default: 30.0)
- `--enable-zip`
- `--delete-folders-after-zip`
- `--keep-outputs`

Outputs: `{project_root}/_testing/job_outputs/<runner>/<job>/<asset>/`

Examples (Kit):

```
# Run auto-detected job (workspace subcommand)
workspace runtime_tests job_runner --enable-zip

# Run a specific job file (recommended for distributed)
python job_runner/job_runner.py D:/simready/_testing/batch_jobs/kit_runner_windows_gpu_000_windows.json --timeout 1200 --enable-zip
```

### report_generator.py

Builds JSON and HTML reports in the output base directory.

Required:
- `--output-dir PATH` (must contain `batch_jobs/` and `job_outputs/` unless overridden)

Optional:
- `--jobs-dir PATH` (default: `{output-dir}/batch_jobs`)
- `--results-dir PATH` (default: `{output-dir}/job_outputs`)
- `--assets-per-page INT` (default: 25)
- `--keep-outputs`

Outputs:
- `{output-dir}/test_results.json`
- `{output-dir}/report/test_results_index.json`
- `{output-dir}/index.html`

Examples:

```
# Default directories
workspace runtime_tests report_generator --output-dir D:/simready/_testing

# Explicit directories and pagination
python report_generator/report_generator.py \
  --output-dir D:/simready/_testing \
  --jobs-dir D:/simready/_testing/batch_jobs \
  --results-dir D:/simready/_testing/job_outputs \
  --assets-per-page 50
```

## runners_info.toml (maintained by user/CI)

`runners_info.toml` is owned by the user or CI/CD maintainer. batch_maker reads this file to know:
- Which engines/runners exist and on which platform they run (Kit and Kit-derived apps)
- Where the engine executable is located
- How many runner instances to create (for distributed asset splitting)
- Optional per-runner output locations and metadata

Required fields per runner:
- `engine` (use `"kit"` for Kit and Kit-derived applications)
- `platform` (`"windows"` or `"linux"`)
- `project_root` (absolute path)
- `executable_path` (absolute or relative to `project_root`)
- `number_of_runners` (int >= 1)
- `hardware_gpu` (true for GPU missions)

Optional fields:
- `output_dir`, `docker_image`, `runner_config_file`

Example (Windows):

```
[kit_runner_windows_gpu]
engine = "kit"
platform = "windows"
project_root = "D:/simready_next/simready_foundations"
executable_path = "../packages/kit_107_3_0"
hardware_gpu = true
number_of_runners = 2
```

Example (Linux):

```
[kit_runner_linux_gpu]
engine = "kit"
platform = "linux"
project_root = "/work/simready_next/simready_foundations"
executable_path = "../packages/kit_107_3_0"
hardware_gpu = true
number_of_runners = 2
```

## Notes
- `runners_info.toml` content is maintained by user/CI; batch_maker only reads it (default path is derived from `--project-root` if not provided).
- Platforms flag uses space-separated values (e.g., `--platforms windows linux`).
