# equipment-class-template-compliance-0.3

| Code | AM.008 |
|---|---|
| Validator | {oav-validator-latest-link}`am-008` |
| Compatibility | {compatibility}`AIF` |
| Tags | {tag}`essential` |

## Summary

The default prim's equipment class must resolve in the AIF 0.3 catalog.
Authored common equipment metadata must use the specified USD attribute types.

## Description

CDU, CRAH, UPS and Compute Rack use the class templates defined by AM.007.
A missing, empty or unknown class is a failure. A missing attribute from a legacy
class template produces a warning. AM.001 requires the Properties layer.

AM.008 checks attribute declarations on the Properties sublayer's default prim and
on the composed stage's default prim. An attribute with a different USD type or a
relationship with the same name is a failure for every equipment class.

| Namespace | Attributes | USD type |
|---|---|---|
| `aif:core:` | `assetClass`, `manufacturer`, `modelNumber`, `assetVersion`, `simreadyVersion`, `assetDescription`, `connectsToModelDocumentation` | `string` |
| `aif:core:` | `height`, `width`, `depth`, `weight`, `installationClearance`, `accessibilityRequirement` | `float` |

For an installed chiller class, the Properties layer and the composed default
prim must identify the same class. The versioned schema specifies the required
equipment attributes, their USD types, units and allowed values. Violating the
chiller schema fails AM.008. The dedicated equipment profile selects the
performance-map, thermal and electrical checks for that chiller.

## Why is it required?

Equipment consumers read these properties through their declared USD types.
Checking the composed prim also catches stronger opinions that change a property type.

## How to comply

Author the class and its template properties on the Properties sublayer's
default prim. Use the USD types listed above for common equipment metadata.

## Related requirements

- [AM.009](physical-dimensions-metadata-0.3.md) defines the physical dimension requirements for 0.3.
- AM.007 defines the equipment template checks for AIF 0.1 and 0.2.
