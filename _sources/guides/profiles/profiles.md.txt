# Profiles Documentation Guide

## About this guide

This guide will walk you through the process of understanding, creating, and managing profiles in the SimReady Foundation system. Profiles are collections of features that define the capabilities and requirements for assets, enabling consistent asset transformation and validation across different simulation environments.

## What is a Profile?

A **Profile** is a named collection of features that defines the complete set of capabilities and requirements for an asset. Profiles serve as blueprints that specify exactly what features an asset must have to be considered compliant with a particular simulation environment or use case.

### Key Components

- **Profile Name (ID)**: Unique identifier for the profile (e.g., `Prop-Robotics-Neutral`)
- **Version**: Specific version of the profile (e.g., `"1.0.0"`, `"2.0.0"`)
- **Feature Requirements**: List of required features with their specific versions
- **Version Locking**: Profile versions are immutable - changes require creating a new version

### Profile Structure

Each profile consists of:

```toml
[Profile-Name]
"version" = {features = [
    {"FEATURE_ID" = {version = "feature_version"}},
    {"FEATURE_ID" = {version = "feature_version"}},
    # ... more features
]}
```

### How Profiles Work

1. **Asset Classification**: Assets are tagged with a specific profile and version
2. **Feature Validation**: Assets are validated against all required features in the profile
3. **Transformation Path**: Feature adapters enable transformation between different profiles
4. **Environment Compatibility**: Profiles ensure assets work correctly in specific simulation environments

## Profile Examples

### Example 1: Prop-Robotics-Neutral Profile

```toml
[Prop-Robotics-Neutral]
"1.0.0" = {features = [
    {"FET000_CORE" = {version = "0.1.0"}}, # "Core"
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Minimal"
    {"FET003_BASE_NEUTRAL" = {version = "0.1.0"}}, # "RBD Physics"
    {"FET004_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Simulate Multi-Body Physics"
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Simulate Grasp Physics"
    {"FET006_BASE_MDL" = {version = "0.1.0"}}, # "Materials (MDL)"
]}
"2.0.0" = {features = [
    {"FET000_CORE" = {version = "0.1.0"}}, # "Core"
    {"FET001_BASE_NEUTRAL" = {version = "1.0.0"}}, # "Minimal"
    {"FET003_BASE_NEUTRAL" = {version = "0.1.0"}}, # "RBD Physics"
    {"FET004_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Simulate Multi-Body Physics"
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Simulate Grasp Physics"
    {"FET006_BASE_MDL" = {version = "0.1.0"}}, # "Materials (MDL)"
]}
```

### Example 2: Prop-Robotics-Physx Profile

```toml
[Prop-Robotics-Physx]
"1.0.0" = {features = [
    {"FET000_CORE" = {version = "0.1.0"}}, # "Core"
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Minimal"
    {"FET003_BASE_PHYSX" = {version = "0.1.0"}}, # "RBD Physics"
    {"FET004_BASE_PHYSX" = {version = "0.1.0"}}, # "Simulate Multi-Body Physics and SDF collision approximation"
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Simulate Grasp Physics"
    {"FET006_BASE_MDL" = {version = "0.1.0"}}, # "Materials (MDL)"
]}
"2.0.0" = {features = [
    {"FET000_CORE" = {version = "0.1.0"}}, # "Core"
    {"FET001_BASE_NEUTRAL" = {version = "1.0.0"}}, # "Minimal"
    {"FET003_BASE_PHYSX" = {version = "0.1.0"}}, # "RBD Physics"
    {"FET004_BASE_PHYSX" = {version = "0.1.0"}}, # "Simulate Multi-Body Physics and SDF collision approximation"
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Simulate Grasp Physics"
    {"FET006_BASE_MDL" = {version = "0.1.0"}}, # "Materials (MDL)"
]}
```

## Creating a New Profile

### Step 1: Define Profile Requirements

Before creating a profile, you need to understand:

1. **Target Environment**: What simulation and or render environment will use this profile
2. **Required Capabilities**: What features need to be accounted for
3. **Feature Dependencies**: Which features are required vs. optional (see the [feature dependency graph](../../features/feature-dependency-graph) and [Asset Profiles](../../profiles/profiles) comparison table)
4. **Version Compatibility**: What versions of features are needed

### Step 2: Choose a Profile Name

**Naming Conventions:**
- Use descriptive names that indicate the target environment
- Use hyphens and title case for multi-word names
- Include the primary use case or environment
- Examples: `Prop-Robotics-Neutral`, `Prop-Robotics-Physx`, `Vehicle-Simulation`

### Step 3: Create the Profile Configuration

Create a new profile entry in the `profiles.toml` file:

```toml
[Your-Profile-Name]
"1.0.0" = {features = [
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Minimal"
    {"FET003_BASE_NEUTRAL" = {version = "0.1.0"}}, # "RBD Physics"
    {"FET004_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Simulate Multi-Body Physics"
    # Add more features as needed
]}
```

### Step 4: Validate Feature Availability

Ensure all referenced feature IDs and versions exist as JSON files under
`nv_core/sr_specs/docs/features/`. Each feature variant+version has a
corresponding file (e.g. `FET_003_base_physx-0.1.0-rigid_body_physics.json`).
The `"id"` and `"version"` fields in the JSON must match what the profile
references.

### Step 5: Test Profile Creation

Create a test asset and validate it against the new profile, see "SimReady - Feature Docs":

```bash 
workspace validate <path to usd asset>
```

### Step 6: Create documentation

In `nv_core/sr_specs/docs/profiles/` each profile should have its own markdown file, that should also be referred to in `profiles.md`.

## Creating a New Profile Version

### When to Create a New Version

Create a new profile version when:
- **Feature Updates**: Required feature(s) have a new version
- **New Requirements**: Additional features are needed
- **Breaking Changes**: Existing features have incompatible changes
- **Environment Changes**: Target simulation environment requirements change

### Step 1: Plan the Version Update

**Version Numbering:**
- **Major Version** (X.0.0): Breaking changes, new features, incompatible updates
- **Minor Version** (0.X.0): New features, backward compatible
- **Patch Version** (0.0.X): Bug fixes, minor updates

### Step 2: Update Feature Versions

Identify which features need version updates:

```toml
[Prop-Robotics-Neutral]
"1.0.0" = {features = [
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Minimal"
    {"FET003_BASE_NEUTRAL" = {version = "0.1.0"}}, # "RBD Physics"
    {"FET004_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Simulate Multi-Body Physics"
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Simulate Grasp Physics"
]}
"2.0.0" = {features = [
    {"FET001_BASE_NEUTRAL" = {version = "1.0.0"}}, # "Minimal" - UPDATED
    {"FET003_BASE_NEUTRAL" = {version = "0.1.0"}}, # "RBD Physics" - SAME
    {"FET004_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Simulate Multi-Body Physics" - SAME
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Simulate Grasp Physics" - SAME
]}
```

### Step 3: Add New Version to Profile

```toml
[Your-Profile-Name]
"1.0.0" = {features = [
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}},
    {"FET002_MATERIAL_BASIC" = {version = "0.1.0"}},
]}
"2.0.0" = {features = [
    {"FET001_BASE_NEUTRAL" = {version = "1.0.0"}}, # Updated feature version
    {"FET002_MATERIAL_BASIC" = {version = "0.1.0"}},
    {"FET100_ANIMATION_BASIC" = {version = "0.1.0"}}, # New feature added
]}
```

### Step 4: Document Version Changes

Create a changelog entry:

```markdown
## Profile Version 2.0.0

### Changes
- Updated FET001_BASE_NEUTRAL from version 0.1.0 to 1.0.0
- Added FET100_ANIMATION_BASIC version 0.1.0
- Improved asset validation for animation properties

### Migration Notes
- Existing assets using version 1.0.0 will need feature adapter transformation
- New animation features require additional asset properties
```

### Step 5: Upgrade assets

Its possible to "upgrade" assets that support a particular profile version to a new version, one way to achieve this is run "workspace upgrade" after creating the appropriate feature adapters, see the next section

## Creating a Second Profile and Required Adapters

### Step 1: Identify Profile Differences

When creating a second profile, identify the differences from existing profiles:

**Example: Prop-Robotics-Neutral vs Prop-Robotics-Physx**

| Feature | Neutral Version | Physx Version | Difference |
|---------|----------------|---------------|------------|
| FET001_BASE_NEUTRAL | 0.1.0 | 0.1.0 | Same |
| FET003_BASE_NEUTRAL | 0.1.0 | - | Neutral physics |
| FET003_BASE_PHYSX | - | 0.1.0 | PhysX physics |
| FET004_BASE_NEUTRAL | 0.1.0 | - | Neutral multi-body |
| FET004_BASE_PHYSX | - | 0.1.0 | PhysX multi-body |
| FET005_BASE_NEUTRAL | 0.1.0 | 0.1.0 | Same |

### Step 2: Plan Required Feature Adapters

Based on the differences, identify required adapters:

**Required Adapters:**
1. `FET003_BASE_NEUTRAL` → `FET003_BASE_PHYSX`
2. `FET004_BASE_NEUTRAL` → `FET004_BASE_PHYSX`


### Step 4: Implement Missing Adapters

If adapters don't exist, please refer to <feature_adapters>

### Step 5: Test Profile Transformation

please refer to "SimReady - Feature Docs" "Feature: Convert" to learn how to convert assets:

```bash
workspace upgrade --output_uri [output asset file path]
--output_profile [profile name] <optional>--output_profile_version [version number]
```

## Best Practices

### 1. **Profile Design**

- **Keep profiles focused** on specific use cases or environments
- **Use descriptive names** that clearly indicate the target environment
- **Minimize feature overlap** between similar profiles
- **Document profile purposes** and use cases

### 2. **Version Management**

- **Never modify existing versions** - always create new versions
- **Use semantic versioning** (major.minor.patch)
- **Document all changes** in version changelogs
- **Maintain backward compatibility** when possible

### 3. **Feature Selection**

- **Include only necessary features** to avoid bloat
- **Consider feature dependencies** and requirements
- **Test feature combinations** for compatibility
- **Validate against real-world use cases**

### 4. **Testing and Validation**

- **Create comprehensive test assets** for each profile version
- **Test all transformation paths** between profiles
- **Validate against real simulation environments**
- **Automate validation** in CI/CD pipelines

## Getting Help

If you need assistance creating or managing profiles:

1. **Review existing profiles** for examples and patterns
2. **Check feature documentation** for available features and versions
3. **Test with simple profiles** before complex ones
4. **Use validation tools** to verify profile correctness
5. **Ask the development team** for guidance on complex profile designs

## Conclusion

This comprehensive guide provides everything needed to understand and manage profiles in the SimReady Foundation system. Profiles are essential for ensuring asset compatibility across different simulation environments, and proper profile management is crucial for maintaining a robust and flexible asset pipeline.

By following the guidelines in this document, you can create effective profiles that meet your simulation requirements while maintaining compatibility and enabling smooth asset transformations between different environments.
