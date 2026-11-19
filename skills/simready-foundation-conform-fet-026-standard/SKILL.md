---
name: simready-foundation-conform-fet-026-standard
description: "Use for repairing exact CAP026_Mates SimReady mate-site conformance. Use when a profile, validation report, or user request names CAP026_Mates; default to version 0-1-0 unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - standard
---

# SimReady Conform CAP026_Mates

## Purpose

The skill command retains its historical `fet` name for compatibility; the selected contract is a Foundations 2 capability with static validation.

Use this exact capability skill when the selected profile, validation report, or user request names `CAP026_Mates`. It repairs or stages Standard mechanical mate sites on a **standalone** asset without authoring assembly connections.

Default to `CAP026_Mates.0-1-0` when the user asks for this capability without a version.

## Source of Truth

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP026_Mates.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP026_Mates.md`

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0-1-0` | `FET003_RigidBody.0-2-0` | `MC.001`–`MC.007` |

## Workflow

1. Stage output; do not silently mutate the source asset.
2. Repair only `MC.001`–`MC.007` (and the FET_003 enabled rigid-body ancestry needed by `MC.003`).
3. Derive `maxPayload` from the manipulator, flange, or load spec. Do not invent mass or payload.
4. Do not author `Connections` prims or joints; that is `CAP027_Connections`.
5. Static validators are not registered yet. Inspect the staged USDA against the requirement docs and report `blocked` for automated validation.

## Capability Guidance

- Discovery is `simready:mate:domain` + `simready:mate:role` on an `Xform`.
- Mechanical sites: `mechanical` + `Socket` or `Plug`. No `Peer`. Sites in other domains are discovered but out of scope; leave them alone rather than rewriting their `domain`.
- `interface` is an exact catalog string. `kind` is optional and warns if unrecognized.
- Insertion vector is optional; default approach is socket `-Z`.
- `MC.003` reads `physics:rigidBodyEnabled`, not just the applied schema. On a standalone asset, leave it at its true default; disabling a part's body is an assembly-side edit that belongs to `CN.011`.

## Report Fields

| Field | Meaning |
|---|---|
| `capability` | `CAP026_Mates.0-1-0` |
| `input` | Source standalone asset |
| `output` | Staged output path |
| `requirements_repaired` | `MC.*` IDs repaired |
| `validation` | Inspection used (validators deferred) |
| `status` | `passed`, `failed`, `skipped`, or `blocked` |
| `next_step` | `CAP027_Connections` on an assembly |
