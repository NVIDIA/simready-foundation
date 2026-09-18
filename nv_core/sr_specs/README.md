# Open USD Capability Documentation

The documentation is no longer a single monolithic tree. Its content is owned by
the SimReady validation tiers under `nv_core/tiers/` (each tier ships its own
`capabilities/`, `features/`, and `profiles/`), by a committed cross-tier
**shared overlay** at `docs/shared/` (hub pages, badge includes, the example
scaffold, and family pages that span tiers), and by the residual site chrome
that stays in `docs/` (`index.md`, `guides/`, `indexes/`, `_static/`).

Both build pipelines stage those sources into a single Sphinx source tree at
`_build/docs-src` with the repoman-free assembler
(`nv_core/tiers/_tooling/assemble_docs.py`), which preserves every published
docname (`capabilities/**`, `features/**`, `profiles/**`).

# Building the Documentation

Internal (repoman) build — prepare the staged tree first, then build:

```bash
cd nv_core/sr_specs
./prep_docs.sh   # installs the Sphinx extension dep + assembles _build/docs-src
./repo.sh docs   # Sphinx build (docs_root = _build/docs-src)
```

Public (GitHub Pages) build — from the repo root; `build_docs.py` assembles the
staged tree and injects the standalone `conf.py` automatically:

```bash
pip install -r requirements-docs.txt
python build_docs.py            # add --strict to treat warnings as errors
```

# Adding a Capability

To add a new capability, follow these steps:

1. Create a new folder in the `capabilities/` directory with a descriptive name (e.g., `visualization/geometry/`)

2. Create a capability overview file:
   - Copy an existing capability file (e.g., `capabilities/visualization/geometry/capability-geometry.md`)
   - Update the title, version, and overview sections
   - The status and requirements sections will be automatically populated when you build the docs

3. Create a `requirements/` subdirectory and add individual requirement files:
   - Copy an existing requirement file (e.g., `capabilities/visualization/geometry/requirements/usdgeom-mesh-topology.md`)
   - Update the following sections:
     - Code and validator information in the header table
     - Summary and description
     - Why it's required
     - Examples with valid and invalid cases
     - How to comply
     - Relevant documentation links

4. Add any necessary validator implementations in the appropriate validator repository

5. Build the documentation to generate tables and badges:
   ```bash
   repo.sh docs
   ```

The capability will automatically appear in the capability status report and its requirements will be included in the generated tables.

# Structural Overview

The **assembled** documentation (the `_build/docs-src` staged tree, and the
published site) is organized into the following logical sections. Note where
each one is *authored*, since the source no longer all lives under `docs/`:

## Capabilities — authored in the tiers
- `capabilities/**` comes from each tier's
  `simready/foundation/<tier>/capabilities/` tree (capability overview,
  `requirements/` pages, and the `validation.py` validators live together).
- The top-level `capabilities/capabilities.md` hub, the `_includes/badges/`
  fragments, and the `example/` scaffold come from the shared overlay
  (`docs/shared/capabilities/`).

## Features & Profiles — authored in the tiers + shared overlay
- `features/**` and `profiles/**` narratives live beside their JSON/TOML owners
  in each tier's `features/` and `profiles/` directories. Hub pages
  (`features.md`, `feature-dependency-graph.md`, `profiles.md`) and family pages
  that span tiers live in the shared overlay (`docs/shared/features|profiles/`).

## Residual site chrome — authored in `docs/`
- `guides/`: End-to-end guides and tutorials
- `indexes/`: Generated index files and reports
  (`capability_status_index.md`: overall capability status report)
- `index.md`: Main documentation landing page
- `_static/`: Static assets (`tags.css`, images, benchmark videos)

## Supporting Infrastructure
- Sphinx extensions (the `tag` role, requirement-table generation, capability
  scoring/badges, and the per-page `{{profile}}`/`{{version}}` substitutions)
  are provided by the `usd-profiles-nvidia` package
  (`usd_profiles_nvidia.sphinx.ext`), installed for both pipelines.
- `nv_core/tiers/_tooling/assemble_docs.py`: the deterministic assembler that
  stages tiers + shared overlay + residual chrome into `_build/docs-src`.

# Custom Sphinx Extensions

## Requirement Tables Extension

The documentation uses a custom Sphinx extension (`sphinx_requirement_table.py`) to automatically generate requirement tables for each capability. The extension:

1. Scans the `docs/capabilities/*/requirements/` directories for markdown files
2. Parses each requirement file to extract:
   - Code
   - Summary
   - Compatibility
   - Validator
   - Tags
3. Groups requirements by capability
4. Sorts requirements by priority:
   - Core requirements first
   - Correctness requirements second
   - High quality requirements third
   - Performance requirements fourth
5. Generates a markdown table for each capability using the Jinja2 template `requirement_table.md.j2`
6. Outputs the tables to `docs/capabilities/_includes/tables/`

The generated tables are then included in the capability documentation pages using:

````markdown
```{requirements-table}
```
````

## Requirement Tag Extension

The documentation uses a custom tag system implemented via Sphinx extensions to categorize requirements and their properties. There are three types of tags:

### Requirement Tags
These tags categorize the type of requirement:
- {tag}`essential` - Core requirements that must be met
- {tag}`performance` - Requirements related to performance optimization
- {tag}`correctness` - Requirements ensuring correct behavior
- {tag}`high-quality` - Requirements for high-quality assets

### Compatibility Tags
These tags indicate compatibility with different USD implementations:
- {compatibility}`Core USD` - Compatible with the core USD implementation
- {compatibility}`OpenUSD` - Compatible with OpenUSD

### Validator Tags
These tags indicate which validator implements the requirement in which version of Asset Validator:
- {oav-validator-link}`0.24.0+_vm-mdl-001` - NVIDIA Asset Validators in version 0.24.0 or above that implements VM.MDL.001 requirements. This example tag will be expanded to a link that points to page "http://omniverse-docs.s3-website-us-east-1.amazonaws.com/asset-validator/0.24.0/source/src/docs/asset_validator/requirements.html#vm-mdl-001". The format is `version+_code`.
- {oav-validator-latest-link}`vm-mdl-001` - NVIDIA Asset Validators in the latest version that implements VM.MDL.001 requirements. This example tag will be expanded to a link that points to page "http://omniverse-docs.s3-website-us-east-1.amazonaws.com/asset-validator/latest/source/src/docs/asset_validator/requirements.html#vm-mdl-001".

The tags are implemented using custom Sphinx roles and styled using CSS. The styling is defined in `docs/_static/tags.css` and the roles are implemented in `docs/_ext/sphinx_tag_role.py`.


## Capability Reporting and Scoring Extension

The documentation uses a custom Sphinx extension (`sphinx_capability_report.py`) to automatically generate capability status reports and badges. The extension:

1. Scans the `docs/capabilities/` directory for capability folders
2. Calculates capability scores based on criteria defined in `_ext/scoring_config.json`:
   - Assigns points for different documentation elements
   - Uses configurable thresholds for status levels (Complete, Development, Draft)
3. Generates two types of output:
   - Individual badge files in `docs/capabilities/_includes/badges/`
   - A consolidated status report in `docs/indexes/capability_status_index.md`
4. Supports filtering capabilities through include/exclude lists in the Sphinx configuration

The scoring system evaluates capabilities based on:
- Documentation completeness
- Requirement coverage
- Implementation status
- Validation coverage

The generated badges show the current status of each capability:
- Complete (green) - 90% or higher score
- Development (yellow) - 33% to 89% score
- Draft (red) - Below 33% score

The badges can be included in capability documentation using:

```markdown
```{include} /capabilities/_includes/badges/capability_name.md
```
