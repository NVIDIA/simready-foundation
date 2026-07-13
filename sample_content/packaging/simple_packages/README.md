# Simple sample packages

These five subfolders are pre-built SimReady-Foundation-conformant
packages used as fixtures by the `package_sample` integration tests
under `nv_core/package_sample/tests/`. Each subfolder is a
self-contained package directory: pointing
`create_simready_package.py --only-post-validation --package-def
<subfolder>/com.nvidia.simready.packaging.json` at one will run the
`Package` profile against it.

Regenerate them deterministically from
`nv_core/package_sample/create_sample_packages.py` after editing the
underlying canonical assets in
`sample_content/common_assets/props_general/`.

| Folder | USDs? | Has BOM? | `metadata[]` entries | What it demonstrates |
|---|---|---|---|---|
| `apple_a01_materials/` | no | yes | `bom` | Materials/textures-only deliverable: no USD content, just `materials/` and `textures/`. Exercises the materials-only path; `bom`-only `metadata[]` matches what a build *without* `--embed-prevalidation` produces. |
| `apple_a01_nobom/` | yes (`apple_a01/simready_usd/sm_apple_a01_01.usd`) | **no** | (none) | Minimal-viable package definition: `format_version`, `package_id`, `license` only. No BOM, no `content_hash`. Matches the output of the `--no-wrapp` lightweight backend. **Naming caveat:** `nobom` refers to the package *definition* having no BOM reference, **not** to the absence of USD content — there *is* a USD here. |
| `apple_a01_usd_bom/` | yes | yes | `bom` + Package-Candidate conformance + root_usds | Full happy-path WRAPP build with `--embed-prevalidation`. The "reference" good package: `content_hash` + `package_hash` (sha256 only) covers BOM and conformance. |
| `apple_a01_usd_bom_multi_hash/` | yes | yes | same as `apple_a01_usd_bom/`, but multi-hash | Same content as `apple_a01_usd_bom/` but every hash carries both `sha256` and `blake3`, exercising the multi-hash code paths in `_bom.py` and `wrapp_compat`. |
| `fruit_f01_multi_usd/` | yes (apple + orange) | yes | `bom` + Package-Candidate conformance + root_usds | Multi-root-USD package containing both `apple_a01/` and `orange_a01/` trees. Exercises root-USD discovery and validation across multiple entry points. |

## Thumbnails

The `Package-Candidate` profile requires SR.002-compliant thumbnails
at `.thumbs/256x256/<filename>.usd.png` next to each root USD.  The
canonical assets in `common_assets/` use a legacy thumbnail convention;
`create_sample_packages.py` copies the legacy thumbnails into the new
location during the build (see `_ensure_thumbnails`).  When no legacy
thumbnail is available a minimal PNG placeholder is written.

## Mapping to the test suite

`nv_core/package_sample/tests/test_sample_packages.py` runs the
`Package` profile against each of these and asserts the expected
pass/fail shape:

- `apple_a01_materials/`, `apple_a01_usd_bom/`,
  `apple_a01_usd_bom_multi_hash/`, `fruit_f01_multi_usd/` —
  every feature must pass.
- `apple_a01_nobom/` — `FET030_PACKAGING_CORE` passes, but
  `FET032_PACKAGING_INTROSPECTION` fails (no BOM to introspect).
  This is the canonical "partial failure" fixture.
