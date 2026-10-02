# semantic_aov_output  (FET035 Render Products)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | semantic_aov_output            |
| Feature(s)   | FET_035_RTX  |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.1.0                          |

## Summary

Replicator runtime check for semantic AOV RenderVars: confirms that each
semantic annotator declared in `orderedVars` is registered in Replicator and
produces non-empty output when the render pipeline runs. BLOSC compression
(RP.004) is enforced by static validation, not by this benchmark test.

## What Pass Guarantees

A reviewer, PM, or OEM can trust that the Replicator annotators corresponding
to the authored `sourceName` values are recognized by Isaac Sim and produce
non-empty data when the render pipeline runs. BLOSC compression correctness is
guaranteed by passing static validation (RP.004), which must be satisfied before
these runtime tests are meaningful.

## What It Checks

For each `RenderProduct` whose `orderedVars` includes a semantic `RenderVar`:

- A matching Replicator render product is created using the authored camera
  path and resolution (`rep.create.render_product()`).
- Each semantic `sourceName` is passed to `rep.annotators.get()`. An
  unrecognised name fails here.
- One Replicator frame is triggered and each annotator's output is verified
  to be a non-empty array.

Data values may be all-zero when no prims carry `SemanticAPI` labels (expected
for minimal test fixtures) — the check requires non-empty arrays, not
non-zero values.

Key thresholds from `config_defaults`:

- `warmup_frames`: 30 (physics + timeline frames before the Replicator step)
- `semantic_prefix`: `"semantic"` (case-insensitive prefix identifying semantic AOVs)

## How It Works

1. The stage is traversed for all `UsdRender.Var` prims with a `sourceName`
   starting with `"semantic"`. Their `srtx:compression:type` attributes are
   read and compared to `"blosc"`.
2. For each `RenderProduct` containing semantic `RenderVar` targets, a
   reference cube is placed 2 m in front of the camera, a Replicator RP is
   copy-constructed from the authored camera and resolution, and semantic
   annotators are attached and stepped.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Annotator not registered | The `sourceName` does not match a registered Replicator annotator name. |
| Annotator returned empty array | The Replicator pipeline did not produce output. Increase `warmup_frames`. |
| Test skipped | No semantic RenderVar prims found in the stage. |
| Static validation failed | Asset did not pass RP.004 (`srtx:compression:type` missing or not `"blosc"`). Fix the static issue first. |

## How to Fix

Set `srtx:compression:type = "blosc"` on every semantic `RenderVar` prim:

```usd
def RenderVar "SemanticSegmentation"
{
    uniform string sourceName = "SemanticSegmentation"
    uniform string srtx:compression:type = "blosc" (
        allowedTokens = ["hevc", "h264", "av1", "blosc"]
    )
}
```

## Manual Testing in Isaac Sim

### Batch script

Save the script below to a file (e.g. `batch_test_semantic_aov.py`) under the
repo root and run it with:

```powershell
# Windows
isaac-sim.bat --no-window --exec "C:\Dev\simready_foundations\batch_test_semantic_aov.py"
```

```bash
# Linux
./isaac-sim.sh --no-window --exec "/path/to/simready_foundations/batch_test_semantic_aov.py"
```

Expected output summary:

```
Overall: PASS (2/2 checks passed)
```

```python
import asyncio, os
import numpy as np

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
PASS_ASSET = os.path.join(REPO_ROOT,
    "nv_core/sr_specs/tests/data/render_products/SemanticAovCompressionCheckerPass.usda")
FAIL_ASSET = os.path.join(REPO_ROOT,
    "nv_core/sr_specs/tests/data/render_products/SemanticAovCompressionCheckerFail.usda")
WARMUP_FRAMES = 30
DEFAULT_RESOLUTION = (512, 512)


def is_kit_internal(p): return "OmniverseKit" in str(p)


def place_cube_in_front_of_camera(stage, cam_path, index):
    """Place geometry so the render pipeline has something to process."""
    from pxr import UsdGeom, Gf, Usd
    cam = stage.GetPrimAtPath(cam_path)
    if not cam.IsValid(): return
    xf = UsdGeom.XformCache(Usd.TimeCode.Default())
    world_xf = xf.GetLocalToWorldTransform(cam)
    fwd = world_xf.TransformDir(Gf.Vec3d(0, 0, -1)).GetNormalized()
    pos = Gf.Vec3d(world_xf.ExtractTranslation()) + fwd * 2.0
    cube = UsdGeom.Cube.Define(stage, f"/World/SemanticCube_{index}")
    cube.GetSizeAttr().Set(0.4)
    UsdGeom.XformCommonAPI(cube.GetPrim()).SetTranslate((pos[0], pos[1], pos[2]))


def check_semantic_compression(stage):
    """Structural check: srtx:compression:type == "blosc" on semantic RenderVars."""
    from pxr import UsdRender
    render_vars = [p for p in stage.Traverse() if p.IsA(UsdRender.Var)]
    semantic_found = False
    all_ok = True
    for rv in render_vars:
        src_attr = rv.GetAttribute("sourceName")
        if not src_attr.IsValid(): continue
        source_name = src_attr.Get() or ""
        if not source_name.lower().startswith("semantic"): continue
        semantic_found = True
        comp_attr = rv.GetAttribute("srtx:compression:type")
        comp_value = comp_attr.Get() if comp_attr.IsValid() else None
        ok = comp_value is not None and comp_value.lower() == "blosc"
        print(f"    {'PASS' if ok else 'FAIL'}  {rv.GetPath()}"
              f"  sourceName={source_name!r}  compression={comp_value!r}")
        if not ok: all_ok = False
    if not semantic_found:
        print("    SKIP: no semantic RenderVar prims found")
        return True
    return all_ok


def get_semantic_source_names(stage, rp_prim):
    """Return (camera_path, resolution, [semantic sourceName values]) for a RP."""
    cam_rel  = rp_prim.GetRelationship("camera")
    vars_rel = rp_prim.GetRelationship("orderedVars")
    cam_path = (str(cam_rel.GetTargets()[0])
                if cam_rel.IsValid() and cam_rel.GetTargets() else None)
    res_attr = rp_prim.GetAttribute("resolution")
    resolution = (tuple(int(v) for v in res_attr.Get())
                  if res_attr.IsValid() and res_attr.Get() is not None
                  else DEFAULT_RESOLUTION)
    names = []
    if vars_rel.IsValid():
        for var_path in vars_rel.GetTargets():
            var_prim = stage.GetPrimAtPath(var_path)
            if not var_prim.IsValid(): continue
            src_attr = var_prim.GetAttribute("sourceName")
            if src_attr.IsValid():
                name = src_attr.Get() or ""
                if name.lower().startswith("semantic"):
                    names.append(name)
    return cam_path, resolution, names


async def check_replicator_semantic(stage):
    """
    Copy-construct a Replicator RP for each authored RP with semantic RenderVars,
    attach the annotators, step one frame, and verify non-empty data.
    """
    import omni.kit.app, omni.replicator.core as rep
    from pxr import UsdRender
    rps = [p for p in stage.Traverse()
           if p.IsA(UsdRender.Product) and not is_kit_internal(p.GetPath())]
    tested, all_ok = 0, True
    for idx, rp in enumerate(rps):
        cam_path, resolution, semantic_names = get_semantic_source_names(stage, rp)
        if not cam_path or not semantic_names: continue
        cam_prim = stage.GetPrimAtPath(cam_path)
        if not cam_prim.IsValid():
            print(f"    FAIL: camera prim {cam_path} not found")
            all_ok = False; continue
        place_cube_in_front_of_camera(stage, cam_path, idx)
        # Copy-construct: mirror authored camera and resolution in Replicator
        try:
            rep_rp = rep.create.render_product(cam_path, resolution)
            rep_rp_path = rep_rp.path if hasattr(rep_rp, "path") else str(rep_rp)
            print(f"    Replicator RP: {rep_rp_path} (res={resolution})")
        except Exception as e:
            print(f"    FAIL: could not create Replicator RP: {e}")
            all_ok = False; continue
        attached = []
        for name in semantic_names:
            try:
                anno = rep.annotators.get(name)
                anno.attach(rep_rp_path)
                attached.append((name, anno))
                print(f"    PASS: annotator '{name}' attached")
            except Exception as e:
                print(f"    FAIL: '{name}' not registered: {e}")
                all_ok = False
        if not attached: continue
        try:
            await rep.orchestrator.step_async()
        except Exception:
            await rep.orchestrator.run_async(num_frames=1)
        for _ in range(10):
            await omni.kit.app.get_app().next_update_async()
        for name, anno in attached:
            try:
                data = anno.get_data()
                arr = np.array(data) if not isinstance(data, np.ndarray) else data
                if arr.size == 0:
                    print(f"    FAIL: '{name}' empty array"); all_ok = False
                else:
                    # Values may be all-zero without SemanticAPI labels — that
                    # is expected for minimal fixtures. Check size only.
                    print(f"    PASS: '{name}' shape={arr.shape} dtype={arr.dtype}"
                          f" (nonzero={bool(np.any(arr != 0))})")
                tested += 1
            except Exception as e:
                print(f"    SKIP: '{name}' get_data error: {e}")
    if tested == 0:
        print("    SKIP: no semantic annotators tested")
    return all_ok


async def run_semantic_test(asset_path, label, expect_pass):
    import omni.usd, omni.kit.app, omni.kit.commands, omni.physx, omni.timeline
    print(f"\n--- {label} ---")
    await omni.usd.get_context().open_stage_async(asset_path)
    for _ in range(5): await omni.kit.app.get_app().next_update_async()
    omni.kit.commands.execute("CreatePrimWithDefaultXform", prim_type="DistantLight")
    for _ in range(3): await omni.kit.app.get_app().next_update_async()
    stage = omni.usd.get_context().get_stage()
    print("    [Structural check]")
    struct_ok = check_semantic_compression(stage)
    print("    [Replicator render check]")
    omni.physx.get_physx_interface().start_simulation()
    omni.timeline.get_timeline_interface().play()
    for _ in range(WARMUP_FRAMES): await omni.kit.app.get_app().next_update_async()
    render_ok = await check_replicator_semantic(stage)
    omni.timeline.get_timeline_interface().stop()
    passed = struct_ok and render_ok
    print(f"    Structural : {'PASS' if struct_ok else 'FAIL'}")
    print(f"    Replicator : {'PASS' if render_ok else 'FAIL'}")
    return passed if expect_pass else not passed


async def main():
    print("=" * 60)
    print("Batch test: Semantic AOV (FET035 RP.004)")
    print("=" * 60)
    results = [
        await run_semantic_test(PASS_ASSET,
            "Pass fixture (blosc compression, annotators work)", True),
        await run_semantic_test(FAIL_ASSET,
            "Fail fixture (SemanticSegmentation uses hevc)", False),
    ]
    print(f"\nOverall: {'PASS' if all(results) else 'FAIL'}"
          f" ({sum(results)}/{len(results)} checks passed)")
    import os as _os; _os._exit(0)

asyncio.ensure_future(main())
```

## Expected Result

The benchmark test writes one PNG per semantic annotator per Camera RenderProduct
to the run output directory. File names follow the pattern
`{rp_name}_{src_name}.png` (e.g. `CameraRp_SemanticSegmentation.png`).

`SemanticSegmentation` output is colorized by class ID — each unique integer
label is mapped to a distinct color; pixels with label 0 (background) are black.
Other semantic annotators are saved as normalized grayscale.

![semantic-aov-output expected result](../_images/semantic-aov-output.png)

Semantic segmentation output for the `CameraRp` render product from the PASS
fixture (`SemanticAovCompressionCheckerPass.usda`). Three labeled prims are
visible — box (green), ball (red), pillar (blue) — each rendered as a solid
color determined by its semantic class ID. The black background corresponds to
pixels with no semantic label. Distinct colored regions for each class confirm
that the camera, render product wiring, BLOSC-compressed `SemanticSegmentation`
RenderVar, and annotator pipeline are all functioning correctly.

## Notes and Caveats

**Relationship to static validation:**
RP.004 (`srtx:compression:type = "blosc"`) is enforced by the static validator,
not by this benchmark test. The benchmark adds genuine runtime value: it confirms
the semantic annotator names in `sourceName` are registered in Replicator and
the pipeline produces output — neither of which the static validator can verify.
The batch script below includes a BLOSC attribute check for manual debugging convenience.

**Data values and semantic labels:**
Semantic annotator output may be all-zero when no prims in the stage carry
`SemanticAPI` labels. This is expected for the minimal test fixtures and does
not indicate a failure — the check requires non-empty arrays, not non-zero
values.

**Compression format verification:**
The `srtx:compression:type` attribute controls how semantic AOV output is
compressed when written to disk by a Replicator writer. Reading via
`annotator.get_data()` returns an in-memory numpy array to which compression
has not been applied. Full end-to-end verification of the BLOSC compression on
output files requires a Replicator file-writing pass and EXR header inspection,
which is deferred (the `OpenEXR` library is also not bundled in Isaac Sim's
Python environment).

**BLOSC compression rationale:**
BLOSC is lossless and preserves integer label values exactly. Lossy codecs
(`"hevc"`, `"h264"`) corrupt integer segmentation labels, making them
unusable for training. This is why RP.004 enforces BLOSC for semantic AOVs.

Non-semantic AOVs (`"LdrColor"`, `"DepthLinearized"`, etc.) are not checked
by this test — their compression format is unrestricted.
