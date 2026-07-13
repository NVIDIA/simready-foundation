# Attribute Naming Conventions

## Purpose

SimReady Foundation builds on OpenUSD to define simulation-ready asset
requirements. When contributors add new capabilities, schemas, or custom
attributes to this repo, every property and attribute name must follow
consistent namespacing rules so that:

- Users and tools can immediately tell which vendor, tier, or package
  introduced a property.
- Names from different vendors or teams never collide.
- Unknown or vendor-specific properties degrade gracefully in tools that do
  not recognise them.

This guide codifies the attribute- and property-level naming rules that all
SimReady Foundation contributors must follow.

Schema *type* naming — requiring a recognisable prefix on IsA schemas and an
`*API` suffix on applied API schemas — is related but out of scope here. A
future document will cover those conventions.

## What is a well-formed vendor prefix?

A **vendor prefix** is a colon-delimited namespace that appears at the start
of every property or attribute name introduced by a vendor, tier, or package.
It tells anyone reading the USD file *who owns this name*.

### Pattern

A well-formed prefix consists of one or more **tokens** separated by colons.
Each token follows the pattern `[a-z][a-zA-Z0-9]*` (camelCase, starting with
a lowercase letter). The full prefix always ends with a colon:

```
vendorToken:
vendorToken:submodule:
vendorToken:submodule:group:
```

- The **outermost token** identifies the vendor, organisation, or umbrella
  ecosystem (e.g. `omni`, `physx`, `acmeCable`).
- **Inner tokens** identify a tier, submodule, or semantic grouping (e.g.
  `simready`, `nonvisual`, `flex`).

### Examples

| Prefix | Owner |
| --- | --- |
| `simready:` | SimReady Foundation core tier |
| `physx:` | PhysX tier |
| `isaac:` | Isaac Sim tier |
| `acmeCable:` | Hypothetical third-party vendor |
| `acmeCable:flex:` | Submodule within that vendor |

> **Note on legacy `omni:simready:` attributes.** Existing material
> attributes in this repo (notably under the non-visual material docs)
> currently use the `omni:simready:*` form. These predate this guidance
> and will be migrated to `simready:*` in a future pass; new
> SimReady-authored attributes should use `simready:` as the outermost
> token from the start.

## Rules

The four rules below cover the property- and attribute-naming aspects of
USD schema hygiene. Each rule states **what to do**, shows **valid and
invalid USD**, and explains **how to comply**.

### Severity levels

- **MUST** — an absolute requirement; violating it is a spec error.
- **SHOULD** — a strong recommendation; deviations require documented
  justification.

### Rule 1 — Applied API schema properties (MUST)

Every property name introduced by an **applied API schema** must start with
a recognisable namespace prefix.

- For **SimReady core** schemas the prefix is
  `simready:<submodule>:`.
- For **other tiers or vendors** the prefix is their own vendor token (e.g.
  `physx:jointMaxForce`, `acmeCable:flex:stiffness`).
- The mechanism for getting the prefix on the property name differs between
  **single-apply** and **multi-apply** schemas — see *How to comply* below.

#### Valid (single-apply)

```usd
# Single-apply applied API — properties carry the acmeCable:flex: prefix.
over "Cable" (
    prepend apiSchemas = ["AcmeCableFlexAPI"]
)
{
    float acmeCable:flex:stiffness = 0.85
    float acmeCable:flex:dampingRatio = 0.3
}
```

#### Valid (multi-apply)

```usd
# Multi-apply API schema — instance name "front" is interpolated between
# the schema's propertyNamespacePrefix and each property name, producing
# the final attribute names shown.
over "Wheel" (
    prepend apiSchemas = ["AcmeBrakeAPI:front"]
)
{
    float acmeBrake:front:torque = 250.0
    float acmeBrake:front:padWear = 0.12
}
```

#### Invalid

```usd
# BAD: no namespace prefix — impossible to tell who owns these properties.
over "Sensor" (
    prepend apiSchemas = ["SimReadyNonvisualAPI"]
)
{
    token sensorType = "lidar"
    float updateRate = 10.0
}
```

#### How to comply

The mechanism depends on whether the schema is single-apply or multi-apply.

- **Single-apply API schemas.** OpenUSD's `usdGenSchema` does **not**
  auto-prefix properties on single-apply schemas — `propertyNamespacePrefix`
  is rejected as a `customData` field on anything other than a multi-apply
  schema. You must spell out the full prefixed name on each property in the
  schema's `schema.usda`. For SimReady core, that means
  `simready:<submodule>:<propName>` directly in the schema definition.
- **Multi-apply API schemas.** Set
  `customData = { token propertyNamespacePrefix = "simready:<submodule>" }`
  (or your vendor prefix) on the schema, and list properties **without** any
  prefix. At runtime the final attribute name is composed as
  `<propertyNamespacePrefix>:<instanceName>:<propertyName>` —
  `usdGenSchema.py` does this via `MakeMultipleApplyNameTemplate(prefix,
  propName)`.

If schema generation fails with *"propertyNamespacePrefix should only be
used as a customData field on multiple-apply API schemas"*, the schema is
single-apply and the property names need to be spelled out manually.

### Rule 2 — Custom properties on standard USD types (MUST)

Any **custom property** added to a **standard USD prim type** (`UsdGeom`,
`UsdLux`, `UsdShade`, `UsdPhysics`, `UsdMedia`, `UsdVol`, `UsdSkel`,
`UsdUI`, `UsdRender`) must use a vendor namespace prefix.

- SimReady core: `simready:<submodule>:<propName>`.
- **Exception:** properties that are scoped by a fully custom IsA container
  schema (e.g. the prim type itself is vendor-defined) may omit the prefix
  because the schema already makes ownership clear.

#### Valid

```usd
# Adding a custom property to a standard UsdGeomMesh prim
def Mesh "Cable"
{
    # Standard USD property — no prefix needed
    float3[] extent = [(-1, -1, 0), (1, 1, 10)]

    # Custom vendor property — MUST have prefix
    custom float acmeCable:flex:bendRadius = 0.05
}
```

#### Invalid

```usd
def Mesh "Cable"
{
    float3[] extent = [(-1, -1, 0), (1, 1, 10)]

    # BAD: custom property on a standard type without a vendor prefix
    custom float bendRadius = 0.05
}
```

#### How to comply

Before adding a property to a standard USD prim type, check whether the
property is defined by the prim's schema or by any applied API schema. If
not, prefix it with `simready:<submodule>:` (or your vendor prefix).

### Rule 3 — Unschema'd custom attributes (MUST)

Any **custom attribute** that is **not part of any schema** must start with a
namespace prefix. The prefix rules from Rule 1 apply.

This is the most common source of naming collisions: ad-hoc attributes added
during pipeline development that lack any namespace. Even if the attribute
seems unique today, another team or vendor may introduce the same name
tomorrow.

#### Valid

```usd
def Xform "ConveyorBelt"
{
    # Well-formed: vendor prefix + semantic grouping
    float acmeCable:flex:stiffness = 0.85
    float acmeCable:flex:dampingRatio = 0.3
}
```

#### Invalid

```usd
def Xform "ConveyorBelt"
{
    # BAD: no prefix — who owns "rig_blob"? what are the four floats?
    custom float4[] rig_blob = [(1, 0, 0, 1)]
}
```

#### How to comply

Replace any unstructured, un-prefixed attribute with properly namespaced
attributes (see the *Example: from unstructured to well-formed* section
below).

### Rule 4 — IsA schema properties inheriting standard USD (SHOULD)

If an **IsA schema** inherits from a **standard USD base** (e.g.
`UsdGeomGprim`), its own properties **should** use namespace prefixes to
distinguish them from the base class properties.

If the IsA schema is fully custom (does not inherit from a standard USD
type), namespacing **may** be omitted because the prim type already makes
ownership clear.

#### Valid

```usd
# AcmeCableHarness is a hypothetical IsA schema that inherits from
# UsdGeomXformable. The vendor prefix on its own properties keeps them
# distinguishable from the inherited xformOp:* properties.
def AcmeCableHarness "MainPower"
{
    # Inherited from Xformable — no prefix needed
    token xformOp:translate = (0, 0, 0)

    # Vendor properties — namespaced to avoid confusion
    asset acmeCable:routingPath = @./harness_path.usda@
    token acmeCable:wireGauge = "AWG-12"
}
```

#### When you may omit the prefix

```usd
# AcmePartManifest is a hypothetical fully custom IsA schema — it
# inherits only from UsdTyped, not from a standard typed base like
# UsdGeomXformable, so its properties are already scoped by the prim
# type name and the prefix may be omitted.
def AcmePartManifest "EngineParts"
{
    string[] partIds = ["pn-001", "pn-002", "pn-003"]
    float[] partWeights = [1.5, 2.3, 0.8]
}
```

## Example: from unstructured to well-formed

The following hypothetical example shows why these rules matter. A pipeline
team at the fictional vendor *AcmeCable* has created a custom
cable-simulation attribute on a prim. Over time the attribute evolves from
an unstructured convention to a well-formed one.

### Before — poorly formed

```usd
def Xform "CableAssembly"
{
    # Single opaque attribute — no namespace, no semantic meaning,
    # no way to tell which vendor or tool created it.
    custom float4[] rig_blob = [(0.85, 0.3, 100.0, 0.01)]
}
```

**Problems:**

- `rig_blob` has no vendor prefix — it could collide with any other team's
  attribute of the same name.
- The `float4[]` packs unrelated values into one opaque array — consumers
  must guess which float means what.
- No schema defines the attribute, so tools cannot validate or document it.

### After — well formed

```usd
def Xform "CableAssembly" (
    prepend apiSchemas = ["AcmeCableFlexAPI"]
)
{
    # Each property is individually named, typed, and vendor-prefixed.
    float acmeCable:flex:stiffness = 0.85
    float acmeCable:flex:dampingRatio = 0.3
    float acmeCable:flex:segmentCount = 100
    float acmeCable:flex:thickness = 0.01
}
```

**Improvements:**

- `acmeCable:flex:` prefix immediately identifies the owning vendor and
  submodule.
- Each property has its own meaningful name and type.
- The applied API schema (`AcmeCableFlexAPI`) documents the property set;
  tools can validate it automatically.

## Naming across tiers and packages

SimReady Foundation validation rules are delivered as separate Python wheels
grouped by their dependency footprint. Each tier owns a namespace for its
rules and introduces USD-attribute prefixes for the schemas it defines:

| Tier | Wheel | Rule namespace | USD-attribute prefix |
| --- | --- | --- | --- |
| USD | `nvidia-usd-validators` | `com.nvidia.usd` | (upstream standard — no prefix) |
| Core | `simready-foundation-core` | `com.nvidia.simready` | `simready:` |
| PhysX | `simready-foundation-physx` | `com.nvidia.simready` (PhysX rules) | `physx:` |
| Newton (planned) | `simready-foundation-newton` | TBD | TBD |
| Isaac Sim (planned) | `isaacsim-foundation.core` | TBD | `isaac:` |

### Key principles

1. **Attribute prefix aligns with the tier that introduces the schema.**
   A schema added by the PhysX tier uses `physx:` prefixes, not
   `simready:`. A schema added by SimReady core uses `simready:`.

2. **Rule-ID namespacing and USD-attribute namespacing are independent.**
   A rule identifier like `com.nvidia.simready.NP.001` names a *rule* in
   the validation system. A USD attribute like
   `simready:<submodule>:<propName>` names a *property* inside an asset.
   Both use the `simready` token but serve different purposes.

3. **Harmonization for downstream packages.**
   Downstream or partner packages (e.g. `isaacsim-foundation.core`,
   `siemens-core`) should follow the same naming patterns documented here,
   substituting their own vendor prefix. A harmonised package does not need
   to depend on SimReady Foundation core, but if its rules, features, and
   profiles follow the same conventions, contributions can be merged back
   into core with minimal friction.

## Capabilities folder layout

When adding a new capability or requirement to the specs, files must be
placed in the correct location under `nv_core/sr_specs/docs/capabilities/`.
The folder structure mirrors the layered hierarchy described above.

### Directory structure

```text
capabilities/
├── _includes/                         # Shared Sphinx snippets (badges, etc.)
│   └── badges/
├── <group>/                           # snake_case group folder
│   ├── <group>.md                     # Group landing page
│   ├── <capability>/                  # snake_case capability folder
│   │   ├── capability-<slug>.md       # Capability overview page
│   │   ├── requirements.md            # Index: {requirements-table} + {toctree}
│   │   ├── requirements/              # One .md per requirement
│   │   │   ├── <kebab-case-slug>.md
│   │   │   └── ...
│   │   └── validation.py              # Validator classes for the capability
│   └── ...
└── capabilities.md                    # Top-level Sphinx entrypoint
```

### Existing groups

| Group folder | Area |
| --- | --- |
| `core/` | Cross-cutting building blocks (atomic asset, naming/paths, units, sim-ready readiness) |
| `visualization/` | Geometry and materials |
| `physics_bodies/` | Physics: rigid bodies, colliders, joints, articulations, materials, graspable |
| `isaac_sim/` | Isaac Sim–specific robot/composition rules |
| `nonvisual_sensors/` | Non-visual sensor materials |
| `semantic_labels/` | Semantic labeling |
| `hierarchy/` | Stage and prim hierarchy |

If a new capability logically belongs to an existing group, place it as a
new subfolder under that group. If it represents an entirely new area,
create a new group folder and add a `<group>.md` landing page alongside it.

### Naming rules for each layer

| Layer | Convention | Example |
| --- | --- | --- |
| **Group folder** | `snake_case` | `physics_bodies/` |
| **Capability folder** | `snake_case` | `physics_rigid_bodies/` |
| **Capability overview** | `capability-<folder_name>.md` — slug **must** match the folder name exactly (use underscores, not hyphens) | `capability-physics_rigid_bodies.md` |
| **Requirements index** | Always `requirements.md` | `requirements.md` |
| **Requirement doc** | `kebab-case` slug under `requirements/` | `requirements/rigid-body-no-instancing.md` |
| **Requirement ID (Code)** | Two-letter prefix + dot + zero-padded number | `RB.005`, `HI.003`, `UN.001` |
| **Python enum** | Dot becomes underscore: `cap.<Cap>Requirements.<PREFIX>_<NNN>` | `cap.HierarchyRequirements.HI_003` |
| **Validator file** | Always `validation.py` in the capability folder | `hierarchy/validation.py` |
| **Validator rule name** | PascalCase string in `@register_rule()` matching the capability | `@register_rule("Hierarchy")` |

> **Known deviations.** Two existing capability overview files do not
> follow the slug-matches-folder rule:
>
> - `physics_colliders/capability-collider_approximations.md` — slug
>   should be `physics_colliders` to match the folder.
> - `base_articulation/capability-base-articulation.md` — slug uses
>   hyphens instead of underscores.
>
> Three Isaac Sim capabilities (`composition/`, `robot_core/`,
> `robot_materials/`) are missing `capability-*.md` overview files
> entirely. `core/robot/` is a stub containing only a placeholder
> `validation.py`. These should be addressed as part of ongoing
> documentation clean-up.

### Requirement document structure

Each requirement `.md` file in `requirements/` must include a metadata
table and standard sections:

```markdown
# kebab-case-title

| Code     | XX.NNN |
|----------|--------|
| Validator| {oav-validator-latest-link}`xx-nnn` |
| Compatibility | {compatibility}`<tier>` |
| Tags     | {tag}`<tag>` |

## Summary
## Description
## Why
## Examples
## How to comply
```

The `Code` value must be unique across the entire spec. The two-letter
prefix is drawn from the capability's abbreviation (e.g. `HI` for
hierarchy, `RB` for rigid bodies, `VG` for visualization/geometry).

### Registering a new capability

After creating the folder and files:

1. Add the capability's `validation.py` import to
   `nv_core/sr_specs/docs/capabilities/__init__.py` so validators are
   discovered at package import time.
2. Add the capability overview page to the parent group's `{toctree}`.
3. Add any badge snippets to `_includes/badges/` if the requirement tables
   need them.

## Relationship to existing requirements

SimReady Foundation already has a **Naming and Paths** capability
(`core/naming_paths`) with requirements NP.001–NP.008. Those requirements
cover **structural naming**:

- NP.001 — prim naming conventions (camelCase / snake_case)
- NP.002 — file naming conventions
- NP.003 — directory structure
- NP.004 — path length limits
- NP.005 — asset folder structure
- NP.006 — metadata location
- NP.007 — relative paths
- NP.008 — asset-path validation

This guide covers **semantic naming** — the namespace prefixes on attributes,
properties, and schema-introduced names. There is no overlap or
contradiction:

- NP.001 says a prim must be named `chairBase` or `chair_base` (structural).
- This guide says an attribute on that prim must be named
  `simready:<submodule>:<propName>`, not `<propName>` (semantic).

When formal requirement IDs are introduced for these rules in the future,
they will live under a separate `core/naming_conventions` capability and
cross-reference NP.001–NP.008 where relevant.

---

## Appendix A: background and motivation

### The problem

USD allows any vendor to define custom schemas and add custom attributes to
prims. Without coordination, this leads to three problems:

1. **Ambiguity.** Users and tools cannot tell whether a property belongs to a
   standard schema, a vendor extension, or an ad-hoc pipeline attribute.
2. **Collision.** Two vendors (or two teams within the same vendor) may
   independently create properties with identical names but different
   semantics, causing silent data corruption when assets move between tools.
3. **Degradation.** Tools that encounter unknown properties may re-create
   prims, drop data, or behave incorrectly if they cannot distinguish
   vendor-specific properties from standard ones.

### How namespacing solves it

OpenUSD already encourages namespace prefixes on properties added by API
schemas — for example, the standard `UsdPhysics` module uses `physics:` as
its property prefix. This guide extends that pattern into a consistent set
of rules that cover not just API-schema properties but also custom
properties on standard types and ad-hoc attributes that have no schema at
all.

The core idea is simple: **every non-standard property must carry a
colon-delimited prefix that identifies its owner**. The prefix is the
contract between the property author and every downstream consumer of the
USD file.

### Schema type naming (future scope)

Two additional conventions apply to schema *type* names rather than property
names:

- **IsA schema names** should start with a recognisable prefix (e.g.
  `Omni*`, `Physx*`, `Acme*`) so that prim types are immediately
  identifiable as vendor-defined.
- **Applied API schema names** should end with the `*API` suffix to
  distinguish them from IsA schemas.

These type-naming conventions are not covered by the rules in this guide and
will be addressed in a separate document.

---

## Appendix B: coverage of the original naming-conventions checklist

The table below maps each item from the original naming-conventions
requirements checklist to its status in this guide. Items marked *not
addressed* or *partial* represent future work.

### Specification scope

| Item | Status | Notes |
| --- | --- | --- |
| Naming convention rules expressed as **Foundation Requirements with unique IDs** (e.g. NC.001, NC.002) under a new `core/naming_conventions` capability | Not addressed | This document provides contributor guidance, not a formal capability with requirement IDs. The rules defined here are the authoritative source from which formal requirements can be created. |
| Requirements cover **specific tier prefixes** (e.g. `simready:`, `physx:`, `isaac:`) **and** the **cross-vendor pattern** (any vendor prefix with well-formedness rules) | Addressed | Rules 1–4 and the *well-formed vendor prefix* section cover both. |
| **IsA schema naming** (recognisable prefix) and **Applied API schema naming** (`*API` suffix) each have their own Requirement | Not addressed | These are schema *type* naming conventions, deferred to a future document. See *Appendix A: background and motivation*. |
| **Property namespace prefixes** and **custom attribute namespacing** each have their own Requirement with unique ID | Partial | Rules 1–3 document the conventions. Formal requirement IDs do not yet exist. |
| Existing **NP.001–NP.008 cross-referenced**; no duplication or contradiction | Addressed | See *Relationship to existing requirements* section. |

### Validation scope

| Item | Status | Notes |
| --- | --- | --- |
| Each Requirement has a **corresponding validator** in `validation.py` using the `omni.asset_validator.core` framework and `@register_requirements()` pattern | Not addressed | No validators are created. Validators depend on formal requirement IDs, which do not yet exist. |
| Validators detect: missing vendor prefix on IsA schemas, missing namespace prefix on properties, use of unstructured attributes where typed schemas should exist | Not addressed | Same dependency on formal requirements and a `core/naming_conventions` capability. |
| Compatibility tier: **NEUTRAL** — no PhysX or Isaac dependency | N/A | No validators to tier. The guide itself is tier-neutral. |
| All existing **sample_assets pass** the new naming validators | N/A | No validators to run. |

### Documentation scope

| Item | Status | Notes |
| --- | --- | --- |
| At least one example shows the **progression** from poorly-formed (`float4[] rig_blob`) to well-formed (`acmeCable:flex:stiffness`, `acmeCable:flex:dampingRatio`) | Addressed | See *Example: from unstructured to well-formed*. |
| Requirement docs follow the established **authoring pattern** (Summary, Description, Why, Examples, How to comply, Related requirements) | Not addressed | No formal requirement `.md` files are created. Each rule section in this guide provides description, examples, and how-to-comply guidance in a lighter format. |
