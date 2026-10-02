# Asset Profiles

Asset profiles bundle capabilities, so that assets can be reasoned about and validated for conformance with lists of capability requirements. Asset profiles can serve as a contract between creators and consumers of assets.

Feature requirements and dependency chains are defined in the [feature dependency graph](../features/feature-dependency-graph). Profile feature sets below align with the profile TOML files under `profiles/` and those specifications.

This section lists the profiles from every SimReady Foundation [tier](../guides/tiers.md) together. The tier that owns a profile indicates how broadly it applies: core-tier profiles are the most portable, while a profile owned by another tier is scoped to that tier's runtime, vendor, or domain.

(profile-comparison)=
## Profile comparison

| Profile | Versions | Summary | Feature set (from profile TOML) |
| --- | --- | --- | --- |
| Robotics-Prop | 3.0.0, 3.1.0, 3.2.0, 3.3.0, 4.0.0 | Consolidated prop profile using Standard feature IDs; 3.2.0 adds required SimReady packaging + nested provenance metadata and optional FET_100_ISAAC@0.4.0; 3.3.0 adopts FET_000_STANDARD@0.2.0 and FET_033_STANDARD@0.4.0 (SR.004 USD/sidecar union); 4.0.0 is the SimReady Foundations 8.0 release of that 3.3.0 contract | FET_000_STANDARD, FET_001_STANDARD, FET_003_STANDARD, FET_004_STANDARD, FET_005_STANDARD, FET_006_STANDARD, FET_006_MDL, FET_007_STANDARD, FET_011_STANDARD, FET_011_RTX, FET_046_STANDARD, FET_031_STANDARD, FET_033_STANDARD, FET_100_ISAAC, FET_000_PHYSX, FET_003_PHYSX, FET_004_PHYSX, FET_000_NEWTON, FET_003_NEWTON, FET_004_NEWTON, FET_000_MUJOCO, FET_003_MUJOCO, FET_004_MUJOCO |
| Robot-Body | 2.0.0, 2.1.0, 2.2.0, 2.3.0, 3.0.0 | Consolidated robot body profile; 2.1.0 adds required SimReady packaging + provenance metadata; 2.2.0 adds optional Isaac ROS-Ready bridge wiring; 2.3.0 adopts FET_033_STANDARD@0.4.0 (SR.004 USD/sidecar provenance union); 3.0.0 is the SimReady Foundations 8.0 release of that 2.3.0 contract | FET_001_STANDARD, FET_003_STANDARD, FET_004_STANDARD, FET_022_STANDARD, FET_024_STANDARD, FET_025_ROS, FET_031_STANDARD, FET_033_STANDARD, FET_004_PHYSX, FET_022_PHYSX, FET_024_PHYSX, FET_000_ISAAC, FET_021_ISAAC, FET_022_ISAAC, FET_023_ISAAC, FET_100_ISAAC |
| Sensor-IMU | 1.0.0 | IMU sensor; applies to any asset carrying an IMU sensor, independent of its primary profile | FET_034_ISAAC |
| Sensor-Joint | 1.0.0 | Joint sensor; applies to any asset carrying a joint state sensor, independent of its primary profile | FET_037_ISAAC |
| Sensor-Camera | 1.0.0 | Camera render products and AOV pipeline; applies to any asset with a camera sensor | FET_035_RTX |
| Sensor-LiDAR | 1.0.0 | RTX LiDAR (OmniLidar); applies to any asset carrying a LiDAR sensor | FET_036_RTX |
| Robot-Gripper | 2.0.0, 2.1.0, 2.2.0, 3.0.0 | Consolidated gripper profile using Standard feature IDs; 2.1.0 adds required SimReady packaging + provenance metadata; 2.2.0 adopts FET_033_STANDARD@0.4.0 (SR.004 USD/sidecar provenance union); 3.0.0 is the SimReady Foundations 8.0 release of that 2.2.0 contract | FET_001_STANDARD, FET_003_STANDARD, FET_004_STANDARD, FET_022_STANDARD, FET_024_STANDARD, FET_028_STANDARD, FET_031_STANDARD, FET_033_STANDARD, FET_004_PHYSX, FET_022_PHYSX, FET_024_PHYSX, FET_021_ISAAC, FET_022_ISAAC, FET_028_ISAAC, FET_100_ISAAC |
| AIF-Entity | 0.1.0, 0.2.0 | AI Factory equipment (CDU, CRAH, UPS, compute rack): class metadata and connection points on top of Core, with `aif:core:assetClass` selecting the class-specific checks; 0.2.0 adopts the Connection Points 2.0 property vocabulary (CP.010-CP.012) in place of the 0.1.0 named-Mesh geometry and naming rules, and adds the SimReady Central publishing contract (FET_031_STANDARD, FET_033_STANDARD@0.4.0) on FET_000_STANDARD@0.2.0 | FET_000_STANDARD, FET_001_STANDARD, FET200_AIF, FET201_AIF, FET202_AIF, FET203_AIF, FET_031_STANDARD, FET_033_STANDARD |
| Package | 1.0.0 | Created package with a bill of materials | FET_030_STANDARD, FET_032_STANDARD |
| Package-NoBOM | 1.0.0 | Created package published without a BOM | FET_030_STANDARD |
| Package-Candidate | 1.0.0, 1.1.0, 1.2.0, 1.3.0 | Source folder preflight before packaging; 1.2.0 adopts FET_033_STANDARD@0.3.0 (stricter SR.003 provenance); 1.3.0 adopts FET_033_STANDARD@0.4.0 (SR.004 USD/sidecar union) | FET_031_STANDARD, FET_033_STANDARD |
| Open-Taxonomy-COCO | 0.1.0 | Semantic labels constrained to the COCO vocabulary | FET_000_STANDARD, FET_011_STANDARD, FET_040_STANDARD |
| Open-Taxonomy-Cityscapes | 0.1.0 | Semantic labels constrained to the Cityscapes vocabulary | FET_000_STANDARD, FET_011_STANDARD, FET_041_STANDARD |
| Open-Taxonomy-ADE20K | 0.1.0 | Semantic labels constrained to the ADE20K vocabulary | FET_000_STANDARD, FET_011_STANDARD, FET_042_STANDARD |
| Open-Taxonomy-PascalVOC | 0.1.0 | Semantic labels constrained to the PASCAL VOC vocabulary | FET_000_STANDARD, FET_011_STANDARD, FET_043_STANDARD |
| Open-Taxonomy-SUNRGBD | 0.1.0 | Semantic labels constrained to the SUN RGB-D vocabulary | FET_000_STANDARD, FET_011_STANDARD, FET_044_STANDARD |
| Open-Taxonomy-ImageNet1K | 0.1.0 | Semantic labels constrained to the ImageNet-1K vocabulary | FET_000_STANDARD, FET_011_STANDARD, FET_045_STANDARD |

The packaging profiles validate a package folder and its sidecar JSON files
rather than the contents of a USD stage.

```{toctree}
:maxdepth: 1

Robotics Prop <robotics-prop>
Robot Body <robot-body>
Robot Gripper <robot-gripper>
Sensor IMU <sensor-imu>
Sensor Joint <sensor-joint>
Sensor Camera <sensor-camera>
Sensor LiDAR <sensor-lidar>
Open Taxonomy COCO <open-taxonomy-coco>
Open Taxonomy Cityscapes <open-taxonomy-cityscapes>
Open Taxonomy ADE20K <open-taxonomy-ade20k>
Open Taxonomy PASCAL VOC <open-taxonomy-pascal_voc>
Open Taxonomy SUN RGB-D <open-taxonomy-sunrgbd>
Open Taxonomy ImageNet-1K <open-taxonomy-imagenet_1k>
AIF Entity <aif-entity>
```
