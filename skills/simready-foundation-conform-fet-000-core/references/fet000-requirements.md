# FET000 Requirement Repair Map

Use this reference when a validation report or inspection identifies FET000_CORE failures. The current checked-in manifest is `FET_000_base_neutral-0.1.0-core.json`; if a newer manifest is selected by a profile, load and follow that version first.

## Requirement Map

| Requirement | What It Means | Safe Repair | Block When |
|---|---|---|---|
| `NP.002` | USD file names use lowercase, portable names with valid USD extensions. | Stage a renamed copy using lowercase letters, digits, underscores, hyphens, dots for version suffixes, and `.usd`, `.usda`, `.usdc`, or `.usdz`. Update internal references to the renamed file when necessary. | The filename is part of a published package contract and renaming would break external callers. |
| `NP.003` | Asset directories are consistently named and organized. | Rename staged folders to lowercase safe names, remove spaces/special characters, and keep logical folders such as `materials`, `textures`, `geometry`, `physics`, or `simready_usd`. | Folder names encode external package or source-control contracts not represented in the staged asset. |
| `NP.004` | File and directory paths stay within target platform limits. | Shorten staged asset root, intermediate folder, and dependency names while preserving extensions and references. Prefer a shorter output root when possible. | A long path comes from an unresolved external dependency that cannot be moved or renamed safely. |
| `NP.005` | Main asset file is one directory below the asset root and its filename contains the asset root name. | Stage as `<asset_root>/<intermediate>/<asset_file>.usd*`, for example `example_asset/simready_usd/example_asset.usda` or `example_asset/simready_usd/sm_example_asset_01.usd`. | The selected asset is a package member, payload layer, or support layer rather than the main asset entrypoint. |
| `NP.006` | Asset metadata is stored in the USD custom layer data or in a same-directory sidecar JSON file. | Prefer `apply-simready-foundation-metadata` when available; it stages the USD, writes root layer `customLayerData['SimReady_Metadata']`, and creates `<usd_stem>.json` beside the main USD file. Otherwise author equivalent metadata directly. | The asset format cannot be edited in place, such as a sealed `.usdz`, and no unpacked or sidecar strategy is acceptable. |
| `NP.007` | References, payloads, sublayers, and asset paths are relative, not absolute or UNC paths. | Rewrite to relative paths using `/` separators after the dependency is inside or under the staged asset root. Update USD composition arcs and authored asset-valued attributes. | The target file is outside the package and cannot be copied or represented portably. |
| `NP.008` | All asset, reference, payload, and sublayer paths resolve. | Copy missing local dependencies into the staged package when their source path is known, then rewrite references. Remove only stale references that are demonstrably unused. | The dependency is missing, remote, licensed separately, or needed for composition semantics. |
| `SR.001` | Root layer `customLayerData` contains required SimReady metadata fields. | Author `SimReady_Metadata`, `asset_name`, `asset_type`, `source_file`, and `usd_date_generated`. Use ISO date format `YYYY-MM-DD`. | Required values are domain-specific and cannot be inferred from the asset, profile, or source path. |
| `HI.010` | The composed asset should not contain undefined prims (`over`) except allowed temporary cases tied to broken references. | Fix missing references first. Convert an over to a defined prim only when the correct type is obvious from the target. Remove orphan overs only when they have no meaningful authored opinions. | The over may become valid after a missing reference/payload is restored, or its intended prim type cannot be inferred safely. |

## Ordering Notes

Repair path and layout failures before metadata and asset-path failures because the final staged location controls sidecar names, relative paths, and provenance.

Repair `NP.008` before deleting or changing `HI.010` overs. Undefined prims are often symptoms of missing references or payloads.

`NP.006` and `SR.001` overlap but are not identical. `NP.006` accepts either metadata in root layer custom data or a same-directory sidecar JSON. `SR.001` specifically requires root layer `customLayerData` fields, including `SimReady_Metadata`, `asset_name`, `asset_type`, `source_file`, and `usd_date_generated`.

Current validator code checks for `SimReady_Metadata` with exact capitalization in `customLayerData`, even though some requirement prose mentions `simready_metadata`. Prefer the validator key unless the feature manifest or validator changes.

## Forward-Tested Scenario

A converted CAD-derived asset can fail `FET000_CORE@0.1.0` only on `NP.006` when SimReady metadata is missing. Running `apply-simready-foundation-metadata` on a staged copy should clear `FET000_CORE`; the full selected profile may still fail on non-Core requirements such as units, rigid bodies, multibody physics, or grasp vectors. Treat that outcome as a successful Core repair and a handoff to the next feature-specific skill.

## Report Template

For each repair attempt, record:

| Field | Meaning |
|---|---|
| `requirement_id` | Requirement being repaired. |
| `status` | `repaired`, `already_passed`, `blocked`, or `failed`. |
| `inputs` | Paths and metadata values used. |
| `outputs` | Files written or references changed. |
| `reason` | Short explanation, especially for blocked items. |
