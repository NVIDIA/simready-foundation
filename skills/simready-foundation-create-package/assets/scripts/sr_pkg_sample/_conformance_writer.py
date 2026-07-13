"""Serialise validation results and root-USD metadata to ``.metadata/``.

Provides helpers for the two JSON artefacts pre-validation writes:

* **Conformance metadata** — one
  ``com.nvidia.simready.conformance.{profile}@{ver}.json`` per profile
  (PKG.CONF.001).
* **Root-USDs metadata** —
  ``com.nvidia.simready.root_usds.json`` listing the top-level USD
  entry points of the asset.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import quote

METADATA_FOLDER = ".metadata"
CONFORMANCE_PREFIX = "com.nvidia.simready.conformance"
ROOT_USDS_FILENAME = "com.nvidia.simready.root_usds.json"
BOM_FILENAME = "com.nvidia.simready.packaging.bom.json"
FORMAT_VERSION = "1.0"

_USD_SUFFIXES = frozenset({".usd", ".usda"})


def conformance_filename(profile_id: str, profile_version: str) -> str:
    """Build the canonical filename for a conformance JSON.

    Percent-encodes ``@`` and ``%`` in the profile id and version per
    the PKG.CONF.001 file-naming rule.
    """
    safe_profile = quote(profile_id, safe="")
    safe_version = quote(profile_version, safe="")
    return f"{CONFORMANCE_PREFIX}.{safe_profile}@{safe_version}.json"


def write_conformance_metadata(
    dest: Path,
    profile_id: str,
    profile_version: str,
    asset_results: list[dict],
    *,
    content_hash: Optional[Dict[str, str]] = None,
) -> Path:
    """Write a conformance JSON into ``dest/.metadata/``.

    Parameters
    ----------
    dest:
        Source folder root (the ``.metadata/`` subdirectory is created
        automatically).
    profile_id, profile_version:
        Profile coordinates recorded in the JSON and encoded into the
        filename.
    asset_results:
        Pre-built ``assets`` array — one dict per validated root USD,
        each carrying ``{"asset": "<rel>", "features": [...]}``.
        Callers build this from the engine's
        :class:`AssetValidationResult`.
    content_hash:
        Optional hash object (PKG.HASH.001) to embed in the file.

    Returns
    -------
    Path
        Absolute path of the file that was written.
    """
    metadata_dir = dest / METADATA_FOLDER
    metadata_dir.mkdir(exist_ok=True)

    payload: dict = {
        "format_version": FORMAT_VERSION,
        "profile": profile_id,
        "profile_version": profile_version,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "assets": asset_results,
    }
    if content_hash is not None:
        payload["content_hash"] = content_hash

    filename = conformance_filename(profile_id, profile_version)
    out = metadata_dir / filename
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def write_bom_metadata(dest: Path, bom: dict) -> Path:
    """Write the BOM JSON into ``dest/.metadata/``.

    Returns the absolute path of the file that was written.
    """
    metadata_dir = dest / METADATA_FOLDER
    metadata_dir.mkdir(exist_ok=True)
    out = metadata_dir / BOM_FILENAME
    out.write_text(json.dumps(bom, indent=2) + "\n", encoding="utf-8")
    return out


def write_root_usds_metadata(dest: Path, entries: list[str]) -> Path:
    """Write ``root_usds.json`` into ``dest/.metadata/``.

    Parameters
    ----------
    dest:
        Source folder root.
    entries:
        Forward-slash relative paths of root USD files (e.g.
        ``["simready_usd/sm_apple_a01_01.usd"]``).

    Returns
    -------
    Path
        Absolute path of the file that was written.
    """
    metadata_dir = dest / METADATA_FOLDER
    metadata_dir.mkdir(exist_ok=True)
    payload = {
        "format_version": FORMAT_VERSION,
        "entries": sorted(entries),
    }
    out = metadata_dir / ROOT_USDS_FILENAME
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def read_root_usds_metadata(source: Path) -> list[str] | None:
    """Read an existing ``root_usds.json`` from ``source/.metadata/``.

    Returns the list of root-USD relative paths, or ``None`` if the
    file does not exist.
    """
    path = source / METADATA_FOLDER / ROOT_USDS_FILENAME
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("entries", [])


def build_asset_results(
    results_by_usd: "list[tuple[str, object | None]]",
) -> list[dict]:
    """Convert engine results into the ``assets`` array for a conformance JSON.

    Parameters
    ----------
    results_by_usd:
        List of ``(relative_path, result)`` pairs as returned by
        :func:`simready.validate.validate_asset_list` zipped with the
        corresponding relative paths.

    Returns
    -------
    list[dict]
        One entry per asset, each with ``asset`` and ``features`` keys
        matching the PKG.CONF.001 schema.
    """
    assets: list[dict] = []
    for rel_path, result in results_by_usd:
        if result is None:
            continue
        features_list: list[dict] = []
        for fid, summary in sorted(result.features_summary.items()):
            dep_str = summary.get("dependencies", "[]")
            try:
                deps = eval(dep_str) if isinstance(dep_str, str) else dep_str
            except Exception:
                deps = []
            failing = []
            if not summary.get("passed", False):
                failing_str = summary.get("failing requirements", "[]")
                try:
                    failing = eval(failing_str) if isinstance(failing_str, str) else failing_str
                except Exception:
                    failing = []
            features_list.append({
                fid: {
                    "version": summary.get("version", "0.0.0"),
                    "passed": bool(summary.get("passed", False)),
                    "failing_requirements": failing,
                    "dependencies": deps,
                }
            })
        assets.append({
            "asset": rel_path,
            "features": features_list,
        })
    return assets
