# SimReady Acceptance Workflow

## Purpose

This guide is a repo-scoped view of the
[SimReady Standardization Workflow](https://docs.omniverse.nvidia.com/simready/latest/simready-standards/standardization_workflow.html).
The published workflow describes the full org-level lifecycle — kickoff, roles,
terminology, internal and external beta, partner coordination. This guide
narrows in on the slice that plays out inside this repository: what artifacts a
spec contribution produces, what gates each artifact passes through, and how
consumers can read the maturity of what's already merged.

Read the published workflow for the full picture. Read this guide to understand
the acceptance criteria your PR will be evaluated against.

## Goals

1. **Design Asset Specifications for Standardization** — identify and define
   new asset capabilities to extend OpenUSD for simulation workflows.
2. **Create End-to-End Reference Pipelines** — produce documentation,
   validators, workflows, samples, and software to enable successful adoption.
3. **Enable Industry Adoption** — involve and encourage ISV / GSI / partner
   adoption, including integration into other DCCs and libraries.

## Process overview

*Phases*

```{mermaid}
:caption: Phases

flowchart TD
    L1["Phase 1 — Definition & Alignment"] --> L2["Phase 2 — Development & Iteration"] --> L3["Phase 3 — Package Deliveries"]
    style L1 fill:#d4e6f1,stroke:#2c3e50
    style L2 fill:#d5f5e3,stroke:#1e8449
    style L3 fill:#fdebd0,stroke:#b9770e
```

*Process*

```{mermaid}
:caption: Process

flowchart TD
    A["Identify Domain & Use-Case"] --> B["Identify Domain Experts & Partners"]
    B --> C{"Existing Standard?"}
    C -- YES --> D["Conceptual Data Mapping"]
    C -- NO --> E["Gap Analysis"]
    D --> E
    E --> FC["Fill in Feature Card"]
    FC --> F["Prototyping"]
    F --> G["Specs"]
    F --> H["Samples"]
    F --> I["Validators"]
    F --> J["Pipeline Blueprint"]
    F --> K["Tests"]
    G --> N{"Accept?"}
    H --> N
    I --> N
    J --> N
    K --> N
    N -- Iterate --> F
    N -- Accept --> O["Candidate Specification"]
    O --> P["Pipeline & Validation"]
    P --> Q["Sample Content"]
    Q --> R["Delivery"]

    style A fill:#d4e6f1,stroke:#2c3e50
    style B fill:#d4e6f1,stroke:#2c3e50
    style C fill:#d4e6f1,stroke:#2c3e50
    style D fill:#d4e6f1,stroke:#2c3e50
    style E fill:#d4e6f1,stroke:#2c3e50
    style FC fill:#d4e6f1,stroke:#2c3e50

    style F fill:#d5f5e3,stroke:#1e8449
    style G fill:#d5f5e3,stroke:#1e8449
    style H fill:#d5f5e3,stroke:#1e8449
    style I fill:#d5f5e3,stroke:#1e8449
    style J fill:#d5f5e3,stroke:#1e8449
    style K fill:#d5f5e3,stroke:#1e8449
    style N fill:#d5f5e3,stroke:#1e8449

    style O fill:#fdebd0,stroke:#b9770e
    style P fill:#fdebd0,stroke:#b9770e
    style Q fill:#fdebd0,stroke:#b9770e
    style R fill:#fdebd0,stroke:#b9770e
```

---

## Phase 1 — Definition & Alignment

Defining the scope is essential for developing USD asset capabilities for
simulation. Start by detailing the MVP use-case and identifying necessary
domain expertise and partners early on.

### Identify domain, use-case, and problem statement

A new spec area begins when a simulation domain or product use-case surfaces
that is not yet covered by an existing profile or feature. The PIC (Pilot in
Command) frames the problem statement: what class of OpenUSD content needs to
be validated, and what simulation behavior must that content support?

| Entry | Exit |
|-------|------|
| Unmet simulation need or partner request. | Documented problem statement with a named domain scope and at least one concrete use-case. |

### Identify domain experts and industry partners

Subject-matter experts (SMEs) and, where applicable, external industry
partners are identified to guide the technical direction. Domain experts with
membership in [AOUSD](https://aousd.org/) (or intention thereof) are
preferred.

| Entry | Exit |
|-------|------|
| Documented problem statement. | Named SME roster; agreement on collaboration scope. |

### Data mapping and gap analysis

A decision gate determines whether an existing standard (ISO, Khronos, domain
convention, etc.) already addresses the problem space.

- **Existing standard → Conceptual Data Mapping.** The standard is mapped onto
  the SimReady data model (capabilities, requirements, features) to identify
  which parts can be adopted and where gaps remain.
- **No existing standard → Gap Analysis.** The workflow proceeds directly to
  gap analysis to identify inputs and outputs needed within the simulation
  runtime.

Both paths converge at a prioritized list of gaps.

| Entry | Exit |
|-------|------|
| SME roster and domain scope. | Prioritized list of gaps with estimated scope; mapping document if a standard exists. |

### Fill in Feature Card

Before moving into development, create a **Feature Card** that documents the
proposed capability. The card serves as both the design brief and a research
summary — it captures the use-case, describes the expected behavior in
simulation, and surveys existing features to avoid duplication or conflict.

A Feature Card should include:

- **Use-case description** — what simulation workflow the feature enables and
  who benefits (e.g. "robot gripper assets need grasp-vector metadata so
  planners can align approach trajectories").
- **Existing feature survey** — review current features in `features/` and
  profiles in `profiles.toml` to identify overlap, dependencies, or features
  that the new work should extend rather than duplicate.
- **Proposed requirements** — a preliminary list of the USD properties or
  structures the feature will check, informed by the gap analysis.
- **Target profile(s)** — which profiles the feature is expected to join and at
  what version.

| Entry | Exit |
|-------|------|
| Prioritized gap list from data mapping / gap analysis. | Completed Feature Card with use-case, existing-feature survey, proposed requirements, and target profiles. |

---

## Phase 2 — Development & Iteration

Once the simulation use-case and goals are defined, begin prototyping and
iterating within OpenUSD to meet runtime requirements. This involves adding
and testing custom attributes, incorporating existing schemas (if they exist),
and documenting efforts.

### Assess viability and prioritize capabilities

Categorize capabilities into:

1. Those that can be standardized across simulation runtimes in a specification.
2. Those that are not yet ready for standardization (e.g. too specific to a
   given solver/runtime/software).

### Prototyping

Gaps are addressed through iterative prototyping. This stage produces four
categories of deliverables:

| Deliverable | Description |
|-------------|-------------|
| **Specs** | New or updated capability requirements, feature definitions (JSON + markdown), and profile entries. |
| **Samples** | Reference OpenUSD assets in `sample_content/` that demonstrate compliant structure for the new domain. |
| **Validators** | Rule implementations (`validation.py`) registered against the corresponding capability. |
| **Tests** | Runtime tests that prove the feature works in a reference simulation runtime. Each test loads a sample asset into the runtime (e.g. Isaac Sim), exercises the behavior the feature claims to enable (physics drop, joint articulation, grasp planning), and asserts an expected outcome. A feature is not considered complete until it has at least one passing runtime test that demonstrates the claimed capability end-to-end. |
| **Pipeline Blueprint** | CI job definitions, batch-maker configurations, or pipeline templates that exercise the new validators at scale. |

### iBeta and QA testing

Draft deliverables are exercised against real and synthetic USD content.
Testing validates that:

- **USD Schemas and Specs** — requirement markdown, feature JSON, and profile
  TOML are internally consistent and link-clean (cross-reference integrity,
  correct IDs, no stale paths).
- **USD Validators** — rule implementations produce correct pass/fail results
  on known-good and known-bad assets, covering edge cases identified during gap
  analysis.

This stage may run in parallel with late prototyping; feedback from testing
often feeds directly back into the prototype.

### Accept / Iterate gate

The central quality checkpoint. All deliverables and test results are reviewed
against the acceptance criteria:

1. Every new requirement has a unique code, a complete markdown file (Summary,
   Description, Why, Examples, How to comply, Related, For More Information),
   and a registered validator rule.
2. Every new feature has a versioned JSON definition with correct `path`,
   `dependencies`, and `requirements`, plus a matching markdown document with
   variant sections.
3. Sample assets validate cleanly against the target profile.
4. Automation jobs run end-to-end without manual intervention.
5. No broken internal links, stale references, or orphaned toctree entries.
6. Domain experts and the PIC confirm that the deliverables address the
   original problem statement.

**Iterate.** If any criterion is not met, work returns to Prototyping with
specific feedback. Multiple iterations are normal and expected.

**Accept.** When all criteria are satisfied, the deliverables advance to
Phase 3.

---

## Phase 3 — Package Deliveries

To be considered a SimReady specification, all prior work — defining the
specification, developing schemas, creating and validating content, and
documenting workflows — must be tested and validated end-to-end.

### Candidate specification

The written specification document created using the spec template in Phase 2
is collected and polished.

### Pipeline & validation

An end-to-end asset workflow pipeline from source data into a simulation
runtime is delivered:

- **Validators** that check candidate assets for compliance with the defined
  asset specification.
- **Converters** that implement source-data-to-OpenUSD conversion according to
  the conceptual data mapping.
- **Workflow documentation** that instructs creators on how to apply the
  capability, validate it, and test it in the intended runtime(s).

### Sample content

Reference datasets and sample content that demonstrate the defined asset
capability, exercise the validators, and serve as examples in the workflow
documentation.

### Delivery

Accepted artifacts are merged into the specification:

- Requirement markdown and `validation.py` land under `capabilities/`.
- Feature JSON and markdown land under `features/`.
- Profile TOML entries and profile markdown land under `profiles/`.
- Sample assets land under `sample_content/`.
- Automation configurations land in the testing framework or CI pipeline
  definitions.

Version numbers are assigned (or bumped) according to the scope of change.
Existing profiles that do not reference the new features remain unaffected.

---

## What to expect as a consumer

Not every spec area in the repository is at the same maturity level. The
lifecycle above means that at any point in time, some capabilities may be
fully delivered while others are still in prototyping or testing.

| Indicator | What it means |
|-----------|---------------|
| A profile lists the feature in `profiles.toml` with a pinned version. | The feature has completed the full standardization workflow and is safe to validate against. |
| A feature JSON exists but is not yet referenced by any profile. | The feature is in late prototyping or testing. It may change before delivery. |
| A capability directory contains requirements but no `validation.py`. | The requirements are defined but validators are still in progress. Treat the requirements as directional, not enforceable. |
| Sample assets exist in `sample_content/` for the domain. | Reference implementations are available; check the corresponding profile version to confirm they are up to date. |

When in doubt, check the feature version and the profile that references it.
Pinned versions in a profile represent the accepted, stable contract.
