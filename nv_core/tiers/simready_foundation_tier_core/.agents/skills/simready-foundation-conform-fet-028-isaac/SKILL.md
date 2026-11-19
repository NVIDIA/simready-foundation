---
name: simready-foundation-conform-fet-028-isaac
description: "Use for repairing exact FET028_Gripper.Isaac SimReady conformance for Isaac gripper-site conformance. Use when a profile, validation report, or user request names FET028_Gripper.Isaac; default to `FET028_Gripper.Isaac.0-1-0` unless a profile or report pins another version. Foundations 1 ID: FET_028_ISAAC."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - isaac
---

# SimReady Conform FET028_Gripper.Isaac

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

Use this exact feature skill when the selected profile, validation report, or user request names `FET028_Gripper.Isaac`. It repairs or stages Isaac gripper-site conformance without drifting into another runtime contract.

Default to `FET028_Gripper.Isaac.0-1-0` when the user asks for this feature without a version. Use another version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET028_Gripper.Isaac.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET028_Gripper.Isaac.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `FET028_Gripper.Isaac.0-1-0` | FET028_Gripper.0-1-0, FET022_DrivenJoints.Isaac.0-1-0 | `GR.ISA.001` |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET028_Gripper.Isaac` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET028_Gripper.Isaac` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET028_Gripper.Isaac` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair only the requirements listed by the selected `FET028_Gripper.Isaac` manifest and its dependencies.
- Do not add schemas, metadata, or runtime behavior for a sibling runtime feature.
- Report missing runtime/tooling evidence as a validation limitation instead of claiming a pass.
- A fixed articulation may validly carry `PhysicsArticulationRootAPI` on its
  world-pin joint, with the rigid-body links beside that joint. FET028 carrier
  attachment must resolve the connected physical body separately from the API
  prim. A carrier setup or restoration error is a test-harness limitation, not
  evidence that this USD pattern is invalid. Do not move the asset's API or
  remove its world pin merely to satisfy the carrier; preserve the authored
  asset and verify the result with a corrected runtime-test provider.
- Preserve authored scale, including scale encoded in a matrix. Compare body
  and collider dimensions before and after native articulation initialization
  and carrier attachment before recommending drive or grasp-site edits.
  Unsupported transform handling is a provider setup limitation, not proof
  that the asset violates this feature. Use installed Evaluate diagnostic and
  repair-report skills for the ordered checks; authoring helpers are not
  substitute acceptance tests.
- Verify fresh static requirements and dependencies, then every runtime test
  listed in the exact selected manifest on the same source revision (this
  version lists both cube and sphere). Use the real Validate output as input
  to the real Evaluate plan. Selected trial PASS, applicability skips and
  missing catalog bindings must remain distinct from complete conformance.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `FET028_Gripper.Isaac.0-1-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
