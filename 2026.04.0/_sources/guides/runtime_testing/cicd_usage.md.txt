# CI/CD Usage (multi-machine, direct CLI)

This guide describes how to use runtime tests in CI/CD pipelines. It focuses on direct CLI usage with explicit paths and multi-machine flows.

## Goals

- Deterministic invocation: no reliance on in-Kit wrappers or local workspace auto-discovery.
- Explicit configuration: pass all paths (project root, search library, runners_info) at CLI time.
- Multi-machine flow: generate jobs on CI, run on target machine(s), aggregate results back on CI for reporting.

## Stage 1: Generate jobs (CI machine)

- Requirements: Python environment for batch_maker and access to the repo/project root
- Inputs:
  - `--project-root`: absolute path to the SimReady project root on the CI filesystem
  - `--search-library-path`: absolute path to the search library directory containing `asset_search_library`
  - `--runner-info`: path to `runners_info.toml` used to select configured runners
  - optional `--modified-assets-list`: JSON array of allowed assets (to reduce scope)

Command:

```
python path/to/batch_maker/batch_maker.py \
  --project-root <ABS_PROJECT_ROOT> \
  --search-library-path <ABS_SEARCH_LIBRARY_DIR> \
  --runner-info <ABS_PROJECT_ROOT>/local_run/runners_info.toml \
  --platforms windows linux \
  --execution-mode local [--modified-assets-list <ABS_ALLOWED_ASSETS_JSON>] \
  --output-directory <ABS_PROJECT_ROOT>/_testing/batch_jobs
```

Output:
- Job JSON written under `<ABS_PROJECT_ROOT>/_testing/batch_jobs`

Artifact handoff:
- Copy the `batch_jobs` folder to the target execution machine(s), preserving the folder structure.

## Stage 2: Run jobs (target machine)

- Requirements: the engine runtime (Kit) properly installed on the target machine; GPU if required; job files copied locally
- Inputs:
  - Specific job JSON to run (recommended to choose target-specific JSON)

Command examples:

```
python path/to/job_runner/job_runner.py <ABS_PROJECT_ROOT>/_testing/batch_jobs/<job_file>.json \
  --timeout 1200 --enable-zip
```

Notes:
- Use platform-appropriate job file(s). If you generated per-runner files, choose the relevant ones.
- For distributed runs, invoke `job_runner.py` per runner instance file.

Output:
- Results and artifacts under `<ABS_PROJECT_ROOT>/_testing/job_outputs/...`
- Optional ZIP archives next to runner directories when `--enable-zip` is used

Artifact handoff back to CI:
- Copy the entire `job_outputs` subtree back to the CI machine, preserving the structure under `_testing/job_outputs`.

## Stage 3: Generate reports (CI machine)

- Requirements: Python environment for report_generator and the aggregated artifacts
- Inputs:
  - `--output-dir`: the root path that contains both `batch_jobs/` and `job_outputs/` copied back from target machines
  - optional: `--jobs-dir` and `--results-dir` if your CI aggregation uses different paths

Command:

```
python path/to/report_generator/report_generator.py \
  --output-dir <ABS_PROJECT_ROOT>/_testing \
  --assets-per-page 50 [--keep-outputs]
```

Output:
- `<ABS_PROJECT_ROOT>/_testing/test_results.json`
- `<ABS_PROJECT_ROOT>/_testing/report/test_results_index.json`
- `<ABS_PROJECT_ROOT>/_testing/index.html`

Publish the HTML as a CI artifact.

## Notes and recommendations

- Avoid auto-discovery: Always pass `--project-root`, `--search-library-path`, and `--runner-info` explicitly in CI.
- Paths are environment-specific: do not reuse machine-local paths; construct them per agent.
- Runner ownership: `runners_info.toml` is maintained by CI; use engine=`kit` for Kit-derived apps.
- Job files are machine-portable: ensure search functions do not hardcode local paths. Use project-relative paths.
- Never hand-edit job JSON: always regenerate via batch_maker.

## Minimal YAML pseudo-template

```
stages:
  - generate
  - run
  - report

generate:
  script:
    - python batch_maker/batch_maker.py --project-root $PROJECT_ROOT --search-library-path $SEARCH_LIB --runner-info $RUNNERS_INFO --platforms windows linux --output-directory $PROJECT_ROOT/_testing/batch_jobs
  artifacts:
    paths:
      - $PROJECT_ROOT/_testing/batch_jobs

run:
  script:
    - python job_runner/job_runner.py $PROJECT_ROOT/_testing/batch_jobs/<job>.json --timeout 1200 --enable-zip
  artifacts:
    paths:
      - $PROJECT_ROOT/_testing/job_outputs

report:
  script:
    - python report_generator/report_generator.py --output-dir $PROJECT_ROOT/_testing --assets-per-page 50
  artifacts:
    paths:
      - $PROJECT_ROOT/_testing/index.html
      - $PROJECT_ROOT/_testing/test_results.json
      - $PROJECT_ROOT/_testing/report/test_results_index.json
```

Adjust paths and shell syntax for your CI runner.
