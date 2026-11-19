# Non-Visual Sensor Material Attributes

## Overview

This capability provides requirements for material attributes that enable accurate non-visual sensor simulation (such as radar, lidar, thermal imaging). These attributes define material properties that affect sensor response but are not visible to the human eye.

```{note}
This capability is only applicable to NVIDIA Omniverse RTX.
```

## Summary

- **All geometry prims with computed purpose "render" or "default" must have non-visual material properties assigned through bound materials**
- **Non-visual material properties must be consistent with visual material properties**
- **Non-visual material properties cannot be time-varying**

## Granularity

**Non-visual sensor attributes must exist on all visual material prims applied to a 3D asset**, including all three predefined metadata properties based on the material substrate (e.g., metal, glass, rubber).

```{important}
There are a defined number of valid, measured values that can be applied to the base, coating and attributes properties. They can be found in this [**table**](nonvisual_attributes_table.md).
```

## USDA Sample

Below is an example of how non-visual sensor attributes are authored on a material prim:

```python
def Material "Aluminum" (
    prepend apiSchemas = ["MaterialBindingAPI"]
)
{
    token omni:simready:nonvisual:base = "aluminum"
    token omni:simready:nonvisual:coating = "paint"
    token[] omni:simready:nonvisual:attributes = ["none"]
}

def Mesh "AluminumSurface" (
    apiSchemas = ["MaterialBindingAPI"]
)
{
    rel material:binding:full = </World/Looks/Aluminum>
}
```

## Requirements

<!-- NONVISUAL_MATERIALS_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- NONVISUAL_MATERIALS_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements
nonvisual_attributes_table
requirements/material-base
requirements/material-coating
requirements/material-attributes
requirements/material-time
requirements/material-binding
requirements/material-consistency
```
