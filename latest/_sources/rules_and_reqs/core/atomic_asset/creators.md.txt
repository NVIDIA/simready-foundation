# Creators

<!-- SCORE_TAG:DCC_EXPORT -->
## Blender

To comply with this capability when creating USD files from Blender:

1. Use only supported file formats:
   - For textures: PNG, JPEG, EXR
   - For audio: M4A, MP3, or WAV

2. When exporting USD, ensure all asset references use relative paths (starting with "./" or "../")

3. Optionally, use the usdz file extension to create a USD archive.

## Omniverse

To comply with this capability when creating USD files from Omniverse:

1. Use only supported file formats:
   - For textures: PNG, JPEG, EXR
   - For audio: M4A, MP3, or WAV

2. When packaging USD assets, ensure all asset references use relative paths (starting with "./" or "../")
  
   This can be done by:
   
   - Manually ensuring to only use relative paths
   - Use the ["Collect" extension](https://docs.omniverse.nvidia.com/extensions/latest/ext_collect.html) to localize assets
   - Use the ["USD Paths" extension](https://docs.omniverse.nvidia.com/extensions/latest/ext_usd-paths.html) to ensure all paths are compliant


## UsdZip (Command Line Tool)

1. Install or build OpenUSD

2. Use the usdz file extension to create a USD archive.

   ```bash
   usdzip scene.usda scene.usdz
   ```
   
   Formore information, see [USDZip Documentation](https://openusd.org/release/toolset.html#usdzip)

