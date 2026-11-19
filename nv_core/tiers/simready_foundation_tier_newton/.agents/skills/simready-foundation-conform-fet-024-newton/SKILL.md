---
name: simready-foundation-conform-fet-024-newton
description: "Use for repairing exact CAP024_BaseArticulation.Newton SimReady conformance for Newton base-articulation conformance. Use when a profile, validation report, or user request names CAP024_BaseArticulation.Newton; default to `CAP024_BaseArticulation.Newton.0-1-0` unless a profile or report pins another version. Foundations 1 ID: FET_024_NEWTON."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - newton
---

# SimReady Conform CAP024_BaseArticulation.Newton

## Purpose

Use this exact capability skill when the selected profile, validation report, or user request names `CAP024_BaseArticulation.Newton`. It repairs or stages Newton base-articulation conformance without drifting into another runtime contract.

Default to `CAP024_BaseArticulation.Newton.0-1-0` when the user asks for this capability without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/capabilities/CAP024_BaseArticulation.Newton.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/capabilities/CAP024_BaseArticulation.Newton.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the capability markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `CAP024_BaseArticulation.Newton.0-1-0` | CAP024_BaseArticulation.0-1-0 | `NEWTON.BA.001` |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `CAP024_BaseArticulation.Newton` manifest and the capability markdown before editing.
3. Load requirement docs linked from the capability markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `CAP024_BaseArticulation.Newton` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `CAP024_BaseArticulation.Newton` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair only the requirements listed by the selected `CAP024_BaseArticulation.Newton` manifest and its dependencies.
- `NEWTON.BA.001`: the stage must have exactly one articulation root. The canonical form is
  `NewtonArticulationRootAPI` (it extends `PhysicsArticulationRootAPI` and defines
  `newton:selfCollisionEnabled`, plus the optional `uniform bool newton:jointsAddMobility`).
  Authoring the bare `bool newton:selfCollisionEnabled` on a `PhysicsArticulationRootAPI`
  root is also accepted. Set `newton:selfCollisionEnabled` explicitly (do not rely on the
  importer default), and author it only on the articulation-root prim. Only set
  `bool newton:selfCollisionEnabled = 0` when source evidence (such as the source URDF/MJCF
  or neutral/PhysX articulation settings, or demonstrated overlapping adjacent-link collision
  approximations that are not intended to self-collide) establishes that articulation-wide
  self-collision is unintended; do not remove intended self-collision behavior merely to make
  a test pass or work around an engine contact-budget limitation.
- Do not add schemas, metadata, or runtime behavior for a sibling runtime feature.
- Report missing runtime/tooling evidence as a validation limitation instead of claiming a pass.

## Samples

- None.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `CAP024_BaseArticulation.Newton.0-1-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact capability skill or user/runtime evidence needed. |
