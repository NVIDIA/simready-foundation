# FET001 Requirement Repair Map

Use this reference when a validation report or inspection identifies `FET001_BASE_NEUTRAL` failures. Load the selected JSON manifest first:

- `FET_001_base_neutral-0.1.0-minimal.json`
- `FET_001_base_neutral-1.0.0-minimal.json`

## Version 0.1.0 Requirements

| Requirement | What It Means | Safe Repair | Block When |
|---|---|---|---|
| `AA.001` | Asset references use anchored paths such as `./` or safe `../`, not absolute paths or resolver search paths. | Localize dependencies under the staged asset root and rewrite asset paths to anchored relative paths. | A dependency is outside the package and cannot be copied or legally/semantically owned by the asset. |
| `AA.002` | Referenced files use supported USD, image, and audio extensions. | Convert or replace unsupported support files with supported formats when conversion is lossless enough and references can be updated. | Conversion is lossy, unsupported by local tools, or would change material/geometry meaning. |
| `UN.001` | The stage declares `upAxis`. | Author `upAxis = "Z"` or the selected profile's required up axis when the asset orientation is already compatible. | The asset is authored Y-up or unknown-up and needs a corrective rotation. |
| `UN.002` | The stage declares `metersPerUnit`. | Author the known source unit value when missing; use converter/source metadata when available. | The source unit is unknown and cannot be inferred from metadata or expected bounds. |
| `UN.007` | The stage declares `metersPerUnit = 1.0`. | Preserve physical size by rescaling linear data, or by adding an equivalent root-scale normalization in the same staged USD when that does not conflict with existing root transforms. | Rescaling would require unstaged external layers, physical size cannot be validated, or a root scale would violate the selected feature/profile contract. |
| `VG.001` | The asset contains at least one imageable geometry prim with render/default purpose. | Fix purpose if geometry exists but is hidden by an incorrect purpose. | No geometry exists; this is an upstream conversion/export failure. |
| `HI.004` | The stage has a valid `defaultPrim`. | Set `defaultPrim` to the single valid asset root prim. | Multiple plausible roots exist and no root can be inferred safely. |

## Version 1.0.0 Additional/Changed Requirements

| Requirement | What It Means | Safe Repair | Block When |
|---|---|---|---|
| `UN.006` | The stage declares `upAxis = "Z"`. | Set Z-up when the asset already appears Z-up; otherwise add a corrective root transform and validate orientation. | Orientation cannot be inferred or rotating would break authored animation/physics. |
| `VG.MESH.001` | Geometry is represented as non-subdivided `UsdGeomMesh`. | Set `subdivisionScheme = "none"` on meshes when appropriate; rerun converter to mesh/polygon output for CAD, curves, points, or implicit shapes. | Non-mesh source must be tessellated and no reliable converter setting is available. |
| `VG.002` | Boundable geometry has valid authored extents. | Recompute extents for local editable meshes using USD bounds/extent APIs after any rescale or topology change. | Geometry is composed from external layers that are not editable or bounds cannot be computed. |
| `VG.014` | Mesh topology is valid. | Remove or repair obviously degenerate faces and invalid indices only when the intended mesh remains clear. | Topology repair requires remeshing, source CAD, or visual/manual review. |
| `VG.029` | Mesh face winding correctly represents front/back orientation. | Flip face order only when all faces are consistently inverted and validation/visual review confirms the fix. | Winding problems are mixed or require semantic surface knowledge. |
| `VG.025` | Asset origin/placement is correct for the asset type. | For a known ground-resting prop, move geometry under the root so the base center is at the origin and the root transform remains neutral. | The asset's placement convention is subjective or depends on attachment/joint behavior. |
| `VG.027` | Non-subdivided meshes have normals. | Generate or preserve `primvars:normals` for editable meshes when smoothing intent can be inferred. | Normals require source shading intent or high-quality remeshing. |
| `VG.028` | Mesh normals are finite, nonzero, unit length, sized correctly, and aligned with winding. | Normalize clean normals and regenerate obviously invalid normals from topology when the intended surface is clear. | Normals/winding conflict cannot be resolved without visual/source review. |
| `HI.001` | All asset content lives under one root hierarchy. | Wrap multiple root prims under one Xform or compose them under a new root in a staged wrapper. | Moving roots breaks references, materials, animations, or payload semantics. |
| `HI.003` | The root prim is xformable. | Use an Xform wrapper root when the current root is not xformable. | The root is a non-transformable schema with authored semantics that should not be wrapped blindly. |

## Unit Normalization Details

For `UN.007`, the physical size preservation formula is:

```text
scale_factor = old_meters_per_unit / 1.0
```

Examples:

| Original `metersPerUnit` | Meaning | Size-preserving factor when normalizing to meters |
|---|---|---|
| `0.001` | millimeters | `0.001` |
| `0.01` | centimeters | `0.01` |
| `1.0` | meters | `1.0` |

Do not simply change `metersPerUnit` from `0.001` to `1.0` on CAD output unless the coordinates have already been converted to meters. That changes the physical interpretation by 1000x.

## Forward-Tested Scenario

After `simready-foundation-conform-fet-000-core` repairs metadata on a converted CAD-derived asset, profile validation may select `FET001_BASE_NEUTRAL@0.1.0` and fail only `UN.007`: stage `metersPerUnit = 0.001`, not `1.0`.

The passing repair copied the FET000 USD into a fresh staged file, set stage `metersPerUnit = 1.0`, and added root xform op `xformOp:scale:meter_normalization` with a per-axis scale value of `0.001`. `FET000_CORE` and `FET001_BASE_NEUTRAL` both passed afterward.

A first wrapper attempt was rejected by current validators: an extra USD payload under `simready_usd` failed `NP.005`, while moving the payload to `../payloads/...` failed `AA.001` as outside the asset root. Prefer same-file normalization or data-space rescaling for this profile unless the package layout contract changes.

## Report Template

For each repair attempt, record:

| Field | Meaning |
|---|---|
| `requirement_id` | Requirement being repaired. |
| `status` | `repaired`, `already_passed`, `blocked`, or `failed`. |
| `old_value` and `new_value` | Unit, axis, hierarchy, or geometry values changed. |
| `scale_factor` | Required for any unit normalization. |
| `bounds_before` and `bounds_after` | Required when physical size is expected to be preserved. |
| `outputs` | Files written or references changed. |
| `reason` | Short explanation, especially for blocked items. |
