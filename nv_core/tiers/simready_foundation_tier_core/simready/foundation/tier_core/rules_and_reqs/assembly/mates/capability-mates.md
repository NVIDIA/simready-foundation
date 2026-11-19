# Mates

This capability defines `simready:mate:` sites on a **standalone** asset: where a port is, what role it plays, and what it fits. An arm declares sockets; a gripper, tool, or sensor declares a plug; a stackable part declares both. No asset refers to any other.

## Summary

A mate site is an `Xform` discovered by authored `simready:mate:domain` and `simready:mate:role`. Mechanical sites additionally declare a catalog `interface` token, an enabled rigid-body ancestor (the mate body), and a positive socket `maxPayload`. Sites in other domains are discovered the same way but are governed by their own domain rules, not the `mechanical:` ones. Pairing, realization, and the connection joint belong to [Connections](../connections/capability-connections.md), not this capability.

An asset declares its sites without knowing what will mate to them. The mate body established here (`MC.003`) is what a jointed connection later targets with `physics:body0` / `physics:body1`, and what a compound connection shares. Because the walk reads `physics:rigidBodyEnabled` rather than the applied schema, an assembly can demote a part into a compound without stripping the physics the asset ships.

A mate site may coexist with `IsaacSiteAPI` on the same prim, and the Isaac samples do apply it. No requirement here reads or checks it. Where both are authored, `isaac:forwardAxis` should be `"Z"` so it agrees with the mate-frame convention (`+Z` out of the socket, withdraw direction), but that agreement is a recommendation, not a validated rule.

## Schema / OpenUSD Specification

- [UsdGeomXform](https://openusd.org/dev/api/class_usd_geom_xform.html)
- [UsdGeomBasisCurves](https://openusd.org/dev/api/class_usd_geom_basis_curves.html)
- [UsdPhysics Rigid Body](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_rigid_bodies)

Custom attributes use the `simready:mate:` and `simready:mate:mechanical:` prefixes. They are unschema'd custom properties on standard `Xform` prims.

## Validation

Static checkers are **deferred**. Requirement pages state the fail/warn contract; implement them with `simready-foundation-add-validator`. Until then, `validation.py` is a placeholder and is not registered in `rules_and_reqs/__init__.py`.

{doc}`Full Requirements List <requirements>`

```{toctree}
:maxdepth: 1
:hidden:

requirements
```
