# SimReady Feature: Baseline Appearance Visualization

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_006_STANDARD` |
| Runtime | `STANDARD` |
| Proprietary Techs | `None` |
| Latest Version | `0.2.0` |
| SME PIC | Jens Jebens (story owner); Jason Batchkoff (SRF review) |
| State | In development — 0.1.0 shipped; this card covers the 0.2.0 scope change |

Approvers

| Date | Name | Notes |
| :---- | :---- | :---- |
| TBD | Ronnie Sharif US | SRF engineering |
| TBD | Asmita Wankhede | Priority / workflow-domain |
| TBD | Jason Batchkoff | Profile impact — this is the version that becomes required |
| TBD | Jens Jebens AU | USD PM |
| TBD | Aaron Luk US | CC / strategic alignment |

## Why this card exists

`FET_006_STANDARD` is not a new feature. 0.1.0 ships on `main` and is listed by twelve
`Prop-Robotics-Neutral` and `Prop-Robotics-Physx` versions. Two things about 0.2.0 need a
decision rather than a changelog entry:

- It goes from two requirements to five, so an asset that conforms to 0.1.0 does not
  automatically conform to 0.2.0.
- `Robotics-Prop` 4.0.0, `Robot-Body` 3.0.0 and `Robot-Gripper` 3.0.0 list it as **required**.
  Every other FET-006 sub-feature stays `optional=true` in those versions. This is the one
  that raises the mandatory bar for every conforming asset.

## 1. Describe what this Feature will enable a user to simulate within a simulator

A SimReady asset with a `UsdPreviewSurface` material loads into any OpenUSD-capable runtime
and renders with its intended surface, without a renderer-specific material and without a
fallback. This is the universal appearance rung: it makes no assumption about render context,
so it is the one surface every consumer can evaluate.

|  | Target Vertical | Target Vertical User | Target Vertical Simulator | Use Case Description |
| ----- | ----- | ----- | ----- | ----- |
| 1 | Robotics | Simulation engineer | Isaac Sim, Isaac Lab | An asset renders with its intended surface in any runtime, whether or not MDL or MaterialX is available. |
| 2 | AIF | Content-pipeline owner | Mega / SDG | A single portable surface survives export to third-party tools and DCCs that read `UsdPreviewSurface` and nothing else. |

## 2. What is needed to test this Feature in runtime?

|  | Type | Desc |
| ----- | :---- | :---- |
| 1 | Platform | Kit |
| 2 | Backend | RTX; hdStorm for the universal path |
| 3 | Application | Isaac Sim (primary); USDView (context) |
| **Runtime Test Desc** |  |  |
| 1 | Render the asset with no `mdl` or `mtlx` render context available, then strip `outputs:surface` and render again. | An image diff proves the preview surface is what produced the render. |
| 2 | **Pass:** the preview surface resolves and binds, and the render changes when it is removed. **Fail:** the render is unchanged, which means a fallback material produced it. | |

## 3. Why is this being defined as a Feature and not as a Capability?

|  | Justification |
| ----- | ----- |
| 1 | The camera-observed outcome — the asset renders with its authored surface rather than a fallback — changes sensor and render output, so it is a Feature. |
| 2 | The authoring, binding and texture rules live in the `visualization/materials` capability. This feature is the universal `UsdPreviewSurface` rung of it. |

## 4. Is there a connection with any of the existing or new Features?

**No feature dependencies.** An asset may author this surface alone, or alongside any
combination of `FET_006_OPENPBR`, `FET_006_MDL` and `FET_010_STANDARD`. None depends on
another, and a consumer uses whichever it can evaluate.

Related but separate: `FET_006_OPENPBR` and `FET_006_MDL` are the render-context-specific
final surfaces, and `FET_010_STANDARD` is the rung below this one for geometry with no
authored material at all.

## 5. Which Feature-Profiles likely would incorporate this Feature?

|  | Feature Profile Name | Why? |
| :---: | :---- | :---- |
| 1 | `robotics-prop` (4.0.0) | Required. Every conforming prop authors a preview surface. |
| 2 | `robot-body` (3.0.0) | Required. Same baseline for robot bodies. |
| 3 | `robot-gripper` (3.0.0) | Required. Same baseline for grippers. |

`FET_006_STANDARD` 0.1.0 stays listed by the twelve `prop-robotics-neutral` and
`prop-robotics-physx` versions that already name it. Those are unchanged: a new version is
how the scope grows, so an asset conforming to 0.1.0 keeps conforming to it.

## 6. For asset validation, which Capabilities would this Feature likely depend on?

|  | Capability Name | Why? What kind of rules would it need for validation? |
| :---: | :---- | :---- |
| 1 | `visualization/materials` (extend) | Provides the binding-scope, preview-surface, material-assignment and texture rules listed in Appendix A. No new capability is needed. |

## Simplified

| simulator | Use case/story | Capability | Feature | Profile | SR approve |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Isaac Sim | An asset renders with its authored surface in any runtime, with no renderer-specific material | `visualization/materials` | `FET_006_STANDARD` | `robotics-prop`, `robot-body`, `robot-gripper` | TBD |

## Open questions

|  | Gap | Notes |
| :---: | ----- | ----- |
| 1 | Making it required | The three consolidated profiles list 0.2.0 as required. Confirm that is the intent, since it is the only FET-006 sub-feature that is not optional. |
| 2 | Migration for existing assets | An asset on 0.1.0 satisfies two of the five requirements by construction. The three added are the ones migration has to close. |

## Appendix A: Requirements

Capability `visualization/materials` (extend). The Status column reads relative to what
0.1.0 already required.

| ID | Requirement | Status |
| :---- | :---- | :---- |
| `com.nvidia.usd.VM.BIND.001` | Material binding scope: a binding target inside the payload the geometry belongs to. | In 0.1.0. Defined by `usd-validation-nvidia` |
| `com.nvidia.usd.VM.PS.001` | `UsdPreviewSurface` conformance: declared inputs, declared types, allowed token values. | In 0.1.0. Defined by `usd-validation-nvidia` |
| `VM.MAT.001` | Every renderable Gprim resolves a material through a direct or inherited binding. | Added at 0.2.0 |
| `VM.TEX.001` | Texture size ceiling. | Added at 0.2.0 |
| `VM.TEX.003` | `UsdPreviewSurface` texture colour space: `inputs:sourceColorSpace` on the `UsdUVTexture`, where nothing declared means `auto`. | Added at 0.2.0 |

Texture colour space is one requirement per surface, because the surface is what says what a
texture is for. In `UsdPreviewSurface` and in MaterialX every image node reads through an input
called `file`, so the node itself says nothing about whether it carries colour or data — the
only thing that settles it is which surface input the texture ends up driving, and the check
traces backwards from the terminal to find out. MDL is the exception: `diffuse_texture` and
`normalmap_texture` name the signal, so there the expectation is read off the input and the
rule is scoped to the shader's own texture inputs.

The surfaces also differ in where the value is written and what it defaults to. `VM.TEX.003` is
the `UsdPreviewSurface` one and belongs to this feature. `VM.TEX.004` covers OpenPBR and
`VM.TEX.005` covers MDL, so neither is part of it, and `VM.TEX.002` is the MDL rule frozen at
what `FET_006_MDL` 0.1.0 shipped.

`VM.MAT.001`, `VM.TEX.001` and `VM.TEX.003` are implemented in this repo, in
`visualization/materials/validation.py`. The two `com.nvidia.usd.` requirements are
implemented by `usd-validation-nvidia` and referenced here under their upstream codes.
