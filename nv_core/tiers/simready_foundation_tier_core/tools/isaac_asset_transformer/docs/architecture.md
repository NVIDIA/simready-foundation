# Architecture and Profiles

## Objective

The adapters use the public, Kit-free `isaacsim.asset.transformer` framework
from `isaacsim-asset-isolated==6.2.0.1`. The thin
`simready.asset_transformer` integration supplies SimReady profiles, CLI/API
conveniences, custom rules, and temporary compatibility patches. There is no
extension lifecycle, `SimulationApp`, or UI dependency.

## Package flow

```text
CLI or Python API
  -> load RuleProfile JSON
  -> discover and register importable rules
  -> AssetTransformerManager creates a working package
  -> ordered rules route and rewrite USD opinions
  -> ExecutionReport records each result and output layer
```

The public distribution supplies the manager, profile/report models, registry
contract, dependency collection, path remapping, and normal rules.

## Rule ownership

The public package supplies the production catalog:

- Structure: variant routing, flattening, interface composition.
- Core: schema, property, prim, and schema-removal routing.
- Performance: geometry deduplication/instancing and material/texture routing.
- Isaac: joint state, joint-pose repair, API list normalization, robot schema,
  mesh merge, MuJoCo-to-PhysX, and URDF-to-MuJoCo/PhysX.

The thin SimReady package retains `PropCleanupRule`,
`RuntimeInstanceRoutingRule`, `NeutralRuntimeVariantRule`, interface
customization, and the profile JSON.
It also temporarily patches four public rule implementations. The geometry patch preserves
the public `GeometriesRoutingRule` class while fixing an upstream issue: physics material
bindings are authored on the local referencing prim and removed from the
instance prototype. This keeps external physics-material targets inside a valid
USD namespace and allows `ComputeBoundMaterial("physics")` to resolve.

`RuntimeInstanceRoutingRule` addresses the corresponding solver-opinion issue.
USD does not permit an external layer to override a descendant of an
instanceable prim. The rule therefore creates one instances layer per runtime,
relocates mesh collision APIs and attributes onto the prototype mesh, and makes
each generated runtime overlay explicitly swap the wrapper reference.
`NeutralRuntimeVariantRule` then relocates those overlays to
`runnables/physics/<runtime>.usd` and re-anchors their references. This keeps the
geometry instanceable while satisfying the neutral runtime-variant contract.
Activation metadata stays aligned with the generated runtime options.

## Runtime dependencies and patches

The optional tier-core `[isaac]` extra requires Python 3.12,
`isaacsim-asset-isolated==6.2.0.1`, and
`isaacsim-robot-schema==6.2.0.0`. Both Isaac distributions are available on
PyPI and install with `pip install "simready-foundation-tier-core[isaac]"`.

Before public and SimReady rules are registered, the integration validates the
exact isolated-wheel version and selected method signatures, then applies three
small patches. The geometry patch keeps package-local asset paths relative when
the rule re-flattens the working layer; the variant-routing patch makes copied
dependencies owner-writable so a read-only source can be transformed; the
publish patch keeps search-path assets such as the built-in `OmniPBR.mdl` bare
instead of anchoring them to a missing `./OmniPBR.mdl`. The 6.0.1 material,
flatten, and joint-state patches are upstream in 6.2 and were removed. Importing
`simready.asset_transformer` registers the PhysX and Isaac robot USD schemas
before any stage opens, because USD builds its schema registry once per process.

The 6.2 manager builds each package in a staging folder and publishes only when
every rule succeeds and the output has no unresolved composition arc. The CLI
and the adapters treat `report.composition_errors` as a failure. The CLI also
stages replacement packages separately, preserving existing output if a rule,
composition check, or final replacement fails. Profile JSON keeps the
public `isaacsim.asset.transformer.rules.*` FQCNs. The patches are removed once
an upstream isolated wheel contains these fixes.

## Profile transforms

### `simready_physx_to_isaac_robot.json`

This is the robot-oriented profile using public
`isaacsim.asset.transformer.rules.*` names. It keeps robot schema routing, `robot.usda`,
and robot relationship normalization. Its runtime variants follow the same
neutral RV contract as the prop profile (items 1 and 3-8 below): `PhysX`,
`Newton`, and `MuJoCo` expose exactly `Enabled` and `Disabled`, default to
`Disabled`, and payload `runnables/physics/<runtime>.usd`. Neutral physics is
always sublayered into `payloads/base.usda`, so there is no generic `Physics`
interface variant. This keeps the source's
`SimReady_Metadata.Variants.Physics.*.activateOption = "Enabled"` descriptors
valid (RV.003/RV.006/RV.009).

### `simready_physx_to_isaac_prop.json`

This profile is derived from the robot profile and differs intentionally:

1. Runtime variants are flattened with PhysX, Newton, and MuJoCo disabled so
   the base contains neutral OpenUSD physics.
2. Isaac robot schema/property routing and `RobotSchemaRule` are omitted.
3. Neutral physics is always composed by sublayering
   `payloads/Physics/physics.usda` into `payloads/base.usda`.
4. The generic `Physics` folder is excluded from interface variant generation.
5. `PhysX`, `Newton`, and `MuJoCo` expose exactly `Enabled` and `Disabled`.
6. PhysX, Newton, and MuJoCo all default to `Disabled`.
7. Runtime mesh opinions are routed through runtime-specific instance layers.
8. Generated folder variants are rewritten to payload-only
   `runnables/physics/<runtime>.usd` variants with empty `Disabled` options.
9. `PropCleanupRule` removes Kit viewport roots and session metadata.
10. `ThumbnailCopyRule` copies `.thumbs/<size>/<source>*` images and renames
    them for the generated interface layer (also used by the robot profile).

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
.thumbs/256x256/asset.usda*.png
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
runnables/
  physics/
    physx.usd
    newton.usd
    mujoco.usd
transform_report.json
```

The interface contains only the asset default prim, references `base.usda`, and
owns the three runtime variant sets. Prim paths for geometry, joints, semantics,
grasp data, and materials remain stable in the composed stage.

## Adapter integration

The prop and robot paths are both integrated in
`nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/physx_to_isaacsim/__init__.py`:

1. A `FET001_MinimalPlaceableVisual.1-0-1` -> `CAP100_IsaacComposition.Isaac.0-4-0` CIP feature adapter
   (`minimal_to_isaac_prop_standalone`) instantiates the public
   `AssetTransformerManager` and loads the `simready_physx_to_isaac_prop`
   transform via `load_profile`, resolving the JSON by explicit path from
   `profile_transforms_dir()`.
2. A `FET001_MinimalPlaceableVisual.1-0-1` -> `CAP101_RobotComposition.Isaac.0-1-0` CIP feature adapter
   (`minimal_to_isaac_robot_standalone`) runs the same public backend with
   the `simready_physx_to_isaac_robot` transform. `CAP101_RobotComposition.Isaac` exists so
   robot profiles route to the robot transform: adapters key only on input/output
   contract IDs, so a distinct output contract is required to disambiguate robot
   from prop composition (both otherwise map from `FET001_MinimalPlaceableVisual.1-0-1`).
3. Deprecated Kit-extension adapters (`CAP100_IsaacComposition.Isaac.0-1-0` and
   the pre-underscore `FET100_BASE_ISAACSIM`) are no longer registered.
4. Both active paths share `_convert_with_simready_transform`, which also
   stamps `kind = component` on the composed interface default prim so the Isaac
   composition requirement `ISA.001` is satisfied.
5. Temporary-directory output and `Sdf.CopySpec` promotion are shared through
   `physx_to_isaacsim/promotion.py`, which is unit-tested in
   `nv_core/tiers/simready_foundation_tier_core/tools/isaac_asset_transformer/tests/test_isaac_prop_adapter_promotion.py`.
6. The adapter imports the installed tier integration and public transformer;
   there is no source-path fallback.
