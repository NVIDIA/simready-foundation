# FET007 Requirement Repair Map

Use this reference when a validation report or inspection identifies `FET007_BASE_NEUTRAL` failures. Load the selected JSON manifest first:

- `FET_007_base_neutral-0.2.0-nonvisual_materials.json`

The feature markdown and requirement docs are useful context, but the selected manifest and current validation report decide which IDs are in scope.

## Manifest Requirements

| Feature Variant | Requirements |
|---|---|
| `FET007_BASE_NEUTRAL@0.2.0` | `NVM.001`, `NVM.002`, `NVM.003`, `NVM.004`, `NVM.005`, `NVM.006` |

## Authored Attributes

FET007 uses three attributes on bound `UsdShade.Material` prims:

| Attribute | Type | Current Validator Values |
|---|---|---|
| `omni:simready:nonvisual:base` | `token` | `aluminum`, `steel`, `oxidized_steel`, `iron`, `oxidized_iron`, `silver`, `brass`, `bronze`, `oxidized_Bronze_Patina`, `tin`, `plastic`, `fiberglass`, `carbon_fiber`, `vinyl`, `plexiglass`, `pvc`, `nylon`, `polyester`, `clear_glass`, `frosted_glass`, `one_way_mirror`, `mirror`, `ceramic_glass`, `asphalt`, `concrete`, `leaf_grass`, `dead_leaf_grass`, `rubber`, `wood`, `bark`, `cardboard`, `paper`, `fabric`, `skin`, `fur_hair`, `leather`, `marble`, `brick`, `stone`, `gravel`, `dirt`, `mud`, `water`, `salt_water`, `snow`, `ice`, `calibration_lambertian` |
| `omni:simready:nonvisual:coating` | `token` | `none`, `paint`, `clearcoat`, `paint_clearcoat` |
| `omni:simready:nonvisual:attributes` | `token[]` | `none`, `emissive`, `retroreflective`, `single_sided`, `visually_transparent` |

The docs table includes a `none` base label, but the current validator does not allow `none` for `omni:simready:nonvisual:base`. Follow the validator for conformance and note the mismatch if it matters to the repair.

## Requirement Map

| Requirement | What It Means | Safe Repair | Block When |
|---|---|---|---|
| `NVM.001` | Bound materials must specify `omni:simready:nonvisual:attributes` as a token array of allowed sensor-response flags. | Add `token[] omni:simready:nonvisual:attributes` from source evidence. Use `["none"]` or an empty token array only when a no-special-attribute policy is approved. | Special attributes such as emissive, retroreflective, single-sided, or visually transparent are ambiguous. |
| `NVM.002` | Bound materials must specify `omni:simready:nonvisual:base` as a non-empty allowed token. | Add or correct the base token from explicit material evidence, source DCC metadata, material names, shader semantics, or user-approved mapping. | The material class is unknown, outside the allowed list, or multiple allowed base classes are plausible. |
| `NVM.003` | Bound materials must specify `omni:simready:nonvisual:coating` as an allowed token. | Add or correct coating from explicit evidence. Use `none` only when no coating is intended by policy. | Paint, clearcoat, or bare-surface status is not inferable and no default policy was approved. |
| `NVM.004` | Non-visual material attributes must be on materials bound to default/render geometry, not orphaned materials. | Bind the intended material, move attributes to the actual bound material, or remove attributes from a clearly orphaned scratch material. | Binding intent is unclear, material reuse crosses payloads or references, or removing attributes might affect another asset. |
| `NVM.005` | Non-visual material properties must be consistent with visual material properties. Current validator registers this requirement but does not objectively verify it in code. | Review visual material evidence and adjust base/coating/attributes to match obvious shader semantics such as metallic, transparent, emissive, painted, or rubber-like surfaces. | The material appearance requires visual review or domain judgement that is unavailable. |
| `NVM.006` | Non-visual material attributes must not be time-varying. | Remove time samples and author one default value when the intended static value is clear. | Time-varying samples encode meaningful runtime behavior or there is no clear default value to preserve. |

## Common Repair Decisions

Use this decision order before editing:

1. Confirm FET007 is selected by the profile or explicitly requested.
2. Confirm visual materials and material bindings exist; if not, hand off to FET006 or a material-assignment step first.
3. List every renderable GPrim or GeomSubset and its computed full-purpose material binding.
4. Classify each unique bound material from reliable evidence.
5. Author all three non-visual attributes on each bound material.
6. Remove or relocate orphaned non-visual attributes.
7. Remove time samples after choosing a static value.
8. Re-run the narrowest available FET007-capable validation.

## USD Authoring Notes

Use USD APIs where available instead of string editing:

- Use `UsdShade.MaterialBindingAPI.ComputeBoundMaterial(materialPurpose=UsdShade.Tokens.full)` to find the material that validation will inspect.
- Use `UsdShade.Material` to author attributes on the material prim, not on the shader or mesh.
- Use `Sdf.ValueTypeNames.Token` for `base` and `coating`.
- Use `Sdf.ValueTypeNames.TokenArray` for `attributes`.
- Clear time samples explicitly before setting the default value for NVM.006 repairs.

Example:

```usd
def Material "PaintedSteel"
{
    token omni:simready:nonvisual:base = "steel"
    token omni:simready:nonvisual:coating = "paint"
    token[] omni:simready:nonvisual:attributes = ["none"]
}
```

## Report Template

For each repair attempt, record:

| Field | Meaning |
|---|---|
| `requirement_id` | Requirement being repaired. |
| `status` | `repaired`, `already_passed`, `blocked`, or `failed`. |
| `material_prim` | Bound material prim inspected or changed. |
| `affected_geometry` | Renderable geometry that computes this material binding. |
| `old_value` and `new_value` | Attribute value, type, time samples, or binding changed. |
| `evidence` | Source classification evidence or user-approved policy. |
| `outputs` | Files written or references changed. |
| `reason` | Short explanation, especially for blocked items or doc/validator mismatches. |
