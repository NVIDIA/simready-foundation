# Universal Robots UR10 asset notices

The UR10 asset files in this directory and its subdirectories are third-party
robot material and are **not covered by this repository's Apache-2.0 license**.
The BSD-3-Clause notice in [LICENSE](LICENSE) applies to the UR10 asset tree,
including `cad/`, `urdf/`, `urdf_2/`, `mjcf/`, `simready_usd/`, and
`simready_isaac_usd/`. The same notice covers the `.dae`, `.mtl`, and `.urdf`
files, which do not carry individual license headers. UR10 is BSD-3-Clause,
not MIT.

The `urdf/` metadata identifies the [ROS-Industrial Universal Robot
description](https://github.com/ros-industrial/universal_robot/tree/6507bb6756d0065d49b76230ff55f875f099a827/ur_description)
as its source. The `mjcf/` model was derived from the Universal Robots URDF;
its original [license](mjcf/LICENSE) and [source notes](mjcf/README.md) are
retained. The `cad/` metadata identifies Universal Robots A/S as supplier and
TraceParts as the CAD file source. Those upstream identities are preserved;
the BSD notice does not grant rights to their names or trademarks.
