# Synthetic network equipment

A fictional 1U network switch for the AIF-Entity and Networking 0.3.0 profiles.
The asset carries eight OSFP fabric ports and one RJ45 management port using
the AIF 0.3 connection-point contract. Connections between equipment instances
belong in an assembled scene.

All identity, dimensions, port ratings, resource allocations and material
densities are synthetic. The mesh represents a simplified hollow enclosure,
connector cages and internal components; mass is the sum of their solid volumes
multiplied by the stated synthetic densities. These are illustrative values,
not manufacturer specifications, measured performance or manufacturing geometry.

The sample preserves the existing AIF dimension properties and their mm/kg
units. Dimensions use separate height, width and depth scalars. The packaging
provenance records `asset_extents` in meters as XYZ. `cpuAllocation`,
`memory_MB`, `storage_GB` and `osImage` demonstrate the proposed networking
contract. CPU allocation units, permitted DSX Air allocation
ranges and image identifier formats still require owner review. The
`synthetic://network-os/1.0` image is a fictional opaque identifier; no image is
bundled or fetched. There is no DSX Air import, connectivity or runtime result.
Cable equipment classes are outside this sample.

## Reproduce

Use Python 3.12 with this checkout's Core/AIF tiers, their matching Newton
dependency and `simready-validate` installed. Planning also needs the AIF
`evaluate` extra. Generation needs OpenUSD; rendering additionally needs a
working `usdrecord` renderer and Pillow.

```sh
python sample_content/aif/Synthetic_NetworkEquipment/generate.py --render
python sample_content/aif/Synthetic_NetworkEquipment/validate.py --stamp
python -m pytest sample_content/aif/Synthetic_NetworkEquipment -q
simready-validate --profile Package-Candidate --version 1.3.0 sample_content/aif/Synthetic_NetworkEquipment/asset/Synthetic_NetworkEquipment.usda
usdchecker --strict sample_content/aif/Synthetic_NetworkEquipment/asset/Synthetic_NetworkEquipment.usda
simready-evaluate --assets sample_content/aif/Synthetic_NetworkEquipment --features FET207_SimulationNetworkTopology.0-3-0 --plan-only
```

`--renderer Metal` selects the native Mac renderer when available.
`generate.py --output <directory>` generates a relocatable copy with its source
data and root declaration. Rendering-only cameras and lights live in
`dcc_source/preview.usda`, outside the equipment asset. The generator reads
its equipment property identities and types from
`standards/equipment-classes/aif-v0.3/network-equipment.csv`; sample values are
separate in `source.json`, and schema defaults remain empty.

Run `--stamp` after generation and rendering. It first verifies both complete
static profiles, then uses the maintained validator to record independent
`AIF-Entity@0.3.0` and `Networking@0.3.0` receipts in the interface USD's
`customLayerData.SimReady_Metadata.validation.profiles`. It refreshes
`validation.json` and `validation-networking.json` after stamping, so their
asset hashes describe the final USD, root metadata and thumbnail. Regeneration
replaces the interface and requires another `--stamp` run.

A regular `validate.py` run remains read-only for the USD and checks
`AIF-Entity@0.3.0`; `--profile Networking` checks `Networking@0.3.0`. Each writes
its corresponding summary with executed versus selected requirements, resolved
contracts, issues, package versions and asset SHA-256 hashes.

`asset/.metadata/com.nvidia.simready.root_usds.json` declares the equipment
interface as the package's only root. Evaluate discovers one switch from either
the sample directory or `asset/` and reads both static receipts. The command
above selects one device connectivity test. Omit `--features` to plan all six
tests across the two profiles. Both commands stop before execution.
`Package-Candidate@1.3.0` checks the switch's packaging, thumbnail and
provenance independently of the two AIF 0.3 profiles.

## License

Synthetic source data, USD layers and rendered images: CC BY 4.0, attributed to
NVIDIA CORPORATION & AFFILIATES. Generator and validation code: Apache-2.0.
