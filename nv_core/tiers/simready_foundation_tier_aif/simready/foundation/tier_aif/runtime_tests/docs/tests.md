# Simulation Network Topology evaluation

`device_connectivity@0.3.0` belongs to
`FET207_SimulationNetworkTopology.0-3-0` and is provided by
`simready.foundation.tier_aif.runtime_tests`. The feature manifest binds the exact
`simready.foundation.tier_aif.runtime_tests:device_connectivity` procedure.

The procedure invokes the DSX Air adapter against an operator-supplied fixture.
A completed adapter result supplies an explicit boolean `passed` value and
transmitted/received packet counts. A false verdict records a measured failure.
Missing fixtures, unavailable infrastructure, API errors and malformed command
output remain execution errors; they are never converted to successful or
inapplicable results. The procedure records sanitized adapter evidence as the
`dsx_air_connectivity` metric and captures no video.

## Configuration and discovery

Install the owning tier with its `evaluate` extra and configure a supported
Evaluate engine/session. The procedure uses Python/DSX Air APIs and no scene
operations, so it declares no engine-specific tag. Evaluate 2026.10 nevertheless
requires a configured engine plugin to dispatch a run; it has no built-in
standalone Python runner.

Set the `fixture_path` test configuration or the
`DSX_AIR_CONNECTIVITY_FIXTURE` environment variable to the reviewed fixture.
Credentials remain in the adapter's environment or credential mechanism, outside
saved fixtures and reports. The whole-test wall-clock allowance is 300 seconds.
A new plan is required after changing the procedure or fixture configuration.

```sh
simready-evaluate --list-tests
simready-evaluate --tests-path nv_core/tiers/simready_foundation_tier_aif/simready/foundation/tier_aif/runtime_tests --list-tests
```

Source discovery and unit tests prove registration and error classification.
They do not establish live DSX Air connectivity. No live-lab evaluation is
included with the synthetic sample.
