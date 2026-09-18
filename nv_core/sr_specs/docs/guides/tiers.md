# SimReady Foundation Tiers

## About This Guide

SimReady Foundation organizes its specification into *tiers*. This guide
explains what a tier is, why the specification is structured this way, and what
tiers mean for you when you validate assets or pick a profile.

This guide is intended for anyone who consumes SimReady Foundation: asset
creators, pipeline engineers, and validation engineers. It assumes you are
familiar with the Foundation model of requirements, capabilities, features, and
profiles. If those concepts are new, start with
[SimReady Foundation](getting_started.md).

This guide is conceptual. For the packaging mechanics — installing tier wheels,
how tier discovery works, and how to build a tier of your own — see
[SimReady Foundation PyPI Packages](foundation_pypi.md).

## What is a tier?

A tier is a slice of the specification that is owned, versioned, and
distributed as a unit. Each tier owns a coherent set of capabilities, features,
and profiles — plus the runtime tests that prove them, where it has any — and
ships as its own Python package.

Tiers serve two purposes at once:

- **Distribution.** A tier is the unit you install. You install only the tiers
  your workflow needs, and you get their requirements, features, profiles,
  validation rules, and bundled runtime tests together.
- **Ownership and adoption.** A tier records who defines a piece of the
  specification and how widely it has been adopted. The core tier holds
  specification content that is broadly agreed on. Other tiers hold content
  that is real and usable but not yet part of that shared core.

Tiers can depend on each other. A tier that depends on another is the
*downstream* tier; the one it depends on is the *upstream* tier. A downstream
tier adds its own content without modifying the upstream package, so
downstream content never changes the meaning of upstream requirements.

## Why the specification is organized into tiers

Simulation domains mature at different rates. A convention that a single team
relies on today — a solver-specific attribute, a runtime-specific asset layout,
an in-house semantic taxonomy — may be exactly right for that team and still be
too specific, too new, or too narrowly reviewed to belong in a specification
that everyone shares.

Without tiers there are only two outcomes for that kind of content, and both
are bad. Either it is pushed into the shared core before it has been proven,
which makes the core less trustworthy for everyone, or it is kept out
entirely, which leaves the team with a private convention that no validator
understands and no tool can check.

Tiers give that content a third option. It lives in its own tier, where it is
formally specified, validated by real rules, and usable in production, while
remaining clearly distinct from the shared core. As the content proves itself
and gains agreement across runtimes and vendors, it can move toward the core
tier. The intent is a path from private convention to shared standard that does
not block adoption at any point along the way.

One consequence is worth stating plainly: **content in a non-core tier is not
lower quality.** It is validated the same way, by the same framework, against
the same kind of machine-checkable rules. What differs is the breadth of
agreement behind it and, therefore, how portable it is across runtimes and
vendors.

## How tiers relate to the rest of the model

Tiers do not replace or reorder the existing concepts. Requirements still roll
up into capabilities, capabilities into features, and features into profiles.
A tier is the container that says which of those artifacts it owns.

| Concept | What it defines | Relationship to tiers |
|---|---|---|
| Requirement | A single testable rule, such as `UN.006`. | Owned by exactly one tier. |
| Capability | A group of related requirements. | Owned by exactly one tier. |
| Feature | A versioned bundle of requirements for a use case. | Owned by one tier; may reference requirements from an upstream tier. |
| Profile | A versioned bundle of features. | Owned by one tier; may reference features from an upstream tier. |
| Runtime test | A behavioral test that exercises a feature in a live runtime. | Bundled in the tier that owns the feature it tests, so the two version together. |

Because features and profiles can reference upstream content, a profile in a
downstream tier can compose core features with that tier's own additions. When
multiple tiers are installed, references resolve across all of them regardless
of install order.

Runtime tests ship inside the tier package rather than as a separate
distribution, so a tier's behavioral proof cannot drift from the specification
it proves. The tests travel with the tier; the Benchmark and engine
dependencies needed to *run* them are an optional install, which keeps a
validation-only setup lightweight. See
[SimReady Benchmark](benchmark/benchmark.md).

When you browse this documentation, tier-owned pages appear in the
[Capabilities](../capabilities/capabilities.md),
[Features](../features/features.md), and
[Profiles](../profiles/profiles.md) sections. The documentation is assembled
from every tier, so those sections present the combined specification rather
than one tier at a time.

## Tiers available today

SimReady Foundation currently publishes a single tier.

| Tier | Package | Contents |
|---|---|---|
| Core | `simready-foundation-tier-core` | The Core, Hierarchy, Visualization, Physics Bodies, Isaac Sim, Non-Visual Sensors, Semantic Labels, Dataset Taxonomies, and Packaging capabilities; the neutral, PhysX, and Isaac prop profiles; the robot and gripper profiles; the package profiles; the Open Taxonomy profiles; and the Foundation runtime tests. |

```{note}
Additional tiers are in development, including tiers contributed by teams
outside the Foundation. Until they are published, all Foundation specification
content ships in the core tier, and installing
`simready-foundation-tier-core` gives you the complete specification.
```

Because tiers are ordinary Python packages, you can also create your own to
distribute organization-specific requirements, features, and profiles without
modifying or repackaging Foundation content. See
[Creating Your Own Tier](foundation_pypi.md#creating-your-own-tier).

## What tiers mean for you

**Installing.** A tier is what you install to get specification content. The
core tier is the baseline; install additional tiers when you need the content
they own. Installing more tiers adds requirements, features, and profiles — it
does not change the ones you already had. A plain install gives you everything
you need to validate; if you also want to run a tier's runtime tests, install
it with its `benchmark` extra, as shown in
[SimReady Foundation PyPI Packages](foundation_pypi.md#installation).

**Choosing a profile.** Pick a profile by the runtime and asset class you are
targeting, as described in
[Getting Started](getting_started.md#q3--what-kind-of-asset-are-you-building).
The tier that owns a profile tells you how portable it is: a profile owned by
the core tier is the most broadly agreed-on option for that scenario, while a
profile owned by another tier is scoped to that tier's runtime, vendor, or
domain.

**Validating.** Validation does not change because of tiers. `simready-validate`
discovers every installed tier and runs the rules for your chosen profile in a
single pass, whichever tiers those rules come from. See the
[SimReady Validation Workflow](validate_workflow.md).

**Reading maturity.** A tier tells you how broadly a piece of the
specification is agreed on. It does not, on its own, tell you whether a
specific feature is finished. For that, use the delivery signals in the
[SimReady Acceptance Workflow](acceptance_workflow.md#what-to-expect-as-a-consumer),
which explain what it means when a feature is pinned in a profile, when a
feature exists but no profile references it, and when requirements exist
without validators. Read the two together: the tier tells you how widely the
contract is shared, and the delivery signals tell you how complete it is.

## Terminology: three uses of "tier"

The word "tier" appears in three unrelated senses in SimReady material. This
guide only describes the first.

| Term | Meaning |
|---|---|
| **Tier** (this guide) | A distributable, separately owned slice of the specification, such as the core tier. Also called a *validation tier* or *tier package*. |
| **Compatibility tier** | Which runtime or shading system a feature variant targets. A property of a feature variant, not a package. |
| **Maturity level** | How far a capability or feature has progressed through the acceptance lifecycle. |

A compatibility tier appears as the suffix on a feature ID and as the
**Runtime** column in the [feature list](../features/features.md). `STANDARD`
marks a runtime-neutral feature; `PHYSX`, `NEWTON`, `MUJOCO`, `ISAAC`, `MDL`,
and `ROS` mark variants for a specific runtime or shading system. For details,
see [Runtime Variant Field](features/features.md#runtime-variant-field-runtime)
and [Multiple Physics Solvers](multiphysics_solvers.md). For maturity, see the
[SimReady Acceptance Workflow](acceptance_workflow.md).

## Where to go next

- [SimReady Foundation PyPI Packages](foundation_pypi.md) — install tiers, how
  tier discovery works, and how to create a tier.
- [SimReady Acceptance Workflow](acceptance_workflow.md) — how specification
  content progresses from an idea to accepted, delivered content.
- [SimReady Validation Workflow](validate_workflow.md) — validate an asset
  against a profile using installed tiers.
- [Attribute Naming Conventions](naming_conventions.md) — how attribute
  prefixes and rule namespaces align with the tier that introduces a schema.
