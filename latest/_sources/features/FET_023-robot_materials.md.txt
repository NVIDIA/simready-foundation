# Feature: `ID:023 - Robot Materials`

## Description

Support for proper material organization in robot assets. This feature ensures that materials in robot assets are structured according to USD best practices, with materials centrally organized in the top-level Looks prim and without nested material hierarchies. These requirements align with the Isaac Sim asset validation rules for ensuring consistent and reliable material handling across different USD applications and renderers.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Isaac Sim Format

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
|Internal ID              | `FET023_ROBOT_MATERIALS`|
| Asset Class             | `Robot`           |
| Supported Validation    | `Robot Materials` |
| Proprietary Techs       | `Isaac Sim`       |
| Dependency              | `OpenUSD`         |

#### Used in Profiles

This version can be used in the following profiles:

- **Robot Asset Profiles** - Used to ensure proper material organization for robot assets
- **Isaac Sim Robot Profiles** - Used in combination with other Isaac Sim features for complete robot asset validation

#### Requirements

* Capability: [Isaac_Sim/Robot_Materials](../capabilities/isaac_sim/robot_materials/requirements.md)
  * Requirements:
    * [No-Nested-Materials](../capabilities/isaac_sim/robot_materials/requirements/no-nested-materials.md)
      * RM.001 | Version 0.1.0
      * [Rule | Implementation](../capabilities/isaac_sim/robot_materials/validation.py)
    * [Materials-On-Top-Level-Only](../capabilities/isaac_sim/robot_materials/requirements/materials-on-top-level-only.md)
      * RM.002 | Version 0.1.0
      * [Rule | Implementation](../capabilities/isaac_sim/robot_materials/validation.py)

#### Pipelines Supported for this Feature

Source file type:
* .usd/.usda/.usdc
  * Via USD authoring tools with proper material organization
* .urdf
  * Via URDF to USD conversion with material consolidation
* .blend
  * Via Blender SimReady Add-ons with proper material export

#### Material Organization Best Practices

To comply with this feature:

1. **Organize Materials in Looks**: All materials must be direct children of the top-level Looks scope
   ```
   /<DefaultPrim>/Looks/Material_01
   /<DefaultPrim>/Looks/Material_02
   ```

2. **Avoid Nested Materials**: Materials must not contain other materials as children
   ```text
   Good: Flat material hierarchy
   Looks/
     - Material_01
     - Material_02
   
   Bad: Nested materials
   Looks/
     - Material_01
         - Material_02  (Nested - not allowed)
   ```

3. **Use Material Bindings**: Reference materials from geometry using material bindings
   ```usd
   def Mesh "mesh_01" (
       prepend apiSchemas = ["MaterialBindingAPI"]
   )
   {
       rel material:binding = </MyAsset/Looks/Material_01>
   }
   ```

4. **Centralize Material Definitions**: Keep all material definitions in one location for easier management and reuse

#### Test Process

* Obtain Isaac Sim 5 (release build) or use the SimReady validation tools
* Launch validation:
  * Use the Isaac Sim asset validator
  * Run validation against the Robot Materials feature requirements
* Test material organization:
  * Verify all materials are in the top-level Looks prim
  * Check that no materials contain nested materials
  * Validate material bindings resolve correctly
* Expected results:
  * No nested materials found
  * All materials located in /<DefaultPrim>/Looks
  * Material bindings resolve correctly
  * Assets render consistently across different USD applications

</details>