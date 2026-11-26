# Liquid-cooled chiller

Set `aif:core:assetClass` to `LiquidCooledChiller` on the Properties sublayer's
default prim. The class defines 59 equipment fields, including 18 Required,
33 Conditional and 8 Optional. The condenser type is `LIQUID`.
[Attribute sheet](liquid-cooled-chiller.csv) · [Synthetic USD example](../../../sample_content/aif/Synthetic_LiquidCooledChiller/README.md)

## Cooling and pressure-drop maps

AM.011 requires 19 tabular arrays. The cooling axes, in order, are evaporator
liquid flow, evaporator leaving temperature, condenser liquid flow, condenser
entering temperature and compressor sequence rank. The last axis varies
fastest. The six cooling lookups are electrical input, net evaporator
capacity, net condenser capacity, oil-cooler heat, auxiliary heat and
operation state.

Author a standby map and a pressure-drop map for each liquid circuit. The
condenser pressure-drop axes are condenser liquid flow and entering
temperature, in that order. Every condenser differential-pressure value is
positive. Each pressure-drop map covers the corresponding cooling-map
envelope. Declared condenser flow limits lie within the condenser flow axis.

## Connection points

TC.004 checks positive net condenser and evaporator capacity. The evaporator
`FWS` supply carries cold leaving water. The condenser `equipment_cooling`
supply carries cold entering water and its return carries warmed leaving
water. On each circuit, the two port design temperatures must be finite and
the return must be warmer than the supply for positive duty.

Within each pair, design flows match. The two circuits may have different
flows and fluid properties. Check the condenser supply temperature against
the condenser entering-temperature envelope. Convert equipment flows from
m³/s to L/s for the ports. The nominal pipe outside diameter and the port
bore are separate dimensions. EL.006 checks the electrical feed against the
reference input power.
