# Foundations 2 Catalog Migration

This is the Foundations 1 input transformation reference. Original Benchmark
terminology and legacy IDs below identify that migration format, not current
Evaluate APIs or current Foundations 2 runtime coverage validation. Use the
[Evaluate guide](evaluate/evaluate.md) for current runtime workflows.

The tier-owned `foundations2/` directories are the canonical projection of all
published Foundations 1 FET manifests and profile pins into the Foundations 2
contract model. The published source files remain available as compatibility
aliases while SimReady Explorer adopts the new loader.

## Classification rule

For every exact published `FET_…@version` contract:

1. If any tier's Benchmark suite maps an executable runtime test to that exact
   legacy ID/version range, it becomes a dotted FET. A tier's suites are the
   top-level packages its wheel ships besides `simready`.
2. The `STANDARD` contract remains a source FET when its family contains a
   tested derived FET, even if the source has no direct runtime test.
3. Every other testless contract becomes a `CAP`-prefixed capability.

This keeps `FET004_Multibody.*` as the source for tested PhysX/Newton
multibody variants. Untested MuJoCo multibody contracts are CAP entries until
an exact runtime test is registered.

The current runtime-backed families are:

| Family | Runtime evidence |
|---|---|
| FET001 | visual presence, normals, culling, pivot, and light response |
| FET003 | ground drop, ground stability, and slope drop (PhysX and Newton) |
| FET004 | joint movement (PhysX and Newton) |
| FET005 | grasp and lift |
| FET006 | Preview Surface, MDL, and OpenPBR renders |
| FET010 | display color response |
| FET011 | semantic segmentation labelled/stripped |
| FET012 | Gaussian splat presence |
| FET022 | driven-joint motion and control tests (PhysX, Isaac, and Newton) |
| FET028 | gripper close/lift tests |
| FET034 | IMU sensor data |
| FET035 | render product and semantic AOV output |
| FET036 | LiDAR point cloud |
| FET037 | joint sensor data |

The Newton variants are tested by the Newton tier's own suite, and FET034–FET037
by the sensors tier's.

## Identity projection

Feature IDs use `<name>[.<runtime>].<version>`. Capability IDs use the same
descriptive suffix but begin with `CAP`. Published semantic versions are
encoded losslessly as one segment by replacing dots with hyphens:

```text
FET_004_PHYSX@0.4.0
-> FET004_Multibody.PhysX.0-4-0

FET_000_STANDARD@0.1.0
-> CAP000_Core.0-1-0
```

The generated `catalog-map.json` in each tier preserves the legacy identity,
new identity, contract kind, and exact runtime-test references.

## Tier layout

Each tier exposes both compatibility and Foundations 2 sources:

```text
tier_*/
  features/                 # published Foundations 1 compatibility manifests
  profiles/                 # published Foundations 1 compatibility profiles
  foundations2/
    capabilities/           # CAP JSON definitions
    features/               # source and runtime FET JSON definitions
    profiles/               # profiles with split FET/CAP selectors
    catalog-map.json        # exact identity/classification map
```

`TierContent.capability_contracts_path`, `feature_contracts_path`, and
`profile_contracts_path` expose the new directories to the validator without
removing the older `features_path` and `profiles_path` attributes.

## Regeneration

Run the deterministic projection after a published compatibility contract,
runtime-test registration, or profile is added:

```text
python nv_core/tiers/_tooling/migrate_foundations2_catalog.py
```

Review `catalog-map.json` and run the catalog-wide contract tests. Do not edit
generated Foundations 2 JSON/TOML files by hand; change the source manifest,
test registration, profile, or migration mapping and regenerate.

## Validator handoff

SimReady Explorer should prefer the three Foundations 2 tier paths when they
exist, load the complete cross-tier CAP/FET catalogs before profiles, validate
source/derived FET relationships, and fall back to the compatibility paths only
for older tiers. See [Validator Integration](validator-integration.md).
