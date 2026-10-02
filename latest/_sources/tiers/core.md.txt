# Core Tier

The Core tier is the baseline SimReady Foundation distribution. It supplies the
requirements, capabilities, feature contracts, profile contracts, and static
validation rules used by general OpenUSD, visualization, physics, robotics,
semantic-label, non-visual-sensor, Isaac Sim, and packaging workflows. It has no
dependency on another Foundation tier.

Install the validator and tier together:

```bash
pip install simready-validate simready-foundation-tier-core
```

Install the optional Benchmark environment and the runtime tests bundled by the
tier with:

```bash
pip install "simready-foundation-tier-core[benchmark]"
```

The tables below reflect the catalogs in the current source tree. The tier's
feature JSON and profile TOML files remain the machine-readable sources of
truth.

## Profiles

Each profile version pins exact feature versions; a feature may also be marked
optional in the profile TOML, which is the machine-readable source of truth.
Links open the dedicated authoring page where one exists, otherwise the shared
profile comparison.

| Profile | Available versions | Catalog file |
| --- | --- | --- |
| [Robotics-Prop](../profiles/robotics-prop.md) | `3.0.0`, `3.1.0`, `3.2.0`, `3.3.0`, `4.0.0` | `robotics_prop.toml` |
| [Robot-Body](../profiles/robot-body.md) | `2.0.0`, `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0` | `robot_body.toml` |
| [Robot-Gripper](../profiles/robot-gripper.md) | `2.0.0`, `2.1.0`, `2.2.0`, `3.0.0` | `robot_gripper.toml` |
| [Package](../profiles/profiles.md#profile-comparison) | `1.0.0` | `package_profiles.toml` |
| [Package-NoBOM](../profiles/profiles.md#profile-comparison) | `1.0.0` | `package_profiles.toml` |
| [Package-Candidate](../profiles/profiles.md#profile-comparison) | `1.0.0`, `1.1.0`, `1.2.0`, `1.3.0` | `package_profiles.toml` |
| [Open-Taxonomy-COCO](../profiles/open-taxonomy-coco.md) | `0.1.0` | `open_taxonomy_profiles.toml` |
| [Open-Taxonomy-Cityscapes](../profiles/open-taxonomy-cityscapes.md) | `0.1.0` | `open_taxonomy_profiles.toml` |
| [Open-Taxonomy-ADE20K](../profiles/open-taxonomy-ade20k.md) | `0.1.0` | `open_taxonomy_profiles.toml` |
| [Open-Taxonomy-PascalVOC](../profiles/open-taxonomy-pascal_voc.md) | `0.1.0` | `open_taxonomy_profiles.toml` |
| [Open-Taxonomy-SUNRGBD](../profiles/open-taxonomy-sunrgbd.md) | `0.1.0` | `open_taxonomy_profiles.toml` |
| [Open-Taxonomy-ImageNet1K](../profiles/open-taxonomy-imagenet_1k.md) | `0.1.0` | `open_taxonomy_profiles.toml` |

## Features

The runtime suffix identifies the contract variant: `STANDARD`, `PHYSX`,
`NEWTON`, `MUJOCO`, `ISAAC`, `ROS`, `RTX`, `OPENPBR`, or `MDL`.

| Feature | Purpose | Available versions |
| --- | --- | --- |
| [FET_000_ISAAC](../features/FET_000_ISAAC.md) | Core (Isaac) | `0.1.0` |
| [FET_000_MUJOCO](../features/FET_000_MUJOCO.md) | Core (MuJoCo) | `0.1.0` |
| [FET_000_NEWTON](../features/FET_000_NEWTON.md) | Core (Newton) | `0.1.0` |
| [FET_000_PHYSX](../features/FET_000_PHYSX.md) | Core (PhysX) | `0.1.0` |
| [FET_000_STANDARD](../features/FET_000_STANDARD.md) | Core | `0.1.0`, `0.2.0` |
| [FET_001_STANDARD](../features/FET_001_STANDARD.md) | Minimal Placeable Visual | `0.1.0`, `1.0.0`, `1.0.1` |
| [FET_002_STANDARD](../features/FET_002_STANDARD.md) | Posable Bodies | `0.1.0` |
| [FET_003_MUJOCO](../features/FET_003_MUJOCO.md) | Rigid Body Physics (MuJoCo) | `0.1.0` |
| [FET_003_NEWTON](../features/FET_003_NEWTON.md) | Rigid Body Physics (Newton) | `0.1.0` |
| [FET_003_PHYSX](../features/FET_003_PHYSX.md) | Rigid Body Physics (PhysX) | `0.1.0`, `0.2.0`, `0.3.0`, `0.4.0` |
| [FET_003_STANDARD](../features/FET_003_STANDARD.md) | Rigid Body Physics | `0.1.0`, `0.2.0` |
| [FET_004_MUJOCO](../features/FET_004_MUJOCO.md) | Simulate Multi-Body Physics (MuJoCo) | `0.1.0` |
| [FET_004_NEWTON](../features/FET_004_NEWTON.md) | Simulate Multi-Body Physics (Newton) | `0.1.0` |
| [FET_004_PHYSX](../features/FET_004_PHYSX.md) | Simulate Multi-Body Physics (PhysX) | `0.1.0`, `0.2.0`, `0.3.0`, `0.4.0` |
| [FET_004_ROBOT_MUJOCO](../features/FET_004_ROBOT_MUJOCO.md) | Simulate Multi-Body Physics (Robot MuJoCo) | `0.1.0` |
| [FET_004_ROBOT_NEWTON](../features/FET_004_ROBOT_NEWTON.md) | Simulate Multi-Body Physics (Robot Newton) | `0.1.0` |
| [FET_004_ROBOT_PHYSX](../features/FET_004_ROBOT_PHYSX.md) | Simulate Multi-Body Physics (Robot PhysX) — **Deprecated; compatibility only** | `0.1.0`, `0.2.0`, `0.3.0`, `0.4.0` |
| [FET_004_STANDARD](../features/FET_004_STANDARD.md) | Simulate Multi-Body Physics | `0.1.0`, `0.2.0` |
| [FET_005_STANDARD](../features/FET_005_STANDARD.md) | Simulate Grasp Physics | `0.1.0` |
| [FET_006_MDL](../features/FET_006_MDL.md) | Materials (MDL) | `0.1.0`, `0.2.0` |
| [FET_006_OPENPBR](../features/FET_006_OPENPBR.md) | Materials (OpenPBR / MaterialX) | `0.1.0` |
| [FET_006_STANDARD](../features/FET_006_STANDARD.md) | Materials (UsdPreviewSurface) | `0.1.0`, `0.2.0` |
| [FET_007_STANDARD](../features/FET_007_STANDARD.md) | Non-Visual Materials | `0.2.0` |
| [FET_010_STANDARD](../features/FET_010_STANDARD.md) | Display Color | `0.1.0` |
| [FET_011_RTX](../features/FET_011_RTX.md) | Semantic Labels (RTX) | `0.1.0` |
| [FET_011_STANDARD](../features/FET_011_STANDARD.md) | Semantic Labels | `0.2.0` |
| [FET_021_ISAAC](../features/FET_021_ISAAC.md) | Robot Core (Isaac) | `0.1.0`, `0.2.0`, `0.3.0` |
| [FET_022_ISAAC](../features/FET_022_ISAAC.md) | Driven Joints (Isaac) | `0.1.0`, `0.2.0` |
| [FET_022_MUJOCO](../features/FET_022_MUJOCO.md) | Driven Joints (MuJoCo) | `0.1.0` |
| [FET_022_NEWTON](../features/FET_022_NEWTON.md) | Driven Joints (Newton) | `0.1.0` |
| [FET_022_PHYSX](../features/FET_022_PHYSX.md) | Driven Joints (PhysX) | `0.1.0`, `0.2.0` |
| [FET_022_STANDARD](../features/FET_022_STANDARD.md) | Driven Joints | `0.1.0`, `0.2.0` |
| [FET_023_ISAAC](../features/FET_023_ISAAC.md) | Robot Materials | `0.1.0` |
| [FET_024_MUJOCO](../features/FET_024_MUJOCO.md) | Base Articulation (MuJoCo) | `0.1.0` |
| [FET_024_NEWTON](../features/FET_024_NEWTON.md) | Base Articulation (Newton) | `0.1.0` |
| [FET_024_PHYSX](../features/FET_024_PHYSX.md) | Base Articulation (PhysX) | `0.1.0` |
| [FET_024_STANDARD](../features/FET_024_STANDARD.md) | Base Articulation | `0.1.0` |
| [FET_025_ROS](../features/FET_025_ROS.md) | ROS Ready (Isaac) | `0.1.0` |
| [FET_028_ISAAC](../features/FET_028_ISAAC.md) | Gripper (Isaac) | `0.1.0` |
| [FET_028_MUJOCO](../features/FET_028_MUJOCO.md) | Gripper (MuJoCo) | `0.1.0` |
| [FET_028_STANDARD](../features/FET_028_STANDARD.md) | Gripper | `0.1.0` |
| [FET_030_STANDARD](../features/FET_030_STANDARD.md) | Packaging Core | `0.1.0` |
| [FET_031_STANDARD](../features/FET_031_STANDARD.md) | Self-contained Package Source | `0.1.0` |
| [FET_032_STANDARD](../features/FET_032_STANDARD.md) | Packaging Introspection | `0.1.0` |
| [FET_033_STANDARD](../features/FET_033_STANDARD.md) | Metadata | `0.1.0`, `0.2.0`, `0.3.0`, `0.4.0` |
| [FET_040_STANDARD](../features/FET_040_STANDARD.md) | Semantic Labels - COCO | `0.1.0` |
| [FET_041_STANDARD](../features/FET_041_STANDARD.md) | Semantic Labels - Cityscapes | `0.1.0` |
| [FET_042_STANDARD](../features/FET_042_STANDARD.md) | Semantic Labels - ADE20K | `0.1.0` |
| [FET_043_STANDARD](../features/FET_043_STANDARD.md) | Semantic Labels - PASCAL VOC | `0.1.0` |
| [FET_044_STANDARD](../features/FET_044_STANDARD.md) | Semantic Labels - SUN RGB-D | `0.1.0` |
| [FET_045_STANDARD](../features/FET_045_STANDARD.md) | Semantic Labels - ImageNet-1K | `0.1.0` |
| [FET_046_STANDARD](../features/FET_046_STANDARD.md) | Semantic Labels - Wikidata | `0.1.0` |
| [FET_100_ISAAC](../features/FET_100_ISAAC.md) | IsaacSim Composition | `0.1.0`, `0.2.0`, `0.3.0`, `0.4.0` |
| [FET_101_ISAAC](../features/FET_101_ISAAC.md) | Robot IsaacSim Composition | `0.1.0` |

## Package contents and discovery

The distribution advertises both the `usd_validation_nvidia` and
`simready.tier` entry-point groups. Together they expose:

- Capability and requirement documentation plus registered validators.
- Generated requirement enums.
- Feature JSON and profile TOML catalogs.
- Optional tier-owned Benchmark runtime tests.

For the package layout, build commands, and local development notes, see the
README in `nv_core/tiers/simready_foundation_tier_core/` in the source tree.
