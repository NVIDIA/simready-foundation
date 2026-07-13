# Validation Sample

A minimal, self-contained sample that demonstrates the SimReady Foundation
validation system. It ships one requirement, one rule, one feature, and one
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

Install `simready-validate` if you have not already (from `nv_core/validator_sample/`):

```bash
pip install -r requirements.txt
```

Then run validation from `nv_core/validator_sample/`:

```bash
simready-validate \
  --rules-path sample_requirements \
  --features-path sample_features \
  --profiles-path sample_profiles/profiles.toml \
  --profile Sample-Profile --version 1.0.0 \
  sample_assets/sample1.usda
```

The terminal should display a report indicating whether the demo asset passes
or fails the checks defined in the sample validator.

## Core concepts

The validation system is built on four layers that form a hierarchy:

```
Profile  --selects-->  Features  --group-->  Requirements  --enforced by-->  Rules (Python)
```

### Requirements

A **requirement** is a single, concrete check that an asset must pass. Each
requirement is defined as a detailed markdown file in `sample_requirements/`
with:

- A **code** that combines a capability prefix and a unique number (e.g.
  `SAMP.001`, `SAMP.002`).
- A **version** (e.g. `1.0.0`).
- Detailed documentation: Summary, Description, and **Valid USDA** / **Invalid
  USDA** subsections with concrete USDA snippets showing exactly what passes
  and what fails.

The code generator reads these markdown files and produces Python enums. For
example, the code `SAMP.002` becomes the enum member
`SampleRequirements.SAMP_002` (dot to underscore). Requirements are grouped
under a **capability** (category): the prefix `SAMP` belongs to the "Sample"
capability. Capabilities are defined in files like `capability-sample.md` which
contain a requirements table listing all the `.md` files that belong to that
category.

### Rules

A **rule** is the Python class that enforces a requirement. Each rule lives in
its own `.py` file inside `sample_requirements/` and subclasses
`BaseRuleChecker`. The class is decorated with
`@register_rule("<CapabilityName>")` and `@register_requirements(...)` to
declare which requirement(s) it checks. When a rule detects a violation it
calls `_AddFailedCheck(...)` with the specific `requirement=` so failures are
reported against the right requirement code.
`sample_requirements/__init__.py` auto-imports every rule module in the
folder, so adding a new `.py` file is all that is needed to register a rule.

### Features

A **feature** is a logical concept: something you can say an asset has or
doesn't have (e.g. "properly named", "has physics", "LOD-ready"). Features
are defined as JSON files in `sample_features/` and each one bundles one or
more requirements together. A feature **passes only when all of its
requirements pass**.

### Profiles

A **profile** is the top-level configuration that selects which features to
validate. Profiles are defined in TOML (`sample_profiles/profiles.toml`) and
list features by id and version. When you run validation you run it *with a
profile*; the profile determines which features are active, which in turn
determines which requirements (and their backing rules) actually execute.

## What the sample contains

In this sample everything is minimal: one requirement (`SAMP.001`), one
feature (`Feat_1`), and one profile (`Sample-Profile`).

### SAMP.001 — default prim must be named "Foo"

The sample ships with a single requirement: the stage must have a default prim
named exactly `"Foo"`. Nothing else is checked.

**Profile** (`sample_profiles/profiles.toml`):

```toml
[Sample-Profile]
"1.0.0" = {features = [
    {"Feat_1" = {version = "1.0.0"}}, # "ProperlyNamed"
]}
```

**Feature** (`sample_features/feat_1_properly_named.json`):

```json
{
    "id": "Feat_1",
    "version": "1.0.0",
    "display_name": "ProperlyNamed",
    "path": "sample_features/feat_1_properly_named.json",
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
)

def Xform "Foo"
{
}
```

**Command** (from `nv_core/validator_sample/`):

```bash
simready-validate \
  --rules-path sample_requirements \
  --features-path sample_features \
  --profiles-path sample_profiles/profiles.toml \
  --profile Sample-Profile --version 1.0.0 \
  sample_assets/sample1.usda
```

The CLI loads the rules from `sample_requirements/`, the feature definitions
from `sample_features/`, and the profile from `sample_profiles/profiles.toml`.
It then validates `sample1.usda` against `Sample-Profile` version `1.0.0`,
which selects feature `Feat_1`, resolves its requirement (`SAMP.001`), and runs
the matching rule against the stage.

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

## Extending the sample

When you extend, the simplest path is to add a new requirement and rule and
attach the requirement to the existing feature, with no new feature or profile
changes needed.

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
from omni.asset_validator import (
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

**4. Add to the feature** — edit
`sample_features/feat_1_properly_named.json` and add `"SAMP.002"` to the
`requirements` array.

**5. Run** — from `nv_core/validator_sample/`, run:

```bash
simready-validate \
  --rules-path sample_requirements \
  --features-path sample_features \
  --profiles-path sample_profiles/profiles.toml \
  --profile Sample-Profile --version 1.0.0 \
  sample_assets/sample1.usda
```

Confirm your rule runs and the failure is reported.

### Adding a new feature

If you want the new requirement to belong to its own logical feature, create a
new JSON file under `sample_features/` with a unique `id` and add it to the
profile in `sample_profiles/profiles.toml`. See the production guides linked
above for the full workflow.

### Adding a new capability

A **capability** is the category a requirement belongs to. If you need a new
category, add a capability file like `sample_requirements/capability-sample.md`
with the capability name, prefix, and a `{requirements-table}` listing the
requirement files.

## Load order

The sample loads in this order:

1. **Requirements** — codegen reads the markdown files and generates enums →
   injected into `omni.capabilities`.
2. **Rules** — `__init__.py` auto-imports all rule modules; decorators register
   checkers.
3. **Features** — JSON files are loaded, linking requirement codes to feature
   ids.
4. **Profiles** — TOML is loaded, linking features to the named profile.

## Profile metadata in production

This sample specifies the profile explicitly via CLI flags. In production,
assets declare their profile inside `customLayerData` so the validator can
determine the correct profile automatically:

```usda
#usda 1.0
(
    customLayerData = {
        dictionary SimReady_Metadata = {
            string profile = "Prop-Robotics-Neutral"
            string profile_version = "1.0.0"
        }
    }
    defaultPrim = "MyAsset"
)
```

See the production validators in `nv_core/sr_specs/` and the
[guides](../sr_specs/docs/guides/guides.md) for the full metadata-driven
approach.
