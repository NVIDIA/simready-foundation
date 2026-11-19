# compression-type-valid

| Code     | RP.005 |
|----------|--------|
| Tags     | {tag}`correctness` |

## Summary

The `srtx:compression:type` attribute on a `RenderVar` prim, if present, must be one of the four supported codec values: `hevc`, `h264`, `av1`, or `blosc`.

## Description

The RTX Sensor API recognises exactly four compression codecs for render var output. The `srtx:compression:type` attribute is optional — if absent, no compression is applied. When it is authored, the value must be one of the four recognised names. An unrecognised value (e.g. `"h265"`, `"avc"`, a typo) will silently produce no output at runtime because the encoder cannot be initialised.

The allowed values and their intended use:

| Value | Intended for |
| :---- | :---- |
| `hevc` | Video-like outputs (`LdrColor`, `HdrColor`) |
| `h264` | Video-like outputs (`LdrColor`, `HdrColor`) |
| `av1` | Video-like outputs (`LdrColor`, `HdrColor`) |
| `blosc` | Non-visual / high-bit-depth data (`GenericModelOutput`, `HdrColor`, `DepthLinearSD`, semantic AOVs) |

## Why is it required?

An invalid codec name is silently ignored by the runtime — no error is raised, but no compressed output is produced. Catching invalid values statically prevents silent data loss in synthetic data generation pipelines.

## Examples

```usd
# Valid: recognised codec
def RenderVar "LdrColor"
{
    uniform string sourceName = "LdrColor"
    uniform string srtx:compression:type = "hevc"
}

# Invalid: unrecognised codec name
def RenderVar "LdrColor"
{
    uniform string sourceName = "LdrColor"
    uniform string srtx:compression:type = "h265"
}
```

## How to comply

Set `srtx:compression:type` to one of `hevc`, `h264`, `av1`, or `blosc`. If compression is not needed, omit the attribute entirely rather than setting an empty or invalid value.
