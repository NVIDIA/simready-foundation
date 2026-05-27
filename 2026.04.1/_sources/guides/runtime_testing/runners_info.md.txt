# Runner Configuration (runners_info.toml)

This page explains how to author and maintain `runners_info.toml`. It replaces and consolidates content from `local_run/runners_info_setup.md`.

## Purpose

Define engines/runners that runtime tests will use. Each runner block specifies the engine, platform, executable location, project root, and concurrency.

Use `engine = "kit"` for Kit and Kit-derived applications.

## File location

- Recommended: `{project_root}/local_run/runners_info.toml`
- Override via `--runner-info` when invoking batch_maker.

## Required fields per runner

- `engine`: engine identifier. Set to `"kit"` for Kit and Kit-derived apps.
- `platform`: `"windows"` or `"linux"`.
- `project_root`: absolute path to your SimReady project root (same folder containing `_testing/`).
- `executable_path`: path to the Kit installation folder (or derivative).
- `number_of_runners`: integer >= 1.
- `hardware_gpu`: `true` for GPU-required runs.

Optional:
- `output_dir`: base path for job outputs (relative to `project_root` or absolute).
- `docker_image`: image tag for containerized runs (Linux CI agents).
- `runner_config_file`: extra engine/runtime config path if needed.

## Recommended layout

```text
simready_next/
  packages/
    kit_107_3_0/           # Omniverse Kit Kernel
    isaac_sim/             # Example Kit-derived install
  simready_foundations/
    local_run/
      runners_info.toml
```

Use relative paths like `../packages/kit_107_3_0` (or `../packages/isaac_sim` when using that derivative) for portability, or absolute paths if preferred.

## Examples (Kit)

### Windows

```toml
[kit_runner_windows_gpu]
engine = "kit"
platform = "windows"
project_root = "D:/simready_next/simready_foundations"
executable_path = "../packages/kit_107_3_0"
hardware_gpu = true
number_of_runners = 2
# optional
# output_dir = "_testing/job_outputs"
# runner_config_file = "local_run/kit_config.toml"
```

### Linux

```toml
[kit_runner_linux_gpu]
engine = "kit"
platform = "linux"
project_root = "/work/simready_next/simready_foundations"
executable_path = "../packages/kit_107_3_0"
hardware_gpu = true
number_of_runners = 2
# optional
# docker_image = "kit_runner_linux"
```

## How batch_maker uses this file

- Validates runner existence when referenced by `RunnerTags.runner_config` in test definitions.
- Resolves `executable_path` relative to the effective `project_root` (runner block or CLI `--project-root`).
- Derives output structure and concurrency from `number_of_runners`.

## Quick verification

```bash
python batch_maker/batch_maker.py --project-root <project_root> --search-library-path <search_lib> --runner-info <project_root>/local_run/runners_info.toml --output-directory <project_root>/_testing/batch_jobs
python job_runner/job_runner.py <project_root>/_testing/batch_jobs/<job>.json --enable-zip
python report_generator/report_generator.py --output-dir <project_root>/_testing
```

If jobs are not generated, the workflow will skip execution/report steps and log why.

## Troubleshooting

- Path not found: verify `executable_path` and `project_root`. Relative paths resolve against `project_root`.
- GPU errors: ensure a GPU-capable environment and appropriate drivers.
- No matching runner: ensure `RunnerTags.runner_config` lists the same TOML table names.
