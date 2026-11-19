# SimReady tier template

Copy this package when you need a **new additive SimReady validation tier**
that depends on `simready-foundation-tier-core`. It ships one example smoke
feature so the wheel builds, registers, and documents end-to-end.

Distribution name in this template: `simready-foundation-tier-template`.

```bash
pip install simready-validate
pip install simready-foundation-tier-template   # brings in simready-foundation-tier-core
```

## Rename checklist

Replace every `template` / `TEMPLATE` / `TMP` token before publishing a real tier:

| Token | Example rename |
|---|---|
| Dir `simready_foundation_tier_template` | `simready_foundation_tier_<name>` |
| PyPI `simready-foundation-tier-template` | `simready-foundation-tier-<name>` |
| Module `simready.foundation.tier_template` | `simready.foundation.tier_<name>` |
| Entry points `tier_template`, `simready-validate-tier-template` | matching `<name>` |
| Capability folder `template/` | your capability category |
| Requirement prefix `TMP.*` | your requirement IDs |
| Capability catalog ID | `CAP`-prefixed ID such as `CAP1000_Smoke` |
| Legacy feature `FET_1000_TEMPLATE` | new dotted `<name>[.<runtime>].<version>` ID |
| Adapter `standard_to_template_smoke` | your adapter module name |

Also add the new tier directory to [`../pyproject.toml`](../pyproject.toml) workspace
`members`, and append its `rules_and_reqs` / `features` / `profiles` paths in
[`../../sr_specs/docs/config.json`](../../sr_specs/docs/config.json).

## What's in the example

- **Capabilities:** `template/smoke` (owns `TMP.001`).
- **Features:** `FET_1000_TEMPLATE@0.1.0` is a Foundations 1 loader fixture.
  New tiers author a dotted ID such as `FET1000_Smoke.Template.0-0-1` only when
  runtime tests and adapters exist. Static-only smoke requirements belong in a
  CAP-prefixed definition.
- **Profiles:** empty placeholder (`profiles/.gitkeep`).
- **Adapter example:** `standard_to_template_smoke` under
  `nv_core/cip_specs/asset_handler_modules/` (ensures `defaultPrim`; shows where
  to import an external package such as `isaacsim.asset.transformer`).

## Layout

```
simready_foundation_tier_template/
├── pyproject.toml
├── README.md
└── simready/foundation/tier_template/
    ├── __init__.py, _plugin.py, _tier.py
    ├── rules_and_reqs/          # requirement docs + validators
    ├── features/              # feature markdown + JSON manifests
    └── profiles/              # profile TOMLs (optional)
```

At build time, codegen adds `requirements/` into the wheel (not committed).

## Discovery surfaces

- **`usd_validation_nvidia`** → `simready.foundation.tier_template:SimReadyPlugin`
- **`simready.tier`** → `simready.foundation.tier_template:tier`

## Building

```bash
# from the repo root
./repo.sh build_tiers
```
