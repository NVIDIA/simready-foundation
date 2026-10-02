---
orphan: true
---

# Test Doc Images

Per-test expected-result frames live in this directory as `<test-name>.png`, and
the matching result videos live in `docs/_static/videos/<test-name>.mp4`. Each
per-test doc embeds its still inline and links its video. The artifacts are
committed into the docset so the docs are self-contained and do not depend on a
local `_testing` run directory.

## How These Were Captured

The stills and videos were taken from a real `simready-benchmark` run. For the dynamic
tests the still is a representative frame extracted from the result video. The
`presence` still is the test's own captured visible frame. The source asset for
each test is listed in the table below.

The FET006 stills are the tests' own captured frames rather than frames pulled
from a video.

The surface-test stills and `coverage-failure.png` were captured on Isaac Sim 6.0.1, which resolves all three surfaces; Isaac Sim 5.0 does not resolve OpenPBR. Each is a composite of two frames from the same run —
the asset as authored on the left, and the same render with the magenta control
material bound underneath the asset's own bindings on the right. The two panels
come from separate stages, so the framing differs slightly between them.
`coverage-failure.png` is the same layout on a fixture where one of two cubes is
bound to nothing, which is what a coverage failure looks like.
`openpbr-migration-before-after.png` is the same layout applied to one test's
frame on two versions of the same asset. In every composite the panels are
downscaled but otherwise unretouched.

`display-color-response.png` is a single unretouched capture of the asset
rendering its own authored `primvars:displayColor` through the OpenPBR
primvar-reader material DISP.001 nominates, bound over the whole asset on its root
prim.

Stills are saved as palette-256 PNGs with Floyd-Steinberg dithering, which is
roughly a third of the size of the raw RGB capture and shows no visible banding
on these renders. All PNGs in this directory are stored through git-lfs by the
repository-wide `*.png` rule in `.gitattributes`.

## Adding the Remaining Captures

Some tests have no artifact yet; the status table below is the list. To add
one, run the test on a suitable asset
through `simready-benchmark`, copy the result video to
`docs/_static/videos/<test-name>.mp4`, save a representative still as
`<test-name>.png` in this directory, then add the inline image and the result
video link to the test doc following the pattern in the other test docs.

| Test | Image | Video | Source asset | Status |
|---|---|---|---|---|
| presence | presence.png | (still only) | apple_a01 | Captured |
| normals_xz | normals-xz.png | normals-xz.mp4 | apple_a01 | Captured |
| culling_xz | culling-xz.png | culling-xz.mp4 | apple_a01 | Captured |
| light_response | light-response.png | light-response.mp4 | apple_a01 | Captured |
| pivot | pivot.png | pivot.mp4 | apple_a01 | Captured |
| ground_drop | ground-drop.png | ground-drop.mp4 | apple_a01 | Captured |
| slope_drop | slope-drop.png | slope-drop.mp4 | apple_a01 | Captured |
| joint_movement | joint-movement.png | joint-movement.mp4 | obs_workbench_tool_a01 | Captured |
| grasp_and_lift | grasp-and-lift.png | grasp-and-lift.mp4 | coffee_cup_grasp_a01 | Captured |
| drive_gain_validation | drive-gain-validation.png | drive-gain-validation.mp4 | ur10 | Captured |
| effort_limit | effort-limit.png | effort-limit.mp4 | ur10 | Captured |
| full_range_sweep | full-range-sweep.png | full-range-sweep.mp4 | ur10 | Captured |
| ik_target_reach | ik-target-reach.png | ik-target-reach.mp4 | ur10 | Captured |
| jacobian_ik | jacobian-ik.png | jacobian-ik.mp4 | ur10 | Captured |
| multi_joint_coordination | multi-joint-coordination.png | multi-joint-coordination.mp4 | ur10 | Captured |
| state_accuracy | state-accuracy.png | state-accuracy.mp4 | ur10 | Captured |
| velocity_limit | velocity-limit.png | velocity-limit.mp4 | ur10 | Captured |
| openpbr_renders | openpbr-renders.png | (still only) | sm_obs_joystick_a01_01 | Captured |
| mdl_renders | mdl-renders.png | (still only) | sm_gen_appliance_toaster_v01_01 | Captured |
| preview_surface_renders | preview-surface-renders.png | (still only) | sm_obs_workbench_tool_a01_01 | Captured |
| display_color_response | display-color-response.png | (still only) | sm_gen_appliance_toaster_v01_01 with `primvars:displayColor` authored | Captured |
| mimic_joint | mimic-joint.png | mimic-joint.mp4 | a robot with a mimic joint pair | Pending |
| gripper_close_lift_cube | gripper-close-lift-cube.png | gripper-close-lift-cube.mp4 | a parallel-jaw gripper, for example Robotiq 2F-85 | Pending |
| gripper_close_lift_sphere | gripper-close-lift-sphere.png | gripper-close-lift-sphere.mp4 | a parallel-jaw gripper, for example Robotiq 2F-85 | Pending |

Figures that illustrate a comparison rather than one test's result:

| Image | Shows | Source assets |
|---|---|---|
| openpbr-migration-before-after.png | The `openpbr_renders` pinned frame for the same prop before and after migration onto the OpenPBR contract: constant inputs on the left, a populated network on the right. Same room, light rig, and camera. | sm_gen_appliance_toaster_v01_01, pre- and post-migration |
| coverage-failure.png | What a coverage failure looks like: two cubes, one bound to a material and one bound to nothing. Left, as authored — the unbound cube on the renderer's default material. Right, the magenta control bound weaker than the asset's own bindings, showing through where nothing is bound. | two_cubes_one_unbound.usda |

The three surface tests also produce a two-frame result video per run
(`<context>_surface.mp4`), which is the same pair as their still. The stills are
what the docs embed.
