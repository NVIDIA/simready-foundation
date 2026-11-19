# Asset-Variation Conformance — obs_electricians_large_tool_box_a02

This sample provides mesh and splat representations with independently selectable
base and lid meshes.

## Result

`sm_obs_electricians_large_tool_box_a02.usda` passes static validation for
`Robotics-Prop@3.0.0`, including `FET001_MinimalPlaceableVisual.1-0-1`,
and the AV.001–AV.010 checks used by
`FET013_MultiRepresentationVisual.0-1-0` and `FET014_MeshVariant.0-1-0`.

See `av-validation-report.txt` for the generated per-rule results. The root
layer carries the current profile validation receipt. The FET013/FET014 runtime
variation tests have not been executed.

## Topology

The root `/Toolbox` (default prim, `kind=component`) hosts three variation sets,
all declared under `customLayerData.SimReady_Metadata.Variants`:

| Set | Category | Options | Impact |
|---|---|---|---|
| `MeshVariant_base` | MeshVariant | base_var_001, base_var_002 | visual-only |
| `MeshVariant_lid` | MeshVariant | lid_var_001, lid_var_002, lid_var_003 | visual-only |
| `Representation` | Representation | Original, Splat | visual-only |

- `MeshVariant_base` / `MeshVariant_lid` are per-part sets; each option carries
  **only a payload arc** to a per-cell wrapper under `wrappers/` (AV.004 purity).
- Each wrapper surfaces a master `Representation` set. USD composes the
  same-named set from every active wrapper into one `Representation` set on
  `/Toolbox` that switches all parts between the mesh (`Original`) and gaussian
  splat (`Splat`) representation together.
- Each part is driven by exactly one active mesh-variant wrapper, so no two
  representations/cells overlap in any composed selection.

## Splat clip (authorized edit, staged only)

The mesh and splat representations must hold the same visual/collision envelope
within 1 mm (AV.005/006/007). As delivered, every **base** splat capture
included low-opacity gaussians ~2.5 mm **below** the mesh floor (z < 0 — ground/
shadow contamination), making the splat envelope 2.1 mm taller in Z than the
mesh. With user authorization, the staged splat copies in `payloads/` drop the
sub-floor gaussians (z < 0) and recompute their authored `extent`:

- `base_var_001_splat.usdc`: 395 gaussians dropped (of 40000)
- `base_var_002_splat.usdc`: 417 gaussians dropped (of 40000)

Lid splats and all X/Y axes were already within tolerance and are unchanged. The
**source** splats are untouched; the long-term fix is to re-crop the capture to
the toolbox floor at authoring time.

## FET015 / FET016 — not applicable

- **FET015_CollisionVariant** — not applicable. The asset authors no
  `UsdPhysics.CollisionAPI` and no `UsdPhysics.MassAPI` on any prim in any
  option, so there are no collider representations to vary (and AV.009 would have
  no authored mass/COM/inertia to hold invariant). A collision variation cannot
  be fabricated without inventing colliders and mass.
- **FET016_AppearanceVariant** — not applicable. The only appearance change
  (lid yellow → red) is bundled into the `MeshVariant_lid` geometry: `lid_var_002`
  and `lid_var_003` bind `opaque__plastic__red_02`, while `lid_var_001`/base bind
  `opaque__plastic__yellow_02`. There is no standalone material-rebind set that
  swaps appearance on fixed geometry, so there is no independent Appearance
  variation to validate.
