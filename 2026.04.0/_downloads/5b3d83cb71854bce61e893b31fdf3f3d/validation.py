# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
"""
Validation rules for Package Structure capability (PKG).

These validators operate on the package directory (not a USD stage).
They verify the presence and structure of the package definition file,
package identity rules, metadata file format, and hash object
conformance. Internal references within USD content are validated
separately by the Atomic Asset capability's AA.001 rule (anchored
asset paths).

Integration with the asset-validator format system
--------------------------------------------------
The :class:`SimReadyPackageFormat` handler registers the SimReady package
manifest (``com.nvidia.simready.packaging.json``) with
``AssetFormatRegistry``. Its ``get_dependencies`` enumerates every content
path in the package (via BOM when available, otherwise by walking the
directory through the ``UriResolver``).

The compliance engine then dispatches one ``CheckFormatDependency`` event
per path in that list, passing a ``FormatDependency(path, uri_resolver,
root_asset_path)`` context object. Each rule in this module collapses to
the root manifest with ``dependency.path == dependency.root_asset_path``
so it only fires once per package. File I/O inside the rules uses
``Ar.GetResolver().OpenAsset`` for bytes and ``dependency.uri_resolver``
for directory listing, keeping the backend abstracted.
"""

import hashlib
import json
import re
from pathlib import PurePosixPath
from typing import Literal

from pxr import Ar

import omni.asset_validator
import omni.capabilities as cap

# Gate the AssetFormat handler below on the presence of the AssetFormat API
# (``register_format`` / ``FormatDependency`` / ``BaseRuleChecker.CheckFormatDependency``).
# The publicly published ``omniverse-asset-validator`` wheel on
# ``pypi.nvidia.com`` (1.15.1 as of 2026-04) does not yet expose this API; the
# first public release expected to carry it is 1.18.0. On older wheels we want
# this module to import cleanly so ``simready.validate.initialize()`` keeps
# working — the rule classes still register but their ``CheckFormatDependency``
# overrides are inert because the old engine has no ``AssetFormat`` to dispatch
# from. ``validate_package.py`` short-circuits with a clear diagnostic before
# attempting validation under that condition.
_HAS_ASSET_FORMAT_API = hasattr(omni.asset_validator, "register_format")


def _sha256_hash(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


PACKAGE_DEFINITION_FILENAME = "com.nvidia.simready.packaging.json"
METADATA_DIR = ".metadata"

REQUIRED_FIELDS = ("format_version", "package_id", "license")

FORMAT_VERSION_RE = re.compile(r"\d+\.\d+$")
LOWERCASE_HEX_RE = re.compile(r"^[0-9a-f]+$")
REVERSE_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9]+(\.[a-zA-Z0-9][-a-zA-Z0-9_@%]*)+\.json$")

# Control chars U+0000–U+001F, U+007F–U+009F, whitespace, and <>:"/\|?*@
PACKAGE_ID_FORBIDDEN_RE = re.compile(r'[\x00-\x1f\x7f-\x9f\s<>:"/\\|?*@]')
PACKAGE_ID_MAX_LENGTH = 255

DESCRIPTION_MAX_LENGTH = 500

BOM_FILENAME = "com.nvidia.simready.packaging.bom.json"
ROOT_USDS_FILENAME = "com.nvidia.simready.root_usds.json"


# ------------------------------------------------------------------
# Shared helpers (consumed by packaging_introspection + conformance_metadata)
# ------------------------------------------------------------------

def _fmt_dep(dependency) -> str:
    """Human-readable label for a ``FormatDependency`` in diagnostic messages."""
    p, r = dependency.path, dependency.root_asset_path
    return p if p == r else f"{p} (root: {r})"


def _open_ar_asset(asset_path: str):
    """Open *asset_path* via ``Ar.GetResolver``. Returns ``None`` if unresolvable."""
    resolver = Ar.GetResolver()
    resolved = resolver.Resolve(asset_path)
    if not resolved:
        return None
    ar_asset = resolver.OpenAsset(resolved)
    if ar_asset is None:
        return None
    return ar_asset


def _read_asset_bytes(asset_path: str) -> bytes | None:
    """Return the full byte content of *asset_path*, or ``None`` on any open error."""
    ar_asset = _open_ar_asset(asset_path)
    if ar_asset is None:
        return None
    try:
        buf = ar_asset.GetBuffer()
        return bytes(buf) if buf is not None else b""
    except Exception:
        return None


def _parse_package_json(asset_path: str):
    """Parse the package manifest JSON at *asset_path*.

    Opens the asset through ``Ar.GetResolver`` and returns the parsed dict,
    or ``None`` on any I/O or JSON error. The target asset-validator branch
    no longer passes an ``Ar.Asset`` to rules, so rules open the manifest
    themselves via this helper.
    """
    raw = _read_asset_bytes(asset_path)
    if raw is None:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


BOM_ABSENT = "absent"
BOM_BROKEN = "broken"
BOM_OK = "ok"

BomStatus = Literal["absent", "broken", "ok"]


def _load_bom(
    pkg_dir: str,
    uri_resolver,
) -> tuple[BomStatus, dict | None, str | None]:
    """Return ``(status, bom, detail)`` describing the BOM at *pkg_dir*.

    ``status`` is one of:

    * :data:`BOM_ABSENT` — the BOM file is not present at the expected
      location (``<pkg_dir>/.metadata/<BOM_FILENAME>``). ``bom`` and
      ``detail`` are ``None``. Callers may fall back to walking the
      package directory.
    * :data:`BOM_BROKEN` — the BOM file exists but cannot be used
      (unreadable, non-UTF-8, invalid JSON, not an object, or missing the
      required ``items`` array). ``bom`` is ``None`` and ``detail`` is a
      short human-readable explanation suitable for a diagnostic message.
      Callers should **not** silently fall back to the filesystem here —
      the BOM exists and is authoritative, just broken. ``BomStructureChecker``
      surfaces the failure; other callers should skip BOM-dependent work.
    * :data:`BOM_OK` — the BOM parsed and passes the minimal shape check.
      ``bom`` is the parsed dict and ``detail`` is ``None``.

    Separating "absent" from "broken" matters because the hash verification
    algorithm is BOM-first (compute-from-BOM when one is present,
    compute-from-filesystem only when no BOM exists). A broken BOM cannot
    silently fall back to the filesystem path or the user gets a
    mismatch diagnostic whose real cause is the corrupt BOM.
    """
    bom_uri = uri_resolver.join_uri(uri_resolver.join_uri(pkg_dir, METADATA_DIR), BOM_FILENAME)
    if not uri_resolver.is_uri_found(bom_uri):
        return BOM_ABSENT, None, None
    raw = _read_asset_bytes(bom_uri)
    if raw is None:
        return BOM_BROKEN, None, "unable to read file"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return BOM_BROKEN, None, "not valid UTF-8"
    try:
        bom = json.loads(text)
    except json.JSONDecodeError as exc:
        return BOM_BROKEN, None, f"invalid JSON: {exc}"
    if not isinstance(bom, dict):
        return BOM_BROKEN, None, (
            f"top-level value must be a JSON object, got {type(bom).__name__}"
        )
    items = bom.get("items")
    if not isinstance(items, list):
        return BOM_BROKEN, None, "missing required 'items' array"
    return BOM_OK, bom, None


def _load_root_usds(pkg_dir: str, uri_resolver) -> set[str] | None:
    """Return the set of forward-slash relative paths declared in the
    package's ``com.nvidia.simready.root_usds.json`` (PKG.CONF.002), or
    ``None`` when the file is absent or unusable.

    Modelled on :func:`_load_bom`, but collapses the absent / broken
    cases into a single ``None``: ``get_dependencies`` has no
    diagnostic surface to emit a separate "root_usds.json is broken"
    error, and the existing ``MetadataFilesChecker`` (PKG.META.001)
    already reports format failures of metadata files independently.
    Returning ``None`` therefore restores today's
    "validate every USD" behaviour (the spec's SHOULD fallback for
    when the file is absent), which is also a safe degraded mode for
    a malformed file.
    """
    uri = uri_resolver.join_uri(uri_resolver.join_uri(pkg_dir, METADATA_DIR), ROOT_USDS_FILENAME)
    if not uri_resolver.is_uri_found(uri):
        return None
    raw = _read_asset_bytes(uri)
    if raw is None:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    entries = data.get("entries")
    if not isinstance(entries, list):
        return None
    return {entry for entry in entries if isinstance(entry, str)}


def _uri_basename(uri: str) -> str:
    """Return the final path component of *uri*.

    Pure string op — does not reach the backend. Works for both local
    filesystem paths and URI-style paths (forward-slash-separated, as
    produced by ``LocalUriResolver``). The upstream ``UriResolver``
    protocol does not expose this helper; once it does we can drop this.
    """
    return PurePosixPath(str(uri).replace("\\", "/")).name


def _relative_uri(base_uri: str, child_uri: str) -> str:
    """Return *child_uri* expressed relative to *base_uri*.

    Pure string op, same caveats as :func:`_uri_basename`. If *child_uri*
    is not a descendant of *base_uri*, returns *child_uri* unchanged.
    """
    base = str(base_uri).replace("\\", "/").rstrip("/") + "/"
    child = str(child_uri).replace("\\", "/")
    if child.startswith(base):
        return child[len(base):]
    return child


def _walk_uris(uri_resolver, base_uri):
    """Yield every leaf URI under *base_uri* recursively.

    Built on ``UriResolver.list_uris`` + ``is_uri_prefix`` so it is
    backend-agnostic. Matches how the old ``folder.walk()`` was consumed
    (the caller sorts the result, so iteration order does not matter).
    """
    for child in uri_resolver.list_uris(base_uri):
        if uri_resolver.is_uri_prefix(child):
            yield from _walk_uris(uri_resolver, child)
        else:
            yield child


def _should_skip_content(rel_path: str) -> bool:
    """Mirror the skip rules used by ``_deps_from_filesystem`` on the old branch.

    Excludes the manifest itself and anything under the ``.metadata/``
    subtree — those are packaging machinery, not package content.
    """
    if rel_path == PACKAGE_DEFINITION_FILENAME:
        return True
    if rel_path == METADATA_DIR or rel_path.startswith(METADATA_DIR + "/"):
        return True
    return False


def _is_valid_hash_object(obj):
    """Return True if *obj* looks like a valid hash object (has ``sha256`` key with lowercase hex)."""
    if not isinstance(obj, dict):
        return False
    sha256_val = obj.get("sha256")
    if not isinstance(sha256_val, str):
        return False
    return bool(LOWERCASE_HEX_RE.fullmatch(sha256_val))


# ------------------------------------------------------------------
# Multi-algorithm hash helpers (PKG.HASH.001)
# ------------------------------------------------------------------
#
# Per hash-object-format.md, every named digest key (sha256, blake3,
# blake2b, sha256-first1m) is an inline lowercase hex string of the
# digest. The sidecar form is reserved for future tree-structured-digest
# keys and is not accepted here. SHA-256 and BLAKE2b come from stdlib
# ``hashlib`` so they are always available; BLAKE3 is verified only when
# the optional ``blake3`` module is importable. When it isn't, declared
# blake3 digests are still format-checked (they must be lowercase hex)
# but not recomputed against the file/buffer bytes.

try:
    import blake3 as _blake3_mod
    _BLAKE3_AVAILABLE = True
except ImportError:
    _blake3_mod = None
    _BLAKE3_AVAILABLE = False

FIRST1M = 1024 * 1024

#: File-level digest keys verified against the file's full bytes
#: (``sha256-first1m`` is verified against the first 1 MiB only).
VERIFIABLE_KEYS = ("sha256", "blake3", "blake2b", "sha256-first1m")

#: Aggregate-buffer digest keys verified against the deterministic byte
#: buffer described by the 5-step / 6-step algorithms in PKG.HASH.001.
#: ``sha256-first1m`` is excluded — the spec restricts it to file-level
#: hashes, not computed aggregates like ``content_hash`` / ``package_hash``.
AGGREGATE_KEYS = ("sha256", "blake3", "blake2b")


def _digest_from_bytes(data: bytes, key: str) -> str | None:
    """Return lowercase hex digest of *data* under algorithm *key*.

    Returns ``None`` when *key* is not a recognised digest key, or when
    the optional ``blake3`` module is needed but not importable. The
    caller treats ``None`` as "skip this verification" — the format
    check in ``_check_hash_object`` already covers the value's shape.
    """
    if key == "sha256":
        return hashlib.sha256(data).hexdigest()
    if key == "blake2b":
        return hashlib.blake2b(data).hexdigest()
    if key == "blake3":
        if not _BLAKE3_AVAILABLE:
            return None
        return _blake3_mod.blake3(data).hexdigest()
    if key == "sha256-first1m":
        return hashlib.sha256(data[:FIRST1M]).hexdigest()
    return None


def _declared_hex_keys(hash_obj: dict, candidate_keys: tuple) -> list:
    """Return *candidate_keys* present on *hash_obj* with a well-formed lowercase-hex value."""
    out = []
    for key in candidate_keys:
        val = hash_obj.get(key)
        if isinstance(val, str) and LOWERCASE_HEX_RE.fullmatch(val):
            out.append(key)
    return out


def _content_hash_buffer_from_bom(bom: dict) -> bytes | None:
    """Build the canonical content_hash byte buffer from BOM items.

    The buffer is the concatenation, in byte-sorted ``relative_path``
    order, of ``utf8(relative_path) + b"\\x00" + sha256_bytes`` for
    every BOM item. Hashing this buffer with SHA-256 yields the value
    of ``content_hash.sha256``; hashing the same buffer with BLAKE3 /
    BLAKE2b yields the corresponding ``content_hash.blake3`` /
    ``content_hash.blake2b``.

    Returns ``None`` if any item is missing a usable ``sha256`` digest.
    """
    items = bom.get("items", [])
    entries = []
    for item in items:
        rel_path = item.get("relative_path")
        hash_obj = item.get("hash", {})
        sha256_hex = hash_obj.get("sha256") if isinstance(hash_obj, dict) else None
        if not isinstance(rel_path, str) or not isinstance(sha256_hex, str):
            return None
        try:
            file_hash = bytes.fromhex(sha256_hex)
        except ValueError:
            return None
        if len(file_hash) != 32:
            return None
        entries.append((rel_path, file_hash))

    entries.sort(key=lambda e: e[0].encode("utf-8"))

    buf = bytearray()
    for rel_path, file_hash in entries:
        buf.extend(rel_path.encode("utf-8"))
        buf.extend(b"\x00")
        buf.extend(file_hash)
    return bytes(buf)


def _content_hash_buffer_from_filesystem(pkg_dir: str, uri_resolver) -> bytes | None:
    """Build the canonical content_hash byte buffer by walking *pkg_dir*.

    Used as the no-BOM fallback. Mirrors the BOM-based path: per-file
    SHA-256 is the input regardless of which final algorithm digests
    the buffer.
    """
    content_entries: list[tuple[str, str]] = []
    for child_uri in _walk_uris(uri_resolver, pkg_dir):
        rel_path = _relative_uri(pkg_dir, child_uri)
        if _should_skip_content(rel_path):
            continue
        content_entries.append((rel_path, child_uri))
    content_entries.sort(key=lambda e: e[0].encode("utf-8"))

    buf = bytearray()
    for rel_path, child_uri in content_entries:
        raw = _read_asset_bytes(child_uri)
        if raw is None:
            return None
        file_hash = _sha256_hash(raw)
        buf.extend(rel_path.encode("utf-8"))
        buf.extend(b"\x00")
        buf.extend(file_hash)
    return bytes(buf)


def _package_hash_buffer(data: dict) -> bytes | None:
    """Build the canonical package_hash byte buffer from *data*.

    Implements steps 1-5 of the package_hash algorithm in PKG.HASH.001.
    Step 6 (final digest) is delegated to the caller so the buffer can
    be reused for multi-algorithm verification (BLAKE3 / BLAKE2b).

    Returns ``None`` when the inputs needed to build the buffer
    (``package_id``, ``license``, valid ``content_hash``) are missing
    or malformed; ``PackageDefinitionChecker`` reports those as
    PKG.DEF.001 failures separately.
    """
    package_id = data.get("package_id")
    license_val = data.get("license")
    content_hash_obj = data.get("content_hash")
    if not isinstance(package_id, str) or not isinstance(license_val, str):
        return None
    if not isinstance(content_hash_obj, dict) or not _is_valid_hash_object(content_hash_obj):
        return None
    try:
        content_hash_bytes = bytes.fromhex(content_hash_obj["sha256"])
    except ValueError:
        return None
    if len(content_hash_bytes) != 32:
        return None
    try:
        buf = bytearray()
        buf.extend(package_id.encode("utf-8"))
        buf.extend(b"\x00")
        buf.extend(license_val.encode("utf-8"))
        buf.extend(b"\x00")
        buf.extend(content_hash_bytes)
        metadata = data.get("metadata", [])
        if isinstance(metadata, list):
            sorted_entries = sorted(
                (
                    e for e in metadata
                    if isinstance(e, dict)
                    and isinstance(e.get("name"), str)
                    and _is_valid_hash_object(e.get("hash", {}))
                ),
                key=lambda e: e["name"].encode("utf-8"),
            )
            for entry in sorted_entries:
                buf.extend(entry["name"].encode("utf-8"))
                buf.extend(b"\x00")
                buf.extend(bytes.fromhex(entry["hash"]["sha256"]))
        return bytes(buf)
    except (RuntimeError, ValueError):
        return None


def _compare_digests_against_buffer(
    hash_obj: dict,
    buf: bytes,
    location: str,
    keys: tuple,
    report_failure,
) -> None:
    """Compare every well-formed digest in *hash_obj* against *buf*.

    For each *key* in *keys* present on *hash_obj* with a lowercase-hex
    value, recompute the digest of *buf* under that algorithm and call
    ``report_failure(message)`` on mismatch. Skipped silently when the
    BLAKE3 module is unavailable (the caller's format check still
    reports a missing/wrong-shape value).
    """
    for key in _declared_hex_keys(hash_obj, keys):
        computed = _digest_from_bytes(buf, key)
        if computed is None:
            continue
        declared = hash_obj[key]
        if computed != declared:
            report_failure(
                f"{location}.{key} mismatch: declared '{declared}', "
                f"computed '{computed}'"
            )


# ------------------------------------------------------------------
# AssetFormat handler for the SimReady package manifest
# ------------------------------------------------------------------
#
# Gated on ``_HAS_ASSET_FORMAT_API`` so the module still imports against the
# publicly published ``omniverse-asset-validator`` (1.15.x) which does not
# expose ``register_format``. On those wheels the handler simply isn't
# registered; ``validate_package.py`` short-circuits with a clear diagnostic
# rather than silently returning misleading PASS results.

if _HAS_ASSET_FORMAT_API:

    @omni.asset_validator.register_format()
    class SimReadyPackageFormat:
        """Asset-format handler for ``com.nvidia.simready.packaging.json``.

        Registers the SimReady package manifest with ``AssetFormatRegistry`` so
        ``ValidationEngine.is_asset_supported`` accepts it and the compliance
        checker walks its dependencies. BOM-based discovery is preferred when
        a BOM is present; otherwise we fall back to a directory walk that
        mirrors the skip rules used by the hash-from-filesystem algorithm.
        """

        def supports(self, asset_path: str) -> bool:
            return PurePosixPath(asset_path).name == PACKAGE_DEFINITION_FILENAME

        def get_dependencies(self, asset_path: str, uri_resolver) -> list[str]:
            data = _parse_package_json(asset_path)
            # The manifest itself is always the first element per the protocol.
            if data is None:
                return [asset_path]

            pkg_dir = uri_resolver.parent_uri(asset_path)

            # PKG.CONF.002: when ``com.nvidia.simready.root_usds.json``
            # declares the package's top-level USD entry points, those
            # entries ARE the dependency list — every other content
            # file (sub-USDs, textures, MDLs, JSON sidecars, ...) is
            # reachable transitively from a root USD's stage closure
            # or covered by manifest-fired rules, so we don't need to
            # walk the BOM at all in this branch.
            root_usds = _load_root_usds(pkg_dir, uri_resolver)
            if root_usds is not None:
                return [
                    asset_path,
                    *(uri_resolver.join_uri(pkg_dir, entry) for entry in sorted(root_usds)),
                ]

            # No root_usds.json: fall back to enumerating every content
            # file via the BOM (preferred) or a directory walk.
            # BomStructureChecker surfaces BOM_BROKEN as a distinct
            # diagnostic; the walk fallback covers BOM_ABSENT too.
            deps: list[str] = []
            status, bom, _ = _load_bom(pkg_dir, uri_resolver)
            if status == BOM_OK:
                for item in bom.get("items", []):
                    rel_path = item.get("relative_path") if isinstance(item, dict) else None
                    if isinstance(rel_path, str):
                        deps.append(uri_resolver.join_uri(pkg_dir, rel_path))
            else:
                for child_uri in _walk_uris(uri_resolver, pkg_dir):
                    rel = _relative_uri(pkg_dir, child_uri)
                    if _should_skip_content(rel):
                        continue
                    deps.append(child_uri)

            return [asset_path, *deps]


@omni.asset_validator.register_rule("PackageStructure")
@omni.asset_validator.register_requirements(cap.PackagingCoreRequirements.PKG_DEF_001)
class PackageDefinitionChecker(omni.asset_validator.BaseRuleChecker):
    """Checker for package definition validity (PKG.DEF.001)."""

    REQUIREMENT = cap.PackagingCoreRequirements.PKG_DEF_001

    def CheckFormatDependency(self, dependency):
        # Fire once per package, on the root manifest.
        if dependency.path != dependency.root_asset_path:
            return

        raw = _read_asset_bytes(dependency.path)
        if raw is None:
            return

        try:
            package_data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._AddFailedCheck(message=f"Package definition is not valid JSON: {exc}", requirement=self.REQUIREMENT)
            return

        if not isinstance(package_data, dict):
            self._AddFailedCheck(
                message=f"Package definition must be a JSON object, got {type(package_data).__name__}",
                requirement=self.REQUIREMENT,
            )
            return

        missing = [f for f in REQUIRED_FIELDS if f not in package_data]
        if missing:
            self._AddFailedCheck(
                message=f"Package definition is missing required field(s): {', '.join(missing)}",
                requirement=self.REQUIREMENT,
            )

        self._validate_format_version(package_data)
        self._validate_package_id(package_data)
        self._validate_license(package_data)
        self._validate_description(package_data)
        self._validate_metadata_array(package_data)
        self._validate_hash_field(package_data, "content_hash")
        self._validate_hash_field(package_data, "package_hash")

    # ------------------------------------------------------------------
    # Per-field validators
    # ------------------------------------------------------------------

    def _validate_format_version(self, data):
        if "format_version" not in data:
            return
        value = data["format_version"]
        if not isinstance(value, str):
            self._AddFailedCheck(
                message=f"'format_version' must be a string, got {type(value).__name__}",
                requirement=self.REQUIREMENT,
            )
            return
        if not FORMAT_VERSION_RE.fullmatch(value):
            self._AddFailedCheck(
                message=f"'format_version' must be in 'major.minor' format (e.g. '1.0'), got '{value}'",
                requirement=self.REQUIREMENT,
            )

    def _validate_package_id(self, data):
        if "package_id" not in data:
            return
        value = data["package_id"]
        if not isinstance(value, str):
            self._AddFailedCheck(
                message=f"'package_id' must be a string, got {type(value).__name__}",
                requirement=self.REQUIREMENT,
            )
            return
        if not value:
            self._AddFailedCheck(
                message="'package_id' must be a non-empty string",
                requirement=self.REQUIREMENT,
            )
            return
        if len(value) > PACKAGE_ID_MAX_LENGTH:
            self._AddFailedCheck(
                message=f"'package_id' exceeds {PACKAGE_ID_MAX_LENGTH} characters (length {len(value)})",
                requirement=self.REQUIREMENT,
            )
        forbidden = set(PACKAGE_ID_FORBIDDEN_RE.findall(value))
        if forbidden:
            chars = ", ".join(repr(c) for c in sorted(forbidden))
            self._AddFailedCheck(
                message=f"'package_id' contains forbidden character(s): {chars}",
                requirement=self.REQUIREMENT,
            )

    def _validate_license(self, data):
        if "license" not in data:
            return
        value = data["license"]
        if not isinstance(value, str):
            self._AddFailedCheck(
                message=f"'license' must be a string, got {type(value).__name__}",
                requirement=self.REQUIREMENT,
            )
            return
        if not value:
            self._AddFailedCheck(
                message="'license' must be a non-empty string",
                requirement=self.REQUIREMENT,
            )

    def _validate_description(self, data):
        if "description" not in data:
            return
        value = data["description"]
        if not isinstance(value, str):
            self._AddFailedCheck(
                message=f"'description' must be a string, got {type(value).__name__}",
                requirement=self.REQUIREMENT,
            )
            return
        if len(value) > DESCRIPTION_MAX_LENGTH:
            self._AddWarning(
                message=f"'description' exceeds {DESCRIPTION_MAX_LENGTH} characters ({len(value)}); detailed information should be provided through metadata files",
                requirement=self.REQUIREMENT,
            )

    def _validate_metadata_array(self, data):
        if "metadata" not in data:
            return
        metadata = data["metadata"]
        if not isinstance(metadata, list):
            self._AddFailedCheck(
                message=f"'metadata' must be an array, got {type(metadata).__name__}",
                requirement=self.REQUIREMENT,
            )
            return
        for i, entry in enumerate(metadata):
            if not isinstance(entry, dict):
                self._AddFailedCheck(
                    message=f"metadata[{i}] must be an object, got {type(entry).__name__}",
                    requirement=self.REQUIREMENT,
                )
                continue
            if "name" not in entry:
                self._AddFailedCheck(
                    message=f"metadata[{i}] is missing required field 'name'",
                    requirement=self.REQUIREMENT,
                )
            elif not isinstance(entry["name"], str):
                self._AddFailedCheck(
                    message=f"metadata[{i}].name must be a string, got {type(entry['name']).__name__}",
                    requirement=self.REQUIREMENT,
                )
            if "hash" not in entry:
                self._AddFailedCheck(
                    message=f"metadata[{i}] is missing required field 'hash'",
                    requirement=self.REQUIREMENT,
                )
            elif not isinstance(entry["hash"], dict):
                self._AddFailedCheck(
                    message=f"metadata[{i}].hash must be an object, got {type(entry['hash']).__name__}",
                    requirement=self.REQUIREMENT,
                )

    def _validate_hash_field(self, data, field_name):
        if field_name not in data:
            return
        value = data[field_name]
        if not isinstance(value, dict):
            self._AddFailedCheck(
                message=f"'{field_name}' must be a hash object, got {type(value).__name__}",
                requirement=self.REQUIREMENT,
            )


@omni.asset_validator.register_rule("MetadataFiles")
@omni.asset_validator.register_requirements(cap.PackagingCoreRequirements.PKG_META_001)
class MetadataFilesChecker(omni.asset_validator.BaseRuleChecker):
    """Checker for metadata file format (PKG.META.001).

    Scans ``.metadata/`` for JSON files and validates reverse-domain
    naming, UTF-8 JSON encoding, and ``format_version`` presence.
    Cross-checks files on disk against the package definition's
    ``metadata`` array.
    """

    REQUIREMENT = cap.PackagingCoreRequirements.PKG_META_001

    def CheckFormatDependency(self, dependency):
        if dependency.path != dependency.root_asset_path:
            return

        data = _parse_package_json(dependency.path)
        if data is None:
            return

        registered_names = set()
        metadata = data.get("metadata")
        if isinstance(metadata, list):
            for entry in metadata:
                if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                    registered_names.add(entry["name"])

        uri_resolver = dependency.uri_resolver
        pkg_dir = uri_resolver.parent_uri(dependency.path)
        meta_dir = uri_resolver.join_uri(pkg_dir, METADATA_DIR)

        if not uri_resolver.is_uri_prefix(meta_dir):
            if registered_names:
                self._AddFailedCheck(
                    message=f"Package definition references metadata files but '{METADATA_DIR}/' directory does not exist",
                    requirement=self.REQUIREMENT,
                )
            return

        meta_entries: list[tuple[str, str]] = []
        for child_uri in uri_resolver.list_uris(meta_dir):
            if uri_resolver.is_uri_prefix(child_uri):
                continue
            name = _uri_basename(child_uri)
            if not name.endswith(".json"):
                continue
            meta_entries.append((name, child_uri))
        meta_entries.sort(key=lambda e: e[0])
        files_on_disk = [name for name, _ in meta_entries]

        for filename, file_uri in meta_entries:
            if not REVERSE_DOMAIN_RE.fullmatch(filename):
                self._AddFailedCheck(
                    message=f"Metadata file '{filename}' does not use reverse domain notation",
                    requirement=self.REQUIREMENT,
                )

            raw = _read_asset_bytes(file_uri)
            if raw is None:
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                self._AddFailedCheck(
                    message=f"Metadata file '{filename}' is not valid UTF-8",
                    requirement=self.REQUIREMENT,
                )
                continue

            try:
                meta_content = json.loads(text)
            except json.JSONDecodeError as exc:
                self._AddFailedCheck(
                    message=f"Metadata file '{filename}' is not valid JSON: {exc}",
                    requirement=self.REQUIREMENT,
                )
                continue

            if not isinstance(meta_content, dict):
                self._AddFailedCheck(
                    message=f"Metadata file '{filename}' must be a JSON object, got {type(meta_content).__name__}",
                    requirement=self.REQUIREMENT,
                )
                continue

            fv = meta_content.get("format_version")
            if fv is None:
                self._AddFailedCheck(
                    message=f"Metadata file '{filename}' is missing required field 'format_version'",
                    requirement=self.REQUIREMENT,
                )
            elif not isinstance(fv, str):
                self._AddFailedCheck(
                    message=f"Metadata file '{filename}': 'format_version' must be a string, got {type(fv).__name__}",
                    requirement=self.REQUIREMENT,
                )
            elif not FORMAT_VERSION_RE.fullmatch(fv):
                self._AddFailedCheck(
                    message=f"Metadata file '{filename}': 'format_version' must be in 'major.minor' format, got '{fv}'",
                    requirement=self.REQUIREMENT,
                )

        for name in sorted(registered_names):
            if name not in files_on_disk:
                self._AddWarning(
                    message=f"Metadata entry '{name}' is listed in the package definition but not found in '{METADATA_DIR}/'",
                    requirement=self.REQUIREMENT,
                )


@omni.asset_validator.register_rule("HashObjectFormat")
@omni.asset_validator.register_requirements(cap.PackagingCoreRequirements.PKG_HASH_001)
class HashObjectFormatChecker(omni.asset_validator.BaseRuleChecker):
    """Checker for hash object conformance (PKG.HASH.001).

    Validates the format of every hash object in the package definition
    (``content_hash``, ``package_hash``, ``metadata[].hash``) and the
    BOM (``items[].hash``).  Also re-derives and compares every advertised
    digest under each of those keys:

    * ``sha256`` — always (stdlib).
    * ``blake2b`` — always (stdlib).
    * ``blake3`` — only when the optional ``blake3`` Python module is
      importable; otherwise the format check still runs but the value
      is not recomputed.
    * ``sha256-first1m`` — file-level only (BOM items, metadata files);
      not applicable to ``content_hash`` / ``package_hash``.

    For ``content_hash`` and ``package_hash``, BLAKE3 / BLAKE2b are
    computed by hashing the same canonical buffer the SHA-256 algorithm
    hashes — see the multi-algo paragraphs in PKG.HASH.001.
    """

    REQUIREMENT = cap.PackagingCoreRequirements.PKG_HASH_001

    def CheckFormatDependency(self, dependency):
        if dependency.path != dependency.root_asset_path:
            return

        data = _parse_package_json(dependency.path)
        if data is None:
            return

        for field in ("content_hash", "package_hash"):
            if field in data:
                self._check_hash_object(dependency, data[field], field)

        metadata = data.get("metadata")
        if isinstance(metadata, list):
            for i, entry in enumerate(metadata):
                if isinstance(entry, dict) and "hash" in entry:
                    self._check_hash_object(dependency, entry["hash"], f"metadata[{i}].hash")

        self._verify_bom_file_hashes(dependency)
        self._verify_metadata_entry_hashes(dependency, data)
        self._verify_content_hash(dependency, data)
        self._verify_package_hash(dependency, data)

    def _check_hash_object(self, dependency, obj, location):
        dep_label = _fmt_dep(dependency)
        if not isinstance(obj, dict):
            self._AddFailedCheck(
                message=f"'{location}' must be a hash object, got {type(obj).__name__} (dependency: {dep_label})",
                requirement=self.REQUIREMENT,
            )
            return

        if "sha256" not in obj:
            self._AddFailedCheck(
                message=f"'{location}' is missing required 'sha256' key (dependency: {dep_label})",
                requirement=self.REQUIREMENT,
            )
            return

        # Format-check sha256 + every optional named key. Per
        # hash-object-format.md, all named keys are inline lowercase hex;
        # the sidecar file reference form is reserved for future
        # tree-structured-digest keys and is rejected here.
        for key in VERIFIABLE_KEYS:
            if key not in obj:
                continue
            val = obj[key]
            if not isinstance(val, str):
                self._AddFailedCheck(
                    message=f"'{location}'.{key} must be a string, got {type(val).__name__} (dependency: {dep_label})",
                    requirement=self.REQUIREMENT,
                )
            elif not LOWERCASE_HEX_RE.fullmatch(val):
                self._AddFailedCheck(
                    message=f"'{location}'.{key} must be lowercase hexadecimal, got '{val}' (dependency: {dep_label})",
                    requirement=self.REQUIREMENT,
                )

    # ------------------------------------------------------------------
    # BOM per-file hash verification
    # ------------------------------------------------------------------

    def _verify_bom_file_hashes(self, dependency):
        """Re-hash every content file listed in the BOM and compare.

        Verifies every well-formed digest under ``VERIFIABLE_KEYS`` on
        each BOM item. Skipped when the BOM is absent (no per-file
        hashes to check) or broken (``BomStructureChecker`` surfaces
        that separately).
        """
        uri_resolver = dependency.uri_resolver
        pkg_dir = uri_resolver.parent_uri(dependency.path)
        status, bom, _ = _load_bom(pkg_dir, uri_resolver)
        if status != BOM_OK:
            return

        dep_label = _fmt_dep(dependency)

        for item in bom.get("items", []):
            if not isinstance(item, dict):
                continue
            rel_path = item.get("relative_path")
            hash_obj = item.get("hash")
            if not isinstance(rel_path, str) or not isinstance(hash_obj, dict):
                continue

            declared_keys = _declared_hex_keys(hash_obj, VERIFIABLE_KEYS)
            if not declared_keys:
                continue

            file_uri = uri_resolver.join_uri(pkg_dir, rel_path)
            raw = _read_asset_bytes(file_uri)
            if raw is None:
                self._AddFailedCheck(
                    message=(
                        f"BOM for package at '{pkg_dir}' lists '{rel_path}' "
                        f"but the file could not be read. (dependency: {dep_label})"
                    ),
                    requirement=self.REQUIREMENT,
                )
                continue

            for key in declared_keys:
                computed = _digest_from_bytes(raw, key)
                if computed is None:
                    continue  # blake3 module unavailable
                declared = hash_obj[key]
                if computed != declared:
                    self._AddFailedCheck(
                        message=(
                            f"BOM hash mismatch for '{rel_path}' in package '{pkg_dir}': "
                            f"BOM declares {key}='{declared}', "
                            f"actual file {key} is '{computed}'. (dependency: {dep_label})"
                        ),
                        requirement=self.REQUIREMENT,
                    )

    # ------------------------------------------------------------------
    # Per-metadata-file hash verification
    # ------------------------------------------------------------------

    def _verify_metadata_entry_hashes(self, dependency, data):
        """Re-hash each ``.metadata/<name>`` file against its declared
        ``metadata[].hash`` digests.

        Catches direct tampering of a metadata file when its declared
        ``sha256`` (or ``blake3`` / ``blake2b`` / ``sha256-first1m``)
        no longer matches the on-disk bytes. Without this, a tampered
        metadata file would only be detected indirectly via
        ``package_hash`` mismatch — and only when ``package_hash`` is
        present and the tampered hash also appears in the package hash
        buffer's input.
        """
        metadata = data.get("metadata")
        if not isinstance(metadata, list):
            return

        uri_resolver = dependency.uri_resolver
        pkg_dir = uri_resolver.parent_uri(dependency.path)
        meta_dir = uri_resolver.join_uri(pkg_dir, METADATA_DIR)
        if not uri_resolver.is_uri_prefix(meta_dir):
            # MetadataFilesChecker reports the missing .metadata/ dir.
            return

        dep_label = _fmt_dep(dependency)

        for i, entry in enumerate(metadata):
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            hash_obj = entry.get("hash")
            if not isinstance(name, str) or not isinstance(hash_obj, dict):
                continue

            declared_keys = _declared_hex_keys(hash_obj, VERIFIABLE_KEYS)
            if not declared_keys:
                continue

            file_uri = uri_resolver.join_uri(meta_dir, name)
            raw = _read_asset_bytes(file_uri)
            if raw is None:
                # MetadataFilesChecker reports the missing/unreadable file
                # via its own diagnostics; skip silently to avoid double-reporting.
                continue

            for key in declared_keys:
                computed = _digest_from_bytes(raw, key)
                if computed is None:
                    continue  # blake3 module unavailable
                declared = hash_obj[key]
                if computed != declared:
                    self._AddFailedCheck(
                        message=(
                            f"metadata[{i}].hash.{key} mismatch for '{name}': "
                            f"declared '{declared}', computed '{computed}' "
                            f"(dependency: {dep_label})"
                        ),
                        requirement=self.REQUIREMENT,
                    )

    # ------------------------------------------------------------------
    # Content hash verification (5-step algorithm + multi-algo extension)
    # ------------------------------------------------------------------

    def _verify_content_hash(self, dependency, data):
        if "content_hash" not in data or not _is_valid_hash_object(data["content_hash"]):
            return

        try:
            uri_resolver = dependency.uri_resolver
            pkg_dir = uri_resolver.parent_uri(dependency.path)
            status, bom, _ = _load_bom(pkg_dir, uri_resolver)
            if status == BOM_BROKEN:
                # A present-but-corrupt BOM is authoritative yet unreadable;
                # we don't know whether the declared content_hash was
                # computed-from-BOM or computed-from-filesystem, so silently
                # falling back to the filesystem would either hide the BOM
                # corruption (hashes happen to agree) or surface a misleading
                # "content_hash mismatch" (whose real cause is the broken
                # BOM). BomStructureChecker reports the BOM problem; we skip
                # hash verification to avoid the confusing diagnostic.
                return
            if status == BOM_OK:
                buf = _content_hash_buffer_from_bom(bom)
            else:  # BOM_ABSENT
                buf = _content_hash_buffer_from_filesystem(pkg_dir, uri_resolver)
            if buf is None:
                return
        except (OSError, RuntimeError, ValueError):
            return

        dep_label = _fmt_dep(dependency)

        def report(msg):
            self._AddFailedCheck(
                message=f"{msg} (dependency: {dep_label})",
                requirement=self.REQUIREMENT,
            )

        _compare_digests_against_buffer(
            data["content_hash"], buf, "content_hash", AGGREGATE_KEYS, report,
        )

    # ------------------------------------------------------------------
    # Package hash verification (6-step algorithm + multi-algo extension)
    # ------------------------------------------------------------------

    def _verify_package_hash(self, dependency, data):
        if "package_hash" not in data or not _is_valid_hash_object(data["package_hash"]):
            return

        buf = _package_hash_buffer(data)
        if buf is None:
            return

        dep_label = _fmt_dep(dependency)

        def report(msg):
            self._AddFailedCheck(
                message=f"{msg} (dependency: {dep_label})",
                requirement=self.REQUIREMENT,
            )

        _compare_digests_against_buffer(
            data["package_hash"], buf, "package_hash", AGGREGATE_KEYS, report,
        )
