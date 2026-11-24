# Runtime attribution QA

This static regression plan covers `RV.010` section purity and `RV.011`
physics isolation for OMPE-119276 / NVBug 7033914. It runs the installed
`simready-validate` public CLI and checks its `--output` JSON. No simulator is
required.

## Setup and execution

Use a Python environment with `simready-validate`, `usd-core`, and the Core and
Newton tier wheels installed. Read the installed validator's `validate-asset`
skill before running the plan. Record the validator and tier versions from each
generated report. The catalogs must provide `Robotics-Prop@5.0.0` and
`CAP000_Core.{PhysX,Newton,MuJoCo}.0-2-0`.

From the repository root, with that environment activated:

```bash
python nv_core/sr_specs/tests/validate_runtime_attribution.py --output outputs/runtime_attribution_qa
```

The output directory must be new. Pass `--validator /path/to/simready-validate`
when the CLI is outside `PATH`. To test Foundation source changes using the
installed validator, add `--catalog-root /path/to/foundation/checkout`; this
loads that checkout's Core and Newton rules, contracts, and profiles through the
public CLI path options. Omit this option to test the installed tier wheels.

## Cases and acceptance criteria

The reproducer generates three independent synthetic USD packages with native
references, payloads, and disabled-by-default physics variant sets:

| Case | Authored data | Expected runtime requirement failures |
|---|---|---|
| `clean` | Empty runtime payloads over shared neutral geometry | Neither `RV.010` nor `RV.011` |
| `inline_physx` | Inline property in PhysX `Enabled` | PhysX `RV.010` only |
| `foreign_physx` | Newton schema and attribute inside the PhysX payload | PhysX `RV.011` only |

Each case is validated against the published `Robotics-Prop@5.0.0` profile.
Its runtime Core selectors are optional: the negative requirement IDs must
appear in PhysX's `optional requirements` JSON field, with `passed = false`.
Newton and MuJoCo must carry neither failure. A missing profile, asset result,
runtime contract, report, or negative requirement ID fails QA.

Two generated QA-only profiles exercise required/optional attribution without
changing published contracts. Both select the three runtime Core contracts:

- `QA-Runtime-Attribution-PhysXRequired@0.0.0` requires PhysX and leaves Newton
  and MuJoCo optional. Each negative must report its ID under PhysX's
  `failing requirements`, set `blocking_failure = true`, and fail that profile.
- `QA-Runtime-Attribution-NewtonRequired@0.0.0` requires Newton and leaves
  PhysX and MuJoCo optional. Each negative must stay in PhysX's
  `optional requirements`, leave every `blocking_failure = false`, and pass
  that profile.

The script exits nonzero for incorrect attribution or missing evidence. Retain
`qa_result.json`, the untouched CLI JSON reports and logs, commands, and generated
USD packages together. JSON requirement fields may be arrays or serialized
Python lists; the reproducer accepts both representations.

## Release dependencies and scope

Foundation's composed-runtime checker fix is MR !703 (release backport in a
separate change). Validator runtime-aware summary attribution is Explorer !568,
backported in !573. The mixed required/optional assertions also need Explorer
!577 or its release backport. A failing mixed-bucket case remains a failed gate
until that external dependency is present; do not skip it or mark it passed.

This is **partial - not submission-ready** evidence. The synthetic fixtures are
negative QA inputs and intentionally omit other asset contracts. Their full
`Robotics-Prop@5.0.0` results may fail unrelated requirements. A successful
attribution gate proves only the listed static checks; asset handoff still
requires a full named profile pass and executed-versus-total requirement counts.
