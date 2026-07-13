"""Small shared helpers for the package sample workflow."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse


def local_path_from_url(url: str) -> Path:
    """Resolve a local-or-``file://`` URL to a :class:`Path`."""
    parsed = urlparse(url)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    return Path(url)
