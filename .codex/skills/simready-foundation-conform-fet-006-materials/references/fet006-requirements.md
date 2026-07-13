# FET006 Requirement Repair Map

Use this reference when a validation report or inspection identifies `FET006_BASE_MDL` or `FET006_BASE_USDPREVIEW` failures. Load the selected JSON manifest first:

- `FET_006_base_mdl-0.1.0-mdl_materials.json`
- `FET_006_base_usdpreview-0.1.0-usdpreview_materials.json`

The feature markdown and requirement docs are useful context, but the selected manifest and current validation report decide which IDs are in scope.

## Manifest Requirements

| Feature Variant | Requirements |
|---|---|
| `FET006_BASE_USDPREVIEW@0.1.0` | `VM.BIND.001`, `VM.PS.001` |
| `FET006_BASE_MDL@0.1.0` | `VM.BIND.001`, `VM.BIND.002`, `VM.MAT.001`, `VM.MDL.001`, `VM.MDL.002`, `VM.TEX.001`, `VM.TEX.002` |

## Requirement Map

| Requirement | What It Means | Safe Repair | Block When |
|---|---|---|---|
| `VM.MAT.001` | Every renderable GPrim with default or render purpose must compute a material binding. Guide geometry is skipped. | Bind an existing valid material to unbound renderable prims or a shared ancestor when the assignment is clear. Create a simple fallback material only when the selected variant and user/workflow policy allow it. | No material source exists, the intended material assignment is ambiguous, or the selected MDL profile has no valid MDL material. |
| `VM.BIND.001` | Material bindings must target valid material scopes and remain portable with payload-local or package-local material paths. | Move or copy material prims into the payload/package scope that owns the binding, then update binding targets to valid absolute prim paths within the composed asset. | Moving material definitions would change published composition semantics, references, variants, or shared payload reuse. |
| `VM.PS.001` | `UsdPreviewSurface` shaders must use expected USD input/output types and allowed token values, and token attrs must not be time-sampled. | Fix incorrect attribute types, allowed token values, and accidental token time samples when the intended value is obvious. | The shader network is custom, the value conversion is lossy, or repairing the shader would change visible material behavior without approval. |
| `VM.MDL.001` | MDL shaders with `sourceAsset` implementation must reference a non-empty relative `.mdl` source asset that exists. Relative paths must start with `./`. | Rewrite a known MDL path to package-relative `./...`, copy/stage an existing local MDL file when approved, and keep source asset references resolvable. | The MDL file is missing, external, unlicensed, unavailable, or there is no clear package anchor. |
| `VM.MDL.002` | MDL shaders must use the current schema: `info:implementationSource = "sourceAsset"`, `info:mdl:sourceAsset`, and `info:mdl:materialType`. Deprecated `mdlMaterial`, `module`, and `name` fields should not be used. | Convert deprecated fields to current schema when they map directly to an existing MDL file and material identifier. Keep any validator-required `info:mdl:sourceAsset:subIdentifier` consistent with the same identifier when needed. | The material identifier cannot be determined, multiple MDL materials are plausible, or schema conversion would break runtime behavior. |
| `VM.BIND.002` | Shader input types must match SDR or MDL specifications, and floating input values must not be NaN or Inf. | Correct input types or numeric values only when the target type/value is clear from the shader spec, source data, or existing material pattern. | SDR/MDL spec data is unavailable, custom shader semantics are unclear, or conversion would be lossy. |
| `VM.TEX.001` | Referenced texture images must not exceed 16,384 pixels on either axis. | Report exact oversized textures and dimensions. Downscale or replace only with user approval and preserve aspect ratio and texture role. | Image tooling is unavailable, the source texture cannot be edited, or resizing would change visual quality beyond the approved policy. |
| `VM.TEX.002` | PBR texture channels must use correct color-space metadata. Current validator expects `sRGB` on specific super-albedo or vertex-color attrs and `raw` on other color-space authored attrs. Requirement docs also describe standard PBR channel policy. | Set color-space metadata when shader wiring, file naming, or source metadata clearly identifies the channel: base color/albedo and emission as sRGB; roughness, metallic, normal, height/displacement, opacity, and masks as raw. For 8-bit normal maps, preserve or author raw color space plus scale `(2, 2, 2, 1)` and bias `(-1, -1, -1, 0)` where the shader pattern uses those controls. | Texture channel semantics are ambiguous, the attribute naming does not match the validator/docs cleanly, or the change could alter intended appearance. |

## Common Repair Decisions

Use this decision order before editing:

1. Choose the selected feature variant from the profile manifest.
2. Determine whether materials already exist and are valid enough to repair.
3. Decide whether missing material bindings can be resolved by existing materials, user-provided material data, a material-assignment output, or an approved neutral fallback.
4. Keep material definitions, MDL files, and textures package-local or payload-local so bindings remain portable.
5. Repair shader schema and inputs after binding scope is correct.
6. Treat texture resizing and material replacement as visual changes that need user approval.

## USD Authoring Notes

Use USD APIs where available instead of string editing. For example:

- Use `UsdShade.MaterialBindingAPI` to compute, add, or update material bindings.
- Use `UsdShade.Material` and `UsdShade.Shader` wrappers to inspect surface outputs and shader inputs.
- Use `Sdf.AssetPath` values for texture and MDL asset paths.
- Resolve references relative to the layer that authors the asset path before rewriting them.

When authoring fallback USDPreview materials, place them under a stable scope such as `/AssetRoot/Looks` or `/AssetRoot/Materials`, bind at the narrowest clear shared ancestor, and record that the material is a fallback.

For MDL variants, do not invent a material library. If a user-approved material-assignment step is needed, run that before this skill or report the FET006 repair as blocked.

## Report Template

For each repair attempt, record:

| Field | Meaning |
|---|---|
| `requirement_id` | Requirement being repaired. |
| `status` | `repaired`, `already_passed`, `blocked`, or `failed`. |
| `affected_prims` | Prim paths inspected or changed. |
| `old_value` and `new_value` | Binding target, shader attr, asset path, texture metadata, or material value changed. |
| `variant` | Selected FET006 feature ID and version. |
| `outputs` | Files written or references changed. |
| `reason` | Short explanation, especially for blocked items or manifest/report mismatches. |
