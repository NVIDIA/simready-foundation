# Architecture and Profiles

## Objective

The previous adapter imported `isaacsim.asset.transformer` from an enabled Kit
extension. The new package keeps the same rule-driven design but runs as normal
Python under the `simready.asset_transformer` namespace. There is no extension
lifecycle, `SimulationApp`, or UI dependency.

## Package flow

```text
CLI or Python API
  -> load RuleProfile JSON
  -> discover and register importable rules
  -> AssetTransformerManager creates a working package
  -> ordered rules route and rewrite USD opinions
  -> ExecutionReport records each result and output layer
```

The manager, profile/report models, registry contract, dependency collection,
path remapping, and deterministic quaternion handling are ported from the
latest transformer core. SPDX and Apache-2.0 provenance are retained.

## Complete rule catalog

All latest production rule sources are included:

- Structure: variant routing, flattening, interface composition.
- Core: schema, property, prim, and schema-removal routing.
- Performance: geometry deduplication/instancing and material/texture routing.
- Isaac: joint state, joint-pose repair, API list normalization, robot schema,
  mesh merge, PhysX-to-MuJoCo, MuJoCo-to-PhysX, and URDF-to-MuJoCo/PhysX.
- SimReady additions: `PropCleanupRule` and `RuntimeInstanceRoutingRule`.

The prop path also fixes an upstream geometry-routing issue: physics material
bindings are authored on the local referencing prim and removed from the
instance prototype. This keeps external physics-material targets inside a valid
USD namespace and allows `ComputeBoundMaterial("physics")` to resolve.

`RuntimeInstanceRoutingRule` addresses the corresponding solver-opinion issue.
USD does not permit an external layer to override a descendant of an
instanceable prim. The rule therefore creates one instances layer per runtime,
relocates mesh collision APIs and attributes onto the prototype mesh, and makes
each runtime `enabled.usda` explicitly swap the wrapper reference. This keeps
the geometry instanceable while ensuring the composed mesh receives the
selected runtime's authored approximation.

## Optional dependency model

The core and prop rules run with Pixar USD and NumPy. Specialized modules retain
their upstream imports:

- `usd.schema.isaac.robot_schema` for `RobotSchemaRule` (now optional; see below).
- `isaacsim.asset.importer.utils` for mesh and solver conversion rules.

Discovery skips only modules whose optional dependency is absent. This lets the
prop demo run in a small environment while preserving the full robot source and
behavior for an Isaac-enabled environment.

`RobotSchemaRule` is a special case: it imports `usd.schema.isaac` optionally so
the module always loads and the rule always registers. When the Isaac schema is
available it uses the Kit path (`ApplyRobotAPI` /
`PopulateRobotSchemaFromArticulation`). When it is not, a Kit-free fallback
authors the same USD the SimReady RC.007 validator checks: it adds the
`IsaacRobotAPI` applied schema to the `apiSchemas` list op via Sdf (so an
unregistered schema is still recorded) and authors `isaac:physics:robotLinks` /
`isaac:physics:robotJoints` from the descendant PhysX rigid bodies and joints.
`isaac:robotType` is intentionally not authored by the fallback. The Kit-free
path is covered by
`nv_core/cip_specs/isaac_asset_transformer/tests/test_robot_schema_kitfree.py`.

## Profile transforms

### `simready_physx_to_isaac_robot.json`

This is the latest upstream robot-oriented profile with rule type names changed
to `simready.asset_transformer.*`. It keeps robot schema routing, `robot.usda`,
robot relationship normalization, generic Physics variants, and all existing
robot composition behavior.

### `simready_physx_to_isaac_prop.json`

This profile is derived from the robot profile and differs intentionally:

1. Runtime variants are flattened with PhysX, Newton, and MuJoCo disabled so
   the base contains neutral OpenUSD physics.
2. Isaac robot schema/property routing and `RobotSchemaRule` are omitted.
3. Neutral physics is always composed by sublayering
   `payloads/Physics/physics.usda` into `payloads/base.usda`.
4. The generic `Physics` folder is excluded from interface variant generation.
5. `PhysX`, `Newton`, and `MuJoCo` expose exactly `Enabled` and `Disabled`.
6. Defaults match the toolbox source: PhysX enabled, Newton and MuJoCo disabled.
7. Runtime mesh opinions are routed through runtime-specific instance layers.
8. `PropCleanupRule` removes Kit viewport roots and session metadata.

## Shared interface enhancements

`InterfaceConnectionRule` gained backwards-compatible options:

- `excluded_variant_sets`
- `include_none_variant`
- `capitalize_variant_names`

Their defaults preserve robot-profile behavior. The prop profile opts into the
new semantics.

## Output contract

```text
asset.usda
Textures/
source_assets/
payloads/
  base.usda
  geometries.usd
  instances.usda
  instances_physx.usda
  instances_newton.usda
  instances_mujoco.usda
  materials.usda
  Physics/physics.usda
  PhysX/{enabled,disabled}.usda
  Newton/{enabled,disabled}.usda
  MuJoCo/{enabled,disabled}.usda
transform_report.json
```

The interface contains only the asset default prim, references `base.usda`, and
owns the three runtime variant sets. Prim paths for geometry, joints, semantics,
grasp data, and materials remain stable in the composed stage.

## Adapter integration

The prop and robot paths are both integrated in
`nv_core/cip_specs/asset_handler_modules/physx_to_isaacsim/__init__.py`:

1. A `FET_001_STANDARD@1.0.1` -> `FET_100_ISAAC@0.4.0` CIP feature adapter
   (`minimal_to_isaac_prop_standalone`) instantiates the standalone
   `AssetTransformerManager` and loads the `simready_physx_to_isaac_prop`
   transform via `load_profile`, resolving the JSON by explicit path from
   `profile_transforms_dir()`.
2. A `FET_001_STANDARD@1.0.1` -> `FET_101_ISAAC@0.1.0` CIP feature adapter
   (`minimal_to_isaac_robot_standalone`) runs the same standalone backend with
   the `simready_physx_to_isaac_robot` transform. `FET_101_ISAAC` exists so
   robot profiles route to the robot transform: adapters key only on input/output
   feature IDs, so a distinct output feature is required to disambiguate robot
   from prop composition (both otherwise map from `FET_001_STANDARD@1.0.1`).
3. The existing Kit-extension adapters (`FET_100_ISAAC@0.1.0`,
   `FET100_BASE_ISAACSIM@0.2.0`, `FET100_BASE_ISAACSIM@0.4.0`) are preserved and
   continue to use the legacy Kit backend.
4. Both standalone paths share `_convert_with_simready_transform`, which also
   stamps `kind = component` on the composed interface default prim so the Isaac
   composition requirement `ISA.001` is satisfied.
5. Temporary-directory output and `Sdf.CopySpec` promotion are shared by both
   backends through `physx_to_isaacsim/promotion.py`, which is unit-tested in
   `nv_core/cip_specs/isaac_asset_transformer/tests/test_isaac_prop_adapter_promotion.py`.
6. Package import in the host runtime: the adapter first checks whether
   `simready.asset_transformer` is importable and, if not, inserts the in-repo
   `isaac_asset_transformer/src` root onto `sys.path`. `simready` is a PEP 420
   namespace package in both this transformer and the tier-core
   `simready.foundation` tree, so the added path merges into the existing
   `simready` namespace without shadowing already-imported subpackages. This lets
   the Kit/CIP runtime, which loads the adapter from repo source, resolve the
   transformer even when it is not pip-installed.
