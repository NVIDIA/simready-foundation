# Release 2026.10 sample repair evidence

These reports were produced by `simready-validate` 2026.10.0rc1 with
`usd-validation-nvidia` and `usd-profiles-nvidia` 1.23.0, `usd-core` 26.8,
`isaacsim-robot-schema` 6.2.0.0, and this branch's Core/Newton 2026.10.0 catalogs.

| Asset | Full profile | Executed / total requirements | Result |
|---|---|---|---|
| UR10 | Robot-Body@3.0.0 | 114 / 114 | Pass |
| Robotiq 2F-85 | Robot-Gripper@2.1.0 | 100 / 100 | Pass |
| Robotiq 2F-85, QA target | Robot-Gripper@3.0.0 | 118 / 118 | Fail: VM.PS.002 |
| Current workbench | Robotics-Prop@3.2.0 | 86 / 86 | Pass |

The counts include optional requirements and count the exact requirements
selected in successfully completed runtime-composition buckets. Optional
failures remain visible in the generated reports. Robot Core and Isaac driven
joint gates pass for both robots, including the QA target. Their retained
receipts were refreshed through the public `validate_stage_against_profiles`
API, then the stages were reopened and validated again.

The Robotiq QA target remains **partial - not submission-ready** for
`Robot-Gripper@3.0.0`: its bound CAD materials expose MDL surfaces without
UsdPreviewSurface outputs (`VM.PS.002`). No 3.0.0 receipt was authored.
Its existing `Robot-Gripper@2.1.0` claim passes.

The five simple packages were regenerated with `simready-package`
2026.10.0rc6 using `nv_core/package_sample/create_sample_packages.py`.
Every USD snapshot passes `Robotics-Prop@3.2.0` and `Robotics-Prop@4.0.0`;
all package post-validation profiles pass. The no-BOM example retains
`Package-NoBOM@1.0.0` and its minimal definition. The other four packages pass
the library's complete BOM/hash verification, including SHA-256 and BLAKE3
for the multi-hash example. Generated package evidence remains in `.metadata/`.

The receipt audit opened all 282 sample USD layers, including binary USD and
historical folders. It removed only the historical workbench's unsupported
root claim and 11 component-layer receipts, plus the invalid profile claim in
its adjacent exporter JSON sidecar. The global workspace cache is unchanged. Comparing each cleaned layer with
its original `customLayerData` restored in memory confirmed that all other
layer content remained identical. The supported workbench entrypoint and claim
remain intact. The historical root is absent from `manifest.csv`, so no
published-profile retirement record applies.

Focused regression command:

```bash
python -m pytest nv_core/tiers/simready_foundation_tier_core/tests/test_release_sample_repairs.py nv_core/tiers/simready_foundation_tier_core/tests/test_ur10_joint_state_api.py -q -p no:cacheprovider
```

The tests cover real robot discovery in neutral and PhysX compositions,
composable relationships, world-anchor ordering, a complete stale-USD-receipt
audit, texture/MDL dependency spelling checked against directory entries even
on Windows, and official package integrity verification. Static validation
does not establish runtime behavioral test completion.

Evaluate 2026.10.0rc5 with the 2026.10.0rc4 host adapter also completed
installed-tier planning against the retained receipts. The installed Core and
Newton 2026.10.0 catalog/runtime files match this source checkout byte for byte.
The unmodified [workbench log](workbench-plan.jsonl) records 18 tests and 15
planned runs for its one profile; the [robot log](robots-plan.jsonl) records
37 tests and 53 planned asset/test runs for the two robot profiles. Both plans
have complete runtime bindings, zero plan warnings, and zero unavailable tests.
Each host log separately reports two Kit-only helper import warnings for missing
`carb`. No Kit engine is configured, and no native simulation was executed.
The full generated plans remain with the staged output under
`.tmp/evaluate-clean-plan-workbench/` and `.tmp/evaluate-clean-plan-robots/`.
