# Optimizations

Isaac optimizations combine welded rigid bodies and compatible visual meshes,
remove inactive collision schemas, and replace MaterialX rendering with a USD
Preview Surface. Physics and geometry are preserved; a newly derived preview
approximates shading features beyond USD Preview Surface.

Every requirement is read from the composed stage, so the answer does not depend
on how the asset was authored, processed, or exported.

## Requirements

```{requirements-table}
```

```{toctree}
:maxdepth: 1
:hidden:

requirements
```
