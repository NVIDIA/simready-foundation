# Temporary Asset Transformer patches

`isolated_620.py` patches `isaacsim-asset-isolated==6.2.0.1` at runtime while the
corresponding fixes are upstreamed. `apply.py` validates the exact distribution
version and the patched signatures before changing anything, then marks each
patched owner with `__simready_patch_version__`. Profile JSON continues to
reference the public `isaacsim.asset.transformer.rules.*` class names.

The 6.0.1 patches (geometry physics-material bindings, material MDL/UDIM
bundling, flatten documentation and `assetInfo:identifier` retargeting, and
joint-state token authoring) are upstream in 6.2 and were removed.

## Remaining fixes

- Geometry re-flatten (`GeometriesRoutingRule._make_references_non_instanceable`):
  the pre-pass re-flattens the working layer, which turns package-relative
  asset paths (the retargeted default-prim `assetInfo:identifier`) absolute and
  fails AA.001. The wrapper restores package-local paths as explicit relative
  paths and clears the flatten documentation.
- Variant routing (`variants.copy_file_to_directory`): `shutil.copy2` keeps a
  read-only source mode, so the rule fails re-saving the copied layers. The
  wrapper makes each copy owner-writable.
- Staged publish (`manager._publish_staged_package`): `relocate_asset` anchors
  every relative path, turning search-path assets such as the built-in
  `OmniPBR.mdl` into `./OmniPBR.mdl`, which resolves to nothing (NP.008). The
  copy keeps unbacked search paths bare; it is otherwise verbatim 6.2.0.1.

## Removing the patches

When these fixes are present in a published isolated wheel:

1. Bump the exact wheel versions in the tier-core `pyproject.toml`.
2. Run the transformer tests and the prop/robot transforms against the new
   wheel with patch application disabled.
3. Delete this directory and remove the patch invocation.
4. Keep the profile JSON unchanged.
