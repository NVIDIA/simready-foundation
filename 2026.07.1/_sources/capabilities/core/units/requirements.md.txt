# Requirements

## Summary

- **An Asset must specify its units (e.g. linear units, mass units, time units, colorspaces)**
- **When composing assets with different units, corrective transformations need to be applied**

## Granularity

Every USD asset **must** have its scale (in meters per unit), mass (in kilograms per unit) and time sampled mapping encoded within it. This information is vital to the successful composition of multiple USD files that are built at different scales. This capability also provides a consistent baseline for physics simulations and accurate time-sampled animation playback.

For more detailed information on Units, please see the [**Units in USD**](https://docs.omniverse.nvidia.com/usd/latest/learn-openusd/independent/units.html) section of the Omniverse documentation.

## Schema / OpenUSD Specification

<!-- SCORE_TAG:LINK_TO_SCHEMA_DOCS:CORE -->
- [Encoding Stage Linear Units](https://openusd.org/dev/api/group___usd_geom_linear_units__group.html)
- [USD Physics Metrics](https://openusd.org/dev/api/usd_physics_2metrics_8h.html#details)
- [USD Timecode](https://openusd.org/dev/api/class_usd_time_code.html)
- [USD Colorspace](https://openusd.org/dev/api/class_usd_color_space_a_p_i.html)

### USDA Sample

```python
#usda 1.0
(
    metersPerUnit = 1
    upAxis = "Z"
    kilogramsPerUnit = 1
    startTimeCode = 0
    endTimeCode = 100
    timeCodesPerSecond = 24
)

```

## Requirements Table
<!-- SCORE_TAG:LIST_OF_REQUIREMENTS -->

<!-- UNITS_REQUIREMENTS_LIST_START -->

<!-- REQUIREMENTS_LIST -->

```{requirements-table}
```


<!-- UNITS_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/meters-per-unit
requirements/kilograms-per-unit
requirements/timecodes-per-second
requirements/corrective-transforms
requirements/upaxis
requirements/upaxis-z
requirements/meters-per-unit-1
```
