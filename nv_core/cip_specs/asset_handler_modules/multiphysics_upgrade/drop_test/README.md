# ovphysx prop drop test

This fixture references a SimReady prop at `/DropTest/Prop`, starts it two
meters above a static ground collider with a small XYZ rotation, and records
every rigid-body pose while stepping ovphysx.

Install the standalone runtime:

```powershell
python -m pip install ovphysx
```

Run a prop:

```powershell
python nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade/drop_test/run_drop_test.py `
  path/to/sm_prop_01.usd `
  --output-dir drop_test_output
```

The command writes:

- `drop_test_scene.usda`: the generated fixture with a relative prop reference.
- `poses.csv`: one row per body per step (`step,time,body,px,py,pz,qx,qy,qz,qw`).

## Rigid-body discovery

The runner does not assume the prop is a single rigid body at the reference
root. It opens the composed fixture with `pxr` and collects every prim under
`/DropTest/Prop` that has `PhysicsRigidBodyAPI` applied and enabled, then binds
those paths explicitly. That covers both shapes a SimReady prop can take:

- a single-rigid-body prop, whose root prim carries the API, and
- a multibody prop, which carries `PhysicsRigidBodyAPI` on each part under
  `Geometry` (`box_obj_01`, `lid_obj_01`, ...) and nothing on the root.

Instance proxies are skipped, because PhysX cannot address a prim inside a
prototype individually — only the instanceable root is bindable.

The run passes when every body loses at least 0.1 m of height and no body sinks
more than 0.5 m below the ground collider (which would mean it tunneled).

## Runtime variant

`--variant` selects which physics runtime variant to enable on the prop:

```powershell
--variant PhysX    # default
--variant Newton
--variant MuJoCo
--variant none     # neutral base, no variant selection
```

Choosing a variant changes collider approximation. The PhysX delta uses SDF
collision, so a mesh that is not watertight or manifold produces
`SDF creation: Mesh is not suitable for SDF ...` warnings from PhysX and the
collision shape may be inaccurate. `--variant MuJoCo` uses convex hulls
instead, which is a useful comparison when SDF results look wrong.

## Device mode

The runner creates PhysX with `device="cpu"`. The tensor bindings hand back
host-side tensors in CPU mode, which is what the NumPy read path needs; a GPU
instance returns device tensors and `binding.read()` fails with a device
mismatch. Expect `GPU solver pipeline failed, switching to software` warnings
as a result — they are the intended CPU fallback, not an error.

Other warnings that are benign here: `omni_usd_resolver.dll` failing to load
(Omniverse URLs are unused), `Cannot find omni client plugin`, missing optional
`pxr.*` modules, and the omnihydra scene-graph-instancing notice.

## Viewing

`ovphysx` is headless and ships no renderer. There is no `--realtime` viewer;
that flag only throttles stepping to wall-clock speed. To watch a run, plot
`poses.csv` afterwards, or stream the pose tensor to an external viewer such as
Rerun (which shows proxy primitives unless the asset geometry is loaded
separately). Producing a video likewise requires an external renderer.
