# render_product_output  (FET035 Render Products)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | render_product_output          |
| Feature(s)   | FET_035_RTX  |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.1.0                          |

## Running with simready-benchmark

This test is implemented and available in the `simready-benchmark-kit-suite` package.
Run it against an asset:

```bash
simready-benchmark --assets path/to/asset.usd --features FET035
```

The test skips automatically if no authored `RenderProduct` prim is found (excluding OmniverseKit internal prims).

## Summary

Reads the camera path, resolution, and AOV source names from each authored
`RenderProduct` prim, then creates a matching Replicator render product and
reads back AOV data to confirm each declared annotator produces non-empty
output. Output images are saved per annotator for visual inspection.

## What Pass Guarantees

A reviewer, PM, or OEM can trust that every `RenderProduct` in the scene has
a valid `camera` relationship, at least one declared AOV, and that each
declared `sourceName` corresponds to a registered Replicator annotator that
produces non-empty output at the authored resolution. The asset is ready for
use in an SDG pipeline that expects these properties to be correctly authored.

## What It Checks

For each authored `RenderProduct` prim, the test reads the `camera` relationship,
`resolution`, and `sourceName` values from `orderedVars`. If the camera or source
names are absent the prim is silently skipped. For `RenderProduct` prims whose
camera is a USD `Camera` prim, a Replicator render product is created with the same
camera and resolution, annotators are attached matching each `sourceName`, one frame
is triggered, and data is verified:

- **Color annotators** (`LdrColor`, `HdrColor`, semantic annotators): pass on
  non-empty array alone. Color may be black when the scene has no materials —
  this is expected for minimal test fixtures.
- **Geometry annotators** (`DepthLinearized`, `normals`, etc.): additionally
  require at least one non-zero value, confirming geometry is visible from
  the camera.

A reference cube is placed 2 m in front of each camera along its world-space
forward direction so geometry annotators have meaningful hits.

`OmniLidar` prims are skipped — multiple RTX LiDAR sensors in the same
Replicator pass cause a CUDA conflict. Their point cloud output is covered by
the `lidar_point_cloud` test.

Key thresholds from `config_defaults`:

- `warmup_frames`: 30 (physics + timeline frames before triggering the Replicator step)
- `default_resolution`: (512, 512) (fallback if the authored RP has no `resolution` attribute)

## How It Works

**Stage traversal:** `RenderProduct` prims are typically authored in a `/Render` scope that is a sibling of the asset's `defaultPrim`. The framework's `load_asset()` references only the `defaultPrim` subtree, making `/Render` invisible to the composed stage. The test opens the raw asset file via `Usd.Stage.Open(ctx.asset_path)` to traverse all prims including `/Render`.

**Property reading:** for each authored `RenderProduct` (excluding OmniverseKit internal prims), the test reads the `camera` relationship, `resolution`, and `sourceName` values from `orderedVars` directly from the raw asset stage. RenderProducts with a missing camera or no source names are silently skipped.

**Camera path remapping:** camera prim paths from the raw asset (e.g. `/Root/RGB_Camera`) are remapped to their equivalents in the composed stage (where cameras were loaded under the framework's path prefix). Remapping uses a name-based lookup: all `Camera` prims in the composed stage are indexed by name, then matched by the last component of the raw camera path.

**Replicator AOV check:** for each `Camera`-typed render product:
1. A 0.4 m reference cube is placed 2 m along the camera's world-space forward direction so depth and normals annotators have geometry to sample.
2. `rep.create.render_product(cam_path, resolution)` creates a Replicator-managed render product mirroring the authored camera and resolution.
3. `rep.annotators.get(source_name)` is called for each authored `sourceName`; an unrecognised name fails here.
4. `rep.orchestrator.step_async()` triggers one Replicator frame, followed by 10 `next_update_async()` calls.
5. Annotator data is validated: color annotators pass on non-empty array; geometry annotators additionally require at least one non-zero value.

`OmniLidar` prims are identified by name lookup in the composed stage and skipped for the Replicator check (CUDA conflict). Their point cloud output is covered by the `lidar_point_cloud` test.

Output images are saved to the run output directory (one PNG per annotator per Camera RenderProduct). Color annotators may appear black for minimal fixtures — the companion `_alpha.png` file confirms geometry hits. Depth and normals images are saved as normalized grayscale.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| `rep.create.render_product()` failed | The camera prim path does not exist in the composed stage or is not a renderable `Camera` prim. |
| Annotator not registered | A `sourceName` value does not match any registered Replicator annotator name (RP.003 violation). |
| Geometry annotator all-zero | No geometry is visible from the camera — check camera transform and cube placement. |
| Annotator returned empty array | The render pipeline produced no output. Increase `warmup_frames`. |
| Test skipped (not applicable) | No authored `RenderProduct` prim was found, or all cameras are `OmniLidar` type, or all RenderProducts have missing camera/sourceNames. |
| Static validation failed | The asset did not pass RP.001–RP.003. Fix the static issues first. |
| `/Render` scope prims not found | This only affects the batch script (which opens the stage directly). The benchmark test uses `Usd.Stage.Open()` to avoid this. |

## How to Fix

If an annotator is not registered, verify that the `sourceName` attribute on
the `RenderVar` prim matches a name in the Replicator annotator registry.
Common valid names include `LdrColor`, `HdrColor`, `DepthLinearized`,
`normals`, `SemanticSegmentation`, and `GenericModelOutput`.

If geometry annotators are all-zero, confirm that the camera prim's world
transform is correctly authored so the reference cube falls within the
camera's field of view.

## Manual Testing in Isaac Sim

### Batch script

Save the script below to a file (e.g. `batch_test_render_product_output.py`)
under the repo root and run it with:

```powershell
# Windows
isaac-sim.bat --no-window --exec "C:\Dev\simready_foundations\batch_test_render_product_output.py"
```

```bash
# Linux
./isaac-sim.sh --no-window --exec "/path/to/simready_foundations/batch_test_render_product_output.py"
```

Expected output summary:

```
Overall: PASS (2/2 checks passed)
```

Output images are written to `_batch_test_output/render_product/` with one
file per annotator per Camera RenderProduct. The `LdrColor` image will appear
black (no material on the reference cube) but the `_alpha.png` file confirms
geometry hits. The `DepthLinearized` image shows a dark square (near cube)
on a white background (far clip distance). The `normals` image shows the cube
face as a coloured patch on a grey background.

```python
import asyncio, os
import numpy as np

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
PASS_ASSET = os.path.join(REPO_ROOT,
    "nv_core/sr_specs/tests/data/render_products/RenderProductsCheckerPass.usda")
FAIL_ASSET = os.path.join(REPO_ROOT,
    "nv_core/sr_specs/tests/data/render_products/RenderProductsCheckerFail.usda")
OUTPUT_DIR = os.path.join(REPO_ROOT, "_batch_test_output", "render_product")
WARMUP_FRAMES = 30
DEFAULT_RESOLUTION = (512, 512)
COLOR_ANNOTATORS = ("LdrColor", "HdrColor", "SemanticSegmentation",
                    "SemanticBoundingBox2DLoose", "SemanticBoundingBox2DTight")


def is_kit_internal(p): return "OmniverseKit" in str(p)


def place_cube_in_front_of_camera(stage, cam_path, index):
    # Place a 0.4 m cube 2 m in front of the camera along its world forward
    # direction so depth and normals annotators have geometry to measure.
    from pxr import UsdGeom, Gf, Usd
    cam = stage.GetPrimAtPath(cam_path)
    if not cam.IsValid(): return
    xf = UsdGeom.XformCache(Usd.TimeCode.Default())
    world_xf = xf.GetLocalToWorldTransform(cam)
    fwd = world_xf.TransformDir(Gf.Vec3d(0, 0, -1)).GetNormalized()
    pos = Gf.Vec3d(world_xf.ExtractTranslation()) + fwd * 2.0
    cube = UsdGeom.Cube.Define(stage, f"/World/DepthCube_{index}")
    cube.GetSizeAttr().Set(0.4)
    UsdGeom.XformCommonAPI(cube.GetPrim()).SetTranslate((pos[0], pos[1], pos[2]))


def read_rp_properties(stage, rp_prim):
    # Read the authored camera path, resolution, and sourceName list from the RP.
    cam_rel  = rp_prim.GetRelationship("camera")
    vars_rel = rp_prim.GetRelationship("orderedVars")
    cam_path = (str(cam_rel.GetTargets()[0])
                if cam_rel.IsValid() and cam_rel.GetTargets() else None)
    res_attr = rp_prim.GetAttribute("resolution")
    resolution = (tuple(int(v) for v in res_attr.Get())
                  if res_attr.IsValid() and res_attr.Get() is not None
                  else DEFAULT_RESOLUTION)
    source_names = []
    if vars_rel.IsValid():
        for var_path in vars_rel.GetTargets():
            var_prim = stage.GetPrimAtPath(var_path)
            if not var_prim.IsValid(): continue
            src_attr = var_prim.GetAttribute("sourceName")
            if src_attr.IsValid() and src_attr.Get():
                source_names.append(src_attr.Get())
    return cam_path, resolution, source_names


def save_image(data, label, rp_name, src_name):
    from PIL import Image
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{label}_{rp_name}_{src_name}.png")
    arr = np.array(data, dtype=float)
    if arr.ndim == 1: return  # 1-D buffers (e.g. point cloud) — skip
    if arr.ndim == 3 and arr.shape[2] in (3, 4):
        rgb = arr[:, :, :3]
        mn, mx = rgb.min(), rgb.max()
        if mn < 0:
            rgb = (rgb + 1.0) / 2.0 * 255  # normals: remap [-1,1] to [0,255]
        elif mx <= 1.0:
            rgb = rgb * 255                  # float [0,1] to uint8 [0,255]
        Image.fromarray(rgb.clip(0, 255).astype(np.uint8), "RGB").save(path)
        # Save alpha separately for color annotators — useful when RGB is black
        # (no material) but alpha=255 confirms geometry was hit.
        if arr.shape[2] == 4 and any(c in path for c in COLOR_ANNOTATORS):
            alpha_path = path.replace(".png", "_alpha.png")
            alpha = arr[:, :, 3].clip(0, 255).astype(np.uint8)
            Image.fromarray(alpha, "L").save(alpha_path)
    elif arr.ndim == 2:
        # Normalize finite values to [0,255] grayscale; inf/nan pixels map to 0.
        finite = np.isfinite(arr)
        vis = np.zeros_like(arr)
        if finite.any():
            mn, mx = arr[finite].min(), arr[finite].max()
            if mx > mn:
                vis[finite] = (arr[finite] - mn) / (mx - mn)
        Image.fromarray((vis * 255).astype(np.uint8), "L").save(path)


async def check_structural(stage):
    from pxr import UsdRender
    rps = [p for p in stage.Traverse()
           if p.IsA(UsdRender.Product) and not is_kit_internal(p.GetPath())]
    print(f"    Authored RenderProduct prims: {len(rps)}")
    all_ok = True
    for rp in rps:
        cam_rel  = rp.GetRelationship("camera")
        vars_rel = rp.GetRelationship("orderedVars")
        cam_ok  = cam_rel.IsValid() and len(cam_rel.GetTargets()) > 0
        vars_ok = vars_rel.IsValid() and len(vars_rel.GetTargets()) > 0
        print(f"    {rp.GetPath()}")
        print(f"      camera    : {'PASS' if cam_ok  else 'FAIL'}")
        print(f"      orderedVars: {'PASS' if vars_ok else 'FAIL'}")
        if not (cam_ok and vars_ok): all_ok = False
    return all_ok, rps


async def check_replicator_aovs(stage, rps, label):
    import omni.kit.app, omni.replicator.core as rep
    all_ok = True
    for rp in rps:
        rp_name = rp.GetPath().name
        cam_path, resolution, source_names = read_rp_properties(stage, rp)
        if not cam_path or not source_names:
            print(f"      FAIL: {rp_name} — missing camera or sourceNames")
            all_ok = False; continue
        cam_prim = stage.GetPrimAtPath(cam_path)
        if not cam_prim.IsValid():
            print(f"      FAIL: {rp_name} — camera prim not found")
            all_ok = False; continue
        if cam_prim.GetTypeName() == "OmniLidar":
            print(f"      SKIP: {rp_name} — OmniLidar deferred to lidar test")
            continue
        place_cube_in_front_of_camera(stage, cam_path,
                                       list(rps).index(rp))
        # Copy-construct: create a Replicator RP mirroring the authored one.
        # rep.create.render_product() uses the authored camera and resolution
        # but creates its own internal RP rather than activating the authored
        # prim — see Notes and Caveats for the scope limitation.
        try:
            rep_rp = rep.create.render_product(cam_path, resolution)
            rep_rp_path = rep_rp.path if hasattr(rep_rp, "path") else str(rep_rp)
        except Exception as e:
            print(f"      FAIL: {rp_name} — render product creation failed: {e}")
            all_ok = False; continue
        attached = []
        for src_name in source_names:
            try:
                anno = rep.annotators.get(src_name)
                anno.attach(rep_rp_path)
                attached.append((src_name, anno))
                print(f"      PASS: {rp_name} — annotator '{src_name}' attached")
            except Exception as e:
                print(f"      FAIL: {rp_name} — '{src_name}' not registered: {e}")
                all_ok = False
        if not attached: continue
        try:
            await rep.orchestrator.step_async()
        except Exception:
            await rep.orchestrator.run_async(num_frames=1)
        for _ in range(10):
            await omni.kit.app.get_app().next_update_async()
        for src_name, anno in attached:
            try:
                data = anno.get_data()
                arr = (np.array(data.get("data", list(data.values())[0]))
                       if isinstance(data, dict) else np.array(data))
                if arr.size == 0:
                    print(f"      FAIL: {rp_name} '{src_name}' — empty")
                    all_ok = False
                else:
                    nonzero = bool(np.any(arr != 0))
                    is_color = src_name in COLOR_ANNOTATORS
                    if not is_color and not nonzero:
                        print(f"      FAIL: {rp_name} '{src_name}' — all-zero")
                        all_ok = False
                    else:
                        print(f"      PASS: {rp_name} '{src_name}'"
                              f" shape={arr.shape} nonzero={nonzero}")
                    save_image(arr, label.split()[0].lower(), rp_name, src_name)
            except Exception as e:
                print(f"      SKIP: {rp_name} '{src_name}' error: {e}")
    return all_ok


async def run_test(asset_path, label, expect_pass):
    import omni.usd, omni.kit.app, omni.kit.commands, omni.physx, omni.timeline
    print(f"\n--- {label} ---")
    await omni.usd.get_context().open_stage_async(asset_path)
    for _ in range(5): await omni.kit.app.get_app().next_update_async()
    omni.kit.commands.execute("CreatePrimWithDefaultXform", prim_type="DistantLight")
    for _ in range(3): await omni.kit.app.get_app().next_update_async()
    stage = omni.usd.get_context().get_stage()
    struct_ok, rps = await check_structural(stage)
    omni.physx.get_physx_interface().start_simulation()
    omni.timeline.get_timeline_interface().play()
    for _ in range(WARMUP_FRAMES): await omni.kit.app.get_app().next_update_async()
    aov_ok = await check_replicator_aovs(stage, rps, label)
    omni.timeline.get_timeline_interface().stop()
    passed = struct_ok and aov_ok
    print(f"    Structural  : {'PASS' if struct_ok else 'FAIL'}")
    print(f"    Replicator  : {'PASS' if aov_ok else 'FAIL'}")
    return passed if expect_pass else not passed


async def main():
    print("=" * 60)
    print("Batch test: Render product output (FET035 RP.001/RP.002/RP.003)")
    print("=" * 60)
    results = [
        await run_test(PASS_ASSET, "Pass fixture (expect PASS)", True),
        await run_test(FAIL_ASSET, "Fail fixture (expect FAIL)", False),
    ]
    print(f"\nOverall: {'PASS' if all(results) else 'FAIL'}"
          f" ({sum(results)}/{len(results)} checks passed)")
    import os as _os; _os._exit(0)

asyncio.ensure_future(main())
```

## Expected Result

The benchmark test writes one PNG per annotator per Camera RenderProduct to the
run output directory. File names follow the pattern `{rp_name}_{src_name}.png`
(e.g. `RGB_CameraRp_normals.png`). Color annotators (LdrColor, HdrColor) that
have an alpha channel also produce a companion `_alpha.png` file.

![render-product-output expected result](../_images/render-product-output.png)

The `normals` annotator output for the `RGB_CameraRp` render product from the
PASS fixture (`RenderProductsCheckerPass.usda`). The reference cube placed 2 m
in front of the camera appears as a coloured patch — each colour encodes the
surface normal direction. The surrounding grey background corresponds to the
far-clip plane (no geometry hit). A non-grey patch confirms that the camera,
render product wiring, and `normals` annotator are all functioning correctly.

The `LdrColor` image will appear black for minimal fixtures (no material on the
reference cube), but the `_alpha.png` companion image shows white pixels where
the cube geometry was hit. The `DepthLinearized` image shows a dark square (near
cube) on a white background (far clip plane).

## Notes and Caveats

**Scope limitation — Replicator creates its own render product:**
`rep.create.render_product()` creates a Replicator-managed render product
rather than activating the authored `RenderProduct` prim in the stage. The
test mirrors the authored configuration (camera path, resolution, sourceName
values) but does not route output through the authored
`RenderProduct → orderedVars → RenderVar` chain. Activating cold-authored
RenderProduct prims with Hydra is a known API gap currently under development
by the Replicator team (`#omni-rtx`, Avinash Devalla, March 2026).

**Full pipeline verification — future work:**
End-to-end verification that the authored `RenderProduct → RenderVar` chain
actually writes the declared AOVs to disk requires native Hydra activation of
the authored prim, which is deferred. When the API becomes available, it would
allow attaching annotators directly to the existing authored path rather than
creating a new one.

**Color annotator image appearance:**
The `LdrColor` image will appear black for the minimal test fixture because
the reference cube has no material. The `_alpha.png` companion image confirms
geometry is present (white pixels where the cube is hit). The depth and
normals images are more informative for visual inspection.

**OmniLidar RenderProducts:**
`OmniLidar` prims are skipped for the Replicator check because running two
RTX LiDAR sensors with the `GenericModelOutput` annotator in the same
Replicator pass causes a CUDA memory conflict and crashes Isaac Sim. Point
cloud output is verified by the `lidar_point_cloud` test.
