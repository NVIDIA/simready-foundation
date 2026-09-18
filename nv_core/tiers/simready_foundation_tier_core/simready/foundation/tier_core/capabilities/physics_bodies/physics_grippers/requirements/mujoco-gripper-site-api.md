# MuJoCo Gripper Site API

| Code     | MUJOCO.GR.001 |
|----------|---------------|
| Validator| MuJoCoGripperSiteAPI |
| Compatibility | {compatibility}`MuJoCo` |
| Tags     | {tag}`essential` |

## Summary

MuJoCo gripper site prims must apply `MjcSiteAPI`.

## Description

The official MuJoCo USD schema defines `MjcSiteAPI` for MuJoCo site metadata. When a SimReady gripper site is intended for MuJoCo runtime workflows, the site prim must keep the Standard gripper-site data and also apply `MjcSiteAPI`.

When `mjc:group` is authored on the site, it must be a non-negative integer.

## Why is it required?

* Allows MuJoCo tooling to discover the authored gripper site as a MuJoCo site.
* Keeps MuJoCo site metadata on the same prim as the SimReady gripper-site contract.
* Avoids adding broader MuJoCo site requirements beyond what the schema currently exposes.

## Examples

```usd
def Xform "gripper_01" (
    prepend apiSchemas = ["MjcSiteAPI"]
)
{
    string simready:attachment:socketType = "Gripper"
    int mjc:group = 0
}
```

## How to comply

* Preserve the Standard gripper-site requirements.
* Apply `MjcSiteAPI` to each gripper site prim used by MuJoCo.
* Keep authored `mjc:group` values non-negative integers.

## Related requirements

- [gripper-socket-type](gripper-socket-type.md)
- [gripper-forward-axis](gripper-forward-axis.md)
- [gripper-grip-line](gripper-grip-line.md)
- [gripper-max-opening](gripper-max-opening.md)

## For More Information

* [MuJoCo OpenUSD mjcPhysics schema](https://github.com/google-deepmind/mujoco/blob/main/doc/OpenUSD/mjcPhysics.rst)
* [MuJoCo mjcPhysics schema.usda](https://github.com/google-deepmind/mujoco/blob/main/src/experimental/usd/mjcPhysics/schema.usda)
