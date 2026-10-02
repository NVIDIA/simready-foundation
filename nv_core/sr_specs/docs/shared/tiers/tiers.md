# Tiers

A SimReady Foundation tier is a separately publishable Python package that owns
a coherent catalog of requirements, capabilities, features, profiles, and
validation rules. A tier can also bundle runtime tests. Installed tiers are
discovered through Python entry points, allowing downstream or
organization-specific tiers to extend Foundation content without modifying an
upstream package.

The Foundation currently ships three tiers:

| Tier | Python package | Purpose |
| --- | --- | --- |
| [Core](core.md) | `simready-foundation-tier-core` | The baseline SimReady contracts and validators for OpenUSD content, visualization, physics, robotics, semantics, packaging, and supported runtime variants. |
| [AIF](aif.md) | `simready-foundation-tier-aif` | The AI Factory equipment contracts: class metadata and connection points for CDU, CRAH, UPS and compute-rack assets. Depends on Core. |
| [Sensors](sensors.md) | `simready-foundation-tier-sensors` | Physics sensor, RTX LiDAR, and camera/render-product contracts: IMU, joint, camera, and LiDAR sensor profiles. |

See the [SimReady Foundation PyPI Packages](../guides/foundation_pypi.md) guide
for installation, discovery, validation, and downstream tier authoring.

```{toctree}
:maxdepth: 1

Core <core>
AIF <aif>
Sensors <sensors>
```
