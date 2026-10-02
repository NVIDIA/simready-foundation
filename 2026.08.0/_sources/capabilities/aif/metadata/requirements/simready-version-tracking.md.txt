# simready-version-tracking

| Code     | AM.005 |
|----------|--------|
| Validator| {oav-validator-latest-link}`am-005` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

The default prim must have an `aif:core:simreadyVersion` attribute recording the SimReady specification version the asset was created against.

## Description

`aif:core:simreadyVersion` records which version of the SimReady AIF specification was used when the asset was authored. This enables downstream tools to determine compatibility and apply the correct validation rules.

The `AIF-Entity` profile defines two versions, `0.1.0` and `0.2.0`. They differ in the
Connection Points feature (`FET201_AIF`) and are mutually exclusive: CP.004 requires
the `<vendor>_<type>_<suffix>` naming a v0.2.0 asset does not use, and CP.010 requires an
Xform where a v0.1.0 asset has a Plane or Disk mesh.

## Why is it required?

- Provides forward/backward compatibility information for asset consumers
- Enables tooling to detect assets created against older spec versions
- Required for asset library versioning and migration tracking

## Examples

An asset conforming to `AIF-Entity` 0.1.0:

```usda
def Xform "Generic_CRAH" {
    string aif:core:simreadyVersion = "0.1.0"
}
```

An asset conforming to `AIF-Entity` 0.2.0:

```usda
def Xform "Generic_CRAH" {
    string aif:core:simreadyVersion = "0.2.0"
}
```

## How to comply

Set `aif:core:simreadyVersion` to the `AIF-Entity` profile version the asset conforms to. An
asset authored to the v0.1.0 connection point vocabulary sets `"0.1.0"`; one authored to the
v0.2.0 property vocabulary sets `"0.2.0"`. The value names the profile version, not the
SimReady Foundation release the asset shipped in.

## Related requirements

- AM.001 `properties-sublayer-required`: the properties sublayer must exist before this attribute can be set
- AM.002 `asset-class-required`: required alongside version tracking for full asset characterization

## For More Information

- [Semantic Versioning](https://semver.org/)
