# Thumbnail Exist

| Code     | SR.002 |
|----------|--------|
| Validator| {oav-validator-latest-link}`sr-002` |
| Compatibility | {compatibility}`core-packaging` |
| Tags     | {tag}`essential` |

## Summary

The SimReady asset file should contain a thumbnail that is representative of the asset.

## Description

SimReady packaged assets should provide a thumbnail image next to the asset file so browsers, registries, and review tools can present a recognizable preview before the asset is opened.

## Example

For a SimReady asset located at `Assets/Manufacturer/Asset_Name/Asset.usd`, the thumbnail should be at `Assets/Manufacturer/Asset_Name/.thumbs/256x256/Asset.usd.png`.

## Why is it required?

- Enables package consumers to identify assets before opening them
- Supports registry, browser, and review workflows that depend on visual previews
- Provides a lightweight preview without loading the full OpenUSD stage

## How to comply

- Add a PNG thumbnail under `.thumbs/256x256/` next to the asset file
- Name the thumbnail after the asset file with `.png` appended, for example `Asset.usd.png`
- Ensure the thumbnail is representative of the asset's visible content
