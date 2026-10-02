# SimReady Feature: Physically Plausible Appearance Visualization

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_006_OPENPBR` |
| Runtime | `OPENPBR` |
| Proprietary Techs | `None` |
| Latest Version | `0.1.0` |
| SME PIC | Divyansh Mishra (Isaac Sim + RTX validation workflow); Beau Perschall (PM); Avinash Devalla (sensor SME) |
| State | In development (post-preflight) |

Approvers

| Date | Name | Notes |
| :---- | :---- | :---- |
| TBD | Ronnie Sharif US | SRF engineering |
| TBD | Jason Batchkoff / Ignacio Llamas | SimReady Core + RTX material-runtime alignment |
| TBD | Divyansh Mishra | Primary validation workflow; canonical sample, runtime stack, pass/fail |
| TBD | Avinash Devalla | Sensor SME, camera / material response |
| TBD | Jens Jebens AU | USD PM |
| TBD | Aaron Luk US | CC / strategic alignment |

## 1. Describe what this Feature will enable a user to simulate within a simulator

A SimReady asset carrying an **OpenPBR** material (authored in MaterialX) loads into a simulator, renders, and produces plausible material response for camera / perception use **without manual material repair**. OpenPBR is an open, renderer-agnostic standard and is the SimReady physically-based surface target — it replaces the NVIDIA-specific MDL requirement (MDL is permitted during migration, as Omniverse's current default). The universal `UsdPreviewSurface` baseline is a *separate* feature (`FET_006_STANDARD`), not part of this one.

|  | Target Vertical | Target Vertical User | Target Vertical Simulator | Use Case Description |
| ----- | ----- | ----- | ----- | ----- |
| 1 | Robotics | Robotics perception engineer | Isaac Sim + RTX | Load a CAD/Blender→SimReady asset, render, validate material response is plausible for camera/perception without manual repair. |
| 2 | AIF | Content-pipeline owner | Mega / Replicator / SDG | Standardized PBR + parameter ranges so datasets generated at scale stay plausible and randomizable. |

## 2. What is needed to test this Feature in runtime?

|  | Type | Desc |
| ----- | :---- | :---- |
| 1 | Platform | Kit |
| 2 | Backend | RTX |
| 3 | Application | Isaac Sim (primary); USDView (context) |
| **Runtime Test Desc** |  |  |
| 1 | White-box render diff: place the asset in a white-box scene and render; then unapply / alter the OpenPBR material and render again. | An image diff proves the material resolves, binds, and affects the render. |
| 2 | **Pass:** the OpenPBR surface resolves and binds, and the render changes when it is altered/removed. **Fail:** binding does not resolve / is ignored, or the asset renders in a single renderer only. *Aspirational (not a hard 0.1 gate): common classes (metal, plastic, glass, rubber, painted) show the expected light response. Translucent / glass response may not be testable today — flag if it blocks.* |

## 3. Why is this being defined as a Feature and not as a Capability?

|  | Justification |
| ----- | ----- |
| 1 | The camera-observed outcome — physically plausible material appearance — materially changes sensor / render output, so it is a Feature. |
| 2 | The material authoring, binding and parameter *rules* live in the `visualization/materials` capability. This feature is specifically the **OpenPBR physically-based surface**; `UsdPreviewSurface` and MDL are separate material features. Binding is an implicit requirement of any material, since the surface must resolve onto renderable prims. |

## 4. Is there a connection with any of the existing or new Features?

**No feature dependencies** — confirmed in the 2026-07-27 pre-flight (this feature does not depend on Object Color Visualization or any other feature).

Related but *separate* (not dependencies): `FET_006_STANDARD`, the universal preview-surface baseline and its own feature, and `FET_006_MDL`. An asset may carry all three surfaces at once, and USD selects between them natively, through two separate calls. The render context picks the surface terminal within a material — `UsdShadeMaterial::ComputeSurfaceSource(renderContext)`, where `mtlx` selects the OpenPBR shader. The binding purpose picks the material bound to a prim — `UsdShadeMaterialBindingAPI::ComputeBoundMaterial(materialPurpose)`. The two are not interchangeable: USD does not validate the purpose argument, so passing a render context such as `"mtlx"` to `ComputeBoundMaterial` raises no error, falls back to the `allPurpose` binding, and leaves the caller reading the default surface — `UsdPreviewSurface` on an asset that carries all three. Context only (not dependencies): Visual Lighting (`FET008`) and Visual Sensor (`FET009`) are the other half of the observed scenario and ship as their own feature cards next round.

## 5. Which Feature-Profiles likely would incorporate this Feature?

|  | Feature Profile Name | Why? |
| :---: | :---- | :---- |
| 1 | `robotics-prop` (4.0.0) | OpenPBR is the physically-based final surface for this profile. Optional. |
| 2 | `robot-body` (3.0.0) | OpenPBR is the physically-based final surface for this profile. Optional. |
| 3 | `robot-gripper` (3.0.0) | OpenPBR is the physically-based final surface for this profile. Optional. |

Per TAC Session 2 those three are the profiles carried forward, so `prop-robotics-neutral`, `prop-robotics-physx` and `robot-body-neutral` are not extended to carry the `FET_006_*` visual-material features. The version blocks above are authored by the OpenPBR appearance specification change rather than by this card.

## 6. For asset validation, which Capabilities would this Feature likely depend on?

|  | Capability Name | Why? What kind of rules would it need for validation? |
| :---: | :---- | :---- |
| 1 | `visualization/materials` (exists, extend) | Extends the materials capability with the OpenPBR rules — surface, parameter ranges, MaterialX structure, and material-binding resolution. Full text in [Appendix A](#appendix-a-requirements). |

## Simplified

| simulator | Use case/story | Capability | Feature | Profile | SR approve |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Isaac Sim + RTX | Plausible material response for camera and perception, without manual material repair | `visualization/materials` | `FET_006_OPENPBR` | `robotics-prop`, `robot-body`, `robot-gripper` | *(Jira status)* |

## Open questions

|  | Gap | Notes |
| :---: | ----- | ----- |
| 1 | Profile selection | TAC Session 2 settled the initial set — `robotics-prop`, `robot-body`, `robot-gripper` — and the feature is optional in every version that lists it. Whether any profile promotes OpenPBR to required, and when, is unresolved. |

## Appendix A: Requirements

Capability `visualization/materials` (extend). The requirement set is authored by the OpenPBR appearance specification change, and the Status column below reads relative to it.

| ID | Requirement | Status |
| :---- | :---- | :---- |
| `VM.PBR.001` | OpenPBR final surface. Phased-permissive: OpenPBR (MaterialX) is the standard, OmniPBR (MDL) is permitted during migration. | New |
| `VM.PBR.002` | OpenPBR parameter ranges: unit floats in `[0,1]`, IOR in `[1, 3]`, `emission_luminance >= 0`, unit colour components in `[0,1]`. | New |
| `VM.PBR.003` | MaterialX graph structure: `info:id` resolves in the shader registry, connected inputs reference an existing source, authored input types match the nodedef, and a surface terminal is authored and connected. Node portability is guidance. | New |
| `com.nvidia.usd.VM.BIND.001` | Material binding scope. | Defined by `usd-validation-nvidia` (`MaterialOutOfScopeChecker`); moved upstream |
| `VM.MAT.001` | Every renderable Gprim resolves a material through a direct or inherited binding. The material is resolved for the `full` purpose, and collection bindings are excluded (new). | In repo, extended |
| `VM.BIND.002` | Every authored shader input is declared by the shader's own definition, with the declared type. | In repo |
| `VM.TEX.001` | Texture size ceiling. | In repo |
| `VM.TEX.004` | OpenPBR texture colour space: the `colorSpace` on an image node's `inputs:file`. | New |

Two earlier proposals on this card were dropped once checked against the repo. "Computable material assignment" and "direct bindings only" are both part of `VM.MAT.001`, so neither needed a new id. A separate `VM.BIND.003` covering the collection-binding exclusion was folded into `VM.MAT.001` and removed, which is the clause marked `(new)` in the table above. `com.nvidia.usd.VM.PS.001` is not listed here because the preview surface is a separate feature (`FET_006_STANDARD`); it too moved upstream to `usd-validation-nvidia`.

Texture colour space is one requirement per surface, because each declares it somewhere different with a different default. `VM.TEX.004` is the OpenPBR one and belongs to this feature: it reads the `colorSpace` on an image node's `inputs:file`, where nothing declared means no transform at all. `VM.TEX.003` covers `UsdPreviewSurface` and `VM.TEX.005` covers MDL, so neither is part of this feature. `VM.TEX.002` is the MDL rule frozen at what `FET_006_MDL` 0.1.0 shipped and stays listed only by that version.

`VM.PBR.001`, `VM.PBR.002` and `VM.PBR.003` are implemented in this repo, as the `check_vm_pbr_001_openpbr_surface`, `check_vm_pbr_002_openpbr_parameter_ranges` and `check_vm_pbr_003_materialx_graph_structure` methods on `VisualMaterialsCapabilityChecker` in `visualization/materials/validation.py`. `usd-validation-nvidia` supplies only the `BaseRuleChecker` base class and the `register_requirements` decorator that checker builds on.
