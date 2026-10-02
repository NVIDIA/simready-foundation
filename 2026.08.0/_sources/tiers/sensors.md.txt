# Sensors Tier

The Sensors tier supplies the requirements, capabilities, feature contracts,
profile contracts, and static validation rules for physics sensors, RTX
LiDAR, and camera/render-product workflows. Its sensor profiles apply
alongside an asset's primary profile (Robot-Body, Prop, fixed-mount, etc.);
validating a sensor-bearing asset typically requires installing both this
tier and the Core tier.

Install the validator and tier together:

```bash
pip install simready-validate simready-foundation-tier-sensors
```

Install the optional Benchmark framework and Kit engine dependencies needed to
execute this tier's bundled runtime tests. This extra requires Python 3.12;
validator-only tier installs also support Python 3.11.

```bash
pip install "simready-foundation-tier-sensors[benchmark]"
```

The tables below reflect the catalogs in the current source tree. The tier's
feature JSON and profile TOML files remain the machine-readable sources of
truth.

## Profiles

The Sensors tier owns four profiles. Each applies to any asset carrying the
corresponding sensor type, independent of the asset's primary profile
(Robot-Body, Prop, fixed-mount, etc.). An asset with multiple sensor types
should be stamped with each applicable profile.

| Profile | Available versions | Catalog file |
| --- | --- | --- |
| [Sensor-IMU](../profiles/sensor-imu.md) | `1.0.0` | `profiles.toml` |
| [Sensor-Joint](../profiles/sensor-joint.md) | `1.0.0` | `profiles.toml` |
| [Sensor-Camera](../profiles/sensor-camera.md) | `1.0.0` | `profiles.toml` |
| [Sensor-LiDAR](../profiles/sensor-lidar.md) | `1.0.0` | `profiles.toml` |

## Features

The Sensors tier owns four feature IDs and four exact feature versions.

| Feature | Purpose | Available versions |
| --- | --- | --- |
| [FET_034_ISAAC](../features/FET_034_ISAAC.md) | IMU Sensor | `0.1.0` |
| [FET_035_RTX](../features/FET_035_RTX.md) | Camera and Render Products | `0.1.0` |
| [FET_036_RTX](../features/FET_036_RTX.md) | RTX Sensors (LiDAR) | `0.1.0` |
| [FET_037_ISAAC](../features/FET_037_ISAAC.md) | Joint Sensor | `0.1.0` |

## Package contents and discovery

The distribution advertises both the `usd_validation_nvidia` and
`simready.tier` entry-point groups. Together they expose:

- Capability and requirement documentation plus registered validators.
- Generated requirement enums.
- Feature JSON and profile TOML catalogs.
- Tier-owned Benchmark runtime tests for the physics-sensors, render-products,
  LiDAR, and joint-sensor features.

For the package layout, build commands, and local development notes, see the
README in `nv_core/tiers/simready_foundation_tier_sensors/` in the source tree.
