# network-device-eligibility

| Code | NET.004 |
|---|---|
| Validator | {oav-validator-latest-link}`net-004` |
| Compatibility | {compatibility}`AIF` |
| Tags | {tag}`essential` |

## Summary

The Properties sublayer's default prim and the composed stage's default prim must
both author `aif:core:assetClass` as a USD `string` whose value is exactly
`network-equipment`. Missing, empty, mistyped or different values fail.

## Why is it required?

The dedicated `Networking@0.3.0` profile applies to network devices. An equipment
class that skips the class-conditional network checks cannot satisfy this profile.
NET.004 is unconditional when selected through FET207_SimulationNetworkTopology.0-3-0.
AIF-Entity does not select that feature, so it retains its broader equipment-class scope.

## How to comply

Author the network-equipment class in the Properties layer and preserve it in
the composed asset. Validate with `Networking@0.3.0`; NET.001–NET.003 separately
check identity values, physical metadata, node configuration and CP2 network ports.
