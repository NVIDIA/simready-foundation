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

## Adding the Remaining Captures

Three tests have no artifact yet. To add one, run the test on a suitable asset
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
| mimic_joint | mimic-joint.png | mimic-joint.mp4 | a robot with a mimic joint pair | Pending |
