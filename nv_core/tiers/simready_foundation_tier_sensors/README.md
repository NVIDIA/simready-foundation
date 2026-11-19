# SimReady Foundation Sensors Tier

The `simready-foundation-tier-sensors` distribution contains the sensor
capabilities, features, requirements, validator rules, and tier-owned Evaluate
runtime tests for physics sensors, RTX LiDAR, and render products.

Install validation support:

```bash
pip install simready-validate simready-foundation-tier-sensors
```

Install the optional Evaluate framework and Kit engine dependencies needed to
execute this tier's bundled runtime tests. This extra requires Python 3.12;
validator-only tier installs also support Python 3.11.

```bash
pip install "simready-foundation-tier-sensors[evaluate]"
```

## Contents

The tier owns the physics-sensors, LiDAR, and render-products capability
groups, together with their features, validation rules, profiles, and
runtime evaluation tests.

### Capabilities

- **`physics_bodies/physics_sensors`** — PS.001 (IMU sensor placement) and PS.002 (joint sensor articulation root)
- **`nonvisual_sensors/lidar`** — LI.001–LI.004 (OmniLidar schema, emitter state length, scan rate, solid-state ray count)
- **`rendering/render_products`** — RP.001–RP.006 (RenderProduct wiring, RenderVar sourceName, semantic AOV compression)

### Features

- `FET034_ImuSensor.Isaac` — IMU Sensor (PS.001)
- `FET035_RenderProducts.RTX` — Camera and Render Products (RP.001–RP.006)
- `FET036_Lidar.RTX` — RTX Sensors (LI.001–LI.004)
- `FET037_JointSensor.Isaac` — Joint Sensor (PS.002)

## Layout

```text
simready_foundation_tier_sensors/
|-- pyproject.toml
|-- README.md
|-- simready/foundation/sensors/
|   |-- __init__.py, _plugin.py, _tier.py
|   |-- rules_and_reqs/
|   |-- features/
|   `-- profiles/
|-- simready/foundation/sensors/runtime_tests/
|   |-- README.md
|   |-- docs/
|   `-- fet034_physics_sensors/, fet035_render_products/, fet036_lidar/, fet037_joint_sensors/
`-- tests/runtime_tests/unit/
```

The shared Hatch build hook generates `simready/foundation/sensors/requirements/`
from the capability Markdown and adds those enums to the wheel. Runtime-test
documentation is colocated with the test package and assembled into the public
Foundation guide from that single source.

## Discovery

The wheel advertises two entry points:

- `usd_validation_nvidia` (`simready-validate-sensors`) -> `simready.foundation.sensors:SimReadyPlugin`
  lets the validator discover rules and requirements.
- `simready.tier` (`sensors`) -> `simready.foundation.sensors:tier` lets validation and
  Evaluate discover the tier's requirement module, catalogs, profile sources,
  and optional runtime-test package.

## Build

From the repository root:

```bash
./repo.sh build_tiers
```

On Windows use `repo.bat build_tiers`. Wheels are written to
`nv_core/tiers/_build/dist/`.

See `simready/foundation/sensors/runtime_tests/docs/tests.md` for runtime-test authoring.
