# Evaluate Reference — Sensors Tier

This section documents every evaluation in the sensors FET suite: what each
test checks, what a passing result guarantees, how the test works, what
failure modes to expect, and how to fix a failing asset. Tests are organized
by feature: each family page lists the tests that validate that feature.

## What the Framework Does

This pack declares `simready.foundation.sensors.runtime_tests` in its bundled
`benchmark-provider.json`. Use `<namespace>:<test-name>` in catalog bindings
and CLI selectors, not internal folder names. Its explicit `import_package` is
also `simready.foundation.sensors.runtime_tests`; the former flat name remains
a provider alias, not a Python import shim. Provider identity and import ownership are
separate declarations; do not merge this
package with Core's physical package.

Evaluation runs as a pipeline: the planner selects the tests an asset is
eligible for, the runner executes them in the engine and captures frames and
logs, the stamper records the outcome on the asset, and the reporter aggregates
results into an HTML and JSON report.

## Test Families

:::{list-table}
:header-rows: 1
:widths: 20 80

* - Family
  - Validates
* - [FET034 IMU Sensors](fet034-imu-sensors.md)
  - IMU sensor angular velocity and linear acceleration output.
* - [FET035 Render Products](fet035-render-products.md)
  - RenderProduct output file generation and semantic AOV BLOSC compression.
* - [FET036 RTX Sensors](fet036-rtx-sensors.md)
  - OmniLidar point cloud output.
* - [FET037 Joint Sensors](fet037-joint-sensors.md)
  - Joint sensor position and velocity state output.
:::

```{toctree}
:maxdepth: 1
:hidden:

FET034 IMU Sensors <fet034-imu-sensors>
FET035 Render Products <fet035-render-products>
FET036 RTX Sensors <fet036-rtx-sensors>
FET037 Joint Sensors <fet037-joint-sensors>
```
