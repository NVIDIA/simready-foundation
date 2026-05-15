# Feature Adapters Documentation Guide

## About this guide

This guide will walk you through the process of understanding, creating, and managing feature adapters in the SimReady Foundation system. Feature adapters are the mechanism that transforms assets from one profile to another by mutating their features.

## What is a Feature Adapter?

A **Feature Adapter** is a mechanism that mutates an asset with a particular profile into a new profile. For this to work, there must be a direct path for all the features that are different from profile A to profile B.

### Key Concepts

- **Profile Transformation**: Converts assets between different feature profiles
- **Feature Mutation**: Modifies asset properties to meet new feature requirements
- **Direct Path Requirement**: All feature differences must have defined transformation logic
- **Asset Handler Modules**: Located in `simready-foundation/nv_core/cip_specs/asset_handler_modules`

### How Feature Adapters Work

1. **Input Profile**: Asset starts with one set of features (e.g., `FET003_BASE_NEUTRAL`)
2. **Transformation Logic**: Adapter applies specific mutations to the asset
3. **Output Profile**: Asset now conforms to new features (e.g., `FET003_BASE_PHYSX`)
4. **Validation**: Asset can now be validated against the new feature set

## Feature Adapter Structure

### Core Components

Each feature adapter consists of:

- **Decorator**: `@feature_adapter` with transformation metadata
- **Input/Output Mapping**: Source and target feature specifications
- **Transformation Function**: Logic that modifies the asset
- **Asset Handler Module**: Location in the asset handler modules directory

### Example: Rigid Body Neutral to PhysX Adapter

Here's a complete example of an existing feature adapter:

```python
import sys
import os
from pxr import Usd, UsdGeom, UsdPhysics
from omni.cip.configurable.feature_adapter import feature_adapter

# Add the root directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

@feature_adapter(
    name="_rigid_body_neutral_to_physx_sample",
    input_feature_id="FET003_BASE_NEUTRAL",
    input_feature_version="0.1.0",
    output_feature_id="FET003_BASE_PHYSX",
    output_feature_version="0.1.0"
)
def modify_stage(input_stage: Usd.Stage, output_stage: Usd.Stage):
    # compute extent for all meshes
    for prim in output_stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            boundable = UsdGeom.Boundable(prim)
            extent = UsdGeom.Boundable.ComputeExtentFromPlugins(boundable, Usd.TimeCode.Default())
            boundable.GetExtentAttr().Set(extent)

    # set collider approximation to SDF
    default_prim = output_stage.GetDefaultPrim()
    if default_prim:
        _set_collider_approximation_to_sdf(default_prim)
        output_stage.Save()


def _set_collider_approximation_to_sdf(prim: Usd.Prim):
    # Set the collider approximation to SDF
    # TODO: add support for PhysxSchema.PhysxTriangleMeshCollisionAPI
    # TODO: add support physxSDFMeshCollision:sdfResolution
    for child in Usd.PrimRange(prim):
        if child.HasAPI(UsdPhysics.MeshCollisionAPI):
            collider = UsdPhysics.MeshCollisionAPI(child)
            approx_attr = collider.GetApproximationAttr()
            if approx_attr:
                approx_attr.Set("sdf")
        elif child.HasAPI(UsdPhysics.CollisionAPI):
            collider = UsdPhysics.MeshCollisionAPI(child)
            approx_attr = child.GetAttribute("physics:approximation")
            if not approx_attr:
                child.CreateAttribute("physics:approximation", Sdf.ValueTypeNames.Token, "sdf")
                approx_attr = child.GetAttribute("physics:approximation")
            approx_attr.Set("sdf")
```

## Creating a New Feature Adapter

### Step 1: Understand the Feature Transformation

Before creating an adapter, you need to understand:

1. **Source Feature**: What features does the asset currently have?
2. **Target Feature**: What features should the asset have after transformation?
3. **Differences**: What specific changes are needed?
4. **Dependencies**: Are there any required libraries or APIs?

### Step 2: Create the Adapter File

Create a new Python file in the appropriate asset handler module directory:

```
simready_foundation/nv_core/cip_specs/asset_handler_modules/[module_name]/
```

**File naming convention:**
- `[feature_name]_[source]_to_[target].py`
- Example: `rigid_body_neutral_to_physx.py`

### Step 3: Implement the Feature Adapter

#### Basic Template

```python
import sys
import os
from pxr import Usd, UsdGeom
from omni.cip.configurable.feature_adapter import feature_adapter

# Add the root directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

@feature_adapter(
    name="[adapter_name]",
    input_feature_id="[INPUT_FEATURE_ID]",
    input_feature_version="[input_version]",
    output_feature_id="[OUTPUT_FEATURE_ID]",
    output_feature_version="[output_version]"
)
def modify_stage(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """
    Transform asset from input_feature_id to output_feature_id.
    
    Args:
        input_stage: Source USD stage with input features
        output_stage: Target USD stage to be modified
    """
    # TODO: Implement transformation logic
    pass


def _helper_function(prim: Usd.Prim):
    """
    Helper function for specific transformation tasks.
    
    Args:
        prim: USD prim to modify
    """
    # TODO: Implement helper logic
    pass
```

#### Complete Example: Simple Material Adapter

```python
import sys
import os
from pxr import Usd, UsdShade, Sdf
from omni.cip.configurable.feature_adapter import feature_adapter

# Add the root directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

@feature_adapter(
    name="minimal_to_material_basic",
    input_feature_id="FET001_BASE_NEUTRAL",
    input_feature_version="0.1.0",
    output_feature_id="FET002_MATERIAL_BASIC",
    output_feature_version="0.1.0"
)
def modify_stage(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """
    Transform asset from minimal features to basic material features.
    Adds basic material properties to all mesh prims.
    """
    # Get the default prim
    default_prim = output_stage.GetDefaultPrim()
    if not default_prim:
        return
    
    # Add materials to all mesh prims
    _add_basic_materials_to_meshes(default_prim)
    
    # Save the modified stage
    output_stage.Save()


def _add_basic_materials_to_meshes(prim: Usd.Prim):
    """
    Add basic material properties to mesh prims.
    
    Args:
        prim: Root prim to traverse
    """
    for child in Usd.PrimRange(prim):
        if child.IsA(UsdGeom.Mesh):
            # Create a basic material binding
            material_binding = UsdShade.MaterialBindingAPI.Apply(child)
            
            # Create a simple material
            material_path = f"{child.GetPath()}/Material"
            material = UsdShade.Material.Define(child.GetStage(), material_path)
            
            # Create a basic shader
            shader_path = f"{material_path}/Shader"
            shader = UsdShade.Shader.Define(child.GetStage(), shader_path)
            shader.CreateIdAttr("UsdPreviewSurface")
            
            # Connect shader to material
            material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
            
            # Bind material to mesh
            material_binding.Bind(material)
```

### Step 4: Define the Adapter Metadata

The `@feature_adapter` decorator requires specific parameters:

#### Required Parameters

- **name**: Unique identifier for the adapter
- **input_feature_id**: Source feature ID (e.g., `FET001_BASE_NEUTRAL`)
- **input_feature_version**: Source feature version (e.g., `"0.1.0"`)
- **output_feature_id**: Target feature ID (e.g., `FET002_MATERIAL_BASIC`)
- **output_feature_version**: Target feature version (e.g., `"0.1.0"`)

#### Naming Conventions

- **Adapter Name**: `[feature_type]_[source]_to_[target]`
- **Feature IDs**: Use the exact IDs from your feature definitions
- **Versions**: Match the versions specified in your feature JSON files

### Step 5: Implement Transformation Logic

#### Core Transformation Function

The main function `modify_stage()` receives two USD stages:

```python
def modify_stage(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """
    This function should:
    1. Read from input_stage (if needed)
    2. Modify output_stage to meet new feature requirements
    3. Save output_stage when complete
    """
    # Read input stage properties
    input_props = _read_input_properties(input_stage)
    
    # Apply transformations to output stage
    _apply_transformations(output_stage, input_props)
    
    # Save the modified output stage
    output_stage.Save()
```

#### Common Transformation Patterns

##### 1. **Adding Properties**

```python
def _add_property_to_prim(prim: Usd.Prim, property_name: str, value):
    """Add a new property to a prim."""
    if not prim.HasAttribute(property_name):
        prim.CreateAttribute(property_name, Sdf.ValueTypeNames.String, "default_value")
    
    attr = prim.GetAttribute(property_name)
    attr.Set(value)
```

##### 2. **Modifying Existing Properties**

```python
def _modify_existing_property(prim: Usd.Prim, property_name: str, new_value):
    """Modify an existing property on a prim."""
    if prim.HasAttribute(property_name):
        attr = prim.GetAttribute(property_name)
        attr.Set(new_value)
```

##### 3. **Adding APIs**

```python
def _add_api_to_prim(prim: Usd.Prim, api_class):
    """Add an API to a prim."""
    if not prim.HasAPI(api_class):
        api_class.Apply(prim)
```

##### 4. **Traversing Prims**

```python
def _process_all_meshes(prim: Usd.Prim):
    """Process all mesh prims in the hierarchy."""
    for child in Usd.PrimRange(prim):
        if child.IsA(UsdGeom.Mesh):
            _process_single_mesh(child)
```

### Step 6: Testing Your Adapter

#### Manual Testing

1. **Create test assets** that conform to the input feature
2. **Run the adapter** on the test assets
3. **Validate the output** against the target feature requirements
4. **Check for errors** and edge cases

#### Automated Testing

```python
def test_adapter_transformation():
    """Test the adapter transformation logic."""
    # Create test input stage
    input_stage = Usd.Stage.CreateInMemory()
    
    # Create test output stage
    output_stage = Usd.Stage.CreateInMemory()
    
    # Run the adapter
    modify_stage(input_stage, output_stage)
    
    # Validate the transformation
    assert _validate_transformation(output_stage)
```

## Advanced Feature Adapter Patterns

### 1. **Conditional Transformations**

```python
def modify_stage(input_stage: Usd.Stage, output_stage: Usd.Stage):
    # Check if transformation is needed
    if not _needs_transformation(input_stage):
        return
    
    # Apply conditional transformations
    if _has_physics_properties(input_stage):
        _transform_physics_properties(output_stage)
    
    if _has_material_properties(input_stage):
        _transform_material_properties(output_stage)
```

### 2. **Batch Processing**

```python
def modify_stage(input_stage: Usd.Stage, output_stage: Usd.Stage):
    # Collect all prims that need transformation
    prims_to_transform = []
    for prim in output_stage.Traverse():
        if _should_transform(prim):
            prims_to_transform.append(prim)
    
    # Process in batches for efficiency
    for batch in _create_batches(prims_to_transform, batch_size=100):
        _process_batch(batch)
```

### 3. **Error Handling and Logging**

```python
import logging

logger = logging.getLogger(__name__)

def modify_stage(input_stage: Usd.Stage, output_stage: Usd.Stage):
    try:
        # Perform transformation
        _apply_transformations(output_stage)
        logger.info("Successfully transformed asset")
        
    except Exception as e:
        logger.error(f"Failed to transform asset: {e}")
        # Optionally, revert changes or provide fallback
        raise
```

## Common Use Cases

### 1. **Adding Physics Properties**

```python
def _add_physics_properties(prim: Usd.Prim):
    """Add basic physics properties to a prim."""
    # Add collision API
    if not prim.HasAPI(UsdPhysics.CollisionAPI):
        UsdPhysics.CollisionAPI.Apply(prim)
    
    # Add rigid body API
    if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
        UsdPhysics.RigidBodyAPI.Apply(prim)
    
    # Set mass
    rigid_body = UsdPhysics.RigidBodyAPI(prim)
    rigid_body.CreateMassAttr(1.0)
```

### 2. **Adding Material Properties**

```python
def _add_material_properties(prim: Usd.Prim):
    """Add basic material properties to a prim."""
    # Create material binding
    material_binding = UsdShade.MaterialBindingAPI.Apply(prim)
    
    # Create material
    material = _create_basic_material(prim.GetStage())
    
    # Bind material
    material_binding.Bind(material)
```

### 3. **Adding Animation Properties**

```python
def _add_animation_properties(prim: Usd.Prim):
    """Add animation properties to a prim."""
    # Add animation API
    if not prim.HasAPI(UsdGeom.Xformable):
        UsdGeom.Xformable.Apply(prim)
    
    # Add animation attributes
    xformable = UsdGeom.Xformable(prim)
    xformable.CreateXformOpOrderAttr()
```

## Best Practices

### 1. **Performance Considerations**

- **Batch operations** when processing multiple prims
- **Avoid unnecessary API calls** - check if APIs already exist
- **Use efficient traversal patterns** for large hierarchies
- **Minimize stage saves** - save once at the end

### 2. **Error Handling**

- **Validate inputs** before processing
- **Handle edge cases** gracefully
- **Provide meaningful error messages**
- **Log important operations** for debugging

### 3. **Code Organization**

- **Separate concerns** into helper functions
- **Use descriptive function names**
- **Add comprehensive documentation**
- **Follow consistent coding style**

### 4. **Testing and Validation**

- **Test with various asset types**
- **Validate output against feature requirements**
- **Test error conditions** and edge cases
- **Performance test** with large assets

## Troubleshooting

### Common Issues

#### 1. **Import Errors**

```python
# Problem: Cannot import required modules
# Solution: Ensure proper path setup
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
```

#### 2. **API Not Found**

```python
# Problem: API class not available
# Solution: Check imports and USD version compatibility
from pxr import UsdPhysics  # Ensure this import works
```

#### 3. **Stage Not Saving**

```python
# Problem: Changes not persisting
# Solution: Call output_stage.Save() at the end
def modify_stage(input_stage: Usd.Stage, output_stage: Usd.Stage):
    # ... transformation logic ...
    output_stage.Save()  # Don't forget this!
```

#### 4. **Performance Issues**

```python
# Problem: Adapter runs slowly on large assets
# Solution: Use batch processing and efficient traversal
def _efficient_traversal(prim: Usd.Prim):
    # Use Usd.PrimRange for efficient traversal
    for child in Usd.PrimRange(prim):
        if child.IsA(UsdGeom.Mesh):  # Filter early
            _process_mesh(child)
```

## Getting Help

If you need assistance creating or debugging feature adapters:

1. **Review existing adapters** for examples and patterns
2. **Check USD documentation** for API usage
3. **Test with simple assets** before complex ones
4. **Use logging** to debug transformation issues
5. **Ask the development team** for guidance on complex transformations

##
This comprehensive guide provides everything needed to understand and create feature adapters, including the complete example from the existing code, step-by-step creation process, best practices, and troubleshooting guidance. It follows the same structure and formatting as the other guides while focusing specifically on the feature adapter functionality.
