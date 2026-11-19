---
name: simready-foundation-conform-fet-016-standard
description: Organize existing alternate material looks of one asset into visual-only Appearance variant sets with discovery metadata, rebinding materials without moving geometry, then validate AV.001-AV.010 with the bundled gate on staged output.
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - variants
---

# Conform Appearance Variant

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

Targets `FET016_AppearanceVariant.0-1-0`, which carries the
asset-variation contract `AV.001`-`AV.010` and depends on the material contract
(`FET006`). Read the feature doc and the `asset_variants` capability (AV.*
requirement pages) first. Use `simready.foundation.tier_core.asset_variants` to
read, recompose, and measure. Work on a staged copy in the requested output
directory and never mutate the source. Do **not** author geometry and do **not**
touch collision or mass: an appearance variant is a pure material re-bind over
shared geometry.

## When it applies

FET016 applies only when two or more alternate material looks bind to the **same**
geometry. If the look differences are instead bundled into distinct geometry
(for example a red mesh and a yellow mesh that are separate `MeshVariant` options),
the appearance change rides on that mesh axis and there is no standalone
material-rebind set: report FET016 not applicable rather than inventing a second
material or splitting geometry. Confirm by inspecting the material bindings per
option; if swapping the look requires swapping geometry, it is not an Appearance
variation.

## Procedure

1. Stage the asset and its dependencies (root, payloads, materials, textures) so
   the output tree is self-contained.
2. Collect the alternate looks that already exist. An appearance option switches
   only the material binding (and, where needed, its isolated material payload);
   the bound geometry is shared across options (`AV.004`).
3. Author an `Appearance` set on the default prim (or per-part
   `Appearance_<part>` sets for scopes that vary independently), each option
   binding one look, plus a root default selection (`AV.002`, `AV.003`).
4. Keep geometry, collision, physics, mass, semantics, and provenance identical
   across options. Every option must leave BOTH the visual envelope (`AV.005`) and
   the collision envelope (`AV.006`) unchanged within
   `asset_variants.ENVELOPE_TOLERANCE_M`; only the bound material changes
   (`AV.007`).
5. Record the discovery metadata (below) and validate with the bundled gate.

## Discovery metadata

Record every set under
`customLayerData.SimReady_Metadata.Variants.Appearance.<variantSetName>` with keys
`prim` (the default prim path), `variantSetName`, `category = "Appearance"`,
`default` (one authored option), and `impactClass = "visual-only"` (`AV.001`,
`AV.007`). The gate is driven by this metadata: a category-named set on the default
prim but absent here fails `AV.001`, and a set with no metadata is invisible to the
gate. Never author or reuse the reserved `Physics` category. A scope with one look
carries no set (`AV.008`). Do not fabricate mass or physical properties (`AV.009`).

## Composition topology

- **Stable part, swappable binding.** The geometry is a stable prim defined in the
  root layer; an appearance option changes only its material binding (and any
  isolated material payload), never the geometry prim's type or transform. Do not
  re-define the bound geometry from inside a variant: `AV.010` fails any prim that
  changes its type or authored transform across a set's options, and a pure
  material rebind leaves both untouched by construction.

Author one `Appearance_<part>` set per independently varied binding on the default
prim; each option authors only the material rebind for the shared geometry
(`AV.004`). A single whole-asset look swap uses the master `Appearance` set. When
appearance options coexist with a per-part mesh or representation axis, keep each
axis's per-part sets at root and payload per-cell wrappers that surface the other
axis's set; `AV.004` checks only root-layer sets, so a payload-surfaced set is
governed by composition and each part resolves exactly one active cell.

## Validate

Run the bundled gate on the staged root with the Python that has the SimReady
tier installed:

```
python assets/scripts/validate_asset_variants.py <staged_root.usda> --diagnose --report <out>/av-report.json
```

It runs AV.001-AV.010, prints PASS/FAIL per requirement, and with `--diagnose`
lists each option's composed visual/collision envelope (both must stay within the
tolerance for an appearance rebind) plus the collider/mass inventory. A "no
Variants metadata declared" note means the pass is vacuous, not conformant.
Iterate to all-green and preserve the report with the staged output.

## Runtime evidence

When requested, run `appearance_variation` through simready-evaluate in
Kit/Isaac, which also confirms consecutive looks render distinctly; preserve
metrics/captures and report runtime unavailability honestly. Profile conformance
requires the feature's other gates too.
