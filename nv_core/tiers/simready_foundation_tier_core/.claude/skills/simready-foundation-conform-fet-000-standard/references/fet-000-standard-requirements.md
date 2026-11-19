# CAP000_Core Requirement Repair Map

Use this reference when a validation report or inspection identifies `CAP000_Core` failures. Load the exact manifest selected by the profile:

- `CAP000_Core.0-2-0`: `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.0-2-0.json`
- `CAP000_Core.0-1-0`: `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.0-1-0.json`

This reference mirrors the requirement lists in `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.md` and should stay synchronized with that feature page and manifests. `NP.006` and `SR.001` apply only to version `CAP000_Core.0-1-0`.

## Requirement Map

| Requirement | What It Means | Safe Repair | Block When |
|---|---|---|---|
| `NP.002` | USD file names use lowercase, portable names with valid USD extensions. | Stage a renamed copy using lowercase letters, digits, underscores, hyphens, dots for version suffixes, and `.usd`, `.usda`, `.usdc`, or `.usdz`. Update internal references to the renamed file when necessary. | The filename is part of a published package contract and renaming would break external callers. |
| `NP.003` | Asset directories are consistently named and organized. | Rename staged folders to lowercase safe names, remove spaces/special characters, and keep logical folders such as `materials`, `textures`, `geometry`, `physics`, or `simready_usd`. | Folder names encode external package or source-control contracts not represented in the staged asset. |
| `NP.004` | File and directory paths stay within target platform limits. | Shorten staged asset root, intermediate folder, and dependency names while preserving extensions and references. Prefer a shorter output root when possible. | A long path comes from an unresolved external dependency that cannot be moved or renamed safely. |
| `NP.005` | The folder holding the main asset file contains no other USD file. | Move or remove any extra `.usd`/`.usda`/`.usdc`/`.usdz` file sharing a folder with the main asset file; relocate it under a supporting subfolder (e.g. `materials/`, `payloads/`) instead. | The selected asset is a package member, payload layer, or support layer rather than the main asset entrypoint. |
| `NP.006` | Version `CAP000_Core.0-1-0` only. Metadata exists in root-layer `SimReady_Metadata` or in `<usd_stem>.json`. | Author `customLayerData.SimReady_Metadata` and/or a same-directory sidecar JSON. | The asset format cannot be edited in place, such as a sealed `.usdz`, and no unpacked or sidecar strategy is acceptable. |
| `NP.007` | References, payloads, sublayers, and asset paths are relative, not absolute or UNC paths. | Rewrite to relative paths using `/` separators after the dependency is inside or under the staged asset root. Update USD composition arcs and authored asset-valued attributes. | The target file is outside the package and cannot be copied or represented portably. |
| `NP.008` | All asset, reference, payload, and sublayer paths resolve. | Copy missing local dependencies into the staged package when their source path is known, then rewrite references. Remove only stale references that are demonstrably unused. | The dependency is missing, remote, licensed separately, or needed for composition semantics. |
| `SR.001` | Version `CAP000_Core.0-1-0` only. Root-layer `customLayerData` directly contains `SimReady_Metadata`, `asset_name`, `asset_type`, `source_file`, and `usd_date_generated`. The checker tests each key for top-level presence independently. | Author all five keys directly in root-layer `customLayerData`. Use ISO date format `YYYY-MM-DD`. A populated `SimReady_Metadata` does not satisfy `SR.001` by itself; the identity strings are top-level siblings of it, not nested inside it. | Required values are domain-specific and cannot be inferred from the asset, profile, or source path. |
| `HI.010` | The composed asset should not contain undefined prims (`over`) except allowed temporary cases tied to broken references. | Fix missing references first. Convert an over to a defined prim only when the correct type is obvious from the target. Remove orphan overs only when they have no meaningful authored opinions. | The over may become valid after a missing reference/payload is restored, or its intended prim type cannot be inferred safely. |

Physics runtime variant requirements (`RV.*`) are **not** part of
`CAP000_Core`. They belong to the runtime Core features `CAP000_Core.PhysX`,
`CAP000_Core.Newton`, and `CAP000_Core.MuJoCo`; repair them through those features, not
this Standard reference.

## Ordering Notes

Repair path and layout failures before metadata and asset-path failures because the final staged location controls sidecar names, relative paths, and provenance.

Repair `NP.008` before deleting or changing `HI.010` overs. Undefined prims are often symptoms of missing references or payloads.

`SR.001` is the root-layer-only Core identity contract on version `CAP000_Core.0-1-0` only.
It reads only the top level of root-layer `customLayerData`; it does not flatten
nested metadata. Placing the identity strings inside `SimReady_Metadata` leaves
`SR.001` failing even when `SimReady_Metadata` is otherwise populated (for
example with `FET013`/`FET014` variant-discovery metadata). The nested and
USD/sidecar-union forms belong to different requirements:
USD/sidecar provenance union, including the no-duplicate-keys rule, is `SR.004`
on `CAP033_SimReadyPackage.0-4-0`. Nested-only provenance is `SR.003` on
`CAP033_SimReadyPackage.0-2-0` / `CAP033_SimReadyPackage.0-3-0`. `NP.006` applies only to version `CAP000_Core.0-1-0`.

## Forward-Tested Scenario

A converted CAD-derived asset can fail `CAP000_Core` only on metadata when SimReady fields are missing. Running `apply-simready-foundation-metadata` on a staged copy should clear `CAP000_Core.0-1-0`; the full selected profile may still fail on non-Core requirements such as units, rigid bodies, multibody physics, or grasp vectors. Treat that outcome as a successful Core repair and a handoff to the next feature-specific skill.

## Report Template

For each repair attempt, record:

| Field | Meaning |
|---|---|
| `requirement_id` | Requirement being repaired. |
| `status` | `repaired`, `already_passed`, `blocked`, or `failed`. |
| `inputs` | Paths and metadata values used. |
| `outputs` | Files written or references changed. |
| `reason` | Short explanation, especially for blocked items. |
