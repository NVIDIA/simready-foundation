# Features Documentation Guide

## About this guide

This guide will walk you through the process of understanding, creating, and managing features in the SimReady Foundation validation system. Features are collections of related requirements that define specific capabilities for USD assets.

## What is a Feature?

A **Feature** is a collection of related requirements that work together to provide a specific capability or functionality. Features are the building blocks of the SimReady validation system and are used to:

- Define what capabilities an asset must have
- Group related requirements logically
- Enable versioning and dependency management
- Support profile-based validation

### Feature Structure

Each feature consists of:

- **ID**: Unique identifier (e.g., `FET001_BASE_NEUTRAL`)
- **Version**: Semantic versioning (e.g., `1.0.0`)
- **Display Name**: Human-readable name (e.g., "Minimal Editor")
- **Path**: File path for documentation
- **Requirements**: List of requirement IDs that the feature depends on

### Example Feature Definition

```json
{
    "id": "FET001_BASE_NEUTRAL",
    "version": "1.0.0",
    "display_name": "Minimal Editor",
    "path": "features/FET_001-minimal_editor.html",
    "dependencies": [
        {
            "FET000_CORE": {
                "version": "0.1.0"
            }
        }
    ],
    "requirements": [
        "AA.001",
        "AA.002",
        "UN.001",
        "UN.002"
    ]
}
```

## Creating a New Feature

Follow these 6 steps to create a new feature:

### Step 1: Create Feature JSON and MD from Sample

Start by copying the sample files and customizing them for your new feature:

#### Sample Feature JSON (`FET_000_base_neutral-new_feature.json`)

```json
{
    "id": "FET000_NEW_FEATURE",
    "version": "0.1.0",
    "display_name": "example new feature",
    "path": "features/FET_000-new_feature.html",
    "dependencies": [
        {
            "FET001_BASE_NEUTRAL": {
                "version": "0.1.0"
            }
        }
    ],    
    "requirements": [
        "AA.001"
    ]
}
```

#### Sample Feature Markdown (`FET_000-new_feature.md`)

```markdown
# Feature: `ID:000 - Sample Feature Documentation`

## Description
This is a sample feature documentation that demonstrates the proper structure and format for documenting features in the validation system. This template should be used as a reference when creating new feature documentation.

## Overview

| **Property**            | **Value**                 |
|-------------------------|---------------------------|
| Proprietary Techs       | `Sample Tech`             |
| Dependency              | `None`                    |
| Profile                 | `Prop-Robotics-Neutral`   |

## Detailed Description

This sample feature showcases the standard format and structure that should be followed when documenting new features. It includes all the necessary sections and demonstrates proper markdown formatting.

## Neutral Format
### Version 1.0.0
<details>
<summary><strong>Details</strong></summary>

#### Requirements

* Capability: [Sample_Capability](../capabilities/sample/sample_capability.md)
  * Requirements:
    * [Sample-Requirement](../capabilities/sample/requirements/sample-requirement.md)
      * SPL.001 | Version 1.0.0

### Comments
* This is a sample comment section
* Add relevant notes, considerations, or future work items here
* Use bullet points for clarity

### Samples 

* Sample asset or reference material
* Additional examples as needed

## Testing Process

### Steps for Manual Testing
* Step 1: Sample testing procedure
* Step 2: Another testing step
* Step 3: Final validation step

### Automated Testing
* Unit tests for core functionality
* Integration tests for component interaction
* End-to-end validation tests

</details>

## Implementation Notes

This feature serves as a documentation template and should not be implemented in production systems. When creating actual feature documentation:

1. Replace sample content with real feature details
2. Update all references and links
3. Ensure proper versioning and dependency information
4. Include relevant technical specifications
5. Document testing procedures thoroughly

## Related Documentation

* [Feature Documentation Guide](../guides/feature_documentation.md)
* [Capability Documentation](../capabilities/README.md)
* [Testing Standards](../testing/standards.md)
```

### Step 2: Generate Feature ID and Version

#### Feature ID Convention

Feature IDs follow the pattern `FET<NNN>_<VARIANT>` where the variant
suffix encodes scope, domain, and compatibility tier. Common examples:

- `FET001_BASE_NEUTRAL` — core OpenUSD only
- `FET003_BASE_PHYSX` — uses PhysxSchema extensions
- `FET021_ROBOT_CORE_ISAAC` — robot core using IsaacSim schemas
- `FET022_DRIVEN_JOINTS_PHYSX` — driven joints using PhysX

The authoritative list of valid variant suffixes is the set of `"id"`
values in the feature JSON files under `features/`.

#### Versioning Strategy

Use semantic versioning:
- **Major.Minor.Patch** (e.g., `1.0.0`)
- **Major**: Breaking changes
- **Minor**: New functionality (backward compatible)
- **Patch**: Bug fixes (backward compatible)

### Step 3: Add Requirements

Identify and list all requirements your feature depends on:

1. **Browse existing capabilities** in `nv_core/sr_specs/docs/capabilities/`
2. **Select relevant requirements** from each capability
3. **List requirement IDs** in the JSON file
4. **Document requirement details** in the markdown file

#### Example Requirements Section

```markdown
#### Requirements 
* Capability: [Core/Atomic_Asset](../capabilities/core/atomic_asset/capability-atomic_asset.md)
    * Requirements
        * [Anchored-Asset-Paths](../capabilities/core/atomic_asset/requirements/anchored-asset-paths.md)
            * AA.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/atomic_asset/validation.py)
        * [Supported-File-Types](../capabilities/core/atomic_asset/requirements/supported-file-types.md)
            * AA.002 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/atomic_asset/validation.py)
```

### Step 4: Place into Feature Folder

Place your feature files in:
```
simready_foundation/nv_core/sr_specs/docs/features/
```

**File naming convention:**
- JSON: `FET_###_base_[tech]-[version]-[description].json`
- Markdown: `FET_###-[description].md`

**Examples:**
- `FET_001_base_neutral-1.0.0-minimal.json`
- `FET_001-minimal.md`

### Step 5: Add New Feature to Features Index

Update `nv_core/sr_specs/docs/features/features.md`:

```markdown
# Features

```{toctree}
:maxdepth: 1

ID:001 - Minimal - Base <FET_001-minimal>
ID:002 - Posable Bodies - Base <FET_002-posable_bodies>
ID:003 - RBD Physics - Base <FET_003-rigid_body_physics>
ID:004 - Simulate Multi-Body Physics - Base <FET_004-simulate_multi_body_physics>
ID:005 - Simulate Grasp Physics - Base <FET_005-simulate_grasp_physics>
ID:000 - Sample Feature - Base <FET_000-new_feature>
```

### Step 6: Use in a Profile

Features are used in profiles to define what capabilities an asset must have. Here's an example profile:

```toml
[Prop-Robotics-Physx]
"1.0.0" = {features = [
    {"FET001_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Minimal"
    {"FET003_BASE_PHYSX" = {version = "0.1.0"}}, # "RBD Physics"
    {"FET004_BASE_PHYSX" = {version = "0.1.0"}}, # "Simulate Multi-Body Physics and SDF collision approximation"
    {"FET005_BASE_NEUTRAL" = {version = "0.1.0"}}, # "Simulate Grasp Physics"

    {"FET000_NEW_FEATURE" = {version = "0.1.0"}}, # "New Feature"
]}
```

### Expanding a feature

**Expanding a feature** means adding a technology-specific requirement that *replaces* a base (e.g. neutral) requirement when the technology supports an exception or extension that the base requirement does not allow. The base and expanded requirements are mutually exclusive for the same feature: a single feature uses one or the other, depending on the profile.

#### When to expand

Use an expansion when:

- A technology (e.g. PhysX) supports a valid pattern that the base spec forbids or does not define.
- Enforcing the base requirement would incorrectly fail assets that use that pattern.
- The two rules cannot both apply: satisfying the expanded rule can violate the base rule, so they must not coexist in the same requirement set.

#### Example: PHYSX.COL.001 and RB.COL.001

- **RB.COL.001** (base / neutral): Every shape (UsdGeom Gprim) must have a collider; CollisionAPI cannot be applied to Xforms. This matches the basic USD/UsdPhysics model where merged mesh is not available.
- **PHYSX.COL.001** (expansion): Same idea—colliders must be well-defined—but adds an exception: a shape does *not* need its own collider if it is covered by a **merged mesh collider**. In PhysX, an Xform with **PhysxMeshMergeCollisionAPI** acts as an umbrella collider for all sibling geometry (at any depth) via its collisionmeshes collection. So both “per-shape collider” and “merged mesh collider” are valid under PHYSX.COL.001.

Assets using a merged mesh collider would fail RB.COL.001 (no per-shape collider). So the two requirements cannot both be in the same feature: the neutral RBD feature uses RB.COL.001; the PhysX RBD feature uses PHYSX.COL.001 (and related PHYSX collider requirements) instead.

#### How to implement an expansion

1. **Add the new requirement**  
   Create the capability and requirement documentation (e.g. `physx-collider-capability.md` for PHYSX.COL.001) that states the expanded rule and its exceptions.

2. **Define the tech-specific feature requirement list**  
   In the technology-specific feature (e.g. `FET003_BASE_PHYSX`), start from the base feature’s full requirement list. Then:
   - **Remove** the base requirement(s) being replaced (e.g. RB.COL.001, and if applicable RB.COL.002).
   - **Add** the new requirement(s) (e.g. PHYSX.COL.001, PHYSX.COL.002).

   The tech feature then carries an explicit, full list of requirements; it does not depend on the base feature for those requirements so that the expanded rule replaces the base rule rather than adding to it.

3. **Wire profiles**  
   Profiles choose which feature (and thus which requirement) applies:
   - **Neutral profile** (e.g. Prop-Robotics-Neutral): uses the base feature (e.g. `FET003_BASE_NEUTRAL`) and therefore RB.COL.001.
   - **PhysX profile** (e.g. Prop-Robotics-Physx): uses the tech feature (e.g. `FET003_BASE_PHYSX`) and therefore PHYSX.COL.001.

**Concrete example:** `FET_003_base_neutral-0.1.0-rigid_body_physics.json` includes `RB.COL.001` in its requirements. `FET_003_base_physx-0.2.0-rigid_body_physics.json` lists all other rigid-body requirements from the base feature but omits `RB.COL.001` (and RB.COL.002) and adds `PHYSX.COL.001` and `PHYSX.COL.002` so that both per-shape and merged-mesh colliders are valid under the PhysX spec.


## Feature Dependencies

### What are Dependencies?

**Dependencies** are references to other features that your feature requires. When specified, the validation system will:

1. **Automatically include** all requirements from dependent features
2. **Recursively resolve** nested dependencies (features that depend on other features)
3. **Validate against** the complete set of requirements from all dependencies
4. **Ensure consistency** across related feature sets

### Dependency Structure

Dependencies are defined in the JSON file as an array of objects:

```json
"dependencies": [
    {
        "FET001_BASE_NEUTRAL": {
            "version": "0.1.0"
        }
    },
    {
        "FET_003_BASE_PHYSX": {
            "version": "0.1.0"
        }
    }
]
```

**Format:**
- **Feature ID**: The ID of the dependent feature (e.g., `FET_001`)
- **Version**: Specific version requirement (e.g., `"0.1.0"`)
- **Multiple Dependencies**: Can specify multiple features in the array

### How Dependencies Work

#### Automatic Requirement Resolution

When a feature has dependencies, the validation system automatically:

1. **Loads all requirements** from the specified dependent features
2. **Combines requirements** with the feature's own requirements
3. **Creates a complete validation set** for the asset
4. **Ensures no conflicts** between feature requirements

#### Example: Dependency Chain

```json
// Feature A depends on Feature B
{
    "id": "FET_A",
    "dependencies": [
        {
            "FET_B": {"version": "0.1.0"}
        }
    ],
    "requirements": ["REQ_A.001"]
}

// Feature B depends on Feature C
{
    "id": "FET_B", 
    "dependencies": [
        {
            "FET_C": {"version": "0.1.0"}
        }
    ],
    "requirements": ["REQ_B.001"]
}

// Feature C has no dependencies
{
    "id": "FET_C",
    "requirements": ["REQ_C.001", "REQ_C.002"]
}
```

**Result:** When validating `FET_A`, the system will validate against:
- `REQ_A.001` (from FET_A)
- `REQ_B.001` (from FET_B dependency)
- `REQ_C.001`, `REQ_C.002` (from FET_C dependency of FET_B)

#### Version Compatibility

Dependencies specify exact version requirements to ensure compatibility:

```json
"dependencies": [
    {
        "FET001_BASE_NEUTRAL": {
            "version": "0.1.0"
        }
    },
    {
        "FET003_BASE_PHYSX": {
            "version": "0.1.0"
        }
    }
]
```

Version values must be exact semantic versions (e.g. `"0.1.0"`) matching
an existing feature JSON file's `"version"` field.

### Benefits of Using Dependencies

#### 1. **Code Reuse**
- Avoid duplicating requirements across features
- Build complex features from simpler building blocks
- Maintain consistency across related feature sets

#### 2. **Automatic Validation**
- No need to manually track dependent requirements
- System automatically validates against all dependencies
- Reduces human error in requirement specification

#### 3. **Maintainability**
- Update requirements in one place (the base feature)
- Changes automatically propagate to dependent features
- Easier to manage complex requirement relationships

#### 4. **Clear Relationships**
- Document how features relate to each other
- Make feature hierarchies explicit and traceable
- Help developers understand feature dependencies

### Best Practices for Dependencies

#### 1. **Keep Dependencies Minimal**
```json
// Good: Only depend on what you actually need
"dependencies": [
    {
        "FET001_BASE_NEUTRAL": {"version": "0.1.0"}  // Core minimal requirements
    }
]

// Avoid: Don't depend on features you don't actually use
"dependencies": [
    {
        "FET001_BASE_NEUTRAL": {"version": "0.1.0"},
        "FET002_BASE_NEUTRAL": {"version": "0.1.0"},  // Unused dependency
        "FET003_BASE_NEUTRAL": {"version": "0.1.0"}   // Unused dependency
    }
]
```

#### 2. **Use Specific Versions**
```json
// Good: Specify exact versions for stability
"dependencies": [
    {
        "FET001_BASE_NEUTRAL": {"version": "0.1.0"}
    }
]

// Avoid: Using version ranges that could cause instability
"dependencies": [
    {
        "FET001_BASE_NEUTRAL": {"version": ">=0.1.0"}  // Could break with future changes
    }
]
```

#### 3. **Document Dependency Purpose**
```json
// Good: Add comments explaining why dependencies are needed
"dependencies": [
    {
        "FET001_BASE_NEUTRAL": {"version": "0.1.0"}  // Provides core asset validation
    },
    {
        "FET_003_BASE_PHYSX": {"version": "0.1.0"}  // Provides physics requirements
    }
]
```

#### 4. **Avoid Circular Dependencies**
```json
// BAD: This creates a circular dependency that will cause errors
// Feature A depends on Feature B
"dependencies": [
    {
        "FET_B": {"version": "0.1.0"}
    }
]

// Feature B depends on Feature A (circular!)
"dependencies": [
    {
        "FET_A": {"version": "0.1.0"}
    }
]
```

### Dependency Validation

The system automatically validates dependencies to ensure:

1. **All dependent features exist** in the system
2. **Specified versions are available** and compatible
3. **No circular dependencies** are created
4. **Requirements can be resolved** without conflicts

#### Validation Errors

Common dependency validation errors:

```json
// Error: Feature doesn't exist
"dependencies": [
    {
        "NONEXISTENT_FEATURE": {"version": "0.1.0"}
    }
]

// Error: Version doesn't exist
"dependencies": [
    {
        "FET001_BASE_NEUTRAL": {"version": "99.99.99"}
    }
]

// Error: Circular dependency detected
"dependencies": [
    {
        "FET001_BASE_NEUTRAL": {"version": "0.1.0"}  // Creates circular reference
    }
]
```

### Example: Complete Feature with Dependencies

```json
{
    "id": "FET004_BASE_PHYSX",
    "version": "0.1.0",
    "display_name": "Simulate Multi-Body Physics",
    "path": "features/FET_004-simulate_multi_body_physics.html",
    "dependencies": [
        {
            "FET003_BASE_PHYSX": {
                "version": "0.1.0"
            }
        }
    ],
    "requirements": [
        "JT.001",
        "JT.002",
        "RB.MB.001"
    ]
}
```

**What this means:**
- `FET004_BASE_PHYSX` automatically includes all requirements from:
  - `FET003_BASE_PHYSX` (rigid body physics requirements)
- Plus its own specific requirements: `JT.001`, `JT.002`, `RB.MB.001`
- Total validation set: All requirements from both features

## Feature Documentation Best Practices

### Content Structure

1. **Clear Description**: Explain what the feature does and why it's needed
2. **Requirements Mapping**: Clearly link to all required capabilities and requirements
3. **Version History**: Document changes between versions
4. **Testing Procedures**: Include both manual and automated testing steps
5. **Examples**: Provide sample assets and use cases

### Markdown Formatting

- Use consistent heading levels
- Include proper links to related documentation
- Use tables for structured information
- Include code blocks for examples
- Use admonitions for important notes

### Validation Integration

- Link to validation rules and implementations
- Include testing procedures
- Document expected outcomes
- Provide troubleshooting guidance

## Testing Your Feature

### Manual Testing

1. **Create test assets** that should pass validation
2. **Create test assets** that should fail validation
3. **Verify requirement coverage** is complete
4. **Test in different contexts** (various asset types)

### Automated Testing

1. **Unit tests** for individual requirements
2. **Integration tests** for feature combinations
3. **End-to-end validation** with real assets
4. **Performance testing** for large assets

## Common Pitfalls

### Avoid These Mistakes

1. **Missing Requirements**: Ensure all dependencies are listed
2. **Incorrect Versioning**: Use semantic versioning consistently
3. **Poor Documentation**: Write clear, comprehensive descriptions
4. **Missing Tests**: Include both manual and automated testing
5. **Broken Links**: Verify all internal links work correctly

### Best Practices

1. **Start Simple**: Begin with minimal requirements and expand
2. **Document Everything**: Include examples, tests, and troubleshooting
3. **Version Control**: Track changes between versions
4. **Peer Review**: Have others review your feature documentation
5. **Regular Updates**: Keep documentation current with implementation


## Getting Help

If you need assistance creating or modifying features:

1. **Review existing features** for examples
2. **Check the capabilities directory** for available requirements
3. **Consult the testing framework** for validation procedures
4. **Ask the development team** for guidance on complex features


## Summary

This guide covers the essentials for understanding and creating features in the SimReady Foundation system, including feature JSON and markdown structure, dependency management, variant naming conventions, and testing procedures.
