# Feature: `ID:001 - Minimal - Base`

| **Property**            | **Value**         |
|-------------------------|-------------------|
|Internal ID              | `FET001_BASE_NEUTRAL`|

## Description

The minimal placeable visual feature comprises a list of requirements that enable the digital representation of a real world object to be visualized in a broad range of applications.

It additionally provides a list of requirements to ensure that the scale, units and placement of the object may be correctly represented, so that the object can be placed and aggregated with other objects in a scene.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products that consume this feature:

- NDAS SDG / Stargate
- MetroSim
- AI Factory
- AV Sim
- IsaacSim
- MEGA
- Lightwheel SOW1

## Neutral Format

### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Prop Robotics Neutral Profile](../profiles/prop-robotics-neutral.md)** (v0.1.0) - Used as the base editor support feature
- **[Prop Robotics Physx Profile](../profiles/prop-robotics-physx.md)** (v0.1.0) - Used as the base editor support feature with PhysX-aware tools

#### Requirements
* Capability: [Core/Atomic_Asset](../capabilities/core/atomic_asset/capability-atomic_asset.md)
    * Requirements
        * [Anchored-Asset-Paths](../capabilities/core/atomic_asset/requirements/anchored-asset-paths.md)
            * AA.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/atomic_asset/validation.py)
        * [Supported-File-Types](../capabilities/core/atomic_asset/requirements/supported-file-types.md)
            * AA.002 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/atomic_asset/validation.py)
* Capability: [Core/Units](../capabilities/core/units/capability-units.md)
    * Requirements
        * [UpAxis](../capabilities/core/units/requirements/upaxis.md)
            * UN.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/units/validation.py)
        * [Meters-Per-Unit](../capabilities/core/units/requirements/meters-per-unit.md)
            * UN.002 | verison 0.1.0
            * [Rule | Implementation](../capabilities/core/units/validation.py)
        * [UpAxis-Z](../capabilities/core/units/requirements/upaxis-z.md)
            * UN.006 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/units/validation.py)
        * [Meters-Per-Unit-1](../capabilities/core/units/requirements/meters-per-unit-1.md)
            * UN.007 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/units/validation.py)
* Capability: [Visualization/Geometry](../capabilities/visualization/geometry/capability-geometry.md)
    * Requirements
        * [At-Least-One-Imageable-Geometry](../capabilities/visualization/geometry/requirements/at-least-one-imageable-geometry.md)
            * VG.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/geometry/validation.py)
* Capability: [Hierarchy](../capabilities/hierarchy/hierarchy.md)
    * Requirements
        * [Stage-Has-Default-Prim](../capabilities/hierarchy/requirements/stage-has-default-prim.md)
            * HI.004 | Version 0.0.0
            * Description
                * Requirement that the current Usd Stage has a defaultPrim.  Believe that this will help limit amount of errors for when we talk about assembly type features.
            * [Rule | Implementation](../capabilities/hierarchy/validation.py)


#### Pipelines Supported for this Feature
Source file type:
* .blend
  * Via Blender SimReady Add-ons
* .mjcf
  * Via Blender SimReady Add-ons + MJCF2USD Tool
* .step
  * Via Blender SimReady Add-ons + CAD Converter

#### Samples

* [sample_content/common_assets/props_general/obs_lamp_revolute_a01/simready_usd/sm_obs_lamp_revolute_a01_01.usd](../../../../sample_content/common_assets/props_general/obs_lamp_revolute_a01/simready_usd/sm_obs_lamp_revolute_a01_01.usd)


#### Test Process

* Obtain the usd sdk
  * [usd sdk link](https://developer.nvidia.com/usd?sortBy=developer_learning_library%2Fsort%2Ffeatured_in.usd_resources%3Adesc%2Ctitle%3Aasc&hitsPerPage=6#section-getting-started)
* Confirm your asset in question has passed validation
* In your commandline type:
  * ```path/to/usdsdk/scripts/usdrecord <path to usdfile.usd> <path to output.png>```
* Open up path/to/output.png
* Expected Result:
  * Confirm it is NOT empty or completely black
  * Example image: ![image1](./images/obs_revolute_lamp_01.png)

</details>



### Version 1.0.0
<details>
<summary><strong>Details</strong></summary>

#### Requirements
* Capability: [Core/Atomic_Asset](../capabilities/core/atomic_asset/capability-atomic_asset.md)
    * Requirements
        * [Anchored-Asset-Paths](../capabilities/core/atomic_asset/requirements/anchored-asset-paths.md)
            * AA.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/atomic_asset/validation.py)
        * [Supported-File-Types](../capabilities/core/atomic_asset/requirements/supported-file-types.md)
            * AA.002 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/atomic_asset/validation.py)
* Capability: [Core/Units](../capabilities/core/units/capability-units.md)
    * Requirements
        * [UpAxis-Z](../capabilities/core/units/requirements/upaxis-z.md)
            * UN.006 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/units/validation.py)
        * [Meters-Per-Unit-1](../capabilities/core/units/requirements/meters-per-unit-1.md)
            * UN.007 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/units/validation.py)

* Capability: [Visualization/Geometry](../capabilities/visualization/geometry/capability-geometry.md)
    * Requirements
        * [Mesh-representation](../capabilities/visualization/geometry/requirements/geom-shall-be-mesh.md)
            * VG.MESH.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/geometry/validation.py)

        * [Geometry-cached-extent](../capabilities/visualization/geometry/requirements/usdgeom-extent.md)
            * VG.002 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/geometry/validation.py)

        * [Geometry-valid-mesh-topology.md](../capabilities/visualization/geometry/requirements/usdgeom-mesh-topology.md)
            * VG.014 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/geometry/validation.py)

        * [Geometry-correct-winding-order.md](../capabilities/visualization/geometry/requirements/usdgeom-mesh-winding-order.md)
            * VG.029 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/geometry/validation.py)

        * [Geometry-surface-normals.md](../capabilities/visualization/geometry/requirements/usdgeom-mesh-normals-exist.md)
            * VG.027 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/geometry/validation.py)

        * [Geometry-valid-normals.md](../capabilities/visualization/geometry/requirements/usdgeom-mesh-normals-must-be-valid.md)
            * VG.028 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/geometry/validation.py)

        * [Asset-transform-origin.md](../capabilities/visualization/geometry/requirements/asset-origin-positioning.md)
            * VG.025 | version 0.1.0
              * For objects that sit on a ground plane, the pivot should be at the center of the object's base.
              * For objects that rotate around a specific point (e.g., a robot arm joint, a hinged door), the pivot should be at the center of rotation.
              * For objects that are attached to other objects (e.g., a camera, a wheel), the pivot should be at the attachment point.
            * [Rule | Implementation](../capabilities/visualization/geometry/validation.py)

* Capability: [Hierarchy](../capabilities/hierarchy/hierarchy.md)
    * Requirements
        * [Single-root-prim](../capabilities/hierarchy/requirements/hierarchy-has-root.md)
          * HI.001 - There shall be a single root prim as a common parent for assets' hierarchy.
          * [Rule | Implementation](../capabilities/hierarchy/validation.py)
        * [Stage-Has-Default-Prim](../capabilities/hierarchy/requirements/stage-has-default-prim.md)
          * HI.004 | Version 0.0.0
          * Description
              * Requirement that the current Usd Stage has a defaultPrim.  Believe that this will help limit amount of errors for when we talk about assembly type features.
          * [Rule | Implementation](../capabilities/hierarchy/validation.py)
        * [Root-is-xformable](../capabilities/hierarchy/requirements/root-is-xformable.md)
          * HI.003 - The root prim of an individual, placeable asset file shall be an Xformable (i.e., a prim that inherits UsdGeomXformable, such as Xform). This allows the entire asset to be easily transformed when instanced into a larger scene.
          * [Rule | Implementation](../capabilities/hierarchy/validation.py)




#### Samples

* [sample_content/common_assets/props_general/obs_lamp_revolute_a01/simready_usd/sm_obs_lamp_revolute_a01_01.usd](../../../../sample_content/common_assets/props_general/obs_lamp_revolute_a01/simready_usd/sm_obs_lamp_revolute_a01_01.usd)


#### Test Process

##### Runtime Validation with SimReady Testing Framework

The Minimal Placeable Visual feature includes automated runtime tests using the SimReady Foundation testing framework. The tests verify:
- Asset loads without warnings or errors (AA.002)
- Proper camera framing of geometry (VG.002)
- Correct transformation and positioning (HI.001, HI.003, HI.004)
- Valid renderable geometry (VG.MESH.001, VG.027)
- Correct winding order and normals (VG.028, VG.029)
- Proper origin positioning (VG.025)

**Prerequisites:**
- Configure runner info in `local_run/runners_info.toml` with paths to Isaac Sim or Kit engine
- See `local_run/runners_info_setup.md` for setup instructions

**Configuring Test Segments:**

The runtime test is divided into segments that can be enabled/disabled in `nv_core/testing_tools/test_definitions/kit_test/feature_vis_fet_001.toml`:

- **S0**: Presence check (verifies asset has visible geometry) - enabled by default
- **S1**: Light response test (validates VG.027, VG.028, VG.029) - produces video
- **S2**: Backface culling Z-axis test (validates VG.029 winding order) - produces videos
- **S3**: Backface culling X-axis test (validates VG.029 winding order) - produces videos
- **S4**: Pivot positioning test (validates VG.025 origin placement) - produces videos
- **S5**: Normal direction test (validates VG.028 normals validity) - produces videos

To enable all segments, edit the `[TestConfig]` section in the TOML file:
```toml
[TestConfig]
# Enable all segments for full MPV validation
segments = "S0,S1,S2,S3,S4,S5"
```

**Note**: S0 only validates presence and does not produce video outputs. To get visual validation videos, enable S1-S5.

**To run runtime tests:**

1. **Generate test batch** for specific assets (Manual mode):
   ```bash
   cd nv_core/testing_tools/testing_framework/source

   # Test a specific asset
   python batch_maker/batch_maker.py \
     --project_root "C:\path\to\simready_foundation" \
     --tests "feature_vis_fet_001" \
     --manual_assets "sample_content/common_assets/props_general/my_asset/my_asset.usd"
   ```

   Or generate tests for all conforming assets (uses search functions):
   ```bash
   python batch_maker/batch_maker.py \
     --project_root "C:\path\to\simready_foundation"
   ```

2. **Execute tests locally**:
   ```bash
   python job_runner/job_runner.py "..\..\..\..\..\_testing\batch_jobs\local_test_windows.json"
   ```

3. **Generate HTML report**:
   ```bash
   python report_generator/report_generator.py --output_dir "..\..\..\..\..\_testing"
   ```

4. **View results**: Open `_testing\index.html` in a web browser

For detailed documentation, see `nv_core/testing_tools/testing_framework/source/REPORT_USAGE.md`



</details>