# Extending the Validation Sample: Adding a New Demo Validator

This guide walks through adding another requirement and rule to the sample, all under the same capability and existing feature (SAMP.001 / Feat_1). You will add a **requirement** (what to check), a **rule** (the Python checker), and add that requirement to the **existing feature**—no new feature or profile.

## Core concepts

Before extending, it helps to understand the four layers that make up the validation system and how they connect.

### Requirements

A **requirement** is a single, concrete check that an asset must pass. Each requirement is defined as a detailed markdown file in `sample_requirements/` with:

- A **code** that combines a capability prefix and a unique number (e.g. `SAMP.001`, `SAMP.002`).
- A **version** (e.g. `1.0.0`).
- Detailed documentation: Summary, Description, and **Valid USDA** / **Invalid USDA** subsections with concrete USDA snippets showing exactly what passes and what fails.

The code generator reads these markdown files and produces Python enums. For example, the code `SAMP.002` becomes the enum member `SampleRequirements.SAMP_002` (dot to underscore). Requirements are grouped under a **capability** (category): the prefix `SAMP` belongs to the "Sample" capability. Capabilities are defined in files like `capability-sample.md` which contain a requirements table listing all the `.md` files that belong to that category (see [Appendix: Capability (category)](#appendix-capability-category)).

### Rules

A **rule** is the Python class that enforces a requirement. Each rule lives in its own `.py` file inside `sample_requirements/` and subclasses `BaseRuleChecker`. The class is decorated with `@register_rule("<CapabilityName>")` and `@register_requirements(...)` to declare which requirement(s) it checks. When a rule detects a violation it calls `_AddFailedCheck(...)` with the specific `requirement=` so failures are reported against the right requirement code. `sample_requirements/__init__.py` auto-imports every rule module in the folder, so adding a new `.py` file is all that is needed to register a rule.

### Features

A **feature** is a logical concept: something you can say an asset has or doesn't have (e.g. "properly named", "has physics", "LOD-ready"). Features are defined as JSON files in `sample_features/` and each one bundles one or more requirements together. A feature **passes only when all of its requirements pass**. The mapping can take multiple forms: one feature backed by a single rule, or by many rules that together define that feature. For example, a feature like "having physics" might require many rules (rigid bodies present, collision shapes, no invalid references, etc.).

### Profiles

A **profile** is the top-level configuration that selects which features to validate. Profiles are defined in TOML (`sample_profiles/profiles.toml`) and list features by id and version. When you run validation you run it *with a profile*; the profile determines which features are active, which in turn determines which requirements (and their backing rules) actually execute.

### How they connect

The layers form a hierarchy:

```
Profile  --selects-->  Features  --group-->  Requirements  --enforced by-->  Rules (Python)
```

At runtime the system loads in this order (see also [Section 4](#4-load-order-and-running)):

1. **Requirements** -- codegen reads the markdown files and generates enums.
2. **Rules** -- `__init__.py` auto-imports all rule modules in the folder; decorators register checkers against requirement enums.
3. **Features** -- JSON files are loaded, linking requirement codes to feature ids.
4. **Profiles** -- TOML is loaded, linking features to the named profile.

In this sample everything is minimal: one requirement (`SAMP.001`), one feature (`Feat_1`), and one profile (`Sample-Profile`). When you extend, the simplest path is to add a new requirement and rule and attach the requirement to the existing feature, with no new feature or profile changes needed.

## Run the demo validator

Before extending, confirm the sample works. From `nv_core/validator_sample/`:

```bash
python validate_asset.py sample_assets/sample1.usda
```

The terminal should display a report indicating whether the demo asset passes or fails the checks defined in the sample validator.

## Where is SAMP.001 defined?

To see how the pieces fit together concretely, trace the existing sample through its files.

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

`sample_requirements/__init__.py` auto-imports every `.py` module in the folder, so this rule is registered automatically.

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

**Script** (`validate_asset.py`):

```python
issues = validate_asset_with_profile("sample_assets/sample1.usda", "Sample-Profile", "1.0.0")
```

In this sample the profile is passed directly in the script call. The script passes `"Sample-Profile"` and version `"1.0.0"` to `validate_asset_with_profile`, which looks up that profile in the registry, finds its features (Feat_1), resolves their requirements (SAMP.001), and runs the matching rule against the stage. In production, assets carry their profile in USD metadata so the validator can detect it automatically; see [Appendix: Profile metadata in production assets](#appendix-profile-metadata-in-production-assets) for details.

## What the sample does (SAMP.001 only)

The sample ships with a single requirement, **SAMP.001**: the stage must have a default prim named exactly `"Foo"`. Nothing else is checked. The rule that enforces this is `SampleNameChecker` in `sample_requirements/rule_name_checker.py`; the requirement is documented in `sample_requirements/requirement-name.md`.

**Valid USDA** — the asset passes when the stage has a default prim named "Foo":

```usda
#usda 1.0
def "Foo"
{
}
```

Or with explicit defaultPrim:

```usda
#usda 1.0
(
    defaultPrim = "Foo"
)
def "Foo"
{
}
```

**Invalid USDA** — the asset fails when there is no default prim, or the default prim has any other name:

- **No default prim** — the stage has no default prim set:

```usda
#usda 1.0
def "SomePrim"
{
}
```

- **Default prim has a different name** — the default prim exists but is not named "Foo":

```usda
#usda 1.0
(
    defaultPrim = "Bar"
)
def "Bar"
{
}
```

Full details and snippets are in `sample_requirements/requirement-name.md`.

## When you extend: what we want SAMP.002 to do

**Goal:** We will add a new requirement. When you add a second requirement, keep it **different** from SAMP.001 (which is only about the default prim). A good next step is **SAMP.002**: the stage must contain at least one prim named `"Bar"`, anywhere in the hierarchy. That is a separate, simple check (traverse the stage; look for a prim whose name is "Bar"). We keep everything on the same feature (Feat_1): define the requirement in markdown, implement the rule in Python, then add SAMP.002 to the existing feature's requirements list. We did not add a new feature or profile; only a new requirement is illustrated.

> **Note:** Do all the work below from `nv_core/validator_sample/`.

## 1. Define a New Requirement (Markdown)

Requirements are specified in markdown under `sample_requirements/`. Use an existing capability prefix (e.g. `SAMP` for Sample) so the code generator produces enums like `SampleRequirements.SAMP_002`. To add a new **category** (capability), see [Appendix: Capability (category)](#appendix-capability-category).

**These requirement files should be very detailed.** Follow the same structure as the existing sample (`sample_requirements/requirement-name.md`): a clear Summary, a full Description, and **Valid USDA** / **Invalid USDA** subsections with explanatory text and concrete USDA snippets for each pass/fail case. That level of detail makes the requirement unambiguous for implementers and for documentation.

### 1a. Add the requirement markdown

Add a new `.md` file in `sample_requirements/`, e.g. `requirement-has-bar.md` for a requirement that is *not* about the default prim (SAMP.001 already covers that). Example for SAMP.002 = stage must contain a prim named "Bar", in the same detailed style as the sample:

````markdown
# has-bar

| Code     | SAMP.002 |
|----------|-----------|
| Version  | 1.0.0 |
| Validator| {oav-validator-latest-link}`samp-002` |
| Compatibility | {compatibility}`sample` |
| Tags     | {tag}`essential` |

## Summary

The stage must contain at least one prim named "Bar".

## Description

This requirement ensures that the USD stage has at least one prim whose name is exactly "Bar", anywhere in the hierarchy. It is independent of the default prim (SAMP.001). The prim may be at root or under another prim.

### Valid USDA

The asset passes SAMP.002 when the stage contains at least one prim named "Bar". For example:

```usda
#usda 1.0
def "Foo"
{
}
def "Bar"
{
}
```

"Bar" may also be nested; the rule traverses the stage:

```usda
#usda 1.0
def "Foo"
{
    def "Bar"
    {
    }
}
```

### Invalid USDA

The asset fails SAMP.002 if:

- **No prim named "Bar"** — the stage has no prim with that name:

```usda
#usda 1.0
def "Foo"
{
}
def "Baz"
{
}
```

- **Only similar names** — "Bar" must match exactly (e.g. "bar", "BarChild" do not satisfy the requirement).
````

Important:

- At the top, the **Code** header must use the capability prefix (e.g. `SAMP`) and a unique number: `SAMP.002`, `SAMP.003`, etc.
- Add this requirement's filename to the capability's requirements table (see [step 1b](#1b-make-the-requirement-discoverable) and [Appendix: Capability (category)](#appendix-capability-category)).

The generator converts `SAMP.002` to the enum member `SampleRequirements.SAMP_002` (dot → underscore).

### 1b. Make the requirement discoverable

Add `requirement-has-bar` to the `{requirements-table}` in the capability markdown `sample_requirements/capability-sample.md`:

````{code-block} markdown
:emphasize-lines: 13

# Sample

**Capability:** Sample (SAMP)

## Overview

A sample category for the sample requirements.

## Requirements

```{requirements-table}
requirement-name
requirement-has-bar
```
````

Without this entry the code generator will not produce an enum for SAMP.002 and the rule will not be loadable.

## 2. Implement the Rule (Python)

Each rule lives in its own `.py` file inside `sample_requirements/`. The `__init__.py` auto-imports every module in the folder, so adding a new file is all that is needed to register a rule.

### 2a. Add a checker class

Subclass `BaseRuleChecker` and decorate with:

- `@register_rule("<CapabilityName>")` — must match the capability (e.g. `"Sample"`).
- `@register_requirements(cap.SampleRequirements.SAMP_002)` — one or more requirement enums.

Example: a rule for SAMP.002 that the stage must contain a prim named "Bar" (different from SAMP.001's default-prim check). Create a new file `sample_requirements/rule_has_bar_checker.py`:

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

- Use `requirement=...` so failures are tied to the right requirement (needed for feature pass/fail and summaries).
- `at=` can be a `Usd.Stage` or a `Usd.Prim` for location info.

## 3. Add the new requirement to the existing feature (JSON)

The rule is now defined, but it is not part of any feature — so nothing will know about it. Now we add it to Feat_1.

Keep the new rule on the same feature as SAMP.001. Edit the existing feature file `sample_features/feat_1_properly_named.json` and add your requirement code to the `requirements` array:

```json
{
    "id": "Feat_1",
    "version": "1.0.0",
    "display_name": "ProperlyNamed",
    "path": "sample_features/feat_1_properly_named.json",
    "requirements": ["SAMP.001", "SAMP.002"]
}
```

The profile already references Feat_1, so no profile or TOML change is needed. The existing `sample_profiles/profiles.toml`:

```toml
[Sample-Profile]
"1.0.0" = {features = [
    {"Feat_1" = {version = "1.0.0"}}, # "ProperlyNamed"
]}
```

To add this rule to a **new** feature instead, see [Appendix: Adding a rule to a new feature](#appendix-adding-a-rule-to-a-new-feature).

## 4. Load Order and Running

The sample loads in this order:

1. **Requirements** (from `sample_requirements/`): codegen generates enums → injected into `omni.capabilities`.
2. **Rules**: `sample_requirements/__init__.py` auto-imports all rule modules in the folder; their `@register_rule` and `@register_requirements` decorators register checkers.
3. **Features**: JSON files under `sample_features/` are loaded and registered.
4. **Profiles**: `sample_profiles/profiles.toml` is loaded and registered.

Run validation:

```bash
python validate_asset.py sample_assets/sample1.usda
```

This uses the profile (e.g. `Sample-Profile` 1.0.0) and runs all rules for the profile's features; results and feature pass/fail are reported via `validate_asset_with_profile` and `build_features_validation_summary`.

## Checklist for extending (stay on SAMP.001 / Feat_1)

1. **Requirement (markdown):** New `.md` in `sample_requirements/` with unique `Code` (e.g. `SAMP.002`), and include it in the capability's requirements table (see appendix).
2. **Rule (Python):** Add a new `.py` file in `sample_requirements/` with a `BaseRuleChecker` with `@register_rule("Sample")` and `@register_requirements(cap.SampleRequirements.SAMP_002)`, and implement the check with `_AddFailedCheck(..., requirement=...)`.
3. **Existing feature (JSON):** Edit `sample_features/feat_1_properly_named.json` and add `"SAMP.002"` to the `requirements` array (with `SAMP.001`). No new feature; no profile change.
4. **Run:** `python validate_asset.py sample_assets/sample1.usda` and confirm your rule runs.

## Tips

- **Naming:** Keep requirement codes and enum names in sync: code `SAMP.002` → `SAMP_002` in `SampleRequirements`.
- **One rule, multiple requirements:** You can use `@register_requirements(cap.SampleRequirements.SAMP_001, cap.SampleRequirements.SAMP_002)` and pass the appropriate `requirement` in each `_AddFailedCheck` so the right requirement is reported.
- **Existing sample:** SAMP.001 is in `requirement-name.md` and `SampleNameChecker` in `rule_name_checker.py`; add SAMP.002 as a different check (e.g. stage contains prim named Bar) and keep it on the same feature.

---

## Appendix: Adding a rule to a new feature

If you want the new requirement to belong to its own **logical feature** (instead of Feat_1), you get a separate feature id and pass/fail in validation summaries—e.g. "ProperlyNamed" (Feat_1) vs "HasBar" (Feat_2). Use this when the new rule represents a distinct capability or when you want to report or gate on it independently.

**1. Add a new feature JSON file**

Create a new file under `sample_features/` with a unique `id`, `version`, and a `requirements` array listing the requirement code(s) that define this feature. The loader picks up every `.json` in the features path. Example for a feature that only checks SAMP.002:

```json
{
    "id": "Feat_2",
    "version": "1.0.0",
    "display_name": "HasBar",
    "path": "sample_features/feat_2_has_bar.json",
    "requirements": ["SAMP.002"]
}
```

- **id** — Must be unique across features; the profile references features by this id.
- **version** — Used with id when a profile specifies which feature version to use.
- **requirements** — Requirement codes as strings (e.g. `"SAMP.002"`). Only registered requirements (from the Python module) are used; unregistered codes cause the feature to be skipped at load.
- **path** — Typically the path to this file (for tooling or docs).
- **display_name** — Optional human-readable label.

You can list multiple requirement codes if this feature is composed of several rules (e.g. `["SAMP.002", "SAMP.003"]`). The feature passes only when all of them pass.

**2. Add the feature to the profile (TOML)**

Profiles list which features are validated for each profile version. Edit `sample_profiles/profiles.toml` and add the new feature to the `features` array for the relevant profile version. Each entry is `{"<FeatureId>" = {version = "<version>"}}`. Example with both Feat_1 and Feat_2:

```toml
[Sample-Profile]
"1.0.0" = {features = [
    {"Feat_1" = {version = "1.0.0"}},
    {"Feat_2" = {version = "1.0.0"}},
]}
```

The loader matches these entries to registered features by id and version. When you run validation with this profile, both Feat_1 and Feat_2 are enabled and their requirements run; the summary reports pass/fail per feature.

**Optional: feature dependencies**

A feature can declare dependencies on other features in its JSON (e.g. a `dependencies` field). The validation loader can pull in those features' requirements when resolving the profile; see `loading/validation_loader.py` for how dependencies are applied.

## Appendix: Capability (category)

A **capability** is the category a requirement belongs to (e.g. "Sample"). The foundation spec code generator turns the capability prefix into an enum namespace: `SAMP` → `SampleRequirements` with codes like `SAMP_001`.

If you are adding a new category, add a capability file like `sample_requirements/capability-sample.md`:

- **Capability:** `<Name>` (`<PREFIX>`), e.g. `Sample (SAMP)`.
- **Requirements table:** list the requirement file names (without `.md`) that belong to this capability, using the `requirements-table` directive.

When you add a new requirement `.md` file, add that requirement's filename (no `.md`) to the capability's requirements table so it is part of that category.

## Appendix: Profile metadata in production assets

This sample specifies the profile explicitly in the script (`"Sample-Profile"`, `"1.0.0"`). In production, assets should declare their profile inside `customLayerData` so the validator can determine the correct profile automatically without hard-coding it in a script.

A production asset typically includes a `SimReady_Metadata` dictionary in its layer metadata:

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

The validator reads `customLayerData["SimReady_Metadata"]` from the root layer and uses the `profile` and `profile_version` fields to look up the registered profile. This means a single validation script can handle any asset without knowing its profile in advance.

This sample does not implement automatic profile detection — it keeps things simple by passing the profile as an argument. See the production validators in `nv_core/sr_specs/` for the full metadata-driven approach.
