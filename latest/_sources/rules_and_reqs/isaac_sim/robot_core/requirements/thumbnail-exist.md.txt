# thumbnail-exist

| Code     | RC.004 |
|----------|--------|
| Compatibility | {compatibility}`Isaac Sim` |
| Tags     | {tag}`high-quality` |

## Summary

The robot interface asset file should contain a thumbnail. The thumbnail should be representative of the robot.

## Example

For a robot asset located at `Robots/Manufacturer/Robot_Name/Robot.usd`, the thumbnail should be at `Robots/Manufacturer/Robot_Name/.thumbs/256x256/Robot.usd.png`.

The file name is the complete USD file name with `.png` appended, so the `.usd`
extension is retained. `Robot.png` does not satisfy this requirement: the
validator derives the expected path from the delivered asset's file name, the
same way `SR.002` does.

## Why

The thumbnail should provide an accurate preview for the robot

## How to comply

- Add a PNG thumbnail under `.thumbs/256x256/` next to the robot asset file
- Name it after the complete robot USD file name with `.png` appended, for example `Robot.usd.png`
- Ensure the thumbnail is representative of the robot

## Authoring guidance

See the [Thumbnail Guidelines](../../../../guides/thumbnail_guidelines.md)
for composition, lighting, background variants, rendering, and the reusable
Thumbnail Library.
