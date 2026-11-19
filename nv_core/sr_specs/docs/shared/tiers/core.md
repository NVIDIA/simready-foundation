# Core Tier

The Core tier is the baseline SimReady Foundation distribution. It supplies the
requirements, capabilities, feature contracts, profile contracts, and static
validation rules used by general OpenUSD, visualization, physics, robotics,
semantic-label, non-visual-sensor, Isaac Sim, and packaging workflows. It installs
the Newton tier for the required Newton contracts in Robot-Body and
Robot-Gripper 4.0.0.

Install the validator and tier together:

```bash
pip install simready-validate simready-foundation-tier-core
```

Install the optional Evaluate environment and the runtime tests bundled by the
tier with:

```bash
pip install "simready-foundation-tier-core[evaluate]"
```

The tables below reflect the catalogs in the current source tree. The tier's
feature and capability JSON and profile TOML files remain the machine-readable
sources of truth.

## Profiles

The Core tier owns 16 profiles. Each version selects features and capabilities
by dotted ID or wildcard selector, and any selection may be marked optional in
the profile TOML. Links open the dedicated authoring page when one exists,
otherwise the shared profile comparison.

| Profile | Available versions | Catalog file |
| --- | --- | --- |
| [Robot-Body](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot-body.md) | `2.0.0`, `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`, `3.1.0`, `4.0.0` | `robot_body.toml` |
| [Robot-Gripper](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot-gripper.md) | `2.0.0`, `2.1.0`, `2.2.0`, `3.0.0`, `4.0.0` | `robot_gripper.toml` |
| [Robotics-Prop](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/robotics-prop.md) | `3.0.0`, `3.1.0`, `3.2.0`, `3.3.0`, `4.0.0`, `5.0.0` | `robotics_prop.toml` |
| [NuRec](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/nurec.md) | `1.0.0` | `nurec.toml` |
| [Material](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/material.md) | `1.0.0` | `material.toml` |
| [Assembly](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/assembly.md) | `0.1.0` | `assembly.toml` |
| [Robot-Assembly](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot-assembly.md) | `0.1.0` | `robot_assembly.toml` |
| [Package](../profiles/profiles.md#profile-comparison) | `1.0.0` | `package_profiles.toml` |
| [Package-NoBOM](../profiles/profiles.md#profile-comparison) | `1.0.0` | `package_profiles.toml` |
| [Package-Candidate](../profiles/profiles.md#profile-comparison) | `1.0.0`, `1.1.0`, `1.2.0`, `1.3.0` | `package_profiles.toml` |
| [Open-Taxonomy-COCO](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/open-taxonomy-coco.md) | `0.1.0` | `open_taxonomy_profiles.toml` |
| [Open-Taxonomy-Cityscapes](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/open-taxonomy-cityscapes.md) | `0.1.0` | `open_taxonomy_profiles.toml` |
| [Open-Taxonomy-ADE20K](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/open-taxonomy-ade20k.md) | `0.1.0` | `open_taxonomy_profiles.toml` |
| [Open-Taxonomy-PascalVOC](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/open-taxonomy-pascal_voc.md) | `0.1.0` | `open_taxonomy_profiles.toml` |
| [Open-Taxonomy-SUNRGBD](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/open-taxonomy-sunrgbd.md) | `0.1.0` | `open_taxonomy_profiles.toml` |
| [Open-Taxonomy-ImageNet1K](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/open-taxonomy-imagenet_1k.md) | `0.1.0` | `open_taxonomy_profiles.toml` |

## Assembly capabilities

These contracts contain static requirements and use CAP identities. They do
not claim runtime evaluation coverage. Their exact IDs retain the original
`0.1.0` contract version encoded as `0-1-0`.

| Capability selector | Purpose |
| --- | --- |
| [CAP026_Mates.0-1-0](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP026_Mates.md) | Mechanical mate-site declarations |
| [CAP027_Connections.0-1-0](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP027_Connections.md) | Assembly connections and compound realization |
| [CAP029_ConnectionJoint.0-1-0](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP029_ConnectionJoint.md) | Neutral fixed joints, attachment strength, and payload rating |
| [CAP029_ConnectionJoint.PhysX.0-1-0](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP029_ConnectionJoint.PhysX.md) | PhysX connection-joint constraints |
| [CAP029_ConnectionJoint.Newton.0-1-0](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP029_ConnectionJoint.Newton.md) | Newton connection-joint constraints |
| [CAP029_ConnectionJoint.MuJoCo.0-1-0](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP029_ConnectionJoint.MuJoCo.md) | MuJoCo connection-joint constraints |

Profiles select these through `capabilities`, alongside runtime-tested contracts
selected through `features`. The conform commands retain their historical
`simready-foundation-conform-fet-026/027/029-*` names for compatibility.

## Features

The Core tier owns 21 runtime-tested features with 42 exact versions. Each ID
has the form `<name>[.<runtime>].<version>`: neutral contracts omit the runtime
segment, runtime variants name their runtime, and the version segment is
the published version with hyphens in place of dots.

| Feature | Purpose | Available versions |
| --- | --- | --- |
| [`FET001_MinimalPlaceableVisual`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET001_MinimalPlaceableVisual.md) | Minimal Placeable Visual | `0-1-0`, `1-0-0`, `1-0-1` |
| [`FET003_RigidBody`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET003_RigidBody.md) | Rigid Body Physics | `0-1-0`, `0-2-0` |
| [`FET003_RigidBody.PhysX`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET003_RigidBody.PhysX.md) | Rigid Body Physics (PhysX) | `0-1-0`, `0-2-0`, `0-3-0`, `0-4-0` |
| [`FET004_Multibody`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.md) | Simulate Multi-Body Physics | `0-1-0`, `0-2-0` |
| [`FET004_Multibody.PhysX`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.PhysX.md) | Simulate Multi-Body Physics (PhysX) | `0-1-0`, `0-2-0`, `0-3-0`, `0-4-0` |
| [`FET004_Multibody.RobotPhysX`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.RobotPhysX.md) | Simulate Multi-Body Physics (Robot PhysX) — **Deprecated; compatibility only** | `0-1-0`, `0-2-0`, `0-3-0`, `0-4-0` |
| [`FET005_Grasp`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET005_Grasp.md) | Simulate Grasp Physics | `0-1-0` |
| [`FET006_Materials.MDL`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET006_Materials.MDL.md) | Materials (MDL) | `0-1-0`, `0-2-0`, `0-3-0` |
| [`FET006_Materials`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET006_Materials.md) | Materials (USDPreviewSurface) | `0-1-0`, `0-2-0`, `0-3-0` |
| [`FET006_Materials.Openpbr`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET006_Materials.Openpbr.md) | Materials (OpenPBR) | `0-1-0`, `0-2-0` |
| [`FET008_ObjectForward`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET008_ObjectForward.md) | Object Forward | `0-1-0` |
| [`FET009_MaterialCoverage`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET009_MaterialCoverage.md) | Material Coverage | `0-1-0` |
| [`FET010_DisplayColor`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET010_DisplayColor.md) | Display Color | `0-1-0` |
| [`FET011_SemanticLabels`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET011_SemanticLabels.md) | Semantic Labels | `0-2-0` |
| [`FET011_SemanticLabels.RTX`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET011_SemanticLabels.RTX.md) | Semantic Labels (RTX) | `0-1-0` |
| [`FET012_GaussianSplat`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET012_GaussianSplat.md) | Sensor Visual 3DGS | `0-1-0` |
| [`FET022_DrivenJoints.Isaac`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET022_DrivenJoints.Isaac.md) | Driven Joints (Isaac) | `0-1-0`, `0-2-0` |
| [`FET022_DrivenJoints`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET022_DrivenJoints.md) | Driven Joints | `0-1-0`, `0-2-0` |
| [`FET022_DrivenJoints.PhysX`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET022_DrivenJoints.PhysX.md) | Driven Joints (PhysX) | `0-1-0`, `0-2-0` |
| [`FET028_Gripper.Isaac`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET028_Gripper.Isaac.md) | Gripper (Isaac) | `0-1-0` |
| [`FET028_Gripper`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET028_Gripper.md) | Gripper | `0-1-0` |

## Capabilities

The Core tier owns 31 capabilities with 40 exact versions. A capability is a
static requirement bundle with no runtime tests; its ID uses the same
`<name>[.<runtime>].<version>` scheme with a `CAP` prefix.

| Capability | Purpose | Available versions |
| --- | --- | --- |
| [`CAP000_Core.Isaac`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.Isaac.md) | Core (Isaac) | `0-1-0`, `0-2-0` |
| [`CAP000_Core.MuJoCo`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.MuJoCo.md) | Core (MuJoCo) | `0-1-0`, `0-2-0` |
| [`CAP000_Core`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.md) | Core | `0-1-0`, `0-2-0` |
| [`CAP000_Core.PhysX`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.PhysX.md) | Core (PhysX) | `0-1-0`, `0-2-0` |
| [`CAP002_PosableBodies`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP002_PosableBodies.md) | Posable Bodies | `0-1-0` |
| [`CAP003_RigidBody.MuJoCo`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP003_RigidBody.MuJoCo.md) | Rigid Body Physics (MuJoCo) | `0-1-0` |
| [`CAP004_Multibody.MuJoCo`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP004_Multibody.MuJoCo.md) | Simulate Multi-Body Physics (MuJoCo) | `0-1-0` |
| [`CAP004_Multibody.RobotMuJoCo`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP004_Multibody.RobotMuJoCo.md) | Simulate Multi-Body Physics (Robot MuJoCo) | `0-1-0` |
| [`CAP007_NonVisualMaterials`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP007_NonVisualMaterials.md) | Non-Visual Materials | `0-2-0` |
| [`CAP021_RobotCore.Isaac`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP021_RobotCore.Isaac.md) | Robot Core (Isaac) | `0-1-0`, `0-2-0`, `0-3-0` |
| [`CAP022_DrivenJoints.MuJoCo`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP022_DrivenJoints.MuJoCo.md) | Driven Joints (MuJoCo) | `0-1-0` |
| [`CAP023_RobotMaterials.Isaac`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP023_RobotMaterials.Isaac.md) | Robot Materials — **Deprecated; compatibility only** | `0-1-0` |
| [`CAP024_BaseArticulation.MuJoCo`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP024_BaseArticulation.MuJoCo.md) | Base Articulation (MuJoCo) | `0-1-0` |
| [`CAP024_BaseArticulation`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP024_BaseArticulation.md) | Base Articulation | `0-1-0` |
| [`CAP024_BaseArticulation.PhysX`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP024_BaseArticulation.PhysX.md) | Base Articulation (PhysX) | `0-1-0` |
| [`CAP025_RosBridge.Ros`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP025_RosBridge.Ros.md) | ROS Ready (Isaac) | `0-1-0` |
| [`CAP028_Gripper.MuJoCo`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP028_Gripper.MuJoCo.md) | Gripper (MuJoCo) | `0-1-0` |
| [`CAP030_PackagingCore`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP030_PackagingCore.md) | Packaging Core | `0-1-0` |
| [`CAP031_SelfContainedPackage`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP031_SelfContainedPackage.md) | Self-contained Package Source | `0-1-0` |
| [`CAP032_PackagingIntrospection`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP032_PackagingIntrospection.md) | Packaging Introspection | `0-1-0` |
| [`CAP033_SimReadyPackage`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP033_SimReadyPackage.md) | Metadata | `0-1-0`, `0-2-0`, `0-3-0`, `0-4-0` |
| [`CAP040_CocoLabels`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP040_CocoLabels.md) | Semantic Labels - COCO | `0-1-0` |
| [`CAP041_CityscapesLabels`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP041_CityscapesLabels.md) | Semantic Labels - Cityscapes | `0-1-0` |
| [`CAP042_Ade20kLabels`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP042_Ade20kLabels.md) | Semantic Labels - ADE20K | `0-1-0` |
| [`CAP043_PascalVocLabels`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP043_PascalVocLabels.md) | Semantic Labels - PASCAL VOC | `0-1-0` |
| [`CAP044_SunRgbdLabels`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP044_SunRgbdLabels.md) | Semantic Labels - SUN RGB-D | `0-1-0` |
| [`CAP045_ImageNet1kLabels`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP045_ImageNet1kLabels.md) | Semantic Labels - ImageNet-1K | `0-1-0` |
| [`CAP046_WikidataLabels`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP046_WikidataLabels.md) | Semantic Labels - Wikidata | `0-1-0` |
| [`CAP100_IsaacComposition.Isaac`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP100_IsaacComposition.Isaac.md) | IsaacSim Composition | `0-1-0`, `0-2-0`, `0-3-0`, `0-4-0` |
| [`CAP101_RobotComposition.Isaac`](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP101_RobotComposition.Isaac.md) | Robot IsaacSim Composition | `0-1-0` |

The Newton runtime variants are owned by the [Newton tier](newton.md).

## Package contents and discovery

The distribution advertises both the `usd_validation_nvidia` and
`simready.tier` entry-point groups. Together they expose:

- Capability and requirement documentation plus registered validators.
- Generated requirement enums.
- Feature and capability JSON and profile TOML catalogs.
- Optional tier-owned Evaluate runtime tests.

For the package layout, build commands, and local development notes, see the
README in `nv_core/tiers/simready_foundation_tier_core/` in the source tree.
