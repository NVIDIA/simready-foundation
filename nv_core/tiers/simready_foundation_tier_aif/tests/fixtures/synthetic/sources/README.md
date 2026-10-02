# Synthetic CRAH and UPS geometry

The geometry is remodeled from `cracunit_01` and `ups_cabinet_01` in the
in-house AIF exemplar collection, archive `AIF_Assets-20260920T235018Z-1-001`.
Jens Jebens confirmed on 2026-09-21 that these were modeled in-house as
exemplars under a former coworker's guidance. This attribution is based on
that confirmation; the archive's reference notes are blank.

`remodel_geometry.py` replaces each source component mesh with its local
bounding box, then bakes its transform. This follows the component-box detail
used for Generic_CDU and gb300. CAD topology, materials and source prim names
are omitted. No external material or geometry dependencies remain.

The assemblies are converted to Z-up meters, centered on X/Y, grounded at
Z=0, and fitted to the existing fictional fixture dimensions read from the
JSON value sources. Dimensions and engineering properties are fixture data,
not specifications inferred from the exemplar models. The CRAC-named model
supplies only the visual assembly for the CRAH fixture; it does not establish
the fixture's cooling technology. Connection-point layers remain unchanged.

With a USD Python runtime and the extracted in-house files, rebuild geometry:

```sh
python remodel_geometry.py /path/to/cracunit_01/model/usd/cracunit_01.usd /path/to/ups_cabinet_01/model/usd/ups_cabinet_01.usd .
```

Run that command from the `synthetic` directory. The resulting
geometry layers are committed, so `build_synthetic_fixtures.py` can regenerate
metadata without access to the original exemplars. The original CAD files are
not part of this repository. The existing asset-license field is unchanged;
the provenance confirmation does not establish a new licensing assertion.

Source USD SHA-256 checksums:

- `cracunit_01.usd`: `c2c1efae6d46c90573063ec50d26c42470e7f47741d54906147a4f9df90e8d96`
- `ups_cabinet_01.usd`: `24cc42de1a682d144d91ad0c96a02aa64648fe4006765643563ebc14c465b820`
