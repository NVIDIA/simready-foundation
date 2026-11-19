# Extending the Validation Sample: Adding a New Demo Validator

This guide walks through adding another requirement and rule to the sample in `nv_core/validator_sample/`. You will add a **requirement** (what to check), a **rule** (the Python checker), a **capability** that bundles the new requirement, and a new **profile version** that selects it.

## Core concepts

Before extending, it helps to understand the layers that make up the validation system and how they connect.

### Requirements

A **requirement** is a single, concrete check that an asset must pass. Each requirement is defined as a detailed markdown file in `sample_requirements/` with:

- A **code** that combines a category prefix and a unique number (e.g. `SAMP.001`, `SAMP.002`).
- A **version** (e.g. `1.0.0`).
- Detailed documentation: Summary, Description, and **Valid USDA** / **Invalid USDA** subsections with concrete USDA snippets showing exactly what passes and what fails.

The code generator reads these markdown files and produces Python enums. For example, the code `SAMP.002` becomes the enum member `SampleRequirements.SAMP_002` (dot to underscore). Requirements are grouped by prefix into a category: `SAMP` belongs to the "Sample" category, declared in `capability-sample.md`, which contains a requirements table listing all the `.md` files in that category (see [Appendix: Requirement category](#appendix-requirement-category)). This markdown category is not the same thing as the `CAP`-prefixed capability contract described below.

### Rules

A **rule** is the Python class that enforces a requirement. Each rule lives in its own `.py` file inside `sample_requirements/` and subclasses `BaseRuleChecker`. The class is decorated with `@register_rule("<CategoryName>")` and `@register_requirements(...)` to declare which requirement(s) it checks. When a rule detects a violation it calls `_AddFailedCheck(...)` with the specific `requirement=` so failures are reported against the right requirement code. `sample_requirements/__init__.py` auto-imports every rule module in the folder, so adding a new `.py` file is all that is needed to register a rule.

### Capabilities

A **capability** is a static contract: something you can say an asset has or doesn't have (e.g. "properly named", "has a Bar prim"). Capabilities are defined as JSON files in `sample_capabilities/` and each one bundles one or more requirements together. A capability **passes only when all of its requirements pass**. A capability can be backed by a single rule or by many rules that together define it.

Every capability has one ID of the form `<name>[.<runtime>].<version>`:

- **name** — `CAP`, a number, and a descriptive suffix, e.g. `CAP900_ProperlyNamed`.
- **runtime** — `OpenUSD` for checks that do not depend on a simulation runtime.
- **version** — an opaque token with hyphens instead of dots, e.g. `1-0-0`.

The ID is the capability's only identity; there is no separate `version` field. A published ID is immutable: to change what a capability requires, publish a new version.

### Features

A **feature** is a contract that is also proven at runtime: something an asset can do in a simulator (e.g. "has physics", "graspable"). Like a capability, a feature bundles one or more requirements and **passes only when all of its requirements pass**. A feature like "has physics" might require many rules (rigid bodies present, collision shapes, no invalid references, etc.). A feature also declares runtime tests, behavioral tests that load the asset into a simulator and check how it behaves.

Features use the same ID scheme as capabilities with an `FET` prefix, e.g. `FET003_RigidBody.PhysX.0-4-0`, where the runtime segment names the simulator the tests run in. A contract with no runtime tests is a capability.

This sample has no runtime tests, so it only uses capabilities. See [Features](features/features.md).

### Profiles

A **profile** is the top-level configuration that selects which capabilities and features to validate. Profiles are defined in TOML (`sample_profiles/profiles.toml`); each profile version lists feature and capability selectors, and each selector matches one or more feature or capability IDs. When you run validation you run it *with a profile*; the profile determines which features and capabilities are active, which in turn determines which requirements (and their backing rules) actually execute. Published profile versions are immutable too: to change what a profile selects, add a new profile version.

### How they connect

The layers form a hierarchy:

```
Profile  --selects-->  Features / Capabilities  --group-->  Requirements  --enforced by-->  Rules (Python)
```

At runtime the system loads in this order (see also [Section 5](#5-load-order-and-running)):

1. **Requirements** -- codegen reads the markdown files and generates enums.
2. **Rules** -- `__init__.py` auto-imports all rule modules in the folder; decorators register checkers against requirement enums.
3. **Features and capabilities** -- JSON files are loaded, linking requirement codes to feature and capability IDs.
4. **Profiles** -- TOML is loaded, and each selector is resolved against the loaded features and capabilities.

In this sample everything is minimal: one requirement (`SAMP.001`), one capability (`CAP900_ProperlyNamed.1-0-0`), and one profile (`Sample-Profile`).

## Run the demo validator

Before extending, confirm the sample works. From `nv_core/validator_sample/`:

```bash
simready-validate \
  --rules-path sample_requirements \
  --features-path sample_capabilities \
  --profiles-path sample_profiles/profiles.toml \
  --profile Sample-Profile --version 1.0.0 \
  sample_assets/sample1.usda
```

The terminal should report `[PASSED] Sample-Profile v1.0.0`. `--features-path` loads contract JSON of both kinds, `CAP` capabilities and `FET` features.

## Where is SAMP.001 defined?

To see how the pieces fit together concretely, trace the existing sample through its files.

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

`sample_requirements/__init__.py` auto-imports every `.py` module in the folder, so this rule is registered automatically.

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

The `--profile Sample-Profile --version 1.0.0` arguments select the profile target. The validator resolves the profile's selector to `CAP900_ProperlyNamed.1-0-0`, collects its requirement (`SAMP.001`), and runs the matching rule. The caller always chooses the profile target; it is never inferred from asset metadata. See [Caller-supplied profile targets](#appendix-caller-supplied-profile-targets).

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

**Goal:** We will add a new requirement. When you add a second requirement, keep it **different** from SAMP.001 (which is only about the default prim). A good next step is **SAMP.002**: the stage must contain at least one prim named `"Bar"`, anywhere in the hierarchy. That is a separate, simple check (traverse the stage; look for a prim whose name is "Bar"). We define the requirement in markdown, implement the rule in Python, bundle it in a new capability, and select that capability from a new profile version. The published `Sample-Profile` `1.0.0` and `CAP900_ProperlyNamed.1-0-0` stay unchanged.

> **Note:** Do all the work below from `nv_core/validator_sample/`.

## 1. Define a New Requirement (Markdown)

Requirements are specified in markdown under `sample_requirements/`. Use an existing category prefix (e.g. `SAMP` for Sample) so the code generator produces enums like `SampleRequirements.SAMP_002`. To add a new category, see [Appendix: Requirement category](#appendix-requirement-category).

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

- At the top, the **Code** header must use the category prefix (e.g. `SAMP`) and a unique number: `SAMP.002`, `SAMP.003`, etc.
- Add this requirement's filename to the category's requirements table (see [step 1b](#1b-make-the-requirement-discoverable) and [Appendix: Requirement category](#appendix-requirement-category)).

The generator converts `SAMP.002` to the enum member `SampleRequirements.SAMP_002` (dot → underscore).

### 1b. Make the requirement discoverable

Add `requirement-has-bar` to the `{requirements-table}` in the category markdown `sample_requirements/capability-sample.md`:

````{code-block} markdown
:emphasize-lines: 13

# Sample

**Capability:** Sample (SAMP)

## Overview

A sample category for demo requirements.

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

- `@register_rule("<CategoryName>")` — must match the category (e.g. `"Sample"`).
- `@register_requirements(cap.SampleRequirements.SAMP_002)` — one or more requirement enums.

Example: a rule for SAMP.002 that the stage must contain a prim named "Bar" (different from SAMP.001's default-prim check). Create a new file `sample_requirements/rule_has_bar_checker.py`:

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

- Use `requirement=...` so failures are tied to the right requirement (needed for capability pass/fail and summaries).
- `at=` can be a `Usd.Stage` or a `Usd.Prim` for location info.

## 3. Add a Capability (JSON)

The rule is now defined, but it is not part of any capability — so no profile can select it. Create `sample_capabilities/CAP901_HasBar.1-0-0.json`:

```json
{
    "id": "CAP901_HasBar.1-0-0",
    "display_name": "HasBar",
    "requirements": ["SAMP.002"]
}
```

- **id** — The capability's only identity: `CAP` plus a number and name, the runtime (`OpenUSD`), and the version token. Name the file after the ID.
- **requirements** — Requirement codes as strings (e.g. `"SAMP.002"`). Only registered requirements (from the Python module) are used; a capability that lists an unregistered code is skipped at load, and any profile that selects it fails to resolve.
- **display_name** — Optional human-readable label.

You can list multiple requirement codes if this capability is composed of several rules (e.g. `["SAMP.002", "SAMP.003"]`). The capability passes only when all of them pass. A capability can also list exact capability IDs it builds on in a `dependencies` array; the validator pulls those in whenever this one is selected.

## 4. Add a Profile Version (TOML)

`Sample-Profile` `1.0.0` is published, so leave it as it is and add version `1.1.0` to `sample_profiles/profiles.toml`, selecting both capabilities:

```toml
[Sample-Profile]
"1.0.0" = {capabilities = [
    {selector = "CAP900_ProperlyNamed.1-0-0"},
]}
"1.1.0" = {capabilities = [
    {selector = "CAP900_ProperlyNamed.1-0-0"},
    {selector = "CAP901_HasBar.1-0-0"},
]}
```

Each entry is a table with a `selector` key. A selector that matches no loaded capability is an error, unless it is marked optional (see [Appendix: Optional and wildcard selectors](#appendix-optional-and-wildcard-selectors)).

## 5. Load Order and Running

The sample loads in this order:

1. **Requirements** (from `sample_requirements/`): codegen generates enums → injected into `omni.capabilities`.
2. **Rules**: `sample_requirements/__init__.py` auto-imports all rule modules in the folder; their `@register_rule` and `@register_requirements` decorators register checkers.
3. **Capabilities**: JSON files under `sample_capabilities/` are loaded and registered.
4. **Profiles**: `sample_profiles/profiles.toml` is loaded, and each selector is resolved against the registered capabilities.

Run validation against the new profile version:

```bash
simready-validate \
  --rules-path sample_requirements \
  --features-path sample_capabilities \
  --profiles-path sample_profiles/profiles.toml \
  --profile Sample-Profile --version 1.1.0 \
  sample_assets/sample1.usda
```

`sample1.usda` has no prim named "Bar", so the new capability fails:

```text
  [FAILED] Sample-Profile v1.1.0
           CAP901_HasBar.1-0-0: failing requirements: ['com.nvidia.simready.SAMP.002']
```

Add a `Bar` prim anywhere under `Foo` and the asset passes. Validating against `--version 1.0.0` still passes, because that profile version does not select the new capability. Add `-v` to print each issue's message.

## Checklist for extending

1. **Requirement (markdown):** New `.md` in `sample_requirements/` with unique `Code` (e.g. `SAMP.002`), and include it in the category's requirements table (see appendix).
2. **Rule (Python):** Add a new `.py` file in `sample_requirements/` with a `BaseRuleChecker` with `@register_rule("Sample")` and `@register_requirements(cap.SampleRequirements.SAMP_002)`, and implement the check with `_AddFailedCheck(..., requirement=...)`.
3. **Capability (JSON):** Add `sample_capabilities/CAP901_HasBar.1-0-0.json` listing `"SAMP.002"`.
4. **Profile (TOML):** Add a new `Sample-Profile` version that selects the new capability. Leave published versions unchanged.
5. **Run:** Validate `sample_assets/sample1.usda` against the new profile version and confirm your rule runs.

## Tips

- **Naming:** Keep requirement codes and enum names in sync: code `SAMP.002` → `SAMP_002` in `SampleRequirements`.
- **One rule, multiple requirements:** You can use `@register_requirements(cap.SampleRequirements.SAMP_001, cap.SampleRequirements.SAMP_002)` and pass the appropriate `requirement` in each `_AddFailedCheck` so the right requirement is reported.
- **Existing sample:** SAMP.001 is in `requirement-name.md` and `SampleNameChecker` in `rule_name_checker.py`; add SAMP.002 as a different check (e.g. stage contains prim named Bar).

---

## Appendix: Adding a requirement to an existing capability

To make SAMP.002 part of "ProperlyNamed" instead of a separate capability, publish a new version of that capability rather than editing `1-0-0`. Create `sample_capabilities/CAP900_ProperlyNamed.1-1-0.json`:

```json
{
    "id": "CAP900_ProperlyNamed.1-1-0",
    "display_name": "ProperlyNamed",
    "requirements": ["SAMP.001", "SAMP.002"]
}
```

Then select it from a new profile version:

```toml
"1.2.0" = {capabilities = [
    {selector = "CAP900_ProperlyNamed.1-1-0"},
]}
```

Assets and profiles that reference `CAP900_ProperlyNamed.1-0-0` keep their original meaning. Use a separate capability when the new rule represents something you want to report or gate on independently; use a new version when it refines the same concept.

## Appendix: Optional and wildcard selectors

Mark a selector `optional = true` to run its checks and report failures without failing the profile:

```toml
"1.3.0" = {capabilities = [
    {selector = "CAP900_ProperlyNamed.1-0-0"},
    {selector = "CAP901_HasBar.1-0-0", optional = true},
]}
```

Validating `sample1.usda` against this version passes and lists `CAP901_HasBar.1-0-0` with its unmet `SAMP.002` requirement. An optional selector that matches nothing is allowed; a required one is an error. If the same capability is selected both ways, required wins.

Selectors may also leave trailing segments off or use `*` wildcards. `CAP900_ProperlyNamed` selects every runtime and version of that capability, and `CAP901` selects the whole `CAP901` family. Wildcard selectors pick up new matching versions automatically, so use an exact ID when the profile must stay reproducible. See [Profiles](profiles/profiles.md) for the full selector rules.

## Appendix: Requirement category

A requirement category groups requirements by code prefix (e.g. "Sample"). The foundation spec code generator turns the prefix into an enum namespace: `SAMP` → `SampleRequirements` with codes like `SAMP_001`.

If you are adding a new category, add a category file like `sample_requirements/capability-sample.md`:

- **Capability:** `<Name>` (`<PREFIX>`), e.g. `Sample (SAMP)`.
- **Requirements table:** list the requirement file names (without `.md`) that belong to this category, using the `requirements-table` directive.

When you add a new requirement `.md` file, add that requirement's filename (no `.md`) to the category's requirements table so it is part of that category.

## Appendix: Caller-supplied profile targets

This sample specifies one profile target explicitly (`Sample-Profile`, `1.0.0`).
Production callers may provide several targets for the same asset, for example a
robotics profile and a marketplace-delivery profile. Resolve and validate every
`(profile, version)` pair independently and retain one result per target.

Do not treat a `SimReady_Metadata.profile` value as a declaration of what the
asset can satisfy; it only records which target was last validated. Validation
targets come from the caller. The reference multi-profile orchestration helper
is `simready.foundation.validation.validate_profiles`.
