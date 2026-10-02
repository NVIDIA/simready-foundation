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

Content is v0.1.0 plus the v0.2.0 Connection Points property vocabulary
(CP.010-012); the two vocabularies coexist by design, a profile selects one.
