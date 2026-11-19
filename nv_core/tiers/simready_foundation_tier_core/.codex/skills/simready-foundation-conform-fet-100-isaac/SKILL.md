---
name: simready-foundation-conform-fet-100-isaac
description: "Use for repairing exact CAP100_IsaacComposition.Isaac SimReady conformance for Isaac composition conformance. Use when a profile, validation report, or user request names CAP100_IsaacComposition.Isaac; default to `CAP100_IsaacComposition.Isaac.0-4-0` unless a profile or report pins another version. Foundations 1 ID: FET_100_ISAAC."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - isaac
---

# SimReady Conform CAP100_IsaacComposition.Isaac

## OpenUSD Competence

Running this conform skill is expert USD authoring. Reason from the OpenUSD /
Pixar USD spec rather than pattern-matching a validator message: composition
arcs and LIVRPS strength ordering, value resolution and list editing
(prepend, append, explicit, delete), the `def`/`over`/`class`
specifiers, native instancing and model hierarchy, stage units and up-axis,
and the `UsdGeom`, `UsdShade`, and `UsdPhysics` schemas. Make the exact native
edit on the correct prim, arc, and layer, derive values from the asset's real
geometry and composition, then reopen the composed stage to confirm the
opinion resolves as intended before claiming the gate passes. Never fabricate
data to satisfy a validator token. The repository-root `AGENTS.md`
"Master-Level OpenUSD Competence for Conform Work" section is the full
statement.

## Purpose

Use this exact capability skill when the selected profile, validation report, or user request names `CAP100_IsaacComposition.Isaac`. It repairs or stages Isaac composition conformance without drifting into another runtime contract.

Default to `CAP100_IsaacComposition.Isaac.0-4-0` when the user asks for this capability without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP100_IsaacComposition.Isaac.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP100_IsaacComposition.Isaac.0-2-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP100_IsaacComposition.Isaac.0-3-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP100_IsaacComposition.Isaac.0-4-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP100_IsaacComposition.Isaac.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the capability markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `CAP100_IsaacComposition.Isaac.0-1-0` | FET003_RigidBody.PhysX.0-1-0 | `ISA.001` |
| `CAP100_IsaacComposition.Isaac.0-2-0` | FET003_RigidBody.PhysX.0-3-0 | `ISA.001` |
| `CAP100_IsaacComposition.Isaac.0-3-0` | FET003_RigidBody.PhysX.0-4-0 | `ISA.001` |
| `CAP100_IsaacComposition.Isaac.0-4-0` | FET003_RigidBody.PhysX.0-4-0 | `ISA.001` |

Version `CAP100_IsaacComposition.Isaac.0-4-0` keeps the `CAP100_IsaacComposition.Isaac.0-3-0` contract (`FET003_RigidBody.PhysX.0-4-0`, `ISA.001`).
It changes only the composition pipeline: prefer producing Isaac composition with
the public, Kit-free `isaacsim.asset.transformer` framework using the
`simready_physx_to_isaac_prop` profile retained by the thin
`simready.asset_transformer` integration
(`nv_core/tiers/simready_foundation_tier_core/tools/isaac_asset_transformer`),
then validate against the selected manifest. Older versions remain supported
for assets pinned to them.

## Runtime Prerequisites

- Use Python 3.12.
- The optional tier-core `[isaac]` extra requires `isaacsim-asset-isolated==6.2.0.1` and
  `isaacsim-robot-schema==6.2.0.0`, both available on PyPI.
- Install `pip install "simready-foundation-tier-core[isaac]"` before running
  the transform; the base tier does not install the Isaac dependencies.
- The public package supplies the framework and normal rules. The thin
  `simready.asset_transformer` package retains profiles, the CLI,
  SimReady-specific rules, and small guarded temporary patches (geometry
  re-flatten paths, read-only variant copies, and search-path assets on publish).
- Profiles preserve public `isaacsim.asset.transformer.rules.*` FQCNs. The
  patches verify the exact wheel version and method signatures and must be
  removed after an upstream isolated wheel includes the fixes.
- Do not add a source-path import fallback or reintroduce a standalone fork.

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `CAP100_IsaacComposition.Isaac` manifest and the capability markdown before editing.
3. Load requirement docs linked from the capability markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `CAP100_IsaacComposition.Isaac` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `CAP100_IsaacComposition.Isaac` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair only the requirements listed by the selected `CAP100_IsaacComposition.Isaac` manifest and its dependencies.
- Do not add schemas, metadata, or runtime behavior for a sibling runtime feature.
- Report missing runtime/tooling evidence as a validation limitation instead of claiming a pass.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `CAP100_IsaacComposition.Isaac.0-4-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact capability skill or user/runtime evidence needed. |
