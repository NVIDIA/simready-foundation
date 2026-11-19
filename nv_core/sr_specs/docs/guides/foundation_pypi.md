# SimReady Foundation PyPI Packages

## About This Guide

SimReady Foundation tier packages let you install the requirements, capabilities, features, profiles, and validation rules required for a specific runtime or use case. They also let you add organization-specific content without modifying or repackaging the Foundation source. This guide explains how to install Foundation tiers, use them to validate assets, and create a new tier that depends on and extends an existing tier.

This guide is intended for:

- **Asset pipeline users and validation engineers** who need to install Foundation content and validate assets with `simready-validate`.
- **Python developers and validation framework developers** who need to package and distribute additional requirements, capabilities, features, profiles, and validation rules.

This guide assumes you are familiar with the SimReady Foundation model of requirements, capabilities, features, and profiles. If these concepts are new to you, [SimReady Foundation](getting_started.md) provides an introduction. The installation and validation sections assume you are familiar with command-line tools and `pip`. The tier-authoring sections also assume you are familiar with Python package development, `pyproject.toml`, package entry points, and SimReady validation rule checkers.

This guide covers the Foundation tier packages. For the SimReady Python libraries that use them — search, retrieve, package, evaluate, thumbnail, and manage — refer to [SimReady Python Libraries](libraries.md).

## Background: What Is a Tier?

The Foundation spec is organized into *tiers*: separately publishable Python packages, each owning a coherent slice of capabilities, features, and profiles. Tiers can form dependency relationships. A tier that depends on another tier is the *downstream tier*; the tier it depends on is the *upstream tier*. The downstream tier declares the upstream tier as a `pip` dependency and adds its own content without modifying the upstream package. For example, a custom `my-simready-tier` that adds organization-specific rules would be downstream of `simready-foundation-tier-core`.

This section covers what a tier is well enough to follow the rest of this guide. For why the specification is divided this way, what tier ownership tells you about a profile, and how tiers differ from compatibility tiers and maturity levels, see [SimReady Foundation Tiers](tiers.md).

Before tier packages, validation content was loaded from shared `capabilities`, `features`, and `profiles` directories under `nv_core/sr_specs/docs/`. The tier structure packages corresponding content in self-contained Python package subtrees under `nv_core/tiers/`. During wheel builds, shared tooling generates each tier's requirements-enum module and embeds it in the wheel.

The SimReady Foundation repository organizes tier package sources as follows.

```text
nv_core/tiers/
├── _tooling/
├── simready_foundation_tier_core/
│   ├── pyproject.toml
│   └── simready/foundation/tier_core/
│       ├── rules_and_reqs/
│       ├── features/
│       └── profiles/
└── simready_foundation_tier_sensors/
    ├── pyproject.toml
    └── simready/foundation/sensors/
        ├── rules_and_reqs/
        └── features/
```

Additional tiers are siblings of `simready_foundation_tier_core/` with the same internal shape, each in its own `simready/foundation/<tier>/` package.

Foundation runtime tests live in their owning tier package beside the tier's
catalogs. The descriptor advertises their package directory without importing
it. Validator-only installs therefore remain lightweight, while a tier's
optional dependency extra installs the Evaluate and engine dependencies needed
to execute those bundled tests.

```{note}
This layout illustrates the SimReady Foundation repository; it does not prescribe the source layout for third-party tiers. A third-party tier must provide the entry points, plugin, and tier descriptor described later in this guide. If it uses the generic descriptor, it also needs `rules_and_reqs/`, `features/`, and `profiles/` directories under its package. Repository directories and Python modules use underscores; PyPI distribution names use hyphens.
```

The Foundation tiers include:

| Package | Contents | Depends on |
|---|---|---|
| `simready-foundation-tier-core` | Core, Hierarchy, Visualization, Physics Bodies, Isaac Sim, Non-Visual Sensors, Semantic Labels, Dataset Taxonomies, and Packaging capabilities; the neutral, PhysX, and Isaac prop profiles, the robot and gripper profiles, the package profiles, and the Open Taxonomy profiles | `simready-foundation-tier-newton` |
| `simready-foundation-tier-isaac` | Isaac Sim static optimization capabilities: rigid-body collapse, visual mesh merge, and render/collision separation | `simready-foundation-tier-core` |
| `simready-foundation-tier-newton` | Newton physics contracts and validators required by Robot-Body and Robot-Gripper 4.0.0 | |
| `simready-foundation-tier-sensors` | Physics Sensors, RTX Sensors / LiDAR, and Camera and Render Products capabilities; IMU, camera, LiDAR and joint sensor profiles | |

## Prerequisites

Use Python 3.12 for the combined toolchain and the Core + Sensors install
commands below. Base Core and the current Newton and Isaac optimization tiers
support Python 3.11–3.13 together. Sensors and AIF require Python `>=3.10,<3.13`,
so an environment containing either of them and Core supports Python 3.11–3.12.
Core's optional `[isaac]` and `[evaluate]` extras require Python 3.12; Evaluate
and its Kit engine require Python `>=3.12,<3.13`.

When upgrading from 2026.8 on Python 3.10, create a fresh Python 3.12 virtual
environment and install the current toolchain there. Upgrading packages inside
a Python 3.10 environment cannot satisfy Core's Python requirement.

The workspace and tier `pyproject.toml` files define compatible dependency
bounds. The tiers workspace has no current qualified lockfile. Reproducible
application environments can generate their own lock once the required Evaluate
releases are available from their configured package indexes. Builds and QA
must still resolve and verify the actual installed dependencies.

## Installation

First, install or upgrade `simready-validate`. Then install or upgrade the
Foundation tiers. Install Core and Sensors to enable sensor validation rules
and the Robot-Body profile's sensor features. Upgrade the tiers explicitly so
an existing 2026.8 installation receives the current profile catalog.

```{note}
Two packages carry "isaac" in their name, and they do different things.

`simready-foundation-tier-isaac` is a tier package. It provides the three Isaac optimization capabilities: `CAP102_RigidBodyCollapse.Isaac`, `CAP103_VisualMeshMerge.Isaac`, and `CAP104_RenderCollisionSeparation.Isaac`. A profile that selects any of these fails to resolve without it.

`simready-foundation-tier-core[isaac]` is an extra on the core tier. It installs the Isaac transformation and schema dependencies. It adds no capabilities.

Core already provides every other Isaac capability, including `CAP000_Core.Isaac`, `CAP021_RobotCore.Isaac`, and `CAP100_IsaacComposition.Isaac`. You do not need the Isaac tier for those.
```

When migrating an environment containing the legacy `0.0.1a*` Isaac tier,
uninstall that legacy package before installing current tiers to avoid duplicate
Isaac requirement registrations. Install the current optimization tier afterward
if a selected profile requires it.

````{note}
Use a fresh Python 3.12 environment for Evaluate. Historical Foundation runtime
tests shipped in the standalone `simready-benchmark-kit-suite` and experimental
`simready-foundation-runtime-tests-kit` distributions. If explicitly maintaining
an old environment, optional manual removal uses those original names:

```bash
pip uninstall simready-benchmark-kit-suite simready-foundation-runtime-tests-kit
```

Those distributions used the old flat `simready_benchmark_kit_suite` package.
Core, Newton and Sensors now ship namespaced runtime packages under their owning
tiers. Their former flat names remain provider aliases for selectors and
catalog bindings; Python imports use the current namespaced packages. Both
`benchmark` and `evaluate` extras declare the same execution dependencies.
Preserved descriptor, registration and data names do not restore the removed
Benchmark Python SDK. An old tier importing `simready_benchmark` requires its
matching Benchmark environment; current tier code requires its declared Evaluate
dependencies. Historical evidence readability does not establish freshness,
current source provenance or native qualification. Dependency ranges remain
independent; equal versions and cross-repository commit pins are not required.
````

### Public PyPI

Install or upgrade `simready-validate`:

```bash
pip install --upgrade simready-validate
```

Then install or upgrade Core and Sensors:

```bash
pip install --upgrade simready-foundation-tier-core simready-foundation-tier-sensors
```

Base core does not install the Isaac tooling, including when core is installed
as a dependency of another tier. For Isaac transformation and schema tooling,
opt in from a Python 3.12 environment:

```bash
pip install --upgrade "simready-foundation-tier-core[isaac]"
```

When upgrading an existing transformer environment, `[isaac]` replaces the
2026.8 `[isaac-transform]` extra. The `simready-transform-asset` command now ships
with Core. Remove the legacy standalone transformer before installing Core
with the new extra so the old distribution cannot retain or overwrite the
shared command and Python modules. `--force-reinstall` restores those files
even if Core was already upgraded before the legacy package was removed:

```bash
pip uninstall simready-isaac-asset-transformer
pip install --upgrade --force-reinstall "simready-foundation-tier-core[isaac]"
```

The extra installs `isaacsim-asset-isolated==6.2.0.1` and
`isaacsim-robot-schema==6.2.0.0` from PyPI. Other tiers that need this tooling can
depend on `simready-foundation-tier-core[isaac]`; they then also require Python
3.12 for these dependencies.

For the optional optimization profile, install or upgrade its tier:

```bash
pip install --upgrade simready-foundation-tier-isaac
```

Install the tier's optional `[evaluate]` extra and consult the installed tier's
declared dependency metadata when checking compatibility. The current Core and
Newton extras require both `simready.evaluate[kit]>=2026.9.0rc2,<2026.11`
and `simready.evaluate.engine-kit>=2026.9.0rc3,<2026.11`. These bounds
admit compatible prerelease and stable updates within this API generation.
Newton's `evaluate` and compatibility `benchmark` extras also require Core
`>=2026.10.0rc1` for their canonical neutral helper imports. This minimum allows
Core to update independently; it does not require matching tier versions.
The tiers verify composed room-floor state and isolate optional encoding
diagnostics without requiring a newer bug-fix release. Native engine errors,
unsafe evidence and cancellation remain fatal to the affected execution.
Newer assessment-aware reports present completed pivot advice explicitly;
older supported reporters retain its raw skip and recorded advisory evidence.
See the [NVIDIA internal index](#nvidia-internal-artifactory) for index
configuration; declared bounds do not establish that a compatible build is
published or available there. Locally built compatible wheels are a separate
development workflow: record their source revision, build and installed package
provenance when qualifying that environment.

Foundation and Explorer can be released independently within the declared API
compatibility ranges. Test the tiers against published baseline dependencies and
newer compatible wheels, including mixed versions. Raise a minimum only for a
required API or behavior that the tier cannot safely support through a tested
compatibility path. CI tests the tier wheels from its own build and resolves
published execution dependencies; no paired source commits are required.

### Using uv

When installing `[isaac]`, if uv reports that `tinyobjloader>=2.0.0rc13` cannot be resolved because
prereleases are disabled, explicitly request the release candidate required by
the Isaac converters:

```bash
uv pip install --upgrade "simready-foundation-tier-core[isaac]" "tinyobjloader==2.0.0rc13"
```

This opts in to that package's prerelease without enabling prereleases for all
dependencies. Both packages resolve from PyPI. The pip commands above already
accept the converters' prerelease requirement.

### NVIDIA Internal Artifactory

Confirm the internal index URL and authentication requirements for your environment before running these commands.
For release-candidate qualification, add `--pre` and select the intended
published versions explicitly; the commands below otherwise use pip's normal
release selection. Apply the same index and version selection to the optional
Isaac installs above.

```bash
pip install --upgrade --extra-index-url https://artifactory.nvidia.com/artifactory/api/pypi/ct-omniverse-pypi-local/simple simready-validate
```

Then install or upgrade Core and Sensors:

```bash
pip install --upgrade --extra-index-url https://artifactory.nvidia.com/artifactory/api/pypi/ct-omniverse-pypi-local/simple simready-foundation-tier-core simready-foundation-tier-sensors
```

For the complete Evaluate environment:

```bash
pip install --upgrade --extra-index-url https://artifactory.nvidia.com/artifactory/api/pypi/ct-omniverse-pypi-local/simple "simready-foundation-tier-core[evaluate]"
```

## How Tier Discovery Works

Each tier wheel contributes one entry point to each of two entry-point groups. A group can contain entry points from multiple installed packages:

- **`usd_validation_nvidia`**: the asset validator (`simready-validate`) uses this group to auto-discover and load the tier's validation rules and requirement enums at startup.
- **`simready.tier`**: the SimReady loader uses this group to enumerate all installed tiers and register their content in a single phased pass across all tiers: requirements and rules, then features, then profiles. Cross-tier references resolve regardless of install order.

These entry points let consumers discover a tier's validators and content from the installed wheel instead of requiring manually supplied content paths.

An installed tier may expose `runtime_tests_path` on its `simready.tier`
descriptor. Evaluate reads that path alongside the tier's specification
catalogs, so their versions cannot drift. Independent test-only distributions
may still use the `simready.evaluate.tests` entry-point group. Explicit
Evaluate `--tests-path` arguments are additive and remain available for
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
    Wheel->>Wheel: import rules_and_reqs and register rules
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

For example, after installing the core and sensors tiers, the output includes `['tier_core', 'sensors']`.

## Validating an Asset

Validate an asset to determine whether it conforms to the contract defined by a selected profile. `simready-validate` loads the profile and its associated features, requirements, and rules from the installed tiers, runs the rule checkers against the asset, and reports the results.

To validate an asset, pass a profile, its version, and the asset path. Because the installed tiers supply the rules, features, and profiles, you do not need the `--rules-path`, `--features-path`, or `--profiles-path` flags:

```bash
simready-validate --profile Robotics-Prop --version 3.2.0 path/to/asset.usd
```

Or from Python:

Call `initialize()` with empty path lists to trigger entry-point-based discovery of installed tiers. Then create an `AssetValidationConfig` that identifies the asset and the profile version to validate against, and pass it to `validate_asset`. The function returns one aggregate result for that asset and profile, so the caller owns multi-profile orchestration: create one config per target.

```python
import simready.validate as sv

sv.initialize(rules_and_requirements_paths=[], features_paths=[], profiles_paths=[])
result = sv.validate_asset(
    sv.AssetValidationConfig(
        asset_path="path/to/asset.usd",
        profile_id="Robotics-Prop",
        profile_version="3.2.0",
    )
)
print(result)
```

For either method, review the output and verify that the validation results match the expected conformance of the asset. When validating against more than one profile, review each profile result independently: Foundations 2 targets are supplied by the caller rather than inferred as one exclusive asset profile.

## Creating Your Own Tier

A tier is an ordinary Python package. For example, if you want to distribute organization-specific validation rules and profiles while reusing Foundation content from the core tier, create your own tier. The steps below outline the package metadata and Python scaffolding for a tier that depends on `simready-foundation-tier-core` and adds a custom validation rule. They do not create a complete installable tier.

### 1. Declare the Package

In the root directory of your tier package, create a `pyproject.toml` file. Declare `simready-foundation-tier-core` as a dependency and register both entry points:

```toml
[project]
name = "my-simready-tier"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
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

The `on_startup` method imports the tier's rules_and_reqs package, which registers its validators through decorator side effects. The `on_shutdown` method does nothing because the loader manages registry cleanup.

```python
# my_org/simready/tier_foo/_plugin.py
from __future__ import annotations


class SimReadyPlugin:
    def on_startup(self) -> None:
        from . import rules_and_reqs  # noqa: F401

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

The `tier` object is discovered through the `simready.tier` entry point and tells SimReady consumers where to find the tier's content. `TierContent` records the tier name, importable validator package, generated requirements module, bundled paths for rules and requirements, capabilities, features, and profiles, plus an optional runtime-test package. The explicit contract paths select Foundations 2 loading. The generic descriptor derives the tier name and module from its package, so a conventional tier can use it without modification.

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
    capability_contracts_path: Path
    feature_contracts_path: Path
    profile_contracts_path: Path
    runtime_tests_path: Path | None = None


tier = TierContent(
    name=_NAME,
    rules_package=f"{_MODULE}.rules_and_reqs",
    requirements_module=f"{_MODULE}.requirements",
    rules_and_requirements_path=_PKG_ROOT / "rules_and_reqs",
    features_path=_PKG_ROOT / "features",
    profiles_path=_PKG_ROOT / "profiles",
    capability_contracts_path=_PKG_ROOT / "capabilities",
    feature_contracts_path=_PKG_ROOT / "features",
    profile_contracts_path=_PKG_ROOT / "profiles",
    runtime_tests_path=None,
)
```

`runtime_tests_path` identifies one importable Evaluate test package directly.
A tier with no bundled runtime tests must leave the field as `None`, as in this
generic example. A tier that bundles a test package in the same wheel may set
the field to that package directory, but it must verify that the source project
or installed distribution owns both the tier descriptor and the test package.
Do not derive it with a fixed `parents[N]` path: that can advertise a similarly
named package owned by another installed distribution. The core tier's
`_tier.py` is the reference ownership-checked implementation. Descriptor
resolution only returns the path; it must not import the test package or its
engine dependencies.

### 4. Add a Requirement, Capability, and Profile

Define requirements, capabilities, features, and profiles that are owned entirely by your tier. Do not import requirements from another tier's module or use `override=True` on another tier's requirements.

The example below adds a new requirement `FOO.001`, a rule checker that validates it, a static capability that includes it, and a profile that selects that capability. Static-only bundles use CAP identities; runtime-tested contracts use FET identities. This pattern mirrors how the core tier's `isaac_sim/composition` capability adds `ISA.001`.

**Define the requirement**

Create a markdown file under your tier's `rules_and_reqs/` tree:

```markdown
<!-- my_org/simready/tier_foo/rules_and_reqs/my_capability/requirements/foo-001.md -->
# my-capability

| Code | FOO.001 |
|------|---------|
| Tags | {tag}`essential` |

## Summary

Assets must satisfy the organization-specific constraint described here.
```

**Write the rule checker**

```python
# my_org/simready/tier_foo/rules_and_reqs/my_capability/validation.py
import my_org.simready.tier_foo.requirements as cap
import usd_validation_nvidia
from pxr import Usd


@usd_validation_nvidia.register_rule("MyCapability")
@usd_validation_nvidia.register_requirements(cap.MyCapabilityRequirements.FOO_001)
class MyCapabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage: Usd.Stage) -> None:
        ...
```

**Import the rule in the rules_and_reqs package**

```python
# my_org/simready/tier_foo/rules_and_reqs/__init__.py
from .my_capability import validation
```

**Define a capability**

Save this manifest as `capabilities/CAP200_MyCapability.0-0-1.json`
under your tier package, in the descriptor's `capability_contracts_path`.

```json
{
    "id": "CAP200_MyCapability.0-0-1",
    "display_name": "My Capability",
    "requirements": ["FOO.001"]
}
```

**Add a profile**

```toml
[My-Profile]
"2.0.0" = {features = [
], capabilities = [
    {selector = "CAP200_MyCapability.0-0-1"},
]}
```

For a complete worked example, refer to `nv_core/tiers/simready_foundation_tier_core/`.

### 5. Install and Validate

Before running these commands, add your tier's requirements, capability definition, and a profile named `My-Profile`. The preceding steps describe this content; create the files in your tier package.

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
pip install \
  simready-validate simready-foundation-tier-core <dist-dir>/my_simready_tier-*.whl
simready-validate --profile My-Profile --version 2.0.0 path/to/asset.usd
```

These commands install the core tier and your custom tier in the same environment. `simready-validate` loads both tiers and runs their registered rules in one validation pass.

### 6. Iterate on Your Tier

Rebuilding and reinstalling a wheel after every edit is a slow loop for tier development. Install your tier as an *editable* install instead. An editable install registers the tier's `simready.tier` entry point while the `TierContent` descriptor keeps resolving to your working tree, because it derives its paths from `__file__`. Validation therefore loads your edits through the same entry-point discovery path a released wheel uses.

If your tier lives under `nv_core/tiers/`, use the bundled helper:

```bash
# every tier in the checkout, into the active interpreter
python nv_core/tiers/_tooling/dev_install.py

# one tier, into a specific virtual environment
python nv_core/tiers/_tooling/dev_install.py \
    --tier my-simready-tier --python .venv/bin/python
```

If your tier lives outside the Foundation repository, `pip` alone is enough:

```bash
pip install -e .
```

Either way, no path flags are needed when validating:

```bash
simready-validate --profile My-Profile --version 2.0.0 path/to/asset.usd
```

Neither form requires `uv`. `pip install -e` drives your tier's Hatchling backend through PEP 517, which resolves `hatchling` and `usd-profiles-nvidia` into an isolated build environment and runs the build hook that generates your requirement enums.

Confirm the tier resolves to your checkout rather than to an installed wheel:

```python
from importlib.metadata import entry_points
import importlib

for ep in entry_points(group="simready.tier"):
    print(ep.name, importlib.import_module(ep.value.split(":")[0]).__file__)
```

`dev_install.py` prints this same report after installing.

```{note}
Editable and wheel-installed tiers coexist. `simready` and `simready.foundation` are namespace packages, so an editable experimental tier loads from its checkout while `simready-foundation-tier-core` remains an ordinary wheel from PyPI. This is the supported way to try an experimental tier alongside released ones: `initialize()` loads either filesystem paths or installed tiers, never both, so the experimental tier has to be installed rather than passed as a path.
```

```{important}
Re-run the editable install in two situations:

- **After adding or removing a requirement page.** Requirement enums are generated at install time, so a new requirement code is not importable until codegen runs again — a validator referencing it fails with `AttributeError`, and a feature referencing it is skipped with `unregistered requirements`. Edits to validators, feature manifests, profiles, and existing requirement prose take effect with no reinstall.
- **After building wheels from the same checkout.** A wheel build clears the in-checkout copy of the generated enums so the wheel cannot ship them twice, which leaves the editable install without its requirements module. The symptom is `ModuleNotFoundError: No module named '<module>.requirements'`.
```

Two things to watch for when authoring a tier this way:

- Do not import `usd_validation_nvidia` at module scope in `_plugin.py`. The validator loads plugins while that package is being imported, so a module-level import re-enters your tier mid-import and plugin discovery fails with `partially initialized module ... has no attribute 'SimReadyPlugin'`. Import `rules_and_reqs` lazily inside `on_startup`, as shown in step 2.
- Feature manifests resolve a bare requirement code only against your tier's own `reverse_domain` (and `com.nvidia.simready`). Requirements owned by the validation framework must be written out in full, for example `com.nvidia.usd.HI.001`. If a feature is skipped with `unregistered requirements`, a missing namespace prefix is the usual cause.
