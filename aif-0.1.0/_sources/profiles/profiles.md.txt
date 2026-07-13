# Asset Profiles

Asset profiles bundle capabilities, so that assets can be reasoned about and validated for conformance with lists of capability requirements. Asset profiles can serve as a contract between creators and consumers of assets.

Feature requirements and dependency chains are defined in the [feature dependency graph](../features/feature-dependency-graph). Profile feature sets below align with `profiles.toml` and those specifications.

(profile-comparison)=
## Profile comparison

| Profile | Versions | Summary | Feature set (from `profiles.toml`) |
| --- | --- | --- | --- |
| Prop-Robotics-Neutral | 1.0.0, 2.0.0 | Neutral format props for robotics | FET000_CORE, FET001_BASE_NEUTRAL, FET003_BASE_NEUTRAL, FET004_BASE_NEUTRAL, FET005_BASE_NEUTRAL, FET006_BASE_MDL |
| Prop-Robotics-Physx | 1.0.0, 2.0.0 | PhysX props for robotics | FET000_CORE, FET001_BASE_NEUTRAL, FET003_BASE_PHYSX, FET004_BASE_PHYSX, FET005_BASE_NEUTRAL, FET006_BASE_MDL |
| Prop-Robotics-Isaac | 1.0.0 | Isaac Sim composition + PhysX props | FET001_BASE_NEUTRAL, FET003_BASE_PHYSX, FET004_BASE_PHYSX, FET005_BASE_NEUTRAL, FET006_BASE_ISAACSIM, FET100_BASE_ISAACSIM |
| Robot-Body-Neutral | 1.0.0 | Neutral robot body physics | FET001_BASE_NEUTRAL, FET003_BASE_NEUTRAL, FET004_BASE_NEUTRAL, FET022_DRIVEN_JOINTS_NEUTRAL, FET024_BASE_ARTICULATION_NEUTRAL |
| Robot-Body-Runnable | 1.0.0 | PhysX robot body, runnable core | FET001_BASE_NEUTRAL, FET004_ROBOT_PHYSX, FET021_ROBOT_CORE_RUNNABLE, FET022_DRIVEN_JOINTS_PHYSX, FET024_BASE_ARTICULATION_PHYSX |
| Robot-Body-Isaac | 1.0.0 | Isaac robot core + PhysX | FET001_BASE_NEUTRAL, FET004_ROBOT_PHYSX, FET021_ROBOT_CORE_ISAAC, FET022_DRIVEN_JOINTS_ISAAC, FET024_BASE_ARTICULATION_PHYSX, FET100_BASE_ISAACSIM |
| Robot-Gripper-Neutral | 0.1.0 | Neutral gripper end-effector with grasp site | FET001_BASE_NEUTRAL, FET003_BASE_NEUTRAL, FET004_BASE_NEUTRAL, FET022_DRIVEN_JOINTS_NEUTRAL, FET024_BASE_ARTICULATION_NEUTRAL, FET028_GRIPPER_NEUTRAL |
| Robot-Gripper-Isaac | 0.1.0 | Isaac gripper end-effector with grasp site | FET001_BASE_NEUTRAL, FET004_ROBOT_PHYSX, FET021_ROBOT_CORE_ISAAC, FET022_DRIVEN_JOINTS_ISAAC, FET024_BASE_ARTICULATION_PHYSX, FET028_GRIPPER_ISAAC, FET100_BASE_ISAACSIM |
| AIF-Entity | 0.1.0 | AI Factory data center equipment digital twin (CDU, CRAH, UPS, Rack); equipment class set by `aif:core:assetClass`, thermal/electrical gated per class | FET000_CORE, FET001_BASE_NEUTRAL, FET200_AIF_NEUTRAL, FET201_AIF_NEUTRAL, FET202_AIF_NEUTRAL, FET203_AIF_NEUTRAL |

```{toctree}
:maxdepth: 1

Prop Robotics Neutral <prop-robotics-neutral>
Prop Robotics Physx <prop-robotics-physx>
Prop Robotics Isaac <prop-robotics-isaac>
Robot Body Neutral <robot-body-neutral>
Robot Body Runnable <robot-body-runnable>
Robot Body Isaac <robot-body-isaac>
Robot Gripper Neutral <robot-gripper-neutral>
Robot Gripper Isaac <robot-gripper-isaac>
AIF Entity <aif-entity>
```
