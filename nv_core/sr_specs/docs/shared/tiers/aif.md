# AIF Tier

The AIF tier is the AI Factory distribution of SimReady Foundation: the
validation contracts for datacenter equipment that a facility-scale digital twin
composes and simulates. It covers four equipment classes today (CDU, CRAH, UPS,
compute rack), the metadata each class carries, and the connection points
through which equipment exchanges liquid, air, power and data.

It depends on the Core tier. Every AIF profile selects `FET_000_STANDARD` and
`FET_001_STANDARD` from Core, so an AIF asset is a SimReady asset first and an
AI Factory asset second.

The tier is an incubation tier. Its content is specified and validated to the
same standard as Core, but it is owned by the AI Factory (DSX) programme rather
than the shared Foundation, and its contracts may change between minor versions
while the equipment vocabulary is still being agreed with the OEMs who author
against it. See [Tiers](../guides/tiers.md) for what that distinction means.

Install the validator and tier together:

```bash
pip install simready-validate simready-foundation-tier-aif
```

The tables below reflect the catalogs in the current source tree. The tier's
feature JSON and profile TOML files remain the machine-readable sources of
truth.

## Profiles

The AIF tier owns one profile. Its `aif:core:assetClass` value selects which
class-specific checks apply, so a single profile covers all four equipment
classes.

| Profile | Available versions | Catalog file |
| --- | --- | --- |
| [AIF-Entity](../profiles/aif-entity.md) | `0.1.0`, `0.2.0` | `aif_entity.toml` |

`0.1.0` is the published contract that the AIF 0.1.0 preview shipped. `0.2.0`
adds the Connection Points 2.0 vocabulary (`CP.010` to `CP.012`): a connection
point becomes an Xform carrying typed `simready:connectionPoint:*` properties,
in place of the named Mesh prims of 0.1.0. An asset authored to 0.1.0 stays
valid against the 0.1.0 profile.

## Features

The AIF tier owns four feature IDs and seven exact feature versions. `FET200_AIF`
and `FET201_AIF` are capabilities carried as features until profiles can
reference capabilities directly.

| Feature | Purpose | Available versions |
| --- | --- | --- |
| [FET200_AIF](../features/FET_200-aif_metadata.md) | AIF Core Metadata | `0.1.0` |
| [FET201_AIF](../features/FET_201-connection_points.md) | Connection Points | `0.1.0`, `0.2.0` |
| [FET202_AIF](../features/FET_202-thermal_cooling.md) | Thermal Cooling | `0.1.0`, `0.2.0` |
| [FET203_AIF](../features/FET_203-electrical.md) | Electrical | `0.1.0`, `0.2.0` |

## Package contents and discovery

The distribution advertises both the `usd_validation_nvidia` and
`simready.tier` entry-point groups. Together they expose:

- Capability and requirement documentation plus registered validators.
- Generated requirement enums.
- The per-class attribute configuration (`config/aif-equipment-*.json`) that
  `AM.007` reads.
- Feature JSON and profile TOML catalogs.

The tier ships no runtime tests yet; `runtime_tests_path` is `None`.

For the package layout, build commands, and local development notes, see the
README in `nv_core/tiers/simready_foundation_tier_aif/` in the source tree.
