# SimReady Feature: Object Color Visualization

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_010_STANDARD` |
| Runtime | `STANDARD` |
| Proprietary Techs | `None` |
| Latest Version | `0.1.0` |
| SME PIC | Divyansh Mishra (Isaac Lab workflow); Jens Jebens (story owner); Avinash Devalla (sensor-adjacent review) |
| State | In development (post-preflight) |

Approvers

| Date | Name | Notes |
| :---- | :---- | :---- |
| TBD | Ronnie Sharif US | SRF engineering |
| TBD | Asmita Wankhede | Priority / workflow-domain |
| TBD | Divyansh Mishra | Primary E2E workflow; canonical sample, pass/fail |
| TBD | Avinash Devalla | Sensor-adjacent review |
| TBD | Jens Jebens AU | USD PM |
| TBD | Aaron Luk US | CC / strategic alignment |

## 1. Describe what this Feature will enable a user to simulate within a simulator

A SimReady asset with standardized `displayColor` values loads into a low-fidelity (non-ray-traced) render path and produces plausible per-object / per-part color and semantic differentiation **without any PBR material authoring** — the minimum conformant visual layer for CAD-origin assets, vision-based RL, and basic scene understanding.

|  | Target Vertical | Target Vertical User | Target Vertical Simulator | Use Case Description |
| ----- | ----- | ----- | ----- | ----- |
| 1 | Robotics | Vision/RL policy developer | Isaac Lab | Load a SimReady asset with low-fi rendering; standardized `displayColor` gives plausible color + semantic differentiation without PBR. |
| 2 | AIF | Content-pipeline owner | Mega / SDG | CAD-origin factory assets often import "clown colored"; this is the minimum conformant visual layer that makes them useful downstream. |

## 2. What is needed to test this Feature in runtime?

|  | Type | Desc |
| ----- | :---- | :---- |
| 1 | Platform | Kit |
| 2 | Application | Isaac Lab (primary) |
| 3 | Application | USDView / Isaac Sim (context) |
| **Runtime Test Desc** |  |  |
| 1 | Render the asset in a low-fi (non-ray-traced) path with authored `displayColor`, then again with `displayColor` altered, then removed. | Three frames (authored / altered / removed) → per-pixel image diff. |
| 2 | **Pass:** the authored frame differs from the altered/removed frames (the color has a visible effect). **Fail:** colors collapse to default gray, or no difference is produced. No perception model is used in the test. |  |

## 3. Why is this being defined as a Feature and not as a Capability?

|  | Justification |
| ----- | ----- |
| 1 | Touching `displayColor` materially changes what a camera / low-fi render path outputs, so it is a Feature. |
| 2 | The rules it relies on (where `displayColor` is authored, its color space, value range) are a Capability (`visualization/display_color`). `displayColor` is a universal USD primvar with no shading network — the lowest, most portable rung of the visual ladder. |

## 4. Is there a connection with any of the existing or new Features?

**None.** Object Color Visualization stands alone — it does not depend on any other feature, and no other feature depends on it. Using a material's base color as a display-color fallback is optional, non-normative *guidance* (a capability a consumer may choose to use), **not** a feature dependency.

## 5. Which Feature-Profiles likely would incorporate this Feature?

|  | Feature Profile Name | Why? |
| :---: | :---- | :---- |
| 1 | `robotics-prop` (4.0.0) | Baseline color rung for props with no authored UsdShade material. |
| 2 | `robot-body` (3.0.0) | Same baseline color rung for robot bodies. |
| 3 | `robot-gripper` (3.0.0) | Same baseline color rung for grippers. |

Per TAC Session 2 those three are the profiles carried forward, so `prop-robotics-neutral`, `prop-robotics-physx` and `robot-body-neutral` are not extended to carry the `FET_006_*` visual-material features. The feature is optional in every version block that lists it; whether a profile promotes it to required is an intent decision resolved at profile authoring, not in this card.

## 6. For asset validation, which Capabilities would this Feature likely depend on?

|  | Capability Name | Why? What kind of rules would it need for validation? |
| :---: | :---- | :---- |
| 1 | `visualization/display_color` (new) | Provides the display-color rules (`DISP.*`) — coverage on renderable prims, plausible values, and the range of the companion `displayOpacity` primvar. Full text in [Appendix A](#appendix-a-requirements). |

## Simplified

| simulator | Use case/story | Capability | Feature | Profile | SR approve |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Isaac Lab | Per-object colour and semantic differentiation in a low-fidelity render path, with no PBR material authoring | `visualization/display_color` | `FET_010_STANDARD` | `robotics-prop`, `robot-body`, `robot-gripper` | *(Jira status)* |

## Open questions

|  | Gap | Notes |
| :---: | ----- | ----- |
| 1 | Profile selection | TAC Session 2 settled the initial set — `robotics-prop`, `robot-body`, `robot-gripper` — and the feature is optional in every version that lists it. Whether any profile promotes display colour to required, and when, is unresolved. |

## Appendix A: Requirements

New capability `visualization/display_color`; rules → a new `visualization/display_color/validation.py`.

| ID | Requirement | Check |
| :---- | :---- | :---- |
| `DISP.001` | Coverage | Every renderable Gprim (resolved `purpose` `default` or `render`) resolves an **effective** `displayColor` — authored on the prim **or inherited** from an ancestor. USD inherits constant-interpolation primvars down namespace, so check the resolved value (e.g. `UsdGeomPrimvarsAPI.FindPrimvarWithInheritance("displayColor")`), *not* direct authoring on each Gprim. |
| `DISP.002` | Value range | Every component of a resolved `displayColor` is within `[0, 1]` and finite, and the array length agrees with the declared interpolation. |
| `DISP.003` | Opacity range | Where `primvars:displayOpacity` is authored, every element is within `[0, 1]` and finite, and the array length agrees with the declared interpolation, on the same terms as DISP.002. Authoring it is not required — a prim without it is treated as fully opaque. |

**Guidance (attached to `DISP.002`) — how color is handled in USD for display colors:** `displayColor` resolves to linear Rec.709 with a D65 white point unless a color space says otherwise. `UsdColorSpaceAPI` supplies the per-attribute token and the resolution order — attribute, then prim, then ancestors — so values taken from an sRGB picker need converting rather than copying, and a mid grey of `0.5` in linear is considerably lighter than `0.5` off an sRGB picker.
