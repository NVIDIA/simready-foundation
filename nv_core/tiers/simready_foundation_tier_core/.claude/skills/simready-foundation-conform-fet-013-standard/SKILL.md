---
name: simready-foundation-conform-fet-013-standard
description: Organize two or more existing visual representations of one asset into composable Representation variant sets with discovery metadata, preserving the visual envelope, then validate AV.001-AV.010 with the bundled gate on staged output.
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - variants
---

# Conform Multi-Representation Visual

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

Targets `FET013_MultiRepresentationVisual.0-1-0`, which carries the
asset-variation contract `AV.001`-`AV.010` and depends on
`FET001_MinimalPlaceableVisual.1-0-1`. Read the feature doc and the
`asset_variants` capability (AV.* requirement pages) first. Use
`simready.foundation.tier_core.asset_variants` to read, recompose, and measure.
Work on a staged copy in the requested output directory and never mutate the
source. Do **not** author geometry: this skill organizes representations that
already exist (for example a render mesh and a Gaussian-splat capture of the same
object) into variant sets.

## When it applies

FET013 applies only when the asset already carries two or more interchangeable
whole-object visual representations. If only one exists, report FET013 not
applicable rather than inventing a second.

## Procedure

1. Stage the asset and its dependencies (root, payloads, materials, textures) so
   the output tree is self-contained.
2. Ensure each representation composes from its own isolated payload, so a
   selection yields exactly one representation and never leaks the others
   (`AV.004`).
3. On the default prim author a `Representation` variant set whose options select
   the representations, and author a root default selection (`AV.002`, `AV.003`).
4. Compose each representation as a **child** of a stable part prim, never as the
   part prim itself. The part prim (a root-layer `Xform` such as `/Asset/Lid`)
   owns the part's transform (pose, pivot), physics, collision, mass, semantics,
   grasp, and provenance; each option brings only its representation geometry in
   as a child. Because representations differ in prim **type** (a render mesh
   versus a Gaussian splat), give each option its own child name -- `Geo_mesh`
   for the mesh, `Geo_splat` for the splat -- so a switch adds and removes whole
   subtrees rather than mutating one `Geo` prim's type in place; the in-place
   type swap is a resync some renderers handle poorly, leaving a ghost of the
   inactive representation on screen until reload. This keeps the switch
   visual-only and honest (`AV.007`), keeps an authored or interactive transform
   (an opened lid) applied to whichever representation is active after a switch,
   and leaves the collision envelope unchanged (`AV.006`). Every option must hold
   the authored-default visual envelope within `asset_variants.ENVELOPE_TOLERANCE_M`
   (`AV.005`).
5. Record the discovery metadata (below) and validate with the bundled gate.

## Discovery metadata

Record every set under
`customLayerData.SimReady_Metadata.Variants.Representation.<variantSetName>` with
keys `prim` (the default prim path), `variantSetName`, `category =
"Representation"`, `default` (one authored option), and `impactClass =
"visual-only"` (`AV.001`). The gate is driven by this metadata: a category-named
set authored on the default prim but absent here fails `AV.001`, and a set with
no metadata is invisible to the gate (a vacuous pass). Never author or reuse the
reserved `Physics` category. A scope with a single representation carries no set
(`AV.008`).

## Composition topology

- **Stable part, swappable child.** Every varied scope is a stable `Xform`
  defined in the root layer that owns the part's transform, physics, collider,
  and semantics; each option composes its geometry as a **child** of that prim
  (`over "<Part>" { def "Geo_mesh" ( ... ) }` / `{ def "Geo_splat" ( ... ) }`
  inside the option, resolving to `/Asset/<Part>/Geo_mesh` or `.../Geo_splat`).
  Never let the option's payload/reference re-define the part prim itself: that
  conflates the swappable geometry with the part's transform and physics, so an
  authored or interactive pose (an opened lid) is dropped when the selection
  changes. Keep the part prim's collider and physics outside every variant
  section. Give the mesh and splat **distinct child names** so a switch removes
  one subtree and adds the other (clean renderer teardown) instead of mutating a
  shared `Geo` prim's type in place, which can leave a ghost of the inactive
  representation on screen until reload.
- **Single axis.** Author the `Representation` set directly on the default prim;
  each option carries only a payload arc that lands its representation under the
  varied scope's child geometry prim. For scopes that vary independently, author
  per-part `Representation_<part>` sets instead.
- **Master drive with per-part override.** To offer a whole-asset toggle *and*
  independent per-part control, author a master `Representation` set on the
  default prim whose options author the per-part `Representation_<part>` child
  selections (`AV.004` allows a master option to author only child selections).
  The driven per-part sets then omit their own root default: `AV.002` accepts a
  per-part set whose default a same-category master supplies. A consumer
  switches the whole asset through the master and overrides one part by
  authoring a stronger per-part selection, which wins over the master.
  - **Ordering is load-bearing.** Variant-set order sets relative strength -
    earlier in the prim's `variantSets` composes stronger - and a per-part set
    surfaced through a `MeshVariant_<part>` payload carries the wrapper's own
    default selection. List `Representation` **before** the per-part-bearing
    sets so the master's child selections outrank those wrapper defaults; a
    master ordered after them is inert. The `AV.002` gate now catches an inert
    master (it composes each master option and fails when the driven per-part
    selection never changes), but order it correctly from the start. A direct
    root/session per-part selection outranks any variant's child selection,
    which is what lets a per-part override win while the master still drives the
    default.
- **Entangled axes.** When a representation axis must coexist with an independent
  per-part axis on the same geometry (for example a `MeshVariant_<part>` set that
  also drives those parts), author the per-part axis as root sets whose options
  each payload a per-cell wrapper, and have each wrapper surface the
  `Representation` set. USD composes the same-named `Representation` set from
  every active wrapper into one master set on the default prim. `AV.004` inspects
  only root-layer-authored sets, so a set surfaced through a payload is governed
  by composition rather than purity; each part is driven by exactly one active
  cell, so the two payload-bearing axes coexist with no overlap. Each wrapper's
  `Representation_<part>` option still composes its mesh/splat as a distinctly
  named child (`Geo_mesh` / `Geo_splat`) of the stable part prim
  (`over "<Part>" { def "Geo_mesh" ( ... ) }`), which is defined with its
  transform, physics, and collider in the root layer; the wrapper never
  re-defines the part prim.
- **Non-mesh representations.** A Gaussian splat is a `UsdGeomBoundable` with an
  authored `extent`. Bring it in through a **typeless** `def` so the referenced
  prim type (and its boundable extent) flows through. A typed `Xform` override
  strips the boundable type, so `BBoxCache` returns no bound and
  `AV.005`/`AV.006`/`AV.007` misread the option.

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

When you authored a master that drives per-part sets, the `AV.002` gate already
fails an inert (misordered) master. To inspect the drive yourself, open the
staged stage, select each master option on the **session** layer, and read the
composed per-part selection with `UsdVariantSet.GetVariantSelection()` (on a
composed stage it reflects the master's drive) or inspect the composed geometry
(mesh vs splat). Confirm a per-part override wins by additionally selecting one
`Representation_<part>` and seeing it beat the master.

## Envelope mismatches

When `--diagnose` flags an option whose visual or collision envelope exceeds the
tolerance, name the axis and cause precisely (for example a splat capture whose
points extend past the mesh on one axis). Reconciling a real mismatch means
editing geometry (re-cropping or cleaning the oversized representation), which is
outside this skill's default scope: report the exact drift and get explicit
authorization before any geometry edit.

## Runtime evidence

When requested, run `representation_variation` through simready-evaluate in
Kit/Isaac; preserve metrics/captures and report runtime unavailability honestly.
A representation that is itself a Gaussian splat should also satisfy
`FET012_GaussianSplat`; FET013 mandates no representation technology. Profile
conformance requires the feature's other gates too.
