# FET023 Requirement Repair Map

Use this reference when a validation report or inspection identifies `FET023_ROBOT_MATERIALS` failures. Load the selected JSON manifest first:

- `FET_023-robot_materials-0.1.0.json`

The feature markdown and requirement docs are useful context, but the selected manifest and current validation report decide which IDs are in scope.

## Manifest Requirements

| Feature Variant | Requirements |
|---|---|
| `FET023_ROBOT_MATERIALS@0.1.0` | `RM.001`, `RM.002` |

## Requirement Map

| Requirement | What It Means | Safe Repair | Block When |
|---|---|---|---|
| `RM.001` | `UsdShade.Material` prims must not contain descendant material prims. | Move each nested material subtree to its own direct child under `/<defaultPrim>/Looks`, preserving shaders, attributes, and metadata. Update bindings and connections from old paths to new paths. | Nested material ownership crosses references, payloads, variants, or layers that cannot be edited safely. |
| `RM.002` | All local material definitions under the default prim must be direct children of the top-level `/<defaultPrim>/Looks` prim. | Create `/<defaultPrim>/Looks` as a `Scope` if needed. Move locally-authored material subtrees into direct child material paths under `Looks`. Update binding and shader targets. | Material prims are authored in external assets, target paths cannot be rewritten safely, or moving materials would alter composition strength. |

## Validator Contract

Current RobotMaterials validation:

- `RM.001` checks each `UsdShade.Material` and fails if any descendant prim is also a `UsdShade.Material`.
- `RM.002` starts at the stage default prim.
- `RM.002` looks for `/<defaultPrim>/Looks`.
- If the default prim or `Looks` scope is missing, the current validator emits info and skips the top-level-only check.
- Direct material children of `Looks` are accepted.
- Any other material encountered while traversing under the default prim fails `RM.002`.
- The current `RM.002` traversal skips children that have authored references or payloads.

Follow the feature docs even when the current validator is permissive: create a top-level `Looks` scope and keep robot material definitions flat.

## Move Planning

Before editing, build a move map:

| Source | Target |
|---|---|
| `/Robot/Arm/Looks/Metal` | `/Robot/Looks/Metal` |
| `/Robot/Link/Material/BluePaint` | `/Robot/Looks/BluePaint` |
| `/Robot/Looks/Parent/Nested` | `/Robot/Looks/Nested` |

For every moved material subtree, include descendant paths in the rewrite map. Example:

| Old Descendant | New Descendant |
|---|---|
| `/Robot/Arm/Looks/Metal/Shader` | `/Robot/Looks/Metal/Shader` |
| `/Robot/Looks/Parent/Nested/Preview` | `/Robot/Looks/Nested/Preview` |

Use deterministic collision handling:

- Prefer the existing material prim name when unique.
- If a name already exists under `Looks`, append a sanitized source scope or numeric suffix.
- Preserve both materials rather than merging unless the prims are provably identical and the user approved deduplication.

## USD Authoring Notes

Use USD APIs where available instead of string editing:

- Use `UsdShade.Material` to identify material prims.
- Use `UsdShade.MaterialBindingAPI` to find and update material bindings.
- Use `Usd.PrimRange` or stage traversal to find material descendants.
- Use `Sdf.CopySpec` or USD namespace editing when moving material subtrees between paths in the same editable layer.
- Update all relationship targets and connection paths that reference old material or descendant paths.

After each move, verify:

- The new material path composes and is a direct child of `/<defaultPrim>/Looks`.
- No old material prim remains under the default prim outside top-level `Looks`.
- No material prim has a descendant material prim.
- All material bindings resolve to the new material paths.
- All shader connections still resolve.

## Report Template

For each repair attempt, record:

| Field | Meaning |
|---|---|
| `requirement_id` | Requirement being repaired. |
| `status` | `repaired`, `already_passed`, `blocked`, or `failed`. |
| `old_material_path` and `new_material_path` | Material path moved or flattened. |
| `bindings_updated` | Binding relationship paths retargeted. |
| `connections_updated` | Shader connection or relationship target paths retargeted. |
| `layer` | Layer where the material move or target rewrite was authored. |
| `outputs` | Files written or references changed. |
| `reason` | Short explanation, especially for blocked items or validator/doc mismatches. |
