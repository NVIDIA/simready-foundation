# Clean Folder

Robot asset folders contain only referenced, required files. No stray or unused content. At the main level of a robot asset, only the interface layer is present. All other required content is bundled on subfolders related to it specific usage.

## Example

```text
Manufacturer/
├── robot.usd
└── Payload/
    ├── material.usda
    ├── base.usda
    ├── geometry.usdc
    ├── instances.usda
    └── Physics/
        ├── physics.usda
        └── physx.usda
```


## Why
Reduces bloat and ambiguity in deployments and validation.

## How to comply
- Remove unreferenced files from robot folders.
- Keep only USD, materials, and textures referenced by the robot.