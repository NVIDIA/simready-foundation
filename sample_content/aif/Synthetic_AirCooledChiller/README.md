# Synthetic air-cooled chiller

This vendor-neutral, fictional equipment package illustrates the AIF v0.3
air-cooled chiller class. Its geometry, materials, performance tables, ratings,
controller and interfaces are invented. They are not OEM data, measurements,
manufacturing instructions or evidence of commercial simulator accuracy.

The asset is CC-BY 4.0, attributed to NVIDIA. The generator is Apache-2.0.

## Reproduce

From the repository root, using an OpenUSD Python environment:

```sh
python sample_content/aif/Synthetic_AirCooledChiller/generate.py
usdchecker sample_content/aif/Synthetic_AirCooledChiller/asset/Synthetic_AirCooledChiller.usda
python sample_content/aif/Synthetic_AirCooledChiller/generate.py --render
simready-validate --project-config sample_content/project_config.toml \
  --profile Air-Cooled-Chiller --version 0.3.0 \
  sample_content/aif/Synthetic_AirCooledChiller/asset/Synthetic_AirCooledChiller.usda
python sample_content/aif/Synthetic_AirCooledChiller/validate.py
```

`source.json` contains every fictional chiller value and the material densities.
The generator derives the attribute inventory, USD types, units and enumerations
from the committed class CSV. Unknown field names, missing required fields,
and missing arrays for a tabular model fail generation. Optional fields with
no source value are omitted from the USD.

Rendering requires `usdrecord` with an available Hydra renderer and Pillow.
Pass `--renderer Metal` on a Metal-enabled host when needed. The render option
records the presentation USD, composites its transparent background onto white,
and generates `preview.png` plus the 256-pixel publishing thumbnail from those
rendered pixels. Cameras, lights and ground remain outside the equipment asset.

`validate.py` runs both installed v0.3 profiles and records their results separately.
[AIF-Entity](validation.json) checks the shared equipment contract and the declared
class template. [Air-Cooled-Chiller](validation-air-cooled-chiller.json) checks the
chiller's tabular performance, evaporator connections and AC inlet. Each report
records the executed and selected requirement counts, issues, package versions and
hashes of the asset files.

## Package

The entry stage has one identity `/world` Xform, Z up, meters and kilograms.
Geometry, Properties and ConnectionPoints are relative sublayers. The Properties
layer illustrates all 58 chiller attributes and the 16 inherited Common fields.
The separate presentation stage references the asset and adds its camera,
lighting and ground.

The packaged outdoor unit has opaque finned condenser banks on both long sides,
four identical electronically commutated (EC) axial fans seated in a continuous
deck with open airflow passages, and an
enclosed lower service bay containing two compressor shells. The control cabinet,
access panels, skid, and connected evaporator headers form one assembled unit.

Equipment mass is the sum of each authored component's geometric volume times
its declared density. Condenser cores use an explicit fictional bulk density
for the porous fin-and-tube assembly; metal parts use their material densities.
The derived total is authored as native USD mass, the Common weight, and
provenance mass. Dimensions come from the composed geometry's aligned bounds.
The geometric mass estimate covers the modeled solids. The separate refrigerant
charge rating gives 8.0 kg for Circuit 1 and 7.5 kg for Circuit 2, in the
order listed in `source.json`.

The two evaporator interfaces lie on the outer faces of the authored flanges.
The electrical inlet lies on the enclosure's inlet plate. Their rigid local +Z
axes face outward. CP2 uses FWS supply/return and power input. Thermal flow is
4 L/s at the authored CP2 operating point, within the cooling map’s
0.004–0.006 m³/s flow range, with a 6 L/s maximum. The pipe's 100 mm internal bore is separate from its 114.3 mm outside
diameter. The electrical connection's 45 kW capacity is separate from the
25 kW reference input.

## Model conventions

The cooling map is a Cartesian product, ordered evaporator flow, evaporator
leaving temperature, condenser entering temperature, relative humidity, ambient
pressure, compressor sequence; the last axis varies fastest.
`aif:spec:referenceCoolingMapPointIndex` selects index 0 for this unit's
100 kW cooling, 25 kW input and 125 kW condenser heat rejection ratings.
The fan bank has a rated maximum shaft speed of 15 revolutions per second
(900 rpm) and a rated motor efficiency of 0.90. Whole-unit input power in
the cooling map already includes fan power.
All points are NORMAL; oil-cooler and auxiliary heat are zero. Standby and
evaporator pressure-drop tables are separate. `source.json` records the exact
algebraic construction and selected physical boundaries.

The WATER mass fraction is 1.0 for the declared water component. This AIF
projection is not a complete ASHRAE-205 LiquidMixture object. Performance-map
temperature axes use Kelvin; the CP2 operating temperatures use Celsius. IPLV, NPLV and
acoustic values are illustrative ratings with stated conventions in the source;
they are not inputs to the invented cooling-map formula or certified test data.

The non-tabular conditional fields illustrate this chosen configuration. Their
presence here does not settle general schema applicability or create defaults.
