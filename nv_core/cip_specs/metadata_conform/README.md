# simready-metadata-conform

Standalone distribution of the deterministic SimReady metadata conformance
pipeline. It conforms a package to `CAP031_SelfContainedPackage.0-1-0` (`AA.001`) and
`CAP033_SimReadyPackage.0-3-0` (`SR.002`, `SR.003`).

The package depends only on `pxr` for stage mutation. It requires no Omniverse
Kit runtime, no `omni.cip`, no repository checkout, and no validator install.

## What it does

For one package, in order:

1. Digest every authored geometry and physics opinion, as a safety baseline.
2. Repair unanchored or absolute authored asset paths that resolve to exactly
   one package-local file (`AA.001`). Covers sublayers, references, payloads,
   and ordinary asset-valued attributes such as texture inputs. MDL
   `info:mdl:sourceAsset` module references are left alone, because a matching
   basename does not prove the module's import closure resolves.
3. Derive the physical fields from the stage: `rigid_body_count`,
   `asset_extents` (meters), `mass` (kilograms), and an authored Wikidata
   `qcode`.
4. Resolve the remaining provenance strings from the caller's request, existing
   nested metadata, promoted top-level `customLayerData`, then a package
   sidecar JSON file.
5. Stamp the merged result into the root layer's `customLayerData` under
   `SimReady_Metadata` (`SR.003`).
6. Normalize the thumbnail to `.thumbs/256x256/<asset filename>.png` (`SR.002`).
7. Re-digest and reject the run if geometry or physics changed.

`rigid_body_count`, `asset_extents`, and `mass` are derived from the asset being
conformed and nothing else. A caller that supplies them gets a
`PHYSICAL_VALUE_REJECTED` blocker rather than a pass, and an asset that carries
no evidence for them gets `PHYSICAL_EVIDENCE_MISSING`. Nothing here fabricates a
mass, an extent, or a thumbnail.

## Install

```bash
pip install simready-metadata-conform
```

For a source checkout:

```bash
cd nv_core/cip_specs/metadata_conform
python -m pip install -e ".[usd,test]"
```

## Python API

```python
from simready.metadata_conform import run_metadata_conform

result = run_metadata_conform(
    "C:/assets/sm_prop_01/staging/sm_prop_01.usda",
    "C:/assets/sm_prop_01/simready_usd",
    metadata={
        "author": "Asset Team",
        "asset_name": "sm_prop_01",
        "asset_type": "prop",
        "asset_license": "Apache-2.0",
        "category": "prop",
        "source_file": "sm_prop_01.blend",
        "usd_date_generated": "2026-09-01",
        "qcode": "Q42177",
    },
    thumbnail_source="C:/assets/sm_prop_01/thumbs/sm_prop_01.usd.png",
    replace_existing=True,
    report_path="C:/assets/sm_prop_01/.diagnostics/metadata_report.json",
    diagnostics_dir="C:/assets/sm_prop_01/.diagnostics",
)
if not result.ok:
    for error in result.errors:
        print(error.stage, error.code, error.detail)
```

The source package is never modified. Work happens in a staging directory next
to the destination; the destination is replaced only after the whole pipeline
succeeds, and a pre-existing destination is restored if promotion fails.

`conform_package()` is the in-place variant for a caller that already owns a
writable copy and does its own promotion.

## Thumbnails

`thumbnail_source` names the PNG explicitly, which is what a host application
should do when it already knows which image is the thumbnail. Without it, valid
package-local PNGs are ranked and a unique winner is copied to the exact
`SR.002` target. Ties are broken in favor of a candidate already inside
`256x256`; a remaining tie is an `THUMBNAIL_AMBIGUOUS` blocker rather than a
guess. Neither path renders an image or writes a placeholder.

## JSON sidecar

Host applications that cannot import USD in-process (for example the SimReady
Blender add-on running on Blender's Python 3.13) invoke the one-shot sidecar in
a Python 3.11 interpreter. It reads one JSON request on stdin and writes one
JSON response on stdout; diagnostics go to stderr.

```bash
echo '{"protocol_version": 1, "op": "metadata_conform", "source_usd": "staging/sm_prop_01.usda", "output_folder": "simready_usd", "metadata": {"author": "Asset Team"}, "replace_existing": true}' | simready-metadata-sidecar
```

`{"op": "ping"}` reports the protocol version, package version, and interpreter
version without touching any asset.

Exit codes: `0` success, `1` conformance failure, `2` malformed or unsupported
request.

## CLI

```bash
simready-metadata-conform source.usda out_folder \
    --author "Asset Team" --asset-license Apache-2.0 \
    --category prop --source-file sm_prop_01.blend \
    --usd-date-generated 2026-09-01
```

Add `--validate-profile Package-Candidate --validate-version 1.2.0` to report an
end-state profile gate. That needs the `validate` extra and does not change the
conformance result.

## Offline wheelhouse

This package ships to host applications inside the shared SimReady wheelhouse
built by the sibling multiphysics distribution, which bundles both sidecars in
one manifest:

```bash
cd ../multiphysics_upgrade
python tools/build_wheelhouse.py --output _build/wheelhouse
python tools/verify_wheelhouse.py _build/wheelhouse
python tools/wheelhouse_smoke_test.py _build/wheelhouse
```

Bumping `PROTOCOL_VERSION` in `protocol.py` requires the matching bump in the
Blender add-on's `metadata/runtime.py`.

## Tests

```bash
python -m pytest tests -q
```
