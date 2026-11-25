# Asset Profiles

Asset profiles select features and capabilities so assets can be validated
against explicit consumer contracts. Foundations 2 selectors may use feature
name/runtime/version wildcards, and feature or capability selectors may be
optional. A caller may validate the same asset against several profiles.
Capability IDs/selectors begin with `CAP`. A testless contract belongs in that
selector group unless it is the source of tested derived FETs.

Feature requirements and dependency chains are defined in the [feature dependency graph](../features/feature-dependency-graph.md). The table below summarizes every published profile version; each profile's TOML holds the exact selectors per version. New versions follow the [profile authoring guide](../../guides/profiles/profiles.md).

This section lists the profiles from every SimReady Foundation [tier](../../guides/tiers.md) together. The tier that owns a profile indicates how broadly it applies: core-tier profiles are the most portable, while a profile owned by another tier is scoped to that tier's runtime, vendor, or domain.

(profile-comparison)=
## Profile comparison

The contracts column lists every feature (`FET`) and capability (`CAP`) any
version of the profile selects, by name and runtime; the selected versions
differ between profile versions.

| Profile | Versions | Summary | Contracts |
| --- | --- | --- | --- |
| Robotics-Prop | 3.0.0, 3.1.0, 3.2.0, 3.3.0, 4.0.0, 5.0.0 | Consolidated prop profile; 3.2.0 adds semantic labels, required SimReady packaging + nested provenance metadata, and optional CAP100_IsaacComposition.Isaac.0-4-0; 3.3.0 adopts CAP000_Core.0-2-0 and CAP033_SimReadyPackage.0-4-0 (SR.004 USD/sidecar union); 4.0.0 is the SimReady Foundations 8.0 release of that contract and requires the UsdPreviewSurface preview, with display colour, OpenPBR and MDL optional; 5.0.0 is the SimReady Foundations 10.0 contract, requiring Object Forward and material coverage with FET009_MaterialCoverage and selecting the 0-2-0 runtime Core capabilities | FET001_MinimalPlaceableVisual, FET003_RigidBody, FET004_Multibody, FET005_Grasp, FET006_Materials, FET006_Materials.MDL, FET006_Materials.Openpbr, FET010_DisplayColor, FET011_SemanticLabels, FET011_SemanticLabels.RTX, FET003_RigidBody.PhysX, FET004_Multibody.PhysX, FET003_RigidBody.Newton, FET004_Multibody.Newton, CAP000_Core, CAP007_NonVisualMaterials, CAP046_WikidataLabels, CAP031_SelfContainedPackage, CAP033_SimReadyPackage, CAP100_IsaacComposition.Isaac, CAP000_Core.PhysX, CAP000_Core.Newton, CAP000_Core.MuJoCo, CAP003_RigidBody.MuJoCo, CAP004_Multibody.MuJoCo, FET008_ObjectForward, FET009_MaterialCoverage |
| NuRec | 1.0.0 | NuRec 3D Gaussian Splat delivery props whose visual is purely a `ParticleField3DGaussianSplat` (no mesh); FET012_GaussianSplat is self-contained, carrying the non-mesh minimal contract plus SPL.001-006 | FET012_GaussianSplat, CAP000_Core |
| Robot-Body | 2.0.0, 2.1.0, 2.2.0, 2.3.0, 3.0.0, 3.1.0, 4.0.0 | Consolidated robot body profile; 2.1.0 adds required SimReady packaging + provenance metadata; 2.2.0 adds optional Isaac ROS-Ready bridge wiring; 2.3.0 adopts CAP033_SimReadyPackage.0-4-0 (SR.004 USD/sidecar provenance union); 3.0.0 is the SimReady Foundations 8.0 release of that contract and requires the UsdPreviewSurface preview, with display colour, OpenPBR and MDL optional; 3.1.0 preserves the complete 3.0.0 bundle and includes Object Forward optionally; 4.0.0 requires CAP000_Core.0-2-0, selects the 0-2-0 runtime and Isaac Core capabilities, leaves out the deprecated CAP023_RobotMaterials.Isaac, and requires material binding and coverage as FET009_MaterialCoverage; Newton rigid-body, multibody, driven-joint, Core, and articulation contracts are required in 4.0.0 | CAP000_Core, FET001_MinimalPlaceableVisual, FET003_RigidBody, FET004_Multibody, FET022_DrivenJoints, FET006_Materials, FET006_Materials.Openpbr, FET006_Materials.MDL, FET010_DisplayColor, FET003_RigidBody.PhysX, FET004_Multibody.PhysX, FET022_DrivenJoints.PhysX, FET003_RigidBody.Newton, FET004_Multibody.Newton, FET022_DrivenJoints.Newton, FET022_DrivenJoints.Isaac, CAP024_BaseArticulation, CAP025_RosBridge.Ros, CAP031_SelfContainedPackage, CAP033_SimReadyPackage, CAP000_Core.Isaac, CAP021_RobotCore.Isaac, CAP023_RobotMaterials.Isaac, CAP100_IsaacComposition.Isaac, CAP000_Core.PhysX, CAP024_BaseArticulation.PhysX, CAP000_Core.Newton, CAP024_BaseArticulation.Newton, CAP000_Core.MuJoCo, CAP003_RigidBody.MuJoCo, CAP004_Multibody.MuJoCo, CAP022_DrivenJoints.MuJoCo, CAP024_BaseArticulation.MuJoCo, FET008_ObjectForward, FET009_MaterialCoverage |
| Sensor-IMU | 1.0.0 | IMU sensor; applies to any asset carrying an IMU sensor, independent of its primary profile | FET034_ImuSensor.Isaac |
| Sensor-Joint | 1.0.0 | Joint sensor; applies to any asset carrying a joint state sensor, independent of its primary profile | FET037_JointSensor.Isaac |
| Sensor-Camera | 1.0.0 | Camera render products and AOV pipeline; applies to any asset with a camera sensor | FET035_RenderProducts.RTX |
| Sensor-LiDAR | 1.0.0 | RTX LiDAR (OmniLidar); applies to any asset carrying a LiDAR sensor | FET036_Lidar.RTX |
| Robot-Gripper | 2.0.0, 2.1.0, 2.2.0, 3.0.0, 4.0.0 | Consolidated gripper profile; 2.1.0 adds required SimReady packaging + provenance metadata; 2.2.0 adopts CAP033_SimReadyPackage.0-4-0 (SR.004 USD/sidecar provenance union); 3.0.0 is the SimReady Foundations 8.0 release of that contract and requires the UsdPreviewSurface preview, with display colour, OpenPBR and MDL optional; 4.0.0 requires CAP000_Core.0-2-0, selects the 0-2-0 runtime Core capabilities, and requires material binding and coverage as FET009_MaterialCoverage; Newton rigid-body, multibody, driven-joint, Core, and articulation contracts are required in 4.0.0 | CAP000_Core, FET001_MinimalPlaceableVisual, FET003_RigidBody, FET004_Multibody, FET022_DrivenJoints, FET028_Gripper, FET006_Materials, FET006_Materials.Openpbr, FET006_Materials.MDL, FET010_DisplayColor, FET003_RigidBody.PhysX, FET004_Multibody.PhysX, FET022_DrivenJoints.PhysX, FET003_RigidBody.Newton, FET004_Multibody.Newton, FET022_DrivenJoints.Newton, FET022_DrivenJoints.Isaac, FET028_Gripper.Isaac, CAP024_BaseArticulation, CAP031_SelfContainedPackage, CAP033_SimReadyPackage, CAP021_RobotCore.Isaac, CAP100_IsaacComposition.Isaac, CAP000_Core.PhysX, CAP024_BaseArticulation.PhysX, CAP000_Core.Newton, CAP024_BaseArticulation.Newton, CAP000_Core.MuJoCo, CAP003_RigidBody.MuJoCo, CAP004_Multibody.MuJoCo, CAP022_DrivenJoints.MuJoCo, CAP024_BaseArticulation.MuJoCo, CAP028_Gripper.MuJoCo, FET009_MaterialCoverage |
| AIF-Entity | 0.1.0, 0.2.0, 0.3.0 | AI Factory equipment (CDU, CRAH, UPS, compute rack): class metadata and connection points on top of Core, with `aif:core:assetClass` selecting the class-specific checks; 0.2.0 adopts the Connection Points 2.0 property vocabulary (CP.010-CP.012) in place of the 0.1.0 named-Mesh geometry and naming rules, and adds the SimReady Central publishing contract (CAP031_SelfContainedPackage.0-1-0, CAP033_SimReadyPackage.0-4-0) on CAP000_Core.0-2-0; 0.3.0 uses scalar equipment dimensions (AM.009), validates common metadata types (AM.008) and checks node configuration and ports for the `network-equipment` class | FET001_MinimalPlaceableVisual, CAP000_Core, CAP200_AifMetadata, CAP201_ConnectionPoints, CAP202_ThermalCooling, CAP203_Electrical, CAP204_Networking, CAP031_SelfContainedPackage, CAP033_SimReadyPackage |
| Networking | 0.3.0 | Networking device eligibility, metadata, node allocation, CP2 ports and DSX Air connectivity feature on the AIF 0.3 baseline | FET001_MinimalPlaceableVisual, FET207_Networking.DSXAir, CAP000_Core, CAP200_AifMetadata, CAP201_ConnectionPoints, CAP204_Networking, CAP031_SelfContainedPackage, CAP033_SimReadyPackage |
| Material | 1.0.0 | Material assets: the visual-material contract without material binding, since a material published on its own has no geometry to bind to, in a self-contained SimReady package | FET006_Materials, FET006_Materials.Openpbr, FET006_Materials.MDL, CAP000_Core, CAP031_SelfContainedPackage, CAP033_SimReadyPackage |
| Assembly | 0.1.0 | **Work In Progress — feedback welcome.** Generic assembly of two or more components with declared compound or jointed mate pairings; packaging and publishing assemblies with their child-asset dependencies is the missing feature | CAP026_Mates, CAP027_Connections, CAP029_ConnectionJoint, CAP029_ConnectionJoint.PhysX, CAP029_ConnectionJoint.Newton, CAP029_ConnectionJoint.MuJoCo |
| Robot-Assembly | 0.1.0 | **Work In Progress — feedback welcome.** Robot composed from separately published assets joined into one articulation; packaging and publishing the composed robot with its child-asset dependencies is the missing feature | CAP026_Mates, CAP027_Connections, CAP029_ConnectionJoint, CAP024_BaseArticulation, FET022_DrivenJoints |
| Package | 1.0.0 | Created package with a bill of materials | CAP030_PackagingCore, CAP032_PackagingIntrospection |
| Package-NoBOM | 1.0.0 | Created package published without a BOM | CAP030_PackagingCore |
| Package-Candidate | 1.0.0, 1.1.0, 1.2.0, 1.3.0 | Source folder preflight before packaging; 1.2.0 adopts CAP033_SimReadyPackage.0-3-0 (stricter SR.003 provenance); 1.3.0 adopts CAP033_SimReadyPackage.0-4-0 (SR.004 USD/sidecar union) | CAP031_SelfContainedPackage, CAP033_SimReadyPackage |
| Open-Taxonomy-COCO | 0.1.0 | Semantic labels constrained to the COCO vocabulary | FET011_SemanticLabels, CAP000_Core, CAP040_CocoLabels |
| Open-Taxonomy-Cityscapes | 0.1.0 | Semantic labels constrained to the Cityscapes vocabulary | FET011_SemanticLabels, CAP000_Core, CAP041_CityscapesLabels |
| Open-Taxonomy-ADE20K | 0.1.0 | Semantic labels constrained to the ADE20K vocabulary | FET011_SemanticLabels, CAP000_Core, CAP042_Ade20kLabels |
| Open-Taxonomy-PascalVOC | 0.1.0 | Semantic labels constrained to the PASCAL VOC vocabulary | FET011_SemanticLabels, CAP000_Core, CAP043_PascalVocLabels |
| Open-Taxonomy-SUNRGBD | 0.1.0 | Semantic labels constrained to the SUN RGB-D vocabulary | FET011_SemanticLabels, CAP000_Core, CAP044_SunRgbdLabels |
| Open-Taxonomy-ImageNet1K | 0.1.0 | Semantic labels constrained to the ImageNet-1K vocabulary | FET011_SemanticLabels, CAP000_Core, CAP045_ImageNet1kLabels |
| Asset-Optimization | 1.0.0, 1.1.0 | Isaac tier structural optimization checks | CAP102_RigidBodyCollapse.Isaac, CAP103_VisualMeshMerge.Isaac, CAP104_RenderCollisionSeparation.Isaac, CAP105_MaterialXRemoval.Isaac |

The packaging profiles validate a package folder and its sidecar JSON files
rather than the contents of a USD stage.

```{toctree}
:maxdepth: 1

Robotics Prop <robotics-prop>
NuRec <nurec>
Asset Optimization <asset-optimization>
Robot Body <robot-body>
Robot Gripper <robot-gripper>
Sensor IMU <sensor-imu>
Sensor Joint <sensor-joint>
Sensor Camera <sensor-camera>
Sensor LiDAR <sensor-lidar>
Material <material>
Assembly <assembly>
Robot Assembly <robot-assembly>
Open Taxonomy COCO <open-taxonomy-coco>
Open Taxonomy Cityscapes <open-taxonomy-cityscapes>
Open Taxonomy ADE20K <open-taxonomy-ade20k>
Open Taxonomy PASCAL VOC <open-taxonomy-pascal_voc>
Open Taxonomy SUN RGB-D <open-taxonomy-sunrgbd>
Open Taxonomy ImageNet-1K <open-taxonomy-imagenet_1k>
AIF Entity <aif-entity>
Networking <networking>
```
