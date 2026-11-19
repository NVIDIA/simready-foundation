---
name: simready-foundation-conform-fet-014-standard
description: Organize existing alternate render meshes of one asset into visual-only MeshVariant variant sets with discovery metadata, preserving both the visual and collision envelopes, then validate AV.001-AV.010 with the bundled gate on staged output.
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - variants
---

# Conform Mesh Variant

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

Targets `FET014_MeshVariant.0-1-0`, which carries the asset-variation
contract `AV.001`-`AV.010` and depends on
`FET001_MinimalPlaceableVisual.1-0-1`. Read the feature doc and the
`asset_variants` capability (AV.* requirement pages) first. Use
`simready.foundation.tier_core.asset_variants` to read, recompose, and measure.
Work on a staged copy in the requested output directory and never mutate the
source. Do **not** author geometry: this skill organizes render meshes that
already exist (for example a high-poly and a decimated low-poly mesh, or two
authored shape options of the same object).

## When it applies

FET014 applies only when two or more alternate render meshes of the asset already
exist for a scope. If only one render mesh exists for a scope, that scope carries
no set; if the whole asset has only one mesh, report FET014 not applicable rather
than decimating one to invent a second.

## Procedure

1. Stage the asset and its dependencies (root, payloads, materials, textures) so
   the output tree is self-contained.
2. Ensure each alternate render mesh composes from its own isolated payload, so a
   selection yields exactly one and never leaks the others (`AV.004`).
3. Author a `MeshVariant` set on the default prim (or per-part
   `MeshVariant_<part>` sets for scopes that vary independently), each option
   selecting one render-mesh payload, plus a root default selection (`AV.002`,
   `AV.003`).
4. Compose each render mesh as a **child** of a stable part prim, never as the
   part prim itself. The part prim (a root-layer `Xform` such as `/Asset/Lid`)
   owns the part's transform (pose, pivot), collision, physics, mass, semantics,
   and provenance; each option brings only its mesh in as a child (for example
   `/Asset/Lid/Geo`). This keeps an authored or interactive transform (an opened
   lid) applied to whichever mesh is active after a switch. Every option must hold
   the authored-default visual envelope (`AV.005`) AND leave the collision
   envelope unchanged (`AV.006`) within `asset_variants.ENVELOPE_TOLERANCE_M`; a
   mesh option that moves collision is not visual-only (`AV.007`).
5. Record the discovery metadata (below) and validate with the bundled gate.

## Discovery metadata

Record every set under
`customLayerData.SimReady_Metadata.Variants.MeshVariant.<variantSetName>` with
keys `prim` (the default prim path), `variantSetName`, `category =
"MeshVariant"`, `default` (one authored option), and `impactClass =
"visual-only"` (`AV.001`, `AV.007`). The gate is driven by this metadata: a
category-named set on the default prim but absent here fails `AV.001`, and a set
with no metadata is invisible to the gate (a vacuous pass). Never author or reuse
the reserved `Physics` category. A scope with one mesh carries no set (`AV.008`).

## Composition topology

- **Stable part, swappable child.** Every varied scope is a stable `Xform`
  defined in the root layer that owns the part's transform, collision, physics,
  and semantics; each option composes its mesh as a **child** of that prim
  (`over "<Part>" { def "Geo" ( ... ) }`, resolving to `/Asset/<Part>/Geo`).
  Never let the option re-define the part prim itself: that conflates the swapped
  mesh with the part's transform and physics, so an authored or interactive pose
  (an opened lid) is dropped when the selection changes. `MeshVariant` options
  are all render meshes (one prim type), so they may reuse one child name
  (`Geo`); if this scope also carries a `Representation` axis whose options differ
  in type (mesh vs splat), give those distinct child names (`Geo_mesh` /
  `Geo_splat`) so the switch is a clean subtree add/remove rather than an
  in-place type change (see the FET013 skill).
- **Per-part sets.** Author one `MeshVariant_<part>` set per independently varied
  scope on the default prim; each option carries only a payload arc that lands
  one mesh cell under the varied scope's child geometry prim (`AV.004` per-part
  purity). A single whole-asset mesh swap uses the master `MeshVariant` set.
- **Coexisting with a representation axis.** When the same parts also carry a
  `Representation` axis (mesh vs splat), keep `MeshVariant_<part>` as the root
  sets and let each option payload a per-cell wrapper that surfaces the
  representation set. `AV.004` checks only root-layer sets, so a payload-surfaced
  set is governed by composition, and each part is driven by exactly one active
  cell, so no two options overlap. Two representation topologies are possible:
  - **Whole-asset only.** Have every wrapper surface a single shared-name
    `Representation` set; USD composes them into one master that switches all
    parts together.
  - **Per-part + master.** Have each part's wrappers surface a per-part
    `Representation_<part>` set, and add a master `Representation` set that drives
    them (see the FET013 skill's master-drive topology) for an independent
    per-part switch plus a whole-asset toggle. List `Representation` **before**
    the `MeshVariant_<part>` sets in `variantSets` so the master's child
    selections outrank the wrapper defaults; otherwise the master is inert.
- **Boundability.** Bring any non-mesh boundable (such as a Gaussian splat in a
  coexisting representation) in through a **typeless** `def` so its boundable type
  and authored `extent` survive; a typed `Xform` override hides the extent and
  breaks the envelope checks.

## Validate

Run the bundled gate on the staged root with the Python that has the SimReady
tier installed:

```
python assets/scripts/validate_asset_variants.py <staged_root.usda> --diagnose --report <out>/av-report.json
```

It runs AV.001-AV.010, prints PASS/FAIL per requirement, and with `--diagnose`
lists each option's composed visual/collision envelope (flagging drift beyond the
tolerance) plus the collider/mass inventory. A "no Variants metadata declared"
note means the pass is vacuous, not conformant. Iterate to all-green and preserve
the report with the staged output.

## Envelope mismatches

When `--diagnose` flags a mesh option whose visual or collision envelope exceeds
the tolerance, name the axis and cause precisely. Reconciling a real mismatch
means editing geometry, which is outside this skill's default scope: report the
exact drift and get explicit authorization before any geometry edit.

## Runtime evidence

When requested, run `mesh_variation` through simready-evaluate in Kit/Isaac;
preserve metrics/captures and report runtime unavailability honestly. Profile
conformance requires the feature's other gates too.
