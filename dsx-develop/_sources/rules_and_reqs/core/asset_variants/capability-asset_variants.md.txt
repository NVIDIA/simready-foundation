# Asset Variants

Asset Variants (AV) is the shared contract for selectable variations of one
asset: alternate visual representations, mesh geometry, collider fidelity, and
surface appearance, expressed with native USD variant sets and isolated
payloads. A variation changes what the author asked it to change while holding
the asset's **visual envelope** and **collision envelope** invariant, so the
asset still places and simulates the same way in a scenario.

The variation feature family builds on this capability:

- `FET013_MultiRepresentationVisual.0-1-0` (`Representation`)
- `FET014_MeshVariant.0-1-0` (`MeshVariant`)
- `FET015_CollisionVariant.0-1-0` (`Collision`)
- `FET016_AppearanceVariant.0-1-0` (`Appearance`)

Each feature inlines `AV.001`-`AV.010` and adds its category's content
requirements. `FET013`, `FET014`, and `FET016` are `visual-only`; `FET015` is
the only `simulation-affecting` member and additionally holds mass, center of
mass, and inertia explicitly authored and invariant across its options
(`AV.009`).

The variant sets live on the asset's default (root) prim, mirroring the
physics-runtime pattern in `runtime_variants`. A category may expose a **master**
switch plus **per-part** switches, all on the root prim. Each set is discoverable
under `customLayerData.SimReady_Metadata.Variants.<Category>`. The reserved
`Physics` category belongs to `runtime_variants` and is never reused here.

## Authoring topology

A variation swaps a **geometry child of a stable part prim**, never the part prim
itself. Each varied scope is a stable `Xform` (for example `/Asset/Lid`) that
owns the part's transform (pose and pivot), physics, collider, and semantics; an
option composes its representation or mesh as a child of that prim (for example
`/Asset/Lid/Geo`). The stable part prim is defined in the asset's root layer, not
by the variant, so it persists across every selection.

When options differ in prim **type** at the same scope -- most often a render
mesh versus a Gaussian splat on a `Representation` axis -- give each option its
own child prim name (for example `Geo_mesh` and `Geo_splat`) rather than
redefining one shared `Geo` prim with a different type per option. Switching then
adds and removes whole child subtrees, which a renderer tears down cleanly;
mutating a single prim's type in place is a resync some Hydra versions handle
poorly, leaving a ghost of the inactive representation on screen until reload.
Same-type options (two render meshes on a `MeshVariant` axis) may reuse one child
prim name.

This keeps authored or interactive transforms applied to whichever option is
active: opening a lid rotates `/Asset/Lid`, and switching the lid's mesh or
representation leaves that rotation on the parent while the new geometry inherits
it. It also makes the envelope and impact invariants (`AV.005`-`AV.007`) hold by
construction, because the collider and physics live on the stable prim outside
every variant section. Redefining the part prim from inside the variant instead
conflates the swappable geometry with the part's transform and physics, so a
selection change drops them. `AV.010` enforces this topology: it fails any prim
that changes its type or authored transform across a set's options, so a variation
may only add or remove geometry leaves under a stable part prim.

```{toctree}
:maxdepth: 1

Requirements <requirements>
```
