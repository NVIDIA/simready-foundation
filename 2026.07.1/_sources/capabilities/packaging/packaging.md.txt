# Packaging

Capabilities in this category define the structure, identity, integrity, metadata, discovery, and delivery requirements for SimReady OpenUSD asset packages and registries.

These capabilities translate requirements from the Asset Packaging Specification and the Asset Registry Specification into SimReady Foundation requirements.

## Separation of concerns: USD composition vs. package distribution

This standard draws two boundaries that should not be confused:

- **USD = authoring/composition boundary.** Clients query identity through standard USD interfaces (e.g. `assetInfo`); identity is readable while the package envelope is intact, and correctly unreadable once the envelope is violated (flatten or modification).
- **Package = distribution/supply-chain boundary.** Package identity is canonically stored in the manifest sidecar, alongside integrity (BOM, content hashes, package hash, signature). Signing scope is the package; per-file integrity delegates to BOM hashes; repack ⇒ resign.

A package may contain non-USD payloads — the BOM covers all payloads, identity-via-USD applies only to the USD ones. USD authoring tools never need to understand the packaging format; the signing pipeline never needs to parse USD composition.

```{toctree}
:maxdepth: 1

Packaging Core <packaging_core/capability-packaging_core>
Conformance Metadata <conformance_metadata/capability-conformance_metadata>
Packaging Introspection <packaging_introspection/capability-packaging_introspection>
```
