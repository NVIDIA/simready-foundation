# SimReady Foundation PyPI Packages

## About This Guide

SimReady Foundation tier packages let you install the requirements, capabilities, features, profiles, and validation rules required for a specific runtime or use case. They also let you add organization-specific content without modifying or repackaging the Foundation source. This guide explains how to install Foundation tiers, use them to validate assets, and create a new tier that depends on and extends an existing tier.

This guide is intended for:

- **Asset pipeline users and validation engineers** who need to install Foundation content and validate assets with `simready-validate`.
- **Python developers and validation framework developers** who need to package and distribute additional requirements, capabilities, features, profiles, and validation rules.

This guide assumes you are familiar with the SimReady Foundation model of requirements, capabilities, features, and profiles. If these concepts are new to you, [SimReady Foundation](getting_started.md) provides an introduction. The installation and validation sections assume you are familiar with command-line tools and `pip`. The tier-authoring sections also assume you are familiar with Python package development, `pyproject.toml`, package entry points, and SimReady validation rule checkers.

## Background: What Is a Tier?

The Foundation spec is organized into *tiers*: separately publishable Python packages, each owning a coherent slice of capabilities, features, and profiles. Tiers can form dependency relationships. A tier that depends on another tier is the *downstream tier*; the tier it depends on is the *upstream tier*. The downstream tier declares the upstream tier as a `pip` dependency and adds its own content without modifying the upstream package. For example, a custom `my-simready-tier` that adds organization-specific rules would be downstream of `simready-foundation-tier-core`.

This section covers what a tier is well enough to follow the rest of this guide. For why the specification is divided this way, what tier ownership tells you about a profile, and how tiers differ from compatibility tiers and maturity levels, see [SimReady Foundation Tiers](tiers.md).

Before tier packages, validation content was loaded from shared `capabilities`, `features`, and `profiles` directories under `nv_core/sr_specs/docs/`. The tier structure packages corresponding content in self-contained Python package subtrees under `nv_core/tiers/`. During wheel builds, shared tooling generates each tier's requirements-enum module and embeds it in the wheel.

The SimReady Foundation repository organizes tier package sources as follows.

```text
nv_core/tiers/
|-- _tooling/
`-- simready_foundation_tier_core/
    |-- pyproject.toml
    `-- simready/foundation/tier_core/
        |-- capabilities/
        |-- features/
        `-- profiles/
```

Additional tiers are siblings of `simready_foundation_tier_core/` with the same internal shape, each in its own `simready/foundation/<tier>/` package.

Foundation runtime tests live in their owning tier package beside the tier's
catalogs. The descriptor advertises their package directory without importing
it. Validator-only installs therefore remain lightweight, while a tier's
optional dependency extra installs the Benchmark and engine dependencies needed
to execute those bundled tests.

```{note}
This layout illustrates the SimReady Foundation repository; it does not prescribe the source layout for third-party tiers. A third-party tier must provide the entry points, plugin, and tier descriptor described later in this guide. If it uses the generic descriptor, it also needs `capabilities/`, `features/`, and `profiles/` directories under its package. Repository directories and Python modules use underscores; PyPI distribution names use hyphens.
```

The Foundation currently publishes a single tier:

| Package | Contents | Depends on |
|---|---|---|
| [`simready-foundation-tier-core`](https://pypi.org/project/simready-foundation-tier-core/) | Core, Hierarchy, Visualization, Physics Bodies, Isaac Sim, Non-Visual Sensors, Semantic Labels, Dataset Taxonomies, and Packaging capabilities; the neutral, PhysX, and Isaac prop profiles, the robot and gripper profiles, the package profiles, and the Open Taxonomy profiles | |

## Prerequisites

This guide requires Python 3.11 or 3.12.

## Installation

First, install or upgrade `simready-validate`. Then install `simready-foundation-tier-core`, which provides the core, neutral, PhysX, Isaac Sim, and package content.

```{important}
Foundation releases use a `major.minor` product version; the Python
distribution prefixes it with the release year (Foundation 7.1 is
`2026.7.1`). Major and minor Foundation releases are not backward-compatible
with older Foundation releases. When following these 7.1 docs, install the
7.1 core tier and use validator, Benchmark, and packaging tool versions that
support Foundation 7.1. Do not combine 7.1 tier content with requirements,
features, profiles, custom tiers, or validation stamps from 7.0 or earlier.
Migrate older assets and custom tiers as needed, then validate them again
against a 7.1 profile.
```

### Foundation 7.1 Library Set

The SimReady libraries use independent release numbers. The supported 7.1
set is:

| Library | Foundation 7.1 version | When it is needed |
|---|---|---|
| `simready-foundation-tier-core` | `2026.7.1` | Always. Supplies the 7.1 requirements, features, profiles, validators, and bundled runtime tests. |
| `simready-validate` | `>=2026.7.0.dev1` | Static validation and the `simready.validate` Python API. |
| `simready-benchmark[kit]` | `>=2026.6.6` | Runtime and behavioral tests in Kit or Isaac Sim. Installed by the core tier's `benchmark` extra. |
| `simready-package` | `>=2026.6.0a1` | Package creation and pre/post validation. Use `simready-package[publish]` when WRAPP publishing is required. |

The tier and tool version numbers are intentionally different; do not replace
the tool versions above with `2026.7.1`. Pip resolves supporting libraries such
as `usd-validation-nvidia>=1.20.0`, `usd-core>=23.5` for Benchmark, and `numpy`
through these direct dependencies. Install those transitive libraries manually
only when developing or diagnosing the Foundation itself.

```{note}
The Isaac Sim capabilities, features, and profiles used to ship in a separate `simready-foundation-tier-isaac` package. They are now part of `simready-foundation-tier-core`, and the Isaac package is no longer published. If you have it installed, run `pip uninstall simready-foundation-tier-isaac` before upgrading: leaving both in one environment registers the Isaac requirement IDs twice.
```

### Public PyPI

For static validation, install the 7.1 tier and its compatible validator:

```bash
pip install "simready-foundation-tier-core==2026.7.1" "simready-validate>=2026.7.0.dev1"
```

To install the core tier together with Benchmark, its Kit engine, and the
published Foundation runtime tests:

```bash
pip install "simready-foundation-tier-core[benchmark]==2026.7.1" "simready-validate>=2026.7.0.dev1"
```

Add packaging support when required:

```bash
pip install "simready-package>=2026.6.0a1"

# Include the publish extra only for WRAPP publishing.
pip install "simready-package[publish]>=2026.6.0a1"
```

### NVIDIA Internal Artifactory

Confirm the internal index URL and authentication requirements for your environment before running these commands. The package names and version constraints are the same as for public PyPI.

```bash
pip install "simready-foundation-tier-core==2026.7.1" "simready-validate>=2026.7.0.dev1"
```

For the complete Benchmark environment:

```bash
pip install "simready-foundation-tier-core[benchmark]==2026.7.1" "simready-validate>=2026.7.0.dev1"
```

For packaging, add:

```bash
pip install "simready-package>=2026.6.0a1"

# Include the publish extra only for WRAPP publishing.
pip install "simready-package[publish]>=2026.6.0a1"
```

## How Tier Discovery Works

Each tier wheel contributes one entry point to each of two entry-point groups. A group can contain entry points from multiple installed packages:

- **`usd_validation_nvidia`**: the asset validator (`simready-validate`) uses this group to auto-discover and load the tier's validation rules and requirement enums at startup.
- **`simready.tier`**: the SimReady loader uses this group to enumerate all installed tiers and register their content in a single phased pass across all tiers: requirements and rules, then features, then profiles. Cross-tier references resolve regardless of install order.

These entry points let consumers discover a tier's validators and content from the installed wheel instead of requiring manually supplied content paths.

An installed tier may expose `runtime_tests_path` on its `simready.tier`
descriptor. Benchmark reads that path alongside the tier's specification
catalogs, so their versions cannot drift. Independent test-only distributions
may still use the `simready_benchmark.tests` entry-point group. Explicit
Benchmark `--tests-path` arguments are additive and remain available for
unpublished tests under local development.

`simready.validate` supports both content sources. When you call `initialize()` with filesystem paths, it loads content from local Foundation directories. When you call `initialize()` without filesystem paths, it discovers and registers installed tier wheels.

The following sequence shows how an installed tier participates in validation.

```{mermaid}
sequenceDiagram
    participant User
    participant pip
    participant CLI as simready-validate
    participant Plugin as usd_validation_nvidia
    participant TierEP as simready.tier
    participant Wheel as Tier wheel

    User->>pip: pip install simready-foundation-tier-core
    pip->>Wheel: install wheel and register entry points

    User->>CLI: simready-validate --profile X --version Y asset.usd
    CLI->>Plugin: discover SimReadyPlugin
    Plugin->>Wheel: on_startup()
    Wheel->>Wheel: import capabilities and register rules
    CLI->>TierEP: discover tier descriptor
    TierEP->>Wheel: resolve TierContent
    Wheel-->>CLI: content paths and requirements module
    CLI->>CLI: load profile, features, and requirements
    CLI->>CLI: run registered rule checkers
    CLI-->>User: validation results
```

## Verifying the Install

After installing the tier, confirm that its entry points are registered:

```python
from importlib.metadata import entry_points

tiers = entry_points(group="simready.tier")
print([ep.name for ep in tiers])
```

For example, after installing the core tier, the output includes `tier_core`.

## Validating an Asset

Validate an asset to determine whether it conforms to the contract defined by a selected profile. `simready-validate` loads the profile and its associated features, requirements, and rules from the installed tiers, runs the rule checkers against the asset, and reports the results.

To validate an asset, pass a profile, its version, and the asset path. Because the installed tiers supply the rules, features, and profiles, you do not need the `--rules-path`, `--features-path`, or `--profiles-path` flags:

```bash
simready-validate --profile Prop-Robotics-Neutral --version 1.0.0 path/to/asset.usd
```

Or from Python:

Call `initialize()` with empty path lists to trigger entry-point-based discovery of installed tiers. Then create an `AssetValidationConfig` that identifies the asset and the profile version to validate against, and pass it to `validate_asset`. The function returns one aggregate result for that asset and profile.

```python
import simready.validate as sv

sv.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])
result = sv.validate_asset(
    sv.AssetValidationConfig(
        asset_path="path/to/asset.usd",
        profile_id="Prop-Robotics-Neutral",
        profile_version="1.0.0",
    )
)
print(result)
```

For either method, review the output and verify that the validation results match the expected conformance of the asset.

## Creating Your Own Tier

A tier is an ordinary Python package. For example, if you want to distribute organization-specific validation rules and profiles while reusing Foundation content from the core tier, create your own tier. The steps below outline the package metadata and Python scaffolding for a tier that depends on `simready-foundation-tier-core` and adds a custom validation rule. They do not create a complete installable tier.

### 1. Declare the Package

In the root directory of your tier package, create a `pyproject.toml` file. Declare `simready-foundation-tier-core` as a dependency and register both entry points:

```toml
[project]
name = "my-simready-tier"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
dependencies = [
    "usd-validation-nvidia>=1.19.3",
    "simready-foundation-tier-core",
]

[project.entry-points."usd_validation_nvidia"]
my-tier-validate = "my_org.simready.tier_foo:SimReadyPlugin"

[project.entry-points."simready.tier"]
tier_foo = "my_org.simready.tier_foo:tier"
```

```{note}
The `path` in `[tool.hatch.build.hooks.custom]` assumes the tier lives alongside the Foundation tiers under `nv_core/tiers/`. If you are building outside the Foundation repository, copy `build_hook.py` from `nv_core/tiers/_tooling/` into your tier structure and adjust `path` accordingly.
```

Then add the Hatchling build configuration:

```toml
[tool.hatch.build.hooks.custom]
path = "../_tooling/build_hook.py"
module = "my_org.simready.tier_foo"
reverse_domain = "com.myorg.simready"

[tool.hatch.build.targets.wheel]
packages = ["my_org"]

[tool.hatch.build.targets.wheel.force-include]
"_build/python/my_org/simready/tier_foo/requirements" = "my_org/simready/tier_foo/requirements"

[build-system]
requires = ["hatchling", "usd-profiles-nvidia"]
build-backend = "hatchling.build"
```

### 2. Implement the Plugin

The asset validator discovers `SimReadyPlugin` through the tier's `usd_validation_nvidia` entry point and calls its startup and shutdown methods. Each tier must provide and export this class; the validator does not supply a default. For a conventional tier, you can use the generic implementation below without modification.

The `on_startup` method imports the tier's capabilities package, which registers its validators through decorator side effects. The `on_shutdown` method does nothing because the loader manages registry cleanup.

```python
# my_org/simready/tier_foo/_plugin.py
from __future__ import annotations


class SimReadyPlugin:
    def on_startup(self) -> None:
        from . import capabilities  # noqa: F401

    def on_shutdown(self) -> None:
        pass
```

The package initializer re-exports `SimReadyPlugin` and `tier` so that the two entry points declared in `pyproject.toml` can resolve those names from the package.

```python
# my_org/simready/tier_foo/__init__.py
from ._plugin import SimReadyPlugin
from ._tier import tier

__all__ = ["SimReadyPlugin", "tier"]
```

### 3. Expose the Tier Descriptor

The `tier` object is discovered through the `simready.tier` entry point and tells SimReady consumers where to find the tier's content. `TierContent` records the tier name, importable validator package, generated requirements module, bundled paths for capabilities and requirements, features, and profiles, plus an optional runtime-test container. The generic descriptor derives the tier name and module from its package, so a conventional tier can use it without modification.

```python
# my_org/simready/tier_foo/_tier.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent
_MODULE = __package__ or _PKG_ROOT.name
_NAME = _MODULE.rsplit(".", 1)[-1]
@dataclass(frozen=True)
class TierContent:
    name: str
    rules_package: str
    requirements_module: str
    rules_and_requirements_path: Path
    features_path: Path
    profiles_path: Path
    runtime_tests_path: Path | None = None


tier = TierContent(
    name=_NAME,
    rules_package=f"{_MODULE}.capabilities",
    requirements_module=f"{_MODULE}.requirements",
    rules_and_requirements_path=_PKG_ROOT / "capabilities",
    features_path=_PKG_ROOT / "features",
    profiles_path=_PKG_ROOT / "profiles",
    runtime_tests_path=None,
)
```

`runtime_tests_path` identifies one importable Benchmark test package directly.
A tier with no bundled runtime tests must leave the field as `None`, as in this
generic example. A tier that bundles a test package in the same wheel may set
the field to that package directory, but it must verify that the source project
or installed distribution owns both the tier descriptor and the test package.
Do not derive it with a fixed `parents[N]` path: that can advertise a similarly
named package owned by another installed distribution. The core tier's
`_tier.py` is the reference ownership-checked implementation. Descriptor
resolution only returns the path; it must not import the test package or its
engine dependencies.

### 4. Add a Requirement, Feature, and Profile

The recommended way to extend the Foundation is to define new requirements, features, and profiles that are owned entirely by your tier. Do not import requirements from another tier's module or use `override=True` on another tier's requirements.

The example below adds a new requirement `FOO.001`, a rule checker that validates it, a feature that includes it, and a profile that references that feature. This pattern mirrors how the core tier's `isaac_sim/composition` capability adds `ISA.001`.

**Define the requirement**

Create a markdown file under your tier's `capabilities/` tree:

```markdown
<!-- my_org/simready/tier_foo/capabilities/my_capability/requirements/foo-001.md -->
# my-capability

| Code | FOO.001 |
|------|---------|
| Tags | {tag}`essential` |

## Summary

Assets must satisfy the organization-specific constraint described here.
```

**Write the rule checker**

```python
# my_org/simready/tier_foo/capabilities/my_capability/validation.py
import my_org.simready.tier_foo.requirements as cap
import usd_validation_nvidia
from pxr import Usd


@usd_validation_nvidia.register_rule("MyCapability")
@usd_validation_nvidia.register_requirements(cap.MyCapabilityRequirements.FOO_001, override=True)
class MyCapabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage: Usd.Stage) -> None:
        ...
```

**Import the rule in the capabilities package**

```python
# my_org/simready/tier_foo/capabilities/__init__.py
from .my_capability import validation
```

**Define a feature**

```json
{
    "id": "FET200_MY_FEATURE",
    "version": "0.1.0",
    "display_name": "My Feature",
    "dependencies": [
        {"FET001_BASE_NEUTRAL": {"version": "0.1.0"}}
    ],
    "requirements": ["FOO.001"]
}
```

**Add a profile**

```toml
[My-Profile]
"1.0.0" = {features = [
    {"FET200_MY_FEATURE" = {version = "0.1.0"}},
]}
```

For a complete worked example, refer to `nv_core/tiers/simready_foundation_tier_core/`.

### 5. Install and Validate

Before running these commands, add your tier's requirements, feature definitions, and a profile named `My-Profile`. The preceding steps do not create this content.

Build the tier wheel using one of the following methods. After either method, continue with install and validate.

**In the Foundation repository**

If your tier lives alongside the Foundation tiers under `nv_core/tiers/`, add its directory to the `members` list in `nv_core/tiers/pyproject.toml`, which is the uv workspace root for the tiers:

```toml
[tool.uv.workspace]
members = [
    "simready_foundation_tier_core",
    "my-simready-tier",
]
```

Then run:

```bash
python _tooling/build_tiers.py
```

`build_tiers.py` generates the requirements-enum module for every workspace member and writes the wheels to the shared `nv_core/tiers/_build/dist/`. It requires `uv` on your PATH.

**Outside the Foundation repository**

If your tier lives outside the Foundation repository, complete the following steps:

1. Copy `build_hook.py` from `nv_core/tiers/_tooling/` into your tier structure.
2. Adjust the Hatchling `path` in `pyproject.toml` to the copied file.
3. Run `uv build --wheel`.

**Install and validate**

Regardless of where your tier lives, install the built wheel and validate an asset. In the Foundation repository the wheel is in the shared `nv_core/tiers/_build/dist/`; outside it, `uv build --wheel` writes to your tier's own `dist/`.

```bash
pip install simready-validate simready-foundation-tier-core <dist-dir>/my_simready_tier-*.whl
simready-validate --profile My-Profile --version 1.0.0 path/to/asset.usd
```

These commands install the core tier and your custom tier in the same environment. `simready-validate` loads both tiers and runs their registered rules in one validation pass.
