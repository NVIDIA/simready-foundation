# Visual Mesh Merge

| Property | Value |
| --- | --- |
| Capability | `CAP103_VisualMeshMerge.Isaac.0-1-0` |
| Owning tier | Isaac |
| Requirement | [`OPT.002`](../rules_and_reqs/isaac_sim/optimizations/requirements/rigid-body-no-multiple-visual-meshes.md) |
| Dependencies | None |
| Profile | [Asset-Optimization@1.0.0](../profiles/asset-optimization.md) |

## Pass condition

Each rigid body owns at most one eligible visual mesh.

The validator groups meshes by their nearest rigid-body owner. Eligible meshes
are visible, have default or render purpose, carry no PhysicsCollisionAPI, and
are not instance proxies. Nested bodies own their meshes independently.

The check reads one composed USD stage with a default prim. An asset with no
applicable meshes passes.

## Validate and repair

1. Run `simready-validate --profile Asset-Optimization --version 1.0.0 asset.usd`
   and inspect `OPT.002`.
2. If this check passes, leave the asset unchanged.
3. If it fails, run `rigid_body_visual_mesh_merge` on a staged copy.
4. Save, reopen, and validate again. Report repair blockers with the affected
   prim and missing precondition.

The adapter uses usd-optimize 1.4 or later to merge each eligible group. It keeps
face materials and the surviving mesh's non-conflicting properties, as described
in `OPT.002`. It leaves collision geometry unchanged.

usd-optimize must share the host's USD runtime and produce one identifiable
merged mesh per group. A failed merge restores the staged output. Run this
adapter after body collapse and collision-schema cleanup when those are selected.

The callback is independently available from
`simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization`.
The installed `simready.feature_adapters` provider declares this capability as
the adapter's exact output, selected by `Asset-Optimization@1.0.0`.

## Validation evidence

Tests cover material bindings, property preservation, multiple merge groups,
and repeatability. Mesh counts are structural evidence; rendering performance
requires a separate measurement.
