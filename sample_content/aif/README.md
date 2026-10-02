# AI Factory sample assets

Four complete equipment assets, one per AIF equipment class. Each validates against
`AIF-Entity` at both 0.1.0 and 0.2.0, and against `Package-Candidate` 1.3.0, the
preflight for publishing to SimReady Central.

| Asset | Class | Identity |
|---|---|---|
| `Generic_CDU` | CDU | KddcCorp Generic CDU |
| `Synthetic_CRAH` | CRAH | Generic Cooling Systems GCS-CRAH-105D |
| `Synthetic_UPS` | UPS | Generic Power Systems GPS-UPS-1000 |
| `gb300` | Compute Rack | NVIDIA Grace Blackwell 300 NVL72 |

Geometry is simplified — boxes fitted to the real envelope, not manufacturing
detail. These illustrate the specification and exercise the validators; they are
not production content. Real partner equipment is published through SimReady
Central.

Each asset states its licence on `SimReady_Metadata.asset_license`, as the
rest of `sample_content` does. These four are **CC-BY 4.0**.

## Against the test fixtures

The tier's own fixtures stay under
`nv_core/tiers/simready_foundation_tier_aif/tests/fixtures/`:

- `synthetic/` — two more class assets and the four connection-point domain
  fixtures, all generated
- `variants/` — deliberately broken assets, one per requirement

Those exist to make a validator fail and are never published. These four exist to
show an author what a conforming asset looks like.

Because they are never published, the fixtures carry no thumbnail, so
`Synthetic_CDU` and `Synthetic_ComputeRack` satisfy every AIF requirement at
0.2.0 but not `SR.002`. The publishing contract applies to what ships.

## Regenerating

`Synthetic_CRAH` and `Synthetic_UPS` come from
`tests/fixtures/synthetic/build_synthetic_fixtures.py`, which writes each asset to
whichever tree its `ASSETS` entry names. Connection-point layers for all four come
from `tests/fixtures/connection_points/build_connection_points.py`, whose
`values.json` addresses them as `samples/<Asset>/...`.

Each asset's thumbnail at `.thumbs/256x256/<usd file name>.png` is a Storm render
of the asset from a three-quarter view, committed rather than generated: Storm
needs an OpenGL context, so no CI job can reproduce it.
