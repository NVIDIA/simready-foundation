# Synthetic network equipment

A fictional 1U network switch for the AIF-Entity and Networking 0.3.0 profiles.
The asset carries eight OSFP fabric ports and one RJ45 management port using
the AIF 0.3 connection-point contract. Connections between equipment instances belong in an
assembled scene.

All identity, dimensions, port ratings, resource allocations and material
densities are synthetic. The mesh represents a simplified hollow enclosure,
connector cages and internal components; mass is the sum of their solid volumes
multiplied by the stated synthetic densities. These are illustrative values,
not manufacturer specifications, measured performance or manufacturing geometry.

The sample preserves the existing AIF dimension properties and their mm/kg
units. Dimensions use separate height, width and depth scalars. The packaging
provenance records `asset_extents` in meters as XYZ. `cpuAllocation`, `memory_MB`, `storage_GB` and `osImage` demonstrate the
proposed networking contract. CPU allocation units, permitted DSX Air allocation
ranges and image identifier formats still require owner review. The
`synthetic://network-os/1.0` image is a fictional opaque identifier; no image is
bundled or fetched. There is no DSX Air import, connectivity or runtime result.
Cable equipment classes are outside this sample.

## Reproduce

Use Python 3.12 with this checkout's Core/AIF tiers and `simready-validate`
installed. Generation needs OpenUSD; rendering additionally needs a working
`usdrecord` renderer and Pillow.

```sh
python sample_content/aif/Synthetic_NetworkEquipment/generate.py --render
python sample_content/aif/Synthetic_NetworkEquipment/validate.py
python sample_content/aif/Synthetic_NetworkEquipment/validate.py --profile Networking
python -m pytest sample_content/aif/Synthetic_NetworkEquipment/test_sample.py -q
usdchecker sample_content/aif/Synthetic_NetworkEquipment/asset/Synthetic_NetworkEquipment.usda
```

`--renderer Metal` selects the native Mac renderer when available.
`--output <directory>` generates a relocatable copy. Rendering-only cameras and
lights live in `preview.usda`, outside the equipment asset. The generator reads
its equipment property identities and types from
`standards/equipment-classes/aif-v0.3/network-equipment.csv`; sample values are
separate in `source.json`, and schema defaults remain empty.

`validate.py` defaults to `AIF-Entity@0.3.0` and preserves its report in
`validation.json`. `--profile Networking` evaluates the dedicated
`Networking@0.3.0` profile and writes `validation-networking.json`. Each report
records executed versus selected requirements, resolved contracts, issues,
package versions and asset SHA-256 hashes. Both evaluate the same authored
asset; their results remain independent. Networking selects
`FET207_SimulationNetworkTopology.0-3-0`; this script evaluates its static requirements
without executing its registered connectivity procedure. These reports contain
no DSX Air runtime or import result.

## License

Synthetic source data, USD layers and rendered images: CC BY 4.0, attributed to
NVIDIA CORPORATION & AFFILIATES. Generator and validation code: Apache-2.0.
