# Profiles Validation Workflow

This guide walks through creating, validating, and managing profiles in the SimReady Foundation spec. A profile is the top-level unit that asset producers and consumers work with — it defines exactly which features (and therefore which requirements and rules) apply to an asset. You will learn how to create a profile, validate assets against it, version it, and manage multi-profile scenarios.

## Core concepts

### What is a profile?

A **profile** is a named, versioned collection of features that represents a complete simulation scenario. When you validate an asset, you validate it *against a profile*. The profile determines which features are active, which in turn determines which requirements (and their backing rules) actually execute.

Profiles are defined in TOML (`profiles/profiles.toml`) and each profile version lists features by id and version:

```toml
[Prop-Robotics-Neutral]
"1.0.0" = {features = [
    {"FET000_CORE" = {version = "0.1.0"}},
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}},
    {"FET003_BASE_NEUTRAL" = {version = "0.1.0"}},
    {"FET004_BASE_NEUTRAL" = {version = "0.1.0"}},
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}},
    {"FET006_BASE_MDL" = {version = "0.1.0"}},
]}
```

### How profiles connect to everything else

```
Profile  --selects-->  Features  --group-->  Requirements  --enforced by-->  Rules (Python)
```

At validation time:

1. The profile is looked up by name and version.
2. Its feature list is resolved — each feature id+version is matched to a registered feature JSON.
3. Each feature's requirements (including those from dependencies) are collected.
4. The corresponding rules execute against the asset.
5. Results are reported per-requirement and per-feature.

### Existing profiles

The current spec ships these profiles:

| Profile | Target | Key differences |
| --- | --- | --- |
| `Prop-Robotics-Neutral` | Props, runtime-neutral | Base features only (neutral physics, neutral colliders) |
| `Prop-Robotics-Physx` | Props, PhysX runtime | PhysX-expanded physics and collider features |
| `Prop-Robotics-Isaac` | Props, Isaac Sim | PhysX physics + Isaac composition |
| `Robot-Body-Neutral` | Robots, runtime-neutral | Adds driven joints and base articulation |
| `Robot-Body-Runnable` | Robots, PhysX runtime | PhysX physics, robot core runnable, PhysX joints |
| `Robot-Body-Isaac` | Robots, Isaac Sim | Isaac robot core, Isaac joints, Isaac composition |

## 1. Determine what the profile needs

Before creating a profile, answer these questions:

| Question | Example answer |
| --- | --- |
| What **asset type** does it cover? | Props, robots, vehicles, environments |
| What **simulation runtime** does it target? | Neutral (any), PhysX, Isaac Sim |
| Which **features** must the asset have? | Rigid-body physics, grasp physics, materials, semantic labels |
| Which **feature variants** apply? | Neutral colliders vs. PhysX merged mesh colliders |
| Are there **existing profiles** to base it on? | Extend `Prop-Robotics-Neutral` with semantic labels |

### Identify required features

Browse the existing feature JSON files under `features/` to find features that match your needs. Each feature has:

- An `id` (e.g. `FET003_BASE_NEUTRAL`)
- A `version` (e.g. `0.1.0`)
- A `display_name` (e.g. "Rigid Body Physics")
- A list of `requirements` it enforces

Use the [feature dependency graph](../features/feature-dependency-graph) to understand how features relate to each other and which dependencies they pull in.

### Check feature availability

Every feature referenced by a profile must exist as a registered JSON file under `features/`. Verify that the feature id and version in your profile match an existing file's `"id"` and `"version"` fields. For example, `{"FET003_BASE_PHYSX" = {version = "0.1.0"}}` requires a file with `"id": "FET003_BASE_PHYSX"` and `"version": "0.1.0"`.

## 2. Create the profile entry

### 2a. Add the profile to `profiles.toml`

Edit `profiles/profiles.toml` and add a new TOML table section for your profile:

```toml
[Prop-Robotics-Labeled]
"1.0.0" = {features = [
    {"FET000_CORE" = {version = "0.1.0"}},                # "Core"
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}},        # "Minimal"
    {"FET003_BASE_NEUTRAL" = {version = "0.1.0"}},        # "RBD Physics"
    {"FET004_BASE_NEUTRAL" = {version = "0.1.0"}},        # "Simulate Multi-Body Physics"
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}},        # "Simulate Grasp Physics"
    {"FET006_BASE_MDL" = {version = "0.1.0"}},            # "Materials (MDL)"
    {"FET011_BASE_NEUTRAL" = {version = "0.2.0"}},        # "Semantic Labels"
]}
```

**Naming conventions:**

- Use descriptive names that indicate the asset type and runtime: `<AssetType>-<Domain>-<Runtime>`.
- Use hyphens and title case: `Prop-Robotics-Neutral`, `Robot-Body-Isaac`.
- The profile name is the TOML table key and must be unique.

**Profile structure:**

- Each profile is a TOML table: `[Profile-Name]`.
- Each version is a quoted key (e.g. `"1.0.0"`) mapping to `{features = [...]}`.
- Each feature entry is `{"FEATURE_ID" = {version = "version"}}`.
- Add inline comments with the feature display name for readability.

### 2b. Create the profile documentation

Create a markdown file in `profiles/` for the new profile (e.g. `prop-robotics-labeled.md`):

```markdown
# Prop-Robotics-Labeled

## Purpose

This profile targets robotics prop assets that require semantic labeling
in addition to the standard physics and material features. Use this
profile when assets will be consumed by perception pipelines or synthetic
data generation systems that rely on semantic labels.

## Version 1.0.0

### Features

| Feature | Version | Description |
| --- | --- | --- |
| FET000_CORE | 0.1.0 | Core asset structure |
| FET001_BASE_NEUTRAL | 0.1.0 | Minimal editor requirements |
| FET003_BASE_NEUTRAL | 0.1.0 | Rigid body physics |
| FET004_BASE_NEUTRAL | 0.1.0 | Multi-body physics |
| FET005_BASE_NEUTRAL | 0.1.0 | Grasp physics |
| FET006_BASE_MDL | 0.1.0 | MDL materials |
| FET011_BASE_NEUTRAL | 0.2.0 | Semantic labels |

### Differences from Prop-Robotics-Neutral

- Adds `FET011_BASE_NEUTRAL` for semantic label validation
- All other features are identical
```

Add the profile to the profiles index in `profiles/profiles.md`.

## 3. Validate assets against the profile

### 3a. Asset metadata

Production assets declare their profile in `customLayerData`:

```usda
#usda 1.0
(
    customLayerData = {
        dictionary SimReady_Metadata = {
            string profile = "Prop-Robotics-Labeled"
            string profile_version = "1.0.0"
        }
    }
    defaultPrim = "MyAsset"
)
```

The validator reads this metadata and automatically selects the correct profile.

### 3b. Run validation

From the repository root:

```bash
python -m simready.foundation.core asset.usda
```

The validator reads the asset's `SimReady_Metadata`, looks up the profile, resolves all features and requirements, and runs every matching rule.

To override or specify a profile explicitly:

```bash
python -m simready.foundation.core --feature FET000_CORE asset.usda
python -m simready.foundation.core --capability Hierarchy asset.usda
```

### 3c. Interpret results

The validation report shows:

- **Per-requirement results:** Each requirement code (e.g. `HI.004`) with pass/fail and any error messages.
- **Per-feature results:** Each feature (e.g. `FET000_CORE`) passes only when all of its requirements pass.
- **Profile result:** The overall profile passes only when all features pass.

A failed requirement traces directly to the rule that detected the violation and the USD prim/attribute at fault.

## 4. Version a profile

Profile versions are **immutable** — once a version is released, it must not be modified. Changes require a new version.

### When to create a new version

| Trigger | Version bump |
| --- | --- |
| A feature version is updated (e.g. `FET001` 0.1.0 → 1.0.0) | Major or minor |
| A new feature is added to the profile | Major or minor |
| A feature is removed from the profile | Major |
| Bug fix in a feature's requirement list | Patch |

### Add the new version

Add a new version entry under the same profile table in `profiles.toml`:

```toml
[Prop-Robotics-Labeled]
"1.0.0" = {features = [
    {"FET000_CORE" = {version = "0.1.0"}},
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}},
    {"FET003_BASE_NEUTRAL" = {version = "0.1.0"}},
    {"FET004_BASE_NEUTRAL" = {version = "0.1.0"}},
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}},
    {"FET006_BASE_MDL" = {version = "0.1.0"}},
    {"FET011_BASE_NEUTRAL" = {version = "0.2.0"}},
]}
"2.0.0" = {features = [
    {"FET000_CORE" = {version = "0.1.0"}},
    {"FET001_BASE_NEUTRAL" = {version = "1.0.0"}},        # Updated
    {"FET003_BASE_NEUTRAL" = {version = "0.1.0"}},
    {"FET004_BASE_NEUTRAL" = {version = "0.1.0"}},
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}},
    {"FET006_BASE_MDL" = {version = "0.1.0"}},
    {"FET011_BASE_NEUTRAL" = {version = "0.2.0"}},
]}
```

### Update documentation

Document the version change in the profile's markdown file:

```markdown
## Version 2.0.0

### Changes from 1.0.0
- Updated FET001_BASE_NEUTRAL from 0.1.0 to 1.0.0

### Migration notes
- Assets validated against 1.0.0 may need updates for FET001 1.0.0 requirements
- Use feature adapters to upgrade assets (see below)
```

### Upgrade assets

Assets pinned to the old profile version can be upgraded using the workspace CLI:

```bash
workspace upgrade --output_uri output_asset.usda \
    --output_profile Prop-Robotics-Labeled \
    --output_profile_version 2.0.0
```

This runs the appropriate feature adapters to transform the asset's USD content from the old feature versions to the new ones.

## 5. Create a runtime-specific profile variant

When the same asset type needs a runtime-specific profile (e.g. neutral → PhysX), follow this pattern:

### 5a. Identify feature differences

Compare the base profile's features with the runtime's needs:

| Feature area | Neutral | PhysX |
| --- | --- | --- |
| Colliders | `FET003_BASE_NEUTRAL` (RB.COL.001) | `FET003_BASE_PHYSX` (COL.001) |
| Multi-body | `FET004_BASE_NEUTRAL` | `FET004_BASE_PHYSX` |
| Grasp | `FET005_BASE_NEUTRAL` | `FET005_BASE_NEUTRAL` (same) |
| Materials | `FET006_BASE_MDL` | `FET006_BASE_MDL` (same) |

### 5b. Create the runtime profile

```toml
[Prop-Robotics-Labeled-Physx]
"1.0.0" = {features = [
    {"FET000_CORE" = {version = "0.1.0"}},
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}},
    {"FET003_BASE_PHYSX" = {version = "0.1.0"}},          # PhysX variant
    {"FET004_BASE_PHYSX" = {version = "0.1.0"}},          # PhysX variant
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}},
    {"FET006_BASE_MDL" = {version = "0.1.0"}},
    {"FET011_BASE_NEUTRAL" = {version = "0.2.0"}},
]}
```

### 5c. Plan feature adapters

For each feature that differs between the neutral and runtime profiles, a feature adapter may be needed. See the [Feature Adapters Guide](feature_adapters/feature_adapters.md) for implementation.

## Checklist for creating a profile

1. **Requirements analysis:** Identify the asset type, target runtime, and required features.
2. **Feature availability:** Verify all feature ids and versions exist as JSON files under `features/`.
3. **Profile TOML:** Add the profile entry to `profiles/profiles.toml` with all features and versions.
4. **Documentation:** Create a profile markdown file in `profiles/` and add it to the profiles index.
5. **Asset metadata:** Ensure target assets include `SimReady_Metadata` with the profile name and version in `customLayerData`.
6. **Validate:** Run `python -m simready.foundation.core` against test assets and confirm the correct features and requirements execute.
7. **Version control:** Never modify a released profile version — create a new version instead.

## Tips

- **Start from an existing profile.** Copy the feature list of the closest existing profile and add/remove/swap features as needed.
- **Use inline comments.** Add `# "Display Name"` after each feature entry in the TOML for readability.
- **Pin versions.** Always use exact version strings (e.g. `"0.1.0"`), not ranges.
- **Test with known-good and known-bad assets.** Validate against assets that should pass and assets that should fail to confirm the profile catches the right issues.
- **Cross-check dependencies.** If a feature has dependencies, those dependencies' requirements also execute — make sure they are appropriate for the profile's target runtime.

---

## Appendix: Profile resolution at runtime

When the validator processes an asset, the resolution works as follows:

1. **Read metadata.** The root layer's `customLayerData["SimReady_Metadata"]` is read to find `profile` and `profile_version`.
2. **Look up profile.** The profile name and version are matched against registered entries in `profiles.toml`.
3. **Resolve features.** Each feature entry is looked up by id and version in the registered feature set.
4. **Resolve dependencies.** If a feature declares dependencies, those are recursively resolved and their requirements are merged.
5. **Collect requirements.** The union of all requirements across all resolved features forms the complete validation set.
6. **Run rules.** Every registered rule that matches a requirement in the validation set executes against the USD stage.
7. **Report.** Results are aggregated per-requirement, per-feature, and for the profile as a whole.

## Appendix: Profile and feature relationship diagram

```text
Prop-Robotics-Neutral 1.0.0
├── FET000_CORE 0.1.0
│   ├── NP.002, NP.003, NP.004, NP.005, NP.006, NP.007, NP.008
│   ├── SR.001
│   └── HI.010
├── FET001_BASE_NEUTRAL 0.1.0
│   └── AA.001, AA.002, UN.001, UN.002
├── FET003_BASE_NEUTRAL 0.1.0
│   └── RB.COL.001, RB.COL.002, RB.COL.003, RB.COL.004, RB.001, ...
├── FET004_BASE_NEUTRAL 0.1.0
│   └── JT.001, JT.002, RB.MB.001
├── FET005_BASE_NEUTRAL 0.1.0
│   └── (grasp requirements)
└── FET006_BASE_MDL 0.1.0
    └── (material requirements)
```

Each requirement traces to a rule in `validation.py` inside the corresponding capability folder. Failures propagate upward: a failed requirement fails its feature, which fails the profile.

## Appendix: What consumers should expect

Not every profile in the repository is at the same maturity level. The [SimReady Acceptance Workflow](acceptance_workflow.md) describes the full lifecycle.

| Indicator | What it means |
| --- | --- |
| A profile lists the feature in `profiles.toml` with a pinned version. | The feature has completed the full acceptance workflow and is safe to validate against. |
| A feature JSON exists but is not yet referenced by any profile. | The feature is in late prototyping or testing. It may change before delivery. |
| A capability directory contains requirements but no `validation.py`. | The requirements are defined but validators are still in progress. |
| Sample assets exist in `sample_content/` for the domain. | Reference implementations are available; check the corresponding profile version to confirm they are up to date. |

When in doubt, check the feature version and the profile that references it. Pinned versions in a profile represent the accepted, stable contract.
