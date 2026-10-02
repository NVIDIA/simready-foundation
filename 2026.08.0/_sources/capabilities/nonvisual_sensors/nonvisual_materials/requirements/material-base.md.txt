# material-base

| Code     | NVM.002 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`nvm-002` |
| Compatibility | {compatibility}`rtx` |
| Tags     | {tag}`correctness` |


## Summary

Materials must specify a base material type

## Description

Materials bound to geometry prims with computed purpose "render" or "default" must have a non-visual material base property assigned to specify the base material type for non-visual sensor simulation.

## Why is it required?

- Non-visual sensor simulation requires material properties. Material properties can be highly non-linear as a function of wavelength and therefore cannot be simply extrapolated from a visual material. The requirement for sensor simulation to have non-visual properties addresses these non-linearities.
- Different materials have different sensor responses. This includes spectrally dependent electromagnetic and acoustic properties along with structural properties to define the non visual material behavior.
- Base material type determines core sensor interaction behavior as a function of wavelength.

## Examples

```usd
# Invalid: No base material type specified
def Material "BadMaterial" (
    prepend apiSchemas = ["MaterialBindingAPI"]
)
{
    token omni:simready:nonvisual:coating = "clearcoat"
}

# Valid: Base material type specified
def Material "GoodMaterial" (
    prepend apiSchemas = ["MaterialBindingAPI"]
)
{
    token omni:simready:nonvisual:base = "aluminum"
    token omni:simready:nonvisual:coating = "clearcoat"
}
```

## How to comply

- Set omni:simready:nonvisual:base on materials
- Use valid base material types:
  - Metals: aluminum, steel, oxidized_steel, iron, oxidized_iron, silver, brass, bronze, oxidized_Bronze_Patina, tin
  - Polymers: plastic, fiberglass, carbon_fiber, vinyl, plexiglass, pvc, nylon, polyester
  - Glass: clear_glass, frosted_glass, one_way_mirror, mirror, ceramic_glass
  - Other: asphalt, concrete, leaf_grass, dead_leaf_grass, rubber, wood, bark, cardboard, paper, fabric, skin, fur_hair, leather, marble, brick, stone, gravel, dirt, mud, water, salt_water, snow, ice, calibration_lambertian
