# Shared tier build tooling

Build infrastructure shared by every SimReady tier under `nv_core/tiers/`. It is
**not** an installed package — tiers reference it by relative path.

Each tier is an ordinary Python package that commits its own content under
`simready/foundation/<tier>/`. The one thing a tier does *not* commit is its
generated requirements-enum module, so the only shared build step is codegen.

| File | Role |
|------|------|
| `build_hook.py` | Hatchling custom build hook that each tier's `pyproject.toml` points at (`path = "../_tooling/build_hook.py"`). It generates the tier's requirements enums (`usd_profiles_nvidia.PythonGenerator`) from the committed capability markdown into `<tier>/_build/python/<module>/requirements`. It reads `module` and `reverse_domain` from the tier's `[tool.hatch.build.hooks.custom]` table. |
| `build_tiers.py` | Repoman-free builder + CLI. Builds every tier workspace member into `<tiers root>/_build/dist/`. Importable (`build_tiers()`, `discover_tiers()`) or runnable standalone (`python build_tiers.py`). `repo build_tiers` is a thin wrapper that just injects the repo-managed `uv`. |

The tiers root (`../pyproject.toml`) is a uv workspace with no `[project]` table,
and each tier is a member. Adding a tier means adding it to that `members` list;
the builder needs no changes.

## Building tiers

The build logic lives here so it can run with or without the repoman framework:

- **Inside this repo:** `repo build_tiers`. That command
  (`tools/repoman/build_tiers.py`) is a thin wrapper that injects the
  repo-managed `uv` and delegates to `build_tiers.py` here.
- **Anywhere else (no repoman):** run this module directly.

```bash
python nv_core/tiers/_tooling/build_tiers.py
```

It builds every tier workspace member into the shared
`nv_core/tiers/_build/dist/`, taking `uv` from `PATH`. A tier may bundle and
advertise Benchmark runtime tests through its descriptor. Codegen needs
`usd_profiles_nvidia` (+ `pxr`) at build time, so set `UV_EXTRA_INDEX_URL` (or
your uv config) if that dependency isn't on the default index.

The builder clears the output directory itself instead of using `uv build
--clear`. `--clear` is applied per package inside `uv build`, so pairing it with
`--all-packages` and a shared `--out-dir` has every member racing to delete the
directory they are all writing into.

## How a tier build flows

1. `uv build --wheel --all-packages` invokes hatchling per tier member,
   which loads `build_hook.py`.
2. The hook runs codegen into `<tier>/_build/python/<module>/requirements`.
3. The tier's `pyproject.toml` ships its committed Python packages, including
   any optional runtime-test package, and `force-include`s the generated
   `requirements/` into the wheel.
4. uv writes all wheels into `<tiers root>/_build/dist/`.

`_build/` is ephemeral and git-ignored; it is regenerated on each build.
