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

The current AIF SimReady specification iteration is `v0.1.0`.

## Why is it required?

- Provides forward/backward compatibility information for asset consumers
- Enables tooling to detect assets created against older spec versions
- Required for asset library versioning and migration tracking

## Examples

```usda
def Xform "CW375" {
    string aif:core:simreadyVersion = "0.1.0"
}
```

## How to comply

Set `aif:core:simreadyVersion` to the semantic version string of the SimReady AIF specification the asset targets. For this `v0.1.0` iteration, set the value to `"0.1.0"`.

## Related requirements

- AM.001 `properties-sublayer-required`: the properties sublayer must exist before this attribute can be set
- AM.002 `asset-class-required`: required alongside version tracking for full asset characterization

## For More Information

- [Semantic Versioning](https://semver.org/)
