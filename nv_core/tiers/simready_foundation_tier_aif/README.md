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

AIF-Entity 0.3.0 uses the 0.2.0 connection-point vocabulary, thermal, electrical
and packaging requirements. AM.008 checks the common metadata types on both the
Properties layer and the composed default prim.

`AIF-Entity@0.3.0` selects `CAP204_NetworkEquipment.0-3-0` for the
`network-equipment` class. It validates node allocations and named network
ports for DSX Air configuration before simulation.

[`Networking@0.3.0`](simready/foundation/tier_aif/profiles/networking.md) selects
the [Networking feature](simready/foundation/tier_aif/features/FET207_Networking.DSXAir.md)
for network equipment. The runtime procedure measures IPv4 reachability between
two directly linked devices in an operator-designated DSX Air simulation.
