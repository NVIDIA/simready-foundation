# Feature Dependency Graph

Edges point from a feature or capability to the exact contracts listed in its
manifest `dependencies`, and from a feature to those listed in its `capabilities`. Every node is a dotted `<name>[.<runtime>].<version>` ID;
capabilities are shaded. A `source_feature` link records classification only and
is not drawn, because it does not make the source contract validate.

## Mermaid Diagram

```{mermaid}
flowchart TD
    CAP039_ObjectAffordances_OpenUSD_0_1_0["CAP039_ObjectAffordances 0-1-0"]
    CAP039_ObjectAffordances_OpenUSD_0_1_0 --> FET011_SemanticLabels_OpenUSD_0_2_0
    CAP000_Core_Isaac_0_1_0["CAP000_Core.Isaac 0-1-0"]
    CAP000_Core_Isaac_0_2_0["CAP000_Core.Isaac 0-2-0"]
    CAP000_Core_MuJoCo_0_1_0["CAP000_Core.MuJoCo 0-1-0"]
    CAP000_Core_MuJoCo_0_2_0["CAP000_Core.MuJoCo 0-2-0"]
    CAP000_Core_Newton_0_1_0["CAP000_Core.Newton 0-1-0"]
    CAP000_Core_Newton_0_2_0["CAP000_Core.Newton 0-2-0"]
    CAP000_Core_OpenUSD_0_1_0["CAP000_Core 0-1-0"]
    CAP000_Core_OpenUSD_0_2_0["CAP000_Core 0-2-0"]
    CAP000_Core_PhysX_0_1_0["CAP000_Core.PhysX 0-1-0"]
    CAP000_Core_PhysX_0_2_0["CAP000_Core.PhysX 0-2-0"]
    FET001_MinimalPlaceableVisual_OpenUSD_0_1_0["FET001_MinimalPlaceableVisual 0-1-0"]
    FET001_MinimalPlaceableVisual_OpenUSD_1_0_0["FET001_MinimalPlaceableVisual 1-0-0"]
    FET001_MinimalPlaceableVisual_OpenUSD_1_0_1["FET001_MinimalPlaceableVisual 1-0-1"]
    CAP002_PosableBodies_OpenUSD_0_1_0["CAP002_PosableBodies 0-1-0"]
    CAP003_RigidBody_MuJoCo_0_1_0["CAP003_RigidBody.MuJoCo 0-1-0"]
    FET003_RigidBody_Newton_0_1_0["FET003_RigidBody.Newton 0-1-0"]
    FET003_RigidBody_OpenUSD_0_1_0["FET003_RigidBody 0-1-0"]
    FET003_RigidBody_OpenUSD_0_2_0["FET003_RigidBody 0-2-0"]
    FET003_RigidBody_PhysX_0_1_0["FET003_RigidBody.PhysX 0-1-0"]
    FET003_RigidBody_PhysX_0_2_0["FET003_RigidBody.PhysX 0-2-0"]
    FET003_RigidBody_PhysX_0_3_0["FET003_RigidBody.PhysX 0-3-0"]
    FET003_RigidBody_PhysX_0_4_0["FET003_RigidBody.PhysX 0-4-0"]
    CAP004_Multibody_MuJoCo_0_1_0["CAP004_Multibody.MuJoCo 0-1-0"]
    CAP004_Multibody_RobotMuJoCo_0_1_0["CAP004_Multibody.RobotMuJoCo 0-1-0"]
    FET004_Multibody_Newton_0_1_0["FET004_Multibody.Newton 0-1-0"]
    FET004_Multibody_OpenUSD_0_1_0["FET004_Multibody 0-1-0"]
    FET004_Multibody_OpenUSD_0_2_0["FET004_Multibody 0-2-0"]
    FET004_Multibody_PhysX_0_1_0["FET004_Multibody.PhysX 0-1-0"]
    FET004_Multibody_PhysX_0_2_0["FET004_Multibody.PhysX 0-2-0"]
    FET004_Multibody_PhysX_0_3_0["FET004_Multibody.PhysX 0-3-0"]
    FET004_Multibody_PhysX_0_4_0["FET004_Multibody.PhysX 0-4-0"]
    FET004_Multibody_RobotNewton_0_1_0["FET004_Multibody.RobotNewton 0-1-0"]
    FET004_Multibody_RobotPhysX_0_1_0["FET004_Multibody.RobotPhysX 0-1-0"]
    FET004_Multibody_RobotPhysX_0_2_0["FET004_Multibody.RobotPhysX 0-2-0"]
    FET004_Multibody_RobotPhysX_0_3_0["FET004_Multibody.RobotPhysX 0-3-0"]
    FET004_Multibody_RobotPhysX_0_4_0["FET004_Multibody.RobotPhysX 0-4-0"]
    FET005_Grasp_OpenUSD_0_1_0["FET005_Grasp 0-1-0"]
    FET006_Materials_MDL_0_1_0["FET006_Materials.MDL 0-1-0"]
    FET006_Materials_MDL_0_2_0["FET006_Materials.MDL 0-2-0"]
    FET006_Materials_MDL_0_3_0["FET006_Materials.MDL 0-3-0"]
    FET006_Materials_OpenUSD_0_1_0["FET006_Materials 0-1-0"]
    FET006_Materials_OpenUSD_0_2_0["FET006_Materials 0-2-0"]
    FET006_Materials_OpenUSD_0_3_0["FET006_Materials 0-3-0"]
    FET006_Materials_Openpbr_0_1_0["FET006_Materials.Openpbr 0-1-0"]
    FET006_Materials_Openpbr_0_2_0["FET006_Materials.Openpbr 0-2-0"]
    CAP007_NonVisualMaterials_OpenUSD_0_2_0["CAP007_NonVisualMaterials 0-2-0"]
    FET009_MaterialCoverage_OpenUSD_0_1_0["FET009_MaterialCoverage 0-1-0"]
    FET010_DisplayColor_OpenUSD_0_1_0["FET010_DisplayColor 0-1-0"]
    FET011_SemanticLabels_OpenUSD_0_2_0["FET011_SemanticLabels 0-2-0"]
    FET011_SemanticLabels_RTX_0_1_0["FET011_SemanticLabels.RTX 0-1-0"]
    FET012_GaussianSplat_OpenUSD_0_1_0["FET012_GaussianSplat 0-1-0"]
    FET013_MultiRepresentationVisual_OpenUSD_0_1_0["FET013_MultiRepresentationVisual 0-1-0"]
    FET014_MeshVariant_OpenUSD_0_1_0["FET014_MeshVariant 0-1-0"]
    FET015_CollisionVariant_OpenUSD_0_1_0["FET015_CollisionVariant 0-1-0"]
    FET016_AppearanceVariant_OpenUSD_0_1_0["FET016_AppearanceVariant 0-1-0"]
    CAP021_RobotCore_Isaac_0_1_0["CAP021_RobotCore.Isaac 0-1-0"]
    CAP021_RobotCore_Isaac_0_2_0["CAP021_RobotCore.Isaac 0-2-0"]
    CAP021_RobotCore_Isaac_0_3_0["CAP021_RobotCore.Isaac 0-3-0"]
    CAP022_DrivenJoints_MuJoCo_0_1_0["CAP022_DrivenJoints.MuJoCo 0-1-0"]
    FET022_DrivenJoints_Isaac_0_1_0["FET022_DrivenJoints.Isaac 0-1-0"]
    FET022_DrivenJoints_Isaac_0_2_0["FET022_DrivenJoints.Isaac 0-2-0"]
    FET022_DrivenJoints_Newton_0_1_0["FET022_DrivenJoints.Newton 0-1-0"]
    FET022_DrivenJoints_OpenUSD_0_1_0["FET022_DrivenJoints 0-1-0"]
    FET022_DrivenJoints_OpenUSD_0_2_0["FET022_DrivenJoints 0-2-0"]
    FET022_DrivenJoints_PhysX_0_1_0["FET022_DrivenJoints.PhysX 0-1-0"]
    FET022_DrivenJoints_PhysX_0_2_0["FET022_DrivenJoints.PhysX 0-2-0"]
    CAP023_RobotMaterials_Isaac_0_1_0["CAP023_RobotMaterials.Isaac 0-1-0"]
    CAP024_BaseArticulation_MuJoCo_0_1_0["CAP024_BaseArticulation.MuJoCo 0-1-0"]
    CAP024_BaseArticulation_Newton_0_1_0["CAP024_BaseArticulation.Newton 0-1-0"]
    CAP024_BaseArticulation_OpenUSD_0_1_0["CAP024_BaseArticulation 0-1-0"]
    CAP024_BaseArticulation_PhysX_0_1_0["CAP024_BaseArticulation.PhysX 0-1-0"]
    CAP025_RosBridge_Ros_0_1_0["CAP025_RosBridge.Ros 0-1-0"]
    CAP028_Gripper_MuJoCo_0_1_0["CAP028_Gripper.MuJoCo 0-1-0"]
    FET028_Gripper_Isaac_0_1_0["FET028_Gripper.Isaac 0-1-0"]
    FET028_Gripper_OpenUSD_0_1_0["FET028_Gripper 0-1-0"]
    CAP030_PackagingCore_OpenUSD_0_1_0["CAP030_PackagingCore 0-1-0"]
    CAP031_SelfContainedPackage_OpenUSD_0_1_0["CAP031_SelfContainedPackage 0-1-0"]
    CAP032_PackagingIntrospection_OpenUSD_0_1_0["CAP032_PackagingIntrospection 0-1-0"]
    CAP033_SimReadyPackage_OpenUSD_0_1_0["CAP033_SimReadyPackage 0-1-0"]
    CAP033_SimReadyPackage_OpenUSD_0_2_0["CAP033_SimReadyPackage 0-2-0"]
    CAP033_SimReadyPackage_OpenUSD_0_3_0["CAP033_SimReadyPackage 0-3-0"]
    CAP033_SimReadyPackage_OpenUSD_0_4_0["CAP033_SimReadyPackage 0-4-0"]
    FET034_ImuSensor_Isaac_0_1_0["FET034_ImuSensor.Isaac 0-1-0"]
    FET035_RenderProducts_RTX_0_1_0["FET035_RenderProducts.RTX 0-1-0"]
    FET036_Lidar_RTX_0_1_0["FET036_Lidar.RTX 0-1-0"]
    FET037_JointSensor_Isaac_0_1_0["FET037_JointSensor.Isaac 0-1-0"]
    CAP040_CocoLabels_OpenUSD_0_1_0["CAP040_CocoLabels 0-1-0"]
    CAP041_CityscapesLabels_OpenUSD_0_1_0["CAP041_CityscapesLabels 0-1-0"]
    CAP042_Ade20kLabels_OpenUSD_0_1_0["CAP042_Ade20kLabels 0-1-0"]
    CAP043_PascalVocLabels_OpenUSD_0_1_0["CAP043_PascalVocLabels 0-1-0"]
    CAP044_SunRgbdLabels_OpenUSD_0_1_0["CAP044_SunRgbdLabels 0-1-0"]
    CAP045_ImageNet1kLabels_OpenUSD_0_1_0["CAP045_ImageNet1kLabels 0-1-0"]
    CAP046_WikidataLabels_OpenUSD_0_1_0["CAP046_WikidataLabels 0-1-0"]
    CAP100_IsaacComposition_Isaac_0_1_0["CAP100_IsaacComposition.Isaac 0-1-0"]
    CAP100_IsaacComposition_Isaac_0_2_0["CAP100_IsaacComposition.Isaac 0-2-0"]
    CAP100_IsaacComposition_Isaac_0_3_0["CAP100_IsaacComposition.Isaac 0-3-0"]
    CAP100_IsaacComposition_Isaac_0_4_0["CAP100_IsaacComposition.Isaac 0-4-0"]
    CAP101_RobotComposition_Isaac_0_1_0["CAP101_RobotComposition.Isaac 0-1-0"]
    CAP200_AifMetadata_OpenUSD_0_1_0["CAP200_AifMetadata 0-1-0"]
    CAP201_ConnectionPoints_OpenUSD_0_1_0["CAP201_ConnectionPoints 0-1-0"]
    CAP201_ConnectionPoints_OpenUSD_0_2_0["CAP201_ConnectionPoints 0-2-0"]
    CAP202_ThermalCooling_OpenUSD_0_1_0["CAP202_ThermalCooling 0-1-0"]
    CAP202_ThermalCooling_OpenUSD_0_2_0["CAP202_ThermalCooling 0-2-0"]
    CAP203_Electrical_OpenUSD_0_1_0["CAP203_Electrical 0-1-0"]
    CAP203_Electrical_OpenUSD_0_2_0["CAP203_Electrical 0-2-0"]
    CAP200_AifMetadata_OpenUSD_0_3_0["CAP200_AifMetadata 0-3-0"]
    CAP201_ConnectionPoints_OpenUSD_0_3_0["CAP201_ConnectionPoints 0-3-0"]
    CAP202_ThermalCooling_OpenUSD_0_3_0["CAP202_ThermalCooling 0-3-0"]
    CAP203_Electrical_OpenUSD_0_3_0["CAP203_Electrical 0-3-0"]
    CAP204_NetworkEquipment_OpenUSD_0_3_0["CAP204_NetworkEquipment 0-3-0"]
    FET207_Networking_DSXAir_0_3_0["FET207_Networking.DSXAir 0-3-0"]
    CAP000_Core_Isaac_0_1_0 --> CAP000_Core_OpenUSD_0_1_0
    CAP000_Core_Isaac_0_2_0 --> CAP000_Core_OpenUSD_0_2_0
    CAP000_Core_MuJoCo_0_1_0 --> CAP000_Core_OpenUSD_0_1_0
    CAP000_Core_MuJoCo_0_2_0 --> CAP000_Core_OpenUSD_0_2_0
    CAP000_Core_Newton_0_1_0 --> CAP000_Core_OpenUSD_0_1_0
    CAP000_Core_Newton_0_2_0 --> CAP000_Core_OpenUSD_0_2_0
    CAP000_Core_PhysX_0_1_0 --> CAP000_Core_OpenUSD_0_1_0
    CAP000_Core_PhysX_0_2_0 --> CAP000_Core_OpenUSD_0_2_0
    FET003_RigidBody_PhysX_0_1_0 --> FET003_RigidBody_OpenUSD_0_1_0
    CAP004_Multibody_MuJoCo_0_1_0 --> CAP003_RigidBody_MuJoCo_0_1_0
    FET004_Multibody_Newton_0_1_0 --> FET003_RigidBody_Newton_0_1_0
    FET004_Multibody_OpenUSD_0_1_0 --> FET003_RigidBody_OpenUSD_0_1_0
    FET004_Multibody_OpenUSD_0_2_0 --> FET003_RigidBody_OpenUSD_0_2_0
    FET004_Multibody_PhysX_0_1_0 --> FET003_RigidBody_PhysX_0_1_0
    FET004_Multibody_PhysX_0_1_0 --> FET004_Multibody_OpenUSD_0_1_0
    FET004_Multibody_PhysX_0_2_0 --> FET003_RigidBody_PhysX_0_2_0
    FET004_Multibody_PhysX_0_2_0 --> FET004_Multibody_OpenUSD_0_1_0
    FET004_Multibody_PhysX_0_3_0 --> FET003_RigidBody_PhysX_0_3_0
    FET004_Multibody_PhysX_0_3_0 --> FET004_Multibody_OpenUSD_0_2_0
    FET004_Multibody_PhysX_0_4_0 --> FET003_RigidBody_PhysX_0_4_0
    FET009_MaterialCoverage_OpenUSD_0_1_0 --> FET006_Materials_OpenUSD_0_3_0
    FET011_SemanticLabels_RTX_0_1_0 --> FET011_SemanticLabels_OpenUSD_0_2_0
    CAP022_DrivenJoints_MuJoCo_0_1_0 --> CAP004_Multibody_RobotMuJoCo_0_1_0
    FET022_DrivenJoints_Isaac_0_1_0 --> FET022_DrivenJoints_PhysX_0_1_0
    FET022_DrivenJoints_Isaac_0_2_0 --> FET022_DrivenJoints_PhysX_0_2_0
    FET022_DrivenJoints_Newton_0_1_0 --> FET004_Multibody_RobotNewton_0_1_0
    FET022_DrivenJoints_OpenUSD_0_1_0 --> FET004_Multibody_OpenUSD_0_1_0
    FET022_DrivenJoints_OpenUSD_0_2_0 --> FET004_Multibody_OpenUSD_0_2_0
    FET022_DrivenJoints_PhysX_0_1_0 --> FET004_Multibody_RobotPhysX_0_1_0
    FET022_DrivenJoints_PhysX_0_2_0 --> FET004_Multibody_PhysX_0_4_0
    CAP024_BaseArticulation_MuJoCo_0_1_0 --> CAP024_BaseArticulation_OpenUSD_0_1_0
    CAP024_BaseArticulation_Newton_0_1_0 --> CAP024_BaseArticulation_OpenUSD_0_1_0
    CAP024_BaseArticulation_PhysX_0_1_0 --> CAP024_BaseArticulation_OpenUSD_0_1_0
    CAP028_Gripper_MuJoCo_0_1_0 --> CAP022_DrivenJoints_MuJoCo_0_1_0
    FET028_Gripper_Isaac_0_1_0 --> FET022_DrivenJoints_Isaac_0_1_0
    FET028_Gripper_Isaac_0_1_0 --> FET028_Gripper_OpenUSD_0_1_0
    CAP032_PackagingIntrospection_OpenUSD_0_1_0 --> CAP030_PackagingCore_OpenUSD_0_1_0
    CAP033_SimReadyPackage_OpenUSD_0_1_0 --> CAP031_SelfContainedPackage_OpenUSD_0_1_0
    CAP033_SimReadyPackage_OpenUSD_0_2_0 --> CAP031_SelfContainedPackage_OpenUSD_0_1_0
    CAP033_SimReadyPackage_OpenUSD_0_3_0 --> CAP031_SelfContainedPackage_OpenUSD_0_1_0
    CAP033_SimReadyPackage_OpenUSD_0_4_0 --> CAP031_SelfContainedPackage_OpenUSD_0_1_0
    CAP201_ConnectionPoints_OpenUSD_0_1_0 --> CAP200_AifMetadata_OpenUSD_0_1_0
    CAP201_ConnectionPoints_OpenUSD_0_2_0 --> CAP200_AifMetadata_OpenUSD_0_1_0
    CAP202_ThermalCooling_OpenUSD_0_1_0 --> CAP201_ConnectionPoints_OpenUSD_0_1_0
    CAP202_ThermalCooling_OpenUSD_0_2_0 --> CAP201_ConnectionPoints_OpenUSD_0_2_0
    CAP203_Electrical_OpenUSD_0_1_0 --> CAP201_ConnectionPoints_OpenUSD_0_1_0
    CAP203_Electrical_OpenUSD_0_2_0 --> CAP201_ConnectionPoints_OpenUSD_0_2_0
    CAP201_ConnectionPoints_OpenUSD_0_3_0 --> CAP200_AifMetadata_OpenUSD_0_3_0
    CAP202_ThermalCooling_OpenUSD_0_3_0 --> CAP201_ConnectionPoints_OpenUSD_0_3_0
    CAP203_Electrical_OpenUSD_0_3_0 --> CAP201_ConnectionPoints_OpenUSD_0_3_0
    CAP204_NetworkEquipment_OpenUSD_0_3_0 --> CAP200_AifMetadata_OpenUSD_0_3_0
    CAP204_NetworkEquipment_OpenUSD_0_3_0 --> CAP201_ConnectionPoints_OpenUSD_0_3_0
    FET207_Networking_DSXAir_0_3_0 --> CAP204_NetworkEquipment_OpenUSD_0_3_0
    FET013_MultiRepresentationVisual_OpenUSD_0_1_0 --> FET001_MinimalPlaceableVisual_OpenUSD_1_0_1
    FET014_MeshVariant_OpenUSD_0_1_0 --> FET001_MinimalPlaceableVisual_OpenUSD_1_0_1
    FET015_CollisionVariant_OpenUSD_0_1_0 --> FET001_MinimalPlaceableVisual_OpenUSD_1_0_1
    FET015_CollisionVariant_OpenUSD_0_1_0 --> FET003_RigidBody_OpenUSD_0_2_0
    FET016_AppearanceVariant_OpenUSD_0_1_0 --> FET001_MinimalPlaceableVisual_OpenUSD_1_0_1
    FET016_AppearanceVariant_OpenUSD_0_1_0 --> FET006_Materials_OpenUSD_0_2_0
    classDef capability fill:#eef,stroke:#333
    class CAP039_ObjectAffordances_OpenUSD_0_1_0 capability
    class CAP000_Core_Isaac_0_1_0,CAP000_Core_Isaac_0_2_0,CAP000_Core_MuJoCo_0_1_0,CAP000_Core_MuJoCo_0_2_0,CAP000_Core_Newton_0_1_0,CAP000_Core_Newton_0_2_0,CAP000_Core_OpenUSD_0_1_0,CAP000_Core_OpenUSD_0_2_0,CAP000_Core_PhysX_0_1_0,CAP000_Core_PhysX_0_2_0,CAP002_PosableBodies_OpenUSD_0_1_0,CAP003_RigidBody_MuJoCo_0_1_0,CAP004_Multibody_MuJoCo_0_1_0,CAP004_Multibody_RobotMuJoCo_0_1_0,CAP007_NonVisualMaterials_OpenUSD_0_2_0,CAP021_RobotCore_Isaac_0_1_0,CAP021_RobotCore_Isaac_0_2_0,CAP021_RobotCore_Isaac_0_3_0,CAP022_DrivenJoints_MuJoCo_0_1_0,CAP023_RobotMaterials_Isaac_0_1_0,CAP024_BaseArticulation_MuJoCo_0_1_0,CAP024_BaseArticulation_Newton_0_1_0,CAP024_BaseArticulation_OpenUSD_0_1_0,CAP024_BaseArticulation_PhysX_0_1_0,CAP025_RosBridge_Ros_0_1_0,CAP028_Gripper_MuJoCo_0_1_0,CAP030_PackagingCore_OpenUSD_0_1_0,CAP031_SelfContainedPackage_OpenUSD_0_1_0,CAP032_PackagingIntrospection_OpenUSD_0_1_0,CAP033_SimReadyPackage_OpenUSD_0_1_0,CAP033_SimReadyPackage_OpenUSD_0_2_0,CAP033_SimReadyPackage_OpenUSD_0_3_0,CAP033_SimReadyPackage_OpenUSD_0_4_0,CAP040_CocoLabels_OpenUSD_0_1_0,CAP041_CityscapesLabels_OpenUSD_0_1_0,CAP042_Ade20kLabels_OpenUSD_0_1_0,CAP043_PascalVocLabels_OpenUSD_0_1_0,CAP044_SunRgbdLabels_OpenUSD_0_1_0,CAP045_ImageNet1kLabels_OpenUSD_0_1_0,CAP046_WikidataLabels_OpenUSD_0_1_0,CAP100_IsaacComposition_Isaac_0_1_0,CAP100_IsaacComposition_Isaac_0_2_0,CAP100_IsaacComposition_Isaac_0_3_0,CAP100_IsaacComposition_Isaac_0_4_0,CAP101_RobotComposition_Isaac_0_1_0,CAP200_AifMetadata_OpenUSD_0_1_0,CAP201_ConnectionPoints_OpenUSD_0_1_0,CAP201_ConnectionPoints_OpenUSD_0_2_0,CAP202_ThermalCooling_OpenUSD_0_1_0,CAP202_ThermalCooling_OpenUSD_0_2_0,CAP203_Electrical_OpenUSD_0_1_0,CAP203_Electrical_OpenUSD_0_2_0,CAP200_AifMetadata_OpenUSD_0_3_0,CAP201_ConnectionPoints_OpenUSD_0_3_0,CAP202_ThermalCooling_OpenUSD_0_3_0,CAP203_Electrical_OpenUSD_0_3_0,CAP204_NetworkEquipment_OpenUSD_0_3_0 capability
```

## Edge List

| Contract | Depends on |
|---|---|
| `CAP000_Core.Isaac.0-1-0` | `CAP000_Core.0-1-0` |
| `CAP000_Core.Isaac.0-2-0` | `CAP000_Core.0-2-0` |
| `CAP000_Core.MuJoCo.0-1-0` | `CAP000_Core.0-1-0` |
| `CAP000_Core.MuJoCo.0-2-0` | `CAP000_Core.0-2-0` |
| `CAP000_Core.Newton.0-1-0` | `CAP000_Core.0-1-0` |
| `CAP000_Core.Newton.0-2-0` | `CAP000_Core.0-2-0` |
| `CAP000_Core.PhysX.0-1-0` | `CAP000_Core.0-1-0` |
| `CAP000_Core.PhysX.0-2-0` | `CAP000_Core.0-2-0` |
| `FET003_RigidBody.PhysX.0-1-0` | `FET003_RigidBody.0-1-0` |
| `CAP004_Multibody.MuJoCo.0-1-0` | `CAP003_RigidBody.MuJoCo.0-1-0` |
| `FET004_Multibody.Newton.0-1-0` | `FET003_RigidBody.Newton.0-1-0` |
| `FET004_Multibody.0-1-0` | `FET003_RigidBody.0-1-0` |
| `FET004_Multibody.0-2-0` | `FET003_RigidBody.0-2-0` |
| `FET004_Multibody.PhysX.0-1-0` | `FET003_RigidBody.PhysX.0-1-0`, `FET004_Multibody.0-1-0` |
| `FET004_Multibody.PhysX.0-2-0` | `FET003_RigidBody.PhysX.0-2-0`, `FET004_Multibody.0-1-0` |
| `FET004_Multibody.PhysX.0-3-0` | `FET003_RigidBody.PhysX.0-3-0`, `FET004_Multibody.0-2-0` |
| `FET004_Multibody.PhysX.0-4-0` | `FET003_RigidBody.PhysX.0-4-0` |
| `FET009_MaterialCoverage.0-1-0` | `FET006_Materials.0-3-0` |
| `FET011_SemanticLabels.RTX.0-1-0` | `FET011_SemanticLabels.0-2-0` |
| `FET013_MultiRepresentationVisual.0-1-0` | `FET001_MinimalPlaceableVisual.1-0-1` |
| `FET014_MeshVariant.0-1-0` | `FET001_MinimalPlaceableVisual.1-0-1` |
| `FET015_CollisionVariant.0-1-0` | `FET001_MinimalPlaceableVisual.1-0-1`, `FET003_RigidBody.0-2-0` |
| `FET016_AppearanceVariant.0-1-0` | `FET001_MinimalPlaceableVisual.1-0-1`, `FET006_Materials.0-2-0` |
| `CAP022_DrivenJoints.MuJoCo.0-1-0` | `CAP004_Multibody.RobotMuJoCo.0-1-0` |
| `FET022_DrivenJoints.Isaac.0-1-0` | `FET022_DrivenJoints.PhysX.0-1-0` |
| `FET022_DrivenJoints.Isaac.0-2-0` | `FET022_DrivenJoints.PhysX.0-2-0` |
| `FET022_DrivenJoints.Newton.0-1-0` | `FET004_Multibody.RobotNewton.0-1-0` |
| `FET022_DrivenJoints.0-1-0` | `FET004_Multibody.0-1-0` |
| `FET022_DrivenJoints.0-2-0` | `FET004_Multibody.0-2-0` |
| `FET022_DrivenJoints.PhysX.0-1-0` | `FET004_Multibody.RobotPhysX.0-1-0` |
| `FET022_DrivenJoints.PhysX.0-2-0` | `FET004_Multibody.PhysX.0-4-0` |
| `CAP024_BaseArticulation.MuJoCo.0-1-0` | `CAP024_BaseArticulation.0-1-0` |
| `CAP024_BaseArticulation.Newton.0-1-0` | `CAP024_BaseArticulation.0-1-0` |
| `CAP024_BaseArticulation.PhysX.0-1-0` | `CAP024_BaseArticulation.0-1-0` |
| `CAP028_Gripper.MuJoCo.0-1-0` | `CAP022_DrivenJoints.MuJoCo.0-1-0` |
| `FET028_Gripper.Isaac.0-1-0` | `FET022_DrivenJoints.Isaac.0-1-0`, `FET028_Gripper.0-1-0` |
| `CAP032_PackagingIntrospection.0-1-0` | `CAP030_PackagingCore.0-1-0` |
| `CAP033_SimReadyPackage.0-1-0` | `CAP031_SelfContainedPackage.0-1-0` |
| `CAP033_SimReadyPackage.0-2-0` | `CAP031_SelfContainedPackage.0-1-0` |
| `CAP033_SimReadyPackage.0-3-0` | `CAP031_SelfContainedPackage.0-1-0` |
| `CAP033_SimReadyPackage.0-4-0` | `CAP031_SelfContainedPackage.0-1-0` |
| `CAP201_ConnectionPoints.0-1-0` | `CAP200_AifMetadata.0-1-0` |
| `CAP201_ConnectionPoints.0-2-0` | `CAP200_AifMetadata.0-1-0` |
| `CAP202_ThermalCooling.0-1-0` | `CAP201_ConnectionPoints.0-1-0` |
| `CAP202_ThermalCooling.0-2-0` | `CAP201_ConnectionPoints.0-2-0` |
| `CAP203_Electrical.0-1-0` | `CAP201_ConnectionPoints.0-1-0` |
| `CAP203_Electrical.0-2-0` | `CAP201_ConnectionPoints.0-2-0` |
| `CAP201_ConnectionPoints.0-3-0` | `CAP200_AifMetadata.0-3-0` |
| `CAP202_ThermalCooling.0-3-0` | `CAP201_ConnectionPoints.0-3-0` |
| `CAP203_Electrical.0-3-0` | `CAP201_ConnectionPoints.0-3-0` |
| `CAP204_NetworkEquipment.0-3-0` | `CAP200_AifMetadata.0-3-0`, `CAP201_ConnectionPoints.0-3-0` |
| `FET207_Networking.DSXAir.0-3-0` | `CAP204_NetworkEquipment.0-3-0` |
| `CAP039_ObjectAffordances.0-1-0` | `FET011_SemanticLabels.0-2-0` |


## No Dependencies

- `CAP000_Core.0-1-0`
- `CAP000_Core.0-2-0`
- `FET001_MinimalPlaceableVisual.0-1-0`
- `FET001_MinimalPlaceableVisual.1-0-0`
- `FET001_MinimalPlaceableVisual.1-0-1`
- `CAP002_PosableBodies.0-1-0`
- `CAP003_RigidBody.MuJoCo.0-1-0`
- `FET003_RigidBody.Newton.0-1-0`
- `FET003_RigidBody.0-1-0`
- `FET003_RigidBody.0-2-0`
- `FET003_RigidBody.PhysX.0-2-0`
- `FET003_RigidBody.PhysX.0-3-0`
- `FET003_RigidBody.PhysX.0-4-0`
- `CAP004_Multibody.RobotMuJoCo.0-1-0`
- `FET004_Multibody.RobotNewton.0-1-0`
- `FET004_Multibody.RobotPhysX.0-1-0`
- `FET004_Multibody.RobotPhysX.0-2-0`
- `FET004_Multibody.RobotPhysX.0-3-0`
- `FET004_Multibody.RobotPhysX.0-4-0`
- `FET005_Grasp.0-1-0`
- `FET006_Materials.MDL.0-1-0`
- `FET006_Materials.MDL.0-2-0`
- `FET006_Materials.MDL.0-3-0`
- `FET006_Materials.0-1-0`
- `FET006_Materials.0-2-0`
- `FET006_Materials.0-3-0`
- `FET006_Materials.Openpbr.0-1-0`
- `FET006_Materials.Openpbr.0-2-0`
- `CAP007_NonVisualMaterials.0-2-0`
- `FET010_DisplayColor.0-1-0`
- `FET011_SemanticLabels.0-2-0`
- `FET012_GaussianSplat.0-1-0`
- `CAP021_RobotCore.Isaac.0-1-0`
- `CAP021_RobotCore.Isaac.0-2-0`
- `CAP021_RobotCore.Isaac.0-3-0`
- `CAP023_RobotMaterials.Isaac.0-1-0`
- `CAP024_BaseArticulation.0-1-0`
- `CAP025_RosBridge.Ros.0-1-0`
- `FET028_Gripper.0-1-0`
- `CAP030_PackagingCore.0-1-0`
- `CAP031_SelfContainedPackage.0-1-0`
- `FET034_ImuSensor.Isaac.0-1-0`
- `FET035_RenderProducts.RTX.0-1-0`
- `FET036_Lidar.RTX.0-1-0`
- `FET037_JointSensor.Isaac.0-1-0`
- `CAP040_CocoLabels.0-1-0`
- `CAP041_CityscapesLabels.0-1-0`
- `CAP042_Ade20kLabels.0-1-0`
- `CAP043_PascalVocLabels.0-1-0`
- `CAP044_SunRgbdLabels.0-1-0`
- `CAP045_ImageNet1kLabels.0-1-0`
- `CAP046_WikidataLabels.0-1-0`
- `CAP100_IsaacComposition.Isaac.0-1-0`
- `CAP100_IsaacComposition.Isaac.0-2-0`
- `CAP100_IsaacComposition.Isaac.0-3-0`
- `CAP100_IsaacComposition.Isaac.0-4-0`
- `CAP101_RobotComposition.Isaac.0-1-0`
- `CAP200_AifMetadata.0-1-0`
- `CAP200_AifMetadata.0-3-0`
