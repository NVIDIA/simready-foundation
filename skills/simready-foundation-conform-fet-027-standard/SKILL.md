---
name: simready-foundation-conform-fet-027-standard
description: "Use for repairing exact CAP027_Connections SimReady assembly-connection conformance. Use when a profile, validation report, or user request names CAP027_Connections; default to version 0-1-0 unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - standard
---

# SimReady Conform CAP027_Connections

## Purpose

The skill command retains its historical `fet` name for compatibility; the selected contract is a Foundations 2 capability with static validation.

Use this exact capability skill when the selected profile, validation report, or user request names `CAP027_Connections`. It repairs declared socket/plug pairings on an **assembly** stage and fully specifies the compound shape.

Jointed connections are declared here but their physics belongs to `CAP029_ConnectionJoint`. This skill sets `realization = "jointed"` and stops; it does not author the joint.

Default to `CAP027_Connections.0-1-0`.

## Source of Truth

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP027_Connections.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP027_Connections.md`

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0-1-0` | `CAP026_Mates.0-1-0` | `CN.001`, `CN.002`, `CN.003`, `CN.004`, `CN.006`, `CN.007`, `CN.008`, `CN.010`, `CN.011`, `CN.012` |

`CN.005` and `CN.009` moved to `CAP029_ConnectionJoint`.

## Workflow

1. Confirm both child assets already satisfy `CAP026_Mates`. Do not create geometry.
2. Stage a standalone assembly (or the requested assembly layer). Compose each part with a `references` or `payload` arc; never author a part inline in the assembly root layer (`CN.010`).
3. Author `Connections` under the default prim with one `socket` rel and one `plug` rel per pairing, each with exactly one target (`CN.001`).
4. Resolve both `MC.003` mate bodies before choosing `realization` (`CN.006`). A mate body is the nearest ancestor with an **enabled** `PhysicsRigidBodyAPI`, so a part carrying `physics:rigidBodyEnabled = false` is transparent to the walk. One shared mate body takes `compound`. Two distinct mate bodies take `jointed`.
5. For the compound case, build the compound body per `CN.011`:
   - Create one assembly-local `Xform` under the default prim with no reference or payload arc. Give it `kind = "group"` so the model hierarchy stays contiguous (`CN.012`).
   - Apply `PhysicsRigidBodyAPI` and `PhysicsMassAPI` to it and leave `physics:rigidBodyEnabled` at its true default.
   - Put the parts under it and author `bool physics:rigidBodyEnabled = false` on each part root, and on each nested assembly's compound body. A part that contains a joint cannot join a compound; connect it `jointed` instead. Disable, never `delete apiSchemas`: the part keeps the mass, inertia, and physics material it was validated with, so the aggregate stays checkable and the demotion stays reversible.
   - Read each part's composed `physics:mass`, sum it stopping at the first mass-authoring prim on each branch, and author the total on the compound body. Skip the aggregate only when every part's mass already sits on its colliders, where the runtime sums it onto the compound body itself.
   - Author no `simready:mate:joint`.
6. For the jointed case, author `realization = "jointed"` and stop. Hand the joint to `simready-foundation-conform-fet-029-standard`; authoring it here would leave `CN.009` unverified.
7. Set `kind = "assembly"` on the default prim, and confirm each child asset root is `component` or `assembly` with no model kinds inside a `component` (`CN.012`).
8. Author `simready:mate:assemblyType` on the assembly default prim (`CN.008`). A nested assembly keeps its own token on its root. It is required and must be one of `robot`, `pallet_stack`. It is informational with respect to physics: never branch realization behavior on it.
9. Validate against `Assembly@0.1.0`, or `Robot-Assembly@0.1.0` for a robot built from robot parts. For a compound, confirm on the composed stage that exactly one enabled rigid body governs it and that its mass equals the part sum.

## Capability Guidance

- Exact `interface` string match. Opposite roles only.
- One site per connection (`CN.007`). A shared socket in two connections fails. A nested assembly's own connections occupy their sites; its unpaired sites are free to use.
- `realization` is derived from the composed mate bodies, not chosen by asset category. A `pallet_stack` may legitimately contain a `jointed` connection and a `robot` may contain `compound` ones.
- `compound` and `jointed` are the only legal tokens. The earlier `none` and `PhysicsFixedJoint` spellings are retired; retoken them when repairing an older asset.
- Never author the aggregate on a referenced part root. That prim means "one of those", and a multiple of that asset's own mass reads as a corrupt part rather than a stack (`CN.011`).
- Never put the compound body on the assembly default prim. Scoping it below keeps one stage able to hold several compound groups, or compound groups alongside jointed parts.
- Parts may sit as siblings under the compound body or nest inside one another. Prefer siblings: each part then carries its own absolute pose instead of a cumulative one.
- In a mixed assembly, each group of compound connections gets its own compound body; jointed parts keep their rigid bodies enabled.
- Spatial coincidence of mate frames is authoring intent; measure it rather than guessing offsets.
- Do not invent payload or mass. The aggregate is summed from the composed parts. If a part authors no mass, report the blocker instead of estimating.
- Mass on a demoted part root is inert: the root is neither a collider nor an enabled body, so the runtime discards it. Such a compound needs the authored aggregate. Author it rather than relocating the part's mass onto its colliders, which would change the part's own contract (`RB.007`).

## Report Fields

| Field | Meaning |
|---|---|
| `capability` | `CAP027_Connections.0-1-0` |
| `input` | Source assembly or child assets |
| `output` | Staged assembly path |
| `requirements_repaired` | `CN.*` IDs repaired |
| `validation` | Inspection used (validators deferred) |
| `status` | `passed`, `failed`, `skipped`, or `blocked` |
| `next_step` | `simready-foundation-conform-fet-029-standard` when any connection is `jointed`; none when the assembly is entirely `compound` |
