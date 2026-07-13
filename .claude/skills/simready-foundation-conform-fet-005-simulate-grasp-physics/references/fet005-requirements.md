# FET005 Requirement Repair Map

Use this reference when a validation report or inspection identifies `FET005_BASE_NEUTRAL` failures. Load the selected JSON manifest first:

- `FET_005_base_neutral-0.1.0-simulate_grasp_physics.json`

## Manifest Requirements

| Feature Variant | Requirements |
|---|---|
| `FET005_BASE_NEUTRAL@0.1.0` | `PMT.001`, `GSP.001` |

The current feature markdown emphasizes `GSP.001`. The current graspable validator checks only `GSP.001`: a `BasisCurves` prim under the default prim, whose name starts with `grasp_identifier`, with at least two points.

## Requirement Map

| Requirement | What It Means | Safe Repair | Block When |
|---|---|---|---|
| `GSP.001` | The asset has at least one grasp vector line that intersects the asset region intended for robotic grasping. Current validation expects a `BasisCurves` prim named `grasp_identifier*` under the default prim with at least two points. | Use visual evidence to choose a useful grasp region, then author a linear `BasisCurves` prim with two or more local-space points, guide purpose, and visible display styling. If the staged USD has no renderable geometry, use the nearest source visual asset only for visual decision-making and convert the chosen points into staged local space. | The current agent/model cannot inspect images with vision, no visual evidence is available, the asset has multiple plausible grasp regions, the line-to-USD coordinate mapping is uncertain, or runtime gripper constraints are required. |
| `PMT.001` | Every collider with `PhysicsCollisionAPI` has a `material:binding:physics` relationship to a valid physics material with `PhysicsMaterialAPI`. | Bind existing colliders to an explicit or approved physics material. Use material values from source data, profile policy, or user approval. | Material properties are unknown, no collider exists, or authoring a material would require property prediction that was not requested. |

## GSP.001 Validator Contract

Current validator behavior:

- Starts at the stage default prim.
- Traverses descendants under the default prim.
- Collects prims with `GetTypeName() == "BasisCurves"` and names starting with `grasp_identifier`.
- Fails if no such prim exists.
- Fails if any such prim has no `points` attribute or fewer than two points.

Current validator does not prove that the line intersects the asset or is a good robotic grasp. The skill must do that with visual review and, when available, runtime testing.

If the current agent/model cannot inspect visual evidence directly, do not author
or repair the grasp vector. Report the repair as blocked and tell the user that
FET005 grasp-line repair requires a vision-capable model/agent.

If the current agent/model can inspect visual evidence directly, it should choose
explicit local-space points from that evidence and run the authoring script. Do
not treat missing user-supplied points as a blocker when the agent can determine
the points from inspected evidence. If points still cannot be chosen, report
`status = "BLOCKED"` and include the evidence path, ambiguity, and exact inputs
needed to continue.

## Grasp Placement Guidance

Choose a line that represents a useful robotic grasp, not merely a validator token:

- Place the line through the part of the asset that opposing gripper fingers should contact.
- Prefer broad, rigid, central regions with clearance for gripper approach.
- Avoid voids, holes, hollow interiors, handles not intended for gripper contact, thin rims, fragile appendages, decorative geometry, sharp protrusions, and support/contact surfaces.
- For handled containers, the main body sidewall is usually better than the handle unless the user requests a handle grasp.
- For box-like objects, a line across opposite side faces is usually better than a line through a corner.
- For cylinders or bottles, a diameter through the main body at a stable height is usually better than top or bottom edges.
- For tools, the designed grip can be correct when it is strong, reachable, and intended as the robot grasp region.

## Authoring Details

Author the grasp vector as `UsdGeom.BasisCurves`:

```usd
def BasisCurves "grasp_identifier_01"
{
    uniform token type = "linear"
    int[] curveVertexCounts = [2]
    point3f[] points = [(x0, y0, z0), (x1, y1, z1)]
    float[] widths = [0.01] (
        interpolation = "constant"
    )
    uniform token purpose = "guide"
}
```

Good practice:

- Author under the default prim or a clear grasp annotation scope under the default prim.
- Use local coordinates relative to the authoring parent.
- Check root and ancestor xform ops before authoring. Converted CAD assets may carry meter-normalization or source-unit scale, so source-space meter points may need conversion into authored local units.
- Keep the line visible in review renders with a non-material display color.
- Preserve existing valid grasp lines unless replacing a line is explicitly requested.
- Record the visual evidence and rationale used to choose the line.
- Save overlay renders or a compact decision JSON when possible, especially when the visual evidence comes from a separate source asset rather than the staged USD.

## Runtime Review

Static validation only checks existence and point count. A final SimReady-quality grasp should also be reviewed by rendering or runtime testing:

- The line visibly intersects the selected grasp region.
- The line avoids excluded regions.
- The gripper can approach without colliding with irrelevant geometry.
- The selected region is physically plausible given colliders, rigid body, and material data.

## Preview Helper

When no renderer or viewport is available, use `assets/scripts/render_grasp_preview.py`
to generate a four-panel PNG from USD mesh points. The helper renders top,
front, side, and isometric point-cloud views and can overlay proposed grasp
points. Treat the PNG as visual evidence to inspect with a vision-capable model;
the helper does not choose points or prove grasp quality by itself.

## Report Template

For each repair attempt, record:

| Field | Meaning |
|---|---|
| `requirement_id` | Requirement being repaired. |
| `status` | `repaired`, `already_passed`, `blocked`, or `failed`. |
| `visual_evidence` | Renders or screenshots used for placement. |
| `affected_prims` | Existing and authored grasp vector prim paths. |
| `points` | Authored local-space points. |
| `rationale` | Why this region is a good grasp and what was avoided. |
| `status` | `PASS`, `BLOCKED`, or `FAIL`; keep `BLOCKED` separate from failed repair attempts. |
| `needed_inputs` | Evidence, points, rationale, coordinate note, gripper context, or user intent needed to unblock repair. |
| `outputs` | Files written or references changed. |
| `reason` | Short explanation, especially for blocked items. |
