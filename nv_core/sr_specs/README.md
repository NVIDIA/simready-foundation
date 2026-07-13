# Open USD Capability Documentation

# Building the Documentation

```bash
cd open-usd-capability-documentation
repo.sh docs
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

The documentation is organized into the following main sections:

## Core Documentation
- `capabilities/`: The main documentation for USD capabilities
  - Each capability has its own folder containing:
    - `capability-[name].md`: Overview of the capability
    - `requirements/`: Individual requirement documentation files
  - `_includes/`: Generated content
    - `badges/`: Status badges for each capability
    - `tables/`: Requirement tables for each capability

## Additional Content
- `guides/`: End-to-end guides and tutorials
- `profiles/`: Profile-specific documentation
- `indexes/`: Generated index files and reports
  - `capability_status_index.md`: Overall capability status report
- `index.md`: Main documentation landing page

## Supporting Infrastructure
- `_ext/`: Custom Sphinx extensions
  - `sphinx_tag_role.py`: Tag system implementation
  - `sphinx_requirement_table.py`: Requirement table generation
  - `sphinx_capability_report.py`: Capability scoring and reporting
- `_static/`: Static assets
  - `tags.css`: CSS styling for tags

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
