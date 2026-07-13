# Hash Object Format and Computation

| Code     | PKG.HASH.001 |
|----------|-----------|
| Validator| _Not yet implemented_ |
| Compatibility | {compatibility}`core-packaging` |
| Tags     | {tag}`essential` |

## Summary

Hash fields MUST be objects containing at least a `sha256` key with lowercase hexadecimal value. Implementations SHOULD also include `blake3` and/or `blake2b` when available, for performance. When `content_hash` or `package_hash` are present, their `sha256` values MUST be computed using the deterministic algorithms defined in this requirement.

## Description

### Hash Object Format

Hash fields throughout the packaging and registry specifications (including `content_hash`, `package_hash`, metadata entry hashes, and BOM item hashes) use a common hash object format. The `hash` field MUST be an object containing content hashes. The object MUST include `sha256`: SHA-256 hash of the full content, encoded as lowercase hexadecimal, authoritative for integrity verification. The object SHOULD include `blake3` (BLAKE3 hash) and/or `blake2b` (BLAKE2b hash) when the implementation has access to these algorithms, as they offer significantly better performance for large files. The object SHOULD include `sha256-first1m`: SHA-256 hash of the first 1,048,576 bytes (1 MB), for quick rejection of changed files without reading the entire content (may be omitted for files smaller than 1 MB; applicable to file-level hashes, not computed hashes like `content_hash` and `package_hash`). For each of the keys named above (`sha256`, `blake3`, `blake2b`, `sha256-first1m`), when present, the value MUST be an **inline lowercase hexadecimal string** of the digest. Future requirements MAY add keys to carry tree-structured digests or other artefacts that cannot be encoded inline (for example, a future BLAKE3 chunk-tree key under a distinct name); such keys MAY use a **sidecar file reference** (a relative path to a file containing the algorithm's native binary format). The sidecar form is reserved for those future extensions and MUST NOT be used for any of the keys named above; the binary layout for sidecars is deliberately unspecified at this requirement and will be defined by whichever future requirement introduces the first sidecar-bearing key.

### Content Hash Computation

The `content_hash` is a deterministic SHA-256 hash identifying the asset content of a package, independent of storage or transport. It covers content files only — all files that are not the package definition file and not in the `.metadata/` folder. The `content_hash` `sha256` key MUST be computed as follows:

1. Enumerate all content files (everything except the package definition file and the `.metadata/` folder).
2. For each file, compute its SHA-256 hash from the file bytes.
3. Sort files by `relative_path` (lexicographic, byte-wise comparison of UTF-8 encoded paths).
4. For each file in sorted order, concatenate: the UTF-8 bytes of `relative_path`, a null byte (`0x00`), and the 32 raw bytes of the SHA-256 hash.
5. Compute the SHA-256 hash of the full concatenation. This is the content hash.

If the package contains no content files (e.g., a dependency-only meta-package), the concatenation in step 4 is empty and the content hash is the SHA-256 hash of the empty byte string (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

When `blake3` and/or `blake2b` are present alongside `sha256` on the `content_hash` object, they MUST be computed by hashing the **same byte buffer** produced by step 4 with BLAKE3 / BLAKE2b instead of SHA-256. The buffer is independent of the digest algorithm — the per-file SHA-256 digests in step 4 are still used to build it — so `content_hash.blake3` and `content_hash.blake2b` are deterministic functions of the same set of files and produce identical results across implementations.

When a BOM is present (see PKG.BOM.001), it defines the authoritative set of content files and their hashes for content hash computation. The Packaging Introspection capability specifies how the BOM supersedes the filesystem enumeration in steps 1–2.

Two packages with different `package_id` values or different metadata may share the same content hash if they contain identical asset files.

### Package Hash Computation

The `package_hash` is a deterministic SHA-256 hash identifying the complete immutable package as published, covering identity, license, content, and the metadata included at creation time. The `package_hash` `sha256` key MUST be computed as follows:

1. Start with an empty byte buffer.
2. Append: UTF-8 bytes of `package_id`, followed by a null byte (`0x00`).
3. Append: UTF-8 bytes of `license`, followed by a null byte (`0x00`).
4. Append: the 32 raw bytes of the `content_hash` SHA-256 hash.
5. For each entry in the `metadata` array, sorted by `name` (lexicographic, byte-wise comparison of UTF-8 encoded names): append the UTF-8 bytes of `name`, followed by a null byte (`0x00`), followed by the 32 raw bytes of the SHA-256 hash from the entry's `hash` object.
6. Compute the SHA-256 hash of the full buffer. This is the package hash.

If the `metadata` field is absent or the array is empty, step 5 contributes no bytes and the package hash is derived solely from `package_id`, `license`, and `content_hash`.

When `blake3` and/or `blake2b` are present alongside `sha256` on the `package_hash` object, they MUST be computed by hashing the **same byte buffer** produced by step 5 with BLAKE3 / BLAKE2b instead of SHA-256. As with `content_hash`, the buffer is built from per-file SHA-256 digests regardless of which algorithm produces the final digest.

Metadata added after package creation does not change the package hash — only entries listed in the `metadata` array of the package definition file are included.

## Why is it required?

- A single hash format shared across packaging and registry layers avoids incompatible verification schemes
- SHA-256 is universally available in every language and platform standard library, ensuring all implementations can produce and verify hashes without external dependencies
- Deterministic computation algorithms let any party independently verify that a package's content and identity have not been tampered with
- BLAKE3 and BLAKE2b are recommended as optional accelerators because they are significantly faster on large files while providing equivalent security

### Rationale for bespoke hash constructions

The content hash and package hash algorithms defined above are deliberately simple flat-concatenation schemes rather than adaptations of existing content-addressable constructions (Merkle DAGs, IPFS CIDs, NIX output hashing, ISCC). This choice was made because (a) the input set is small and fully enumerable at creation time — there is no need for incremental or streaming verification of sub-trees, (b) the construction requires no additional dependencies or format knowledge beyond SHA-256 and sorted file paths, keeping the barrier to independent implementation minimal, and (c) the signing scope is the package as a whole, not individual chunks or blocks. Should an established standard emerge that covers the same integrity guarantees with broader ecosystem interoperability, the specification is open to adopting it in a future requirement revision before the installed base grows large.

## Examples

```json
// Valid: hash object with required sha256 key
{
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

```json
// Valid: hash object with recommended performance hashes
{
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "blake3": "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
  "blake2b": "786a02f742015903c6c6fd852552d272912f4740e15847618a86e217f71f5419"
}
```

```json
// Valid: hash object with partial hash for a large file
{
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "sha256-first1m": "a948904f2f0f479b8f8564e9f2a7c10e1db28e82085f01e1e168a12b4a2db5c3"
}
```

```json
// Invalid: missing sha256 key
{
  "blake3": "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
}
```

```json
// Invalid: uppercase hex value
{
  "sha256": "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855"
}
```

## How to comply

- Include a `sha256` key with lowercase hexadecimal SHA-256 hash in all hash objects
- Include `blake3` and/or `blake2b` keys when these algorithms are available, for faster verification by consumers that support them
- Include `sha256-first1m` for file-level hashes over 1 MB
- Encode every digest value for the named keys (`sha256`, `blake3`, `blake2b`, `sha256-first1m`) as an inline lowercase hexadecimal string; do not emit sidecar file references for these keys (the sidecar form is reserved for future tree-structured-digest keys defined by separate requirements)
- When `content_hash` is present, verify it matches the 5-step content hash computation algorithm
- When `package_hash` is present, verify it matches the 6-step package hash computation algorithm
- Additional hash algorithms may be added by future requirements

## Related Requirements

- [package-definition](/capabilities/packaging/packaging_core/requirements/package-definition)
- [bom-structure](/capabilities/packaging/packaging_introspection/requirements/bom-structure)

## For More Information

- [SHA-256 (FIPS 180-4)](https://csrc.nist.gov/publications/detail/fips/180/4/final)
- [BLAKE3 specification](https://github.com/BLAKE3-team/BLAKE3-specs/blob/master/blake3.pdf)
- [BLAKE2b (RFC 7693)](https://www.rfc-editor.org/rfc/rfc7693)
