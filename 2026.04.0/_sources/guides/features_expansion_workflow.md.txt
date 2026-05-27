# Adding a New Feature

## At a glance

1. Create requirement markdown + validation rule under an existing `capabilities/` folder.
2. Create a feature JSON under `features/` that lists the requirement codes.
3. Document the feature and add it to `features/features.md`.
4. Add the feature to `Prop-Robotics-Neutral` in `profiles/profiles.toml`.
5. `pip install simready-validate`, then run `simready-validate` to verify.

---

This guide walks through adding a new feature to the SimReady Foundation spec end-to-end. The example adds a dummy **"Has Foo Prim"** feature (`FET_099`) with one requirement (`FOO.001`) to the existing `hierarchy` capability.

## Core concepts

### What is a feature?

A **feature** describes a runtime behavior that an asset either supports or doesn't (e.g. "has physics", "can drive", "is grasp-ready"). Features are defined as JSON files in `features/` and each one bundles one or more requirements together. A feature **passes only when all of its requirements pass**.

### Feature dependencies

A feature can depend on other features. When specified, the validation system:

1. **Automatically includes** all requirements from dependent features.
2. **Recursively resolves** nested dependencies.
3. **Validates against** the complete set of requirements from all dependencies.

This lets you build on existing features without duplicating their requirement lists.

## 1. Add the new requirement

### 1a. Create the requirement documentation

Add a new `.md` file in the existing capability's `requirements/` folder. For this example, create `capabilities/hierarchy/requirements/has-foo-prim.md`:

````markdown
# has-foo-prim

| Code     | FOO.001 |
|----------|---------|
| Validator| {oav-validator-latest-link}`foo-001` |
| Compatibility | {compatibility}`open-usd` |
| Tags     | {tag}`essential` |

## Summary

The stage must contain a prim named "Foo".

## Description

The stage's default prim hierarchy must include at least one prim named
"Foo". This is a structural requirement that downstream tools depend on
to locate the primary content root.

### Valid USDA

```usda
#usda 1.0
(
    defaultPrim = "Root"
)
def Xform "Root"
{
    def Xform "Foo"
    {
    }
}
```

### Invalid USDA

```usda
#usda 1.0
(
    defaultPrim = "Root"
)
def Xform "Root"
{
    def Xform "Bar"
    {
    }
}
```

## How to comply

- Add an Xform prim named "Foo" under the default prim hierarchy.
````

### 1b. Register the requirement

Add the requirement filename to `capabilities/hierarchy/requirements.md` in the toctree:

```markdown
```{toctree}
:maxdepth: 1
:hidden:

requirements/hierarchy-has-root
requirements/exclusive-xform-parent-for-usdgeom
requirements/root-is-xformable
requirements/stage-has-default-prim
requirements/logical-geometry-grouping
requirements/xform-common-api-usage
requirements/placeable-posable-are-xformable
requirements/has-foo-prim                        <-- add this line
```

### 1c. Implement the rule

Add the checker class to `capabilities/hierarchy/validation.py`:

```python
@omni.asset_validator.register_rule("Hierarchy")
@omni.asset_validator.register_requirements(cap.HierarchyRequirements.FOO_001)
class HasFooPrimChecker(omni.asset_validator.BaseRuleChecker):
    """Stage must contain a prim named 'Foo'."""
    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            return
        for child in default_prim.GetAllChildren():
            if child.GetName() == "Foo":
                return
        self._AddFailedCheck(
            requirement=cap.HierarchyRequirements.FOO_001,
            message="No prim named 'Foo' found under the default prim.",
        )
```

## 2. Define the feature

Create `features/FET_099_base_neutral-0.1.0-has_foo_prim.json`:

```json
{
    "id": "FET099_BASE_NEUTRAL",
    "version": "0.1.0",
    "display_name": "Has Foo Prim",
    "path": "features/FET_099-has_foo_prim.html",
    "requirements": [
        "FOO.001"
    ]
}
```

If your feature builds on an existing feature, you can declare a dependency to inherit its requirements and only list **additional** ones:

```json
{
    "id": "FET099_BASE_NEUTRAL",
    "version": "0.1.0",
    "display_name": "Has Foo Prim",
    "path": "features/FET_099-has_foo_prim.html",
    "dependencies": [
        {"FET003_BASE_NEUTRAL": {"version": "0.1.0"}}
    ],
    "requirements": [
        "FOO.001"
    ]
}
```

The validation system merges all requirement sets (from dependencies and the feature itself) into a single set that gets validated.

### Feature ID conventions

Feature IDs follow the pattern `FET<NNN>_<VARIANT>`:

| Variant suffix | Meaning |
| --- | --- |
| `BASE_NEUTRAL` | Core OpenUSD only |
| `BASE_PHYSX` | Uses PhysX extensions |
| `BASE_MDL` | Uses MDL materials |
| `ROBOT_PHYSX` | Robot domain with PhysX |
| `ROBOT_CORE_ISAAC` | Robot core for Isaac Sim |

Pick the next available number for a new logical feature. If your feature is a runtime-specific variant of an existing feature, reuse the same number with a different suffix.

## 3. Add feature documentation

### 3a. Create a feature markdown

Create `features/FET_099-has_foo_prim.md`:

```markdown
# Feature: `ID:099 - Has Foo Prim`

## Neutral Format
### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

#### Requirements
* Capability: [Hierarchy](../capabilities/hierarchy/capability-hierarchy.md)
    * FOO.001
</details>
```

### 3b. Update the features index

Add the feature to `features/features.md` in the toctree:

```markdown
```{toctree}
:maxdepth: 1

ID:099 - Has Foo Prim - Base <FET_099-has_foo_prim>
```

## 4. Wire profiles

Add your feature to the `Prop-Robotics-Neutral` profile in `profiles/profiles.toml`:

```toml
[Prop-Robotics-Neutral]
"1.0.0" = {features = [
    {"FET000_CORE" = {version = "0.1.0"}},            # "Core"
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}},     # "Minimal"
    {"FET003_BASE_NEUTRAL" = {version = "0.1.0"}},     # "RBD Physics"
    {"FET004_BASE_NEUTRAL" = {version = "0.1.0"}},     # "Simulate Multi-Body Physics"
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}},     # "Simulate Grasp Physics"
    {"FET006_BASE_MDL" = {version = "0.1.0"}},         # "Materials"
    {"FET099_BASE_NEUTRAL" = {version = "0.1.0"}},     # "Has Foo Prim"   <-- add this line
]}
```

## 5. Install and verify

### 5a. Install simready-validate

Requires **Python >=3.10,<3.13** (Python 3.12 recommended).

```bash
pip install simready-validate
```

### 5b. Confirm it fails on a non-conforming asset

From the root of this repository (`simready_foundations/`), run the following. The sample asset `sm_apple_a01_01.usd` has no prim named "Foo", so it should fail `FOO.001`:

```bash
simready-validate \
  --rules-path nv_core/sr_specs/docs/capabilities \
  --features-path nv_core/sr_specs/docs/features \
  --profiles-path nv_core/sr_specs/docs/profiles/profiles.toml \
  --profile Prop-Robotics-Neutral --version 1.0.0 \
  sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd
```

Expected output:

```text
Asset: sample_content/.../sm_apple_a01_01.usd
  [FAILED] Prop-Robotics-Neutral v1.0.0
           FET099_BASE_NEUTRAL: failing requirements: ['FOO.001']
```

### 5c. Fix the asset

Add a "Foo" prim to the stage using the USD Python API and export the result:

```python
from pxr import Usd, UsdGeom

stage = Usd.Stage.Open(
    "sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd"
)
default_prim = stage.GetDefaultPrim()
UsdGeom.Xform.Define(stage, default_prim.GetPath().AppendChild("Foo"))
stage.Export("fixed_asset.usd")
```

The exported `fixed_asset.usd` now contains the required prim:

```usda
def Xform "Root"
{
    def Xform "Foo"
    {
    }
    # ... existing geometry ...
}
```

### 5d. Confirm it passes

Re-run validation against the fixed asset:

```bash
simready-validate \
  --rules-path nv_core/sr_specs/docs/capabilities \
  --features-path nv_core/sr_specs/docs/features \
  --profiles-path nv_core/sr_specs/docs/profiles/profiles.toml \
  --profile Prop-Robotics-Neutral --version 1.0.0 \
  fixed_asset.usd
```

Expected output:

```text
Asset: fixed_asset.usd
  [PASSED] Prop-Robotics-Neutral v1.0.0
```

## Checklist

1. **Requirement markdown:** Create under the existing capability's `requirements/` folder. Add to the `requirements.md` toctree.
2. **Validation rule:** Implement the checker class in the capability's `validation.py`.
3. **Feature JSON:** Create under `features/`.
4. **Feature documentation:** Create the feature markdown under `features/`. Add to `features/features.md`.
5. **Profile wiring:** Add the feature to `Prop-Robotics-Neutral` in `profiles/profiles.toml`.
6. **Install:** `pip install simready-validate`
7. **Verify:** Run `simready-validate` against a sample asset and confirm pass/fail behavior.

## Tips

- **Version from 0.1.0.** Start at `0.1.0` and bump the version when the requirement set changes.
- **One feature per logical concept.** Don't pack unrelated checks into the same feature.
- **Document clearly.** In the feature markdown, list every requirement and link back to the capability docs.
- **Test with sample assets.** Use the reference assets in `sample_content/` to validate against the target profile before merging.

```{note}
For the full acceptance lifecycle (domain identification, gap analysis, prototyping, QA, delivery), see the [SimReady Acceptance Workflow](acceptance_workflow.md).
```

---

## Appendix A: Creating a new capability

If your requirement doesn't fit any existing capability, create a new capability folder under `capabilities/`:

```text
capabilities/
└── foo_prims/
    ├── capability-foo_prims.md
    ├── requirements.md
    ├── requirements/
    │   └── has-foo-prim.md
    └── validation.py
```

Then register it by adding the `validation` import to `capabilities/__init__.py`. Once the capability exists, the steps in this guide apply the same way -- add requirements, wire features, and validate.

## Appendix B: Validating with the Python API

The `simready-validate` CLI is backed by the `simready.validate` Python library, which you can use directly for scripted or programmatic validation:

```python
from pathlib import Path
import simready.validate as sv

FOUNDATIONS_DOCS_DIR = Path("nv_core/sr_specs/docs")

sv.initialize(
    rules_and_requirements_paths=[FOUNDATIONS_DOCS_DIR / "capabilities"],
    features_paths=[FOUNDATIONS_DOCS_DIR / "features"],
    profiles_paths=[FOUNDATIONS_DOCS_DIR / "profiles"],
)

result = sv.validate_asset(sv.AssetValidationConfig(
    asset_path="fixed_asset.usd",
    profile_id="Prop-Robotics-Neutral",
    profile_version="1.0.0",
))

assert result is not None
assert result.passed
```
