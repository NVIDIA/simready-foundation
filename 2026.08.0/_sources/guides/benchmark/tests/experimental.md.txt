# Experimental and disabled runtime tests

This page inventories implementations that remain in the source tree with
`enabled=False`. They are not discoverable shipped coverage, are not selected by
normal plans, and must not be presented as supported tests. Their presence in
source is useful for future investigation and for preserving focused helper
code.

| Test | Family | Test version | Registered features | Shipped status |
|---|---|---|---|---|
| `culling_x` | FET001 | 2.0.0 | `FET_001_STANDARD` | Disabled |
| `culling_z` | FET001 | 2.0.0 | `FET_001_STANDARD` | Disabled |
| `normals_x` | FET001 | 2.0.0 | `FET_001_STANDARD` | Disabled |
| `normals_z` | FET001 | 2.0.0 | `FET_001_STANDARD` | Disabled |
| `ground_stability` | FET003 | 2.0.0 | `FET_003_STANDARD`, `FET_003_PHYSX`, `FET_003_NEWTON` | Disabled |

## Promotion requirements

Do not enable one of these tests only to make it appear in discovery. Before
promotion:

1. verify the behavior and verdict boundaries against the current supported
   engines;
2. add or update focused unit and runtime coverage;
3. add a complete per-test page and family entry;
4. bump the test version when behavior or evidence semantics changed;
5. run documentation parity, discovery, plan, and runtime checks.

The `@test` decorator remains the source of truth for enabled status. The
documentation parity tests require disabled registrations to remain absent from
the shipped per-test reference.
