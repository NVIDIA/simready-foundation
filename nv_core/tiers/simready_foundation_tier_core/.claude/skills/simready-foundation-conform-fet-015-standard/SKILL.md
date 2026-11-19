---
name: simready-foundation-conform-fet-015-standard
description: Organize existing alternate collider approximations of one asset into simulation-affecting Collision variant sets with discovery metadata, preserving the collision envelope and leaving the render mesh in place, then validate AV.001-AV.010 with the bundled gate on staged output.
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - variants
---

# Conform Collision Variant

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

Targets `FET015_CollisionVariant.0-1-0`, which carries the
asset-variation contract `AV.001`-`AV.010` and depends on the rigid-body contract
(`FET003`). Read the feature doc and the `asset_variants` capability (AV.*
requirement pages) first. Use `simready.foundation.tier_core.asset_variants` to
read, recompose, and measure. Work on a staged copy in the requested output
directory and never mutate the source. Do **not** author geometry: this skill
organizes collider approximations that already exist (for example a convex hull
and a convex decomposition of the same body).

## When it applies

FET015 applies only when the asset already carries a rigid body with authored
`UsdPhysics.MassAPI` (mass/centerOfMass/diagonalInertia) and two or more alternate
collider approximations for a scope. Confirm this first with the bundled gate's
`--diagnose` collider/mass inventory: if it reports no `CollisionAPI`/`MassAPI`,
FET015 is not applicable (there are no colliders to vary and no authored mass for
`AV.009`) -- report that rather than generating a collider or fabricating mass.

## Procedure

1. Stage the asset and its dependencies so the output tree is self-contained.
2. Ensure each alternate collider composes from its own isolated payload, so a
   selection yields exactly one and never leaks the others (`AV.004`). Colliders
   carry the `proxy`/`guide` purposes, not `render`.
3. Author a `Collision` set on the default prim (or per-part `Collision_<part>`
   sets for scopes that vary independently), each option selecting one collider
   payload, plus a root default selection (`AV.002`, `AV.003`).
4. Keep the render mesh, semantics, and provenance on the neutral prim outside
   every variant. Every option must hold the authored-default collision envelope
   (`AV.006`) and leave the visual envelope unchanged (`AV.005`) within
   `asset_variants.ENVELOPE_TOLERANCE_M`: a collision variant may change
   simulation fidelity but must not resize the collider footprint or move the
   visible mesh (`AV.007`).
5. Authored mass/center-of-mass/inertia must be present and identical across all
   collider options; derive them from the asset and never fabricate them to pass
   (`AV.009`). Record the discovery metadata (below) and validate.

## Discovery metadata

Record every set under
`customLayerData.SimReady_Metadata.Variants.Collision.<variantSetName>` with keys
`prim` (the default prim path), `variantSetName`, `category = "Collision"`,
`default` (one authored option), and `impactClass = "simulation-affecting"`
(`AV.001`, `AV.007`). The gate is driven by this metadata: a category-named set on
the default prim but absent here fails `AV.001`, and a set with no metadata is
invisible to the gate. Never author or reuse the reserved `Physics` category (that
belongs to the runtime_variants `RV.*` contract, which switches whole physics
runtimes, not collider approximations). A scope with one collider carries no set
(`AV.008`).

## Composition topology

- **Stable part, swappable child.** Every varied body is a stable `Xform` defined
  in the root layer that owns the part's transform, physics, mass, semantics, and
  its render mesh; each collider option composes only as a **child** of that prim.
  Never let an option's payload re-define the part prim itself: that conflates the
  swappable collider with the part's transform and mass, so an authored or
  interactive pose is dropped and the authored mass can shift when the selection
  changes. Collider options share a prim type, so they may reuse one child name;
  the invariant `AV.010` enforces is that no prim present across options changes
  its type or authored transform.

Author one `Collision_<part>` set per independently varied body on the default
prim; each option carries only a payload arc to one collider cell (`AV.004`
per-part purity). A single whole-body swap uses the master `Collision` set. When
collision options must coexist with a per-part mesh or representation axis, keep
each axis's per-part sets at root and payload per-cell wrappers that surface the
other axis's set; `AV.004` checks only root-layer sets, so a payload-surfaced set
is governed by composition and each part resolves exactly one active cell.

## Validate

Run the bundled gate on the staged root with the Python that has the SimReady
tier installed:

```
python assets/scripts/validate_asset_variants.py <staged_root.usda> --diagnose --report <out>/av-report.json
```

It runs AV.001-AV.010, prints PASS/FAIL per requirement, and with `--diagnose`
lists each option's composed visual/collision envelope (flagging drift beyond the
tolerance) plus the collider/mass inventory used for the applicability and
`AV.009` checks. Iterate to all-green and preserve the report with the staged
output.

## Envelope mismatches

When `--diagnose` flags an option that resizes the collision envelope or moves the
visual envelope, name the axis and cause precisely. Reconciling a real mismatch
means editing collider geometry, which is outside this skill's default scope:
report the exact drift and get explicit authorization before any geometry edit.

## Runtime evidence

When requested, run `collision_variation` through simready-evaluate in Kit/Isaac;
preserve metrics/captures and report runtime unavailability honestly. Profile
conformance requires the feature's other gates too.
