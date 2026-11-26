# SimReady AI Factory (AIF) Tier

The `simready-foundation-tier-aif` distribution contains the AI Factory
profile, features, requirements, and validator rules: AIF core metadata,
Connection Points, thermal cooling, and electrical. It depends on
`simready-foundation-tier-core` for the base SimReady requirements every AIF
asset also has to satisfy.

Install validation support:

```bash
pip install simready-validate simready-foundation-tier-core simready-foundation-tier-aif
```

## AIF 0.3 chiller definitions

Each chiller class supplies a review CSV under
`standards/equipment-classes/aif-v0.3/`, a generated schema under
`config/v0.3/`, and a matching validator module under `rules_and_reqs/aif/`.
The module name is the schema's class identifier with hyphens replaced by
underscores. The tier imports each installed module to register its dedicated
profile checks. AIF-Entity applies the general metadata checks to every
registered class. AIF 0.1 and 0.2 retain their existing equipment classes.

Regenerate the packaged schemas from the repository root with
`python nv_core/tiers/simready_foundation_tier_aif/tools/generate_chiller_schema.py`.
Pass `--check` to compare the packaged definitions with the review CSVs.

## Profiles

Content is v0.1.0 plus the v0.2.0 Connection Points property vocabulary
(CP.010-012); the two vocabularies coexist by design, a profile selects one.

AIF-Entity 0.3.0 uses the 0.2.0 connection-point vocabulary, thermal, electrical
and packaging requirements. AM.008 checks the common metadata types on both the
Properties layer and the composed default prim.
