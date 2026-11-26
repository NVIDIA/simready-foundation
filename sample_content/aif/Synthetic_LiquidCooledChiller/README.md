# Synthetic liquid-cooled chiller

`SYN-WC-500` is a fictional 500 kW indoor water-cooled screw chiller for
the `Liquid-Cooled-Chiller@0.3.0` profile. Two compressors sit above a pair of
horizontal shell-and-tube heat exchangers on a common skid. The chilled-water
barrel has an insulation jacket. Each water circuit has two flanged connections,
and a control cabinet carries the single three-phase electrical inlet.

## Design references

- The Trane RTWD catalog shows the four water connections and electrical sections
  on pp. 44–45. Its mechanical specifications on p. 50 informed the two screw
  compressors and shell-and-tube exchangers. The RTWD family spans 80–250 US
  refrigeration tons (about 281–879 kW). [Trane RTWD product catalog, October 2025](https://elibrary.tranetechnologies.com/public/commercial-hvac/Literature/Product%20Catalog/RLC-PRC029P-EN_10312025.pdf)
- The Carrier 30XW/30XW-P product gallery informed the evaporator insulation,
  circular exchanger heads and flanged water connections. The family spans
  270–1,760 kW. [Carrier AquaForce 30XW/30XW-P](https://www.carrier.com/commercial/en/eu/products/air-conditioning/water-cooled-chillers/30xw-30xw-p/)

The fictional 500 kW design point falls within both published ranges. All geometry,
dimensions, materials, ratings and performance values were created for this example.
The asset identifies its manufacturer as `Synthetic` and its model as `SYN-WC-500`.

## Operating point

With both compressors operating, the evaporator removes 500 kW and the chiller
draws 90 kW, giving a cooling COP of 5.56. The condenser rejects their sum,
590 kW. Facility pumping is outside the modeled electrical boundary.

| Water circuit | CP2 system | Entering | Leaving | Design flow | Pressure drop |
| --- | --- | ---: | ---: | ---: | ---: |
| Evaporator | `FWS` | 11.98 °C (return) | 7.00 °C (supply) | 24 L/s | 35 kPa |
| Condenser | `equipment_cooling` | 30.00 °C (supply) | 35.04 °C (return) | 28 L/s | 42 kPa |

Both circuits use water. The two temperature changes follow `Q = ṁ cp ΔT` with
water density 1,000 kg/m³ and specific heat 4,180 J/(kg·K). The four physical
connection frames lie on the outer flange faces, with local +Z pointing outward.
The modeled pipes have a 150 mm bore and a 168.3 mm outside diameter. The 400 V,
50 Hz electrical inlet has a separate 145 kW real-power capacity.

## Performance data

The 108-point cooling map combines three evaporator flows, two evaporator
leaving temperatures, three condenser flows, three condenser entering
temperatures and two compressor stages. Compressor stage varies fastest.
At reference point 45 (zero-based), both compressors run. At the same water
conditions with one compressor running, the model supplies 55% of rated cooling.
Every normal operating point conserves energy across the chiller boundary.

Separate tables describe evaporator and condenser pressure drop and electrical
standby consumption. Water temperatures use kelvin in the performance maps and
degrees Celsius at the connection points. [source.json](source.json) records the
synthetic coefficients, flattening order, water properties and units. This sample
projects the [ASHRAE 205 RS0001 liquid chiller representation](https://data.ashrae.org/standard205/assets/schema/RS0001.schema.json)
into the AIF attribute sheet.

## Reproduce

From the repository root with OpenUSD and the Core and AIF validation packages
installed:

```sh
python sample_content/aif/Synthetic_LiquidCooledChiller/generate.py --render
usdchecker sample_content/aif/Synthetic_LiquidCooledChiller/asset/Synthetic_LiquidCooledChiller.usda
python sample_content/aif/Synthetic_LiquidCooledChiller/validate.py
```

The generator reads USD types, units and allowed values from the committed CSV.
The sample authors all 59 class attributes. A single `/world` Xform composes
relative geometry, properties and connection-point layers, with Z up and units
of meters and kilograms. Equipment dimensions come from the composed geometry
bounds. Mass is the sum of the modeled solids’ volumes times their assigned
material densities. It excludes working fluids and unmodeled internals.

`--render` uses `usdrecord` and Pillow to generate the preview and publishing
thumbnail. The camera, lights and ground are in `preview.usda`. `validate.py`
records requirement coverage, issues, package versions and asset hashes for
[AIF-Entity](validation.json) and [Liquid-Cooled-Chiller](validation-liquid-cooled-chiller.json), both at 0.3.0.

The asset is CC-BY 4.0, attributed to NVIDIA. The generator is Apache-2.0.
