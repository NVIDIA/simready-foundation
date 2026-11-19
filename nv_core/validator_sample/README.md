# Validation Sample

A minimal, self-contained sample that demonstrates the SimReady Foundation
validation system. It ships one requirement, one rule, one capability, and one
profile so you can see the full stack in a few files before working with the
production spec.

For production workflows, see the guides in
`nv_core/sr_specs/docs/guides/`:

- **[Acceptance Workflow](../sr_specs/docs/guides/acceptance_workflow.md)** —
  end-to-end walkthrough of adding requirements, rules, and features to the
  production spec.
- **[Features Expansion Workflow](../sr_specs/docs/guides/features_expansion_workflow.md)** —
  creating technology-specific feature variants (e.g. neutral → PhysX).
- **[Profiles Validation Workflow](../sr_specs/docs/guides/profiles_validation_workflow.md)** —
  creating, versioning, and validating assets against profiles.

---

## Quick start

Install `simready-validate` if you have not already (from the repository root):

```bash
pip install -r requirements.txt
```

Then run validation from `nv_core/validator_sample/`:

```bash
simready-validate \
  --rules-path sample_requirements \
  --features-path sample_capabilities \
  --profiles-path sample_profiles/profiles.toml \
  --profile Sample-Profile --version 1.0.0 \
  sample_assets/sample1.usda
```

The terminal should display a report indicating whether the demo asset passes
or fails the checks defined in the sample validator.

## Core concepts

The validation system is built on four layers that form a hierarchy:

```
Profile  --selects-->  Features / Capabilities  --group-->  Requirements  --enforced by-->  Rules (Python)
```

### Requirements

A **requirement** is a single, concrete check that an asset must pass. Each
requirement is defined as a detailed markdown file in `sample_requirements/`
with:

- A **code** that combines a category prefix and a unique number (e.g.
  `SAMP.001`, `SAMP.002`).
- A **version** (e.g. `1.0.0`).
- Detailed documentation: Summary, Description, and **Valid USDA** / **Invalid
  USDA** subsections with concrete USDA snippets showing exactly what passes
  and what fails.

The code generator reads these markdown files and produces Python enums. For
example, the code `SAMP.002` becomes the enum member
`SampleRequirements.SAMP_002` (dot to underscore). Requirements are grouped by
prefix into a category: `SAMP` belongs to the "Sample" category, declared in
`capability-sample.md`, which contains a requirements table listing all the
`.md` files in that category. This markdown category is not the same thing as
the `CAP`-prefixed capability contract described below.

### Rules

A **rule** is the Python class that enforces a requirement. Each rule lives in
its own `.py` file inside `sample_requirements/` and subclasses
`BaseRuleChecker`. The class is decorated with
`@register_rule("<CategoryName>")` and `@register_requirements(...)` to
declare which requirement(s) it checks. When a rule detects a violation it
calls `_AddFailedCheck(...)` with the specific `requirement=` so failures are
reported against the right requirement code.
`sample_requirements/__init__.py` auto-imports every rule module in the
folder, so adding a new `.py` file is all that is needed to register a rule.

### Capabilities

A **capability** is a static contract: something you can say an asset has or
doesn't have (e.g. "properly named"), defined as a JSON file that bundles one
or more requirements. A capability **passes only when all of its requirements
pass**. Its `id` has the form `<name>[.<runtime>].<version>`, where the name
starts with `CAP` and a number, neutral checks omit the runtime segment,
and the version uses hyphens (`1-0-0`). The `id` is the capability's
only identity; there is no separate `version` field.

### Features

A **feature** is a contract that is also proven at runtime: something an asset
can do in a simulator (e.g. "has physics", "graspable"). Like a capability, a
feature bundles one or more requirements and **passes only when all of its
requirements pass**. A feature also declares runtime tests, behavioral tests
that load the asset into a simulator and check how it behaves. Its `id` uses
the same form with an `FET` prefix, e.g. `FET003_RigidBody.PhysX.0-4-0`, where
the runtime segment names the simulator the tests run in.

This sample has no runtime tests, so it only uses capabilities.

### Profiles

A **profile** is the top-level configuration that selects which capabilities
and features to validate. Profiles are defined in TOML
(`sample_profiles/profiles.toml`) as lists of feature and capability
selectors. When you run validation you run it *with a profile*; the profile
determines which features and capabilities are active, which in turn
determines which requirements (and their backing rules) actually execute.

## What the sample contains

In this sample everything is minimal: one requirement (`SAMP.001`), one
capability (`CAP900_ProperlyNamed.1-0-0`), and one profile
(`Sample-Profile`).

### SAMP.001 — default prim must be named "Foo"

The sample ships with a single requirement: the stage must have a default prim
named exactly `"Foo"`. Nothing else is checked.

**Profile** (`sample_profiles/profiles.toml`):

```toml
[Sample-Profile]
"1.0.0" = {capabilities = [
    {selector = "CAP900_ProperlyNamed.1-0-0"},
]}
```

**Capability** (`sample_capabilities/CAP900_ProperlyNamed.1-0-0.json`):

```json
{
    "id": "CAP900_ProperlyNamed.1-0-0",
    "display_name": "ProperlyNamed",
    "requirements":
    [
        "SAMP.001"
    ]
}
```

**Rule** (`sample_requirements/rule_name_checker.py`):

```python
@register_rule("Sample")
@register_requirements(cap.SampleRequirements.SAMP_001)
class SampleNameChecker(BaseRuleChecker):
    """
    The default prim must be named "Foo".
    """
    def CheckStage(self, stage: Usd.Stage):
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim.", at=stage, requirement=cap.SampleRequirements.SAMP_001)
            return
        if default_prim.GetName() != "Foo":
            self._AddFailedCheck("Root prim must be named 'Foo'.", at=default_prim, requirement=cap.SampleRequirements.SAMP_001)
            return
```

**Asset** (`sample_assets/sample1.usda`):

```usda
#usda 1.0
(
    defaultPrim = "Foo"
    metersPerUnit = 1
    upAxis = "Z"
)

def Xform "Foo"
{
    def Scope "Geometry"
    {
        def Xform "some_transform"
        {
        }
    }
}
```

**Command** (from `nv_core/validator_sample/`):

```bash
simready-validate \
  --rules-path sample_requirements \
  --features-path sample_capabilities \
  --profiles-path sample_profiles/profiles.toml \
  --profile Sample-Profile --version 1.0.0 \
  sample_assets/sample1.usda
```

The CLI loads the rules from `sample_requirements/`, the capability from
`sample_capabilities/` (`--features-path` loads both `CAP` and `FET`
contracts), and the profile from `sample_profiles/profiles.toml`. It then
validates `sample1.usda` against `Sample-Profile` version `1.0.0`, which
selects `CAP900_ProperlyNamed.1-0-0`, resolves its requirement
(`SAMP.001`), and runs the matching rule against the stage.

### Valid and invalid examples

**Valid USDA** — the asset passes when the stage has a default prim named
"Foo":

```usda
#usda 1.0
(
    defaultPrim = "Foo"
)
def "Foo"
{
}
```

**Invalid USDA** — the asset fails when there is no default prim, or the
default prim has any other name:

- **No default prim:**

```usda
#usda 1.0
def "SomePrim"
{
}
```

- **Default prim has a different name:**

```usda
#usda 1.0
(
    defaultPrim = "Bar"
)
def "Bar"
{
}
```

`sample_assets/sample_fail.usda` is a failing example. Validating it reports:

```text
  [FAILED] Sample-Profile v1.0.0
           CAP900_ProperlyNamed.1-0-0: failing requirements: ['com.nvidia.simready.SAMP.001']
```

## Extending the sample

Published capability and profile versions are immutable. To add a check, add a
new requirement and rule, put the requirement in a new capability, and select
it from a new profile version.

### Adding SAMP.002

A good next step is **SAMP.002**: the stage must contain at least one prim
named `"Bar"`, anywhere in the hierarchy. That is a separate, simple check
(traverse the stage; look for a prim whose name is "Bar").

**1. Add the requirement markdown** — create
`sample_requirements/requirement-has-bar.md` with Code `SAMP.002`, Summary,
Description, and Valid/Invalid USDA sections.

**2. Make it discoverable** — add `requirement-has-bar` to the
`{requirements-table}` in `sample_requirements/capability-sample.md`.

**3. Implement the rule** — create
`sample_requirements/rule_has_bar_checker.py`:

```python
import omni.capabilities as cap
from usd_validation_nvidia import (
    BaseRuleChecker,
    register_requirements,
    register_rule,
)
from pxr import Usd

@register_rule("Sample")
@register_requirements(cap.SampleRequirements.SAMP_002)
class SampleHasBarChecker(BaseRuleChecker):
    """Stage must contain a prim named 'Bar'."""
    def CheckStage(self, stage: Usd.Stage):
        for prim in stage.Traverse():
            if prim.GetName() == "Bar":
                return
        self._AddFailedCheck("Stage must contain a prim named 'Bar'.", at=stage, requirement=cap.SampleRequirements.SAMP_002)
```

**4. Add a capability** — create
`sample_capabilities/CAP901_HasBar.1-0-0.json`:

```json
{
    "id": "CAP901_HasBar.1-0-0",
    "display_name": "HasBar",
    "requirements": ["SAMP.002"]
}
```

**5. Add a profile version** — leave `"1.0.0"` unchanged and add `"1.1.0"` to
`sample_profiles/profiles.toml`:

```toml
"1.1.0" = {capabilities = [
    {selector = "CAP900_ProperlyNamed.1-0-0"},
    {selector = "CAP901_HasBar.1-0-0"},
]}
```

**6. Run** — from `nv_core/validator_sample/`, run:

```bash
simready-validate \
  --rules-path sample_requirements \
  --features-path sample_capabilities \
  --profiles-path sample_profiles/profiles.toml \
  --profile Sample-Profile --version 1.1.0 \
  sample_assets/sample1.usda
```

`sample1.usda` has no prim named "Bar", so `CAP901_HasBar.1-0-0`
fails with `SAMP.002`.

### Optional selectors

Mark a selector `optional = true` to report its failures without failing the
profile:

```toml
"1.2.0" = {capabilities = [
    {selector = "CAP900_ProperlyNamed.1-0-0"},
    {selector = "CAP901_HasBar.1-0-0", optional = true},
]}
```

### Adding a requirement category

If you need a new requirement category, add a file like
`sample_requirements/capability-sample.md` with the category name, prefix, and
a `{requirements-table}` listing the requirement files.

## Load order

The sample loads in this order:

1. **Requirements** — codegen reads the markdown files and generates enums →
   injected into `omni.capabilities`.
2. **Rules** — `__init__.py` auto-imports all rule modules; decorators register
   checkers.
3. **Features and capabilities** — JSON files are loaded, linking requirement
   codes to feature and capability IDs.
4. **Profiles** — TOML is loaded, resolving each selector against the loaded
   features and capabilities.

## Profile targets

The CLI validates one profile target per run, given by `--profile` and
`--version`. Validating the same asset against several profiles produces one
independent result per target; profile selection always comes from the
caller, never from metadata stamped into the asset. See the
[profiles guide](../sr_specs/docs/guides/profiles/profiles.md).
