# Robot Schema

Robot USDs declare and use the required schemas and physics attributes.

## Why
Ensures compatibility with Isaac Sim and validators.

## How to comply
- Apply correct schemas to robot prims.
- Set physics attributes on the appropriate layers.

## Example

The default prim should have the `IsaacRobotAPI` applied, with relationships to robot links and joints.

For example:

```usd
# Valid: Proper robot schema joint definition
over "Robot" (
    prepend apiSchemas = ["IsaacRobotAPI"]
)
{
    string isaac:namespace (
        displayName = "Namespace"
        doc = "Namespace of the prim in Isaac Sim"
    )
    rel isaac:physics:robotJoints = [
        </joints_0>,
        </joints_1>,
        </joints_2>,
    ]
    rel isaac:physics:robotLinks = [
        </link_0>,
        </link_1>,
        </link_2>,
    ]
}
```
