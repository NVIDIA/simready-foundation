# Shared tier build tooling

Build infrastructure shared by every SimReady tier under `nv_core/tiers/`. It is
**not** an installed package — tiers reference it by relative path.

Each tier is an ordinary Python package that commits its own content under
`simready/foundation/<tier>/`. The one thing a tier does *not* commit is its
generated requirements-enum module, so the only shared build step is codegen.

| File | Role |
|------|------|
| `build_hook.py` | Hatchling custom build hook that each tier's `pyproject.toml` points at (`path = "../_tooling/build_hook.py"`). It generates the tier's requirements enums (`usd_profiles_nvidia.PythonGenerator`) from the committed capability markdown into `<tier>/_build/python/<module>/requirements`. It reads `module`, `reverse_domain`, and `package_licenses` from the tier's `[tool.hatch.build.hooks.custom]` table. Selected dependency notices ship under `PACKAGE-LICENSES/`; each tier's Apache license ships under `dist-info/licenses/` using its project license metadata. For an **editable** build it also mirrors that generated package into the tier checkout, which is the only location the tier's own `__path__` can import it from. |
| `build_tiers.py` | Repoman-free builder + CLI. Builds every tier workspace member into `<tiers root>/_build/dist/`. Importable (`build_tiers()`, `discover_tiers()`) or runnable standalone (`python build_tiers.py`). Requires `uv` on `PATH`. `repo build_tiers` is a thin wrapper that just injects the repo-managed `uv`. |
| `dev_install.py` | Editable-installs tiers for local development so `simready-validate` loads them from the checkout. Pure stdlib + `pip`; **no `uv` and no repoman**. Importable (`dev_install()`, `resolve_tiers()`) or runnable standalone (`python dev_install.py`). |
| `checkout_requirements.py` | `ensure_checkout_requirements()`, called by tier test `conftest.py` files: generates a tier's requirements enums into its checkout when the tests import it from there and a wheel build has removed them. Does nothing when the tier imports from an installed wheel. |
| `assemble_docs.py` | Stitches the tier docs, the shared overlay in `nv_core/sr_specs/docs/shared/`, and the residual site pages into the Sphinx source tree at `nv_core/sr_specs/_build/docs-src`, repointing markdown links at the assembled layout. Stdlib only. |
| `check_doc_links.py` | Checks docs links in the markdown sources (`source`) and in a built HTML site (`html`). See [Docs links](#docs-links). |

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
advertise Evaluate runtime tests through its descriptor. Codegen needs
`usd_profiles_nvidia` (+ `pxr`) at build time, so set `UV_EXTRA_INDEX_URL` (or
your uv config) if that dependency isn't on the default index.

The builder writes every wheel to an owned temporary staging directory. Only
after the complete build succeeds does it publish the staged artifacts to the
shared output directory. During publication it replaces wheels for the exact
distributions produced by the build and preserves unrelated files, directories,
and wheel distributions. A failed build leaves the previously published output
unchanged.

## Standalone validation dependencies

The sample-content and specification-consistency CI jobs load validators directly
from source, including the MR target checkout. They do not inherit dependencies
from an installed Core wheel. Keep their explicit PhysX schema dependency and
both source requirements files aligned with Core's declared dependency and CI's
Foundations 2 validator API floor. Register
the schema provider before the comparison checkout initializes USD's registry.

Tier CI also runs Core's real-stage PhysX schema compatibility regressions against
the built wheel. The tooling dependency tests guard all three source-validation
commands and ensure that this coverage remains in the tier CI test selection.

## Runtime unit suites

The default `repo test` suites include Core and Newton runtime units in
separate Python 3.12 virtual environments, alongside the upstream tooling,
cross-tier, AIF and Isaac Asset Transformer suites. Their dependency requirements
enforce the Evaluate/Kit compatible version bounds declared by the tiers and
used by tier CI (Evaluate `>=2026.9.0rc2,<2026.11` and Kit `>=2026.9.0rc3,<2026.11`). Source bootstrap
applies only when no installed tier is importable; built-wheel qualification
keeps using the wheel.

The API baseline supplies live geometry and required-cleanup worker retirement.
Core and Newton verify composed floor collision/visibility before physics; Core
isolates only optional encoder warning/timing callbacks. Native engine failures,
unsafe evidence paths and cancellation still propagate. Qualify these behaviors
with installed baseline and newer wheels, including compatible mixed versions.
Tier CI resolves published dependencies normally and tests its own built tier
artifacts; it does not require a matching Explorer commit or unpublished wheels.
The `test-tier-wheels` job supplies the internal registry through `UV_INDEX`,
because `uv run` does not read `PIP_EXTRA_INDEX_URL`. The resolver regression uses
the job's environment-variable names against a temporary local index, offline
and without installing packages. It uses the executable exposed by `uv run` (or
`uv` on `PATH`); a missing executable is an error in built-wheel CI and a skip
in standalone tooling checks.

Compatible `simready.evaluate` and `simready.evaluate.engine-kit` distributions
must be published to the configured registry before CI can resolve the runtime
extras. Publishing the former Benchmark names does not satisfy these renamed
dependencies. During the rename rollout, publish Explorer's compatible wheels
through the normal release workflow, then rerun Foundation's tier-wheel and
runtime-unit jobs. A dependency-resolution failure happens before tests execute;
it is not a runtime-test failure. Do not bypass it with `--no-deps`, weaker
compatibility bounds, or paired source-commit pins.
See the [installation guide](../../sr_specs/docs/guides/foundation_pypi.md).

Run both owners' unit suites:

```bash
./repo.sh test -s tier_core tier_newton -c release
```

```powershell
.\repo.bat test -s tier_core tier_newton -c release
```

Omit `-s` to run all six default suites. These are unit and source-consistency
checks, not a replacement for native-engine sample-asset qualification.

## Docs links

Write every relative link, image, and `{include}` path in a docs markdown file
relative to that file in the repository, so it works in a file browser and in
the GitLab markdown view. Link to the `.md` file itself, even when it lives in
another tier or in `nv_core/sr_specs/docs/`. The assembler moves pages into one
tree for Sphinx and repoints each link at the target's assembled location.
Toctree entries are Sphinx docnames, not links, and name the assembled page.

CI checks both ends:

```bash
python nv_core/tiers/_tooling/check_doc_links.py source
python nv_core/tiers/_tooling/check_doc_links.py html nv_core/sr_specs/_build/docs
```

`source` reports links that do not resolve from their file, root-relative
links (`/rules_and_reqs/…`), links to directories, and links to markdown that is
not published. `source --fix` rewrites links written against the assembled
layout into source-relative ones. `html` reports local `href`/`src` targets and
`#fragment` ids that are missing from the built site.

## Developing a tier (editable installs)

Building and reinstalling a wheel on every edit is the wrong loop for tier
authoring. `dev_install.py` editable-installs tiers instead, so a tier's
`simready.tier` entry point is registered while its descriptor keeps resolving
to the checkout:

```bash
python nv_core/tiers/_tooling/dev_install.py
```

`simready-validate` then loads the working tree through its normal
entry-point path, with no `--rules-path` / `--features-path` / `--profiles-path`
flags:

```bash
simready-validate --profile Robotics-Prop --version 3.1.0 path/to/asset.usd
```

This example selects an existing profile, not an alias for retired profiles.
Use the exact registered ID/version intended for your asset; successful setup
does not imply that an arbitrary asset conforms to this example's profile.

Useful flags: `--tier NAME` (repeatable) to install one tier, `--python PATH`
to target a virtual environment, `--no-deps` to leave an existing dependency
stack alone.

This needs only Python and `pip`. `pip install -e` drives each tier's own
Hatchling backend through PEP 517, resolving `hatchling` and
`usd-profiles-nvidia` into an isolated build environment, so **neither `uv` nor
repoman is required** — unlike `build_tiers.py`, which takes `uv` from `PATH`.

Editable and wheel-installed tiers coexist: `simready` and
`simready.foundation` are namespace packages, so an editable experimental tier
loads from its checkout while `simready-foundation-tier-core` stays installed as
an ordinary wheel.

Re-run `dev_install.py` in two situations:

- **After adding or removing a requirement page.** Requirement enums are
  generated at install time, so a new requirement code is not importable until
  codegen runs again. Edits to validators, feature manifests, profiles, and
  existing requirement prose take effect immediately, with no re-run.
- **After building wheels** (`repo build_tiers` / `build_tiers.py` / `pip
  wheel`). A wheel build clears the in-checkout codegen mirror so the wheel
  cannot ship it twice, which leaves an active editable install without its
  requirements module. The symptom is
  `ModuleNotFoundError: No module named '<module>.requirements'`.

## How a tier build flows

1. `uv build --wheel --all-packages` invokes hatchling per tier member,
   which loads `build_hook.py`.
2. The hook runs codegen into `<tier>/_build/python/<module>/requirements`.
3. The tier's `pyproject.toml` ships its committed Python packages, including
   any optional runtime-test package, and `force-include`s the generated
   `requirements/` into the wheel.
4. uv writes all wheels into `<tiers root>/_build/dist/`.

`_build/` is ephemeral and git-ignored; it is regenerated on each build.

An **editable** build (`pip install -e`, via `dev_install.py`) runs the same
codegen and then also mirrors `<module>/requirements` into the tier checkout.
That copy is required because a tier is a regular package whose `__path__` is
the single checkout directory, so the `force-include`d copy under
`site-packages` is unreachable; only the namespace ancestors merge across
locations. The mirrored directory is git-ignored. Standard wheel contents are
unaffected.
