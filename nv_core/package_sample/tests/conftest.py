"""Shared fixtures for the package_sample integration tests.

The per-phase tests drive the public ``sr_pkg_sample.*`` Python API
directly and assert on the returned result objects; the end-to-end
test invokes ``create_simready_package.py`` as a subprocess to cover
the CLI surface.

``_validation_runtime`` is a session-scoped autouse fixture that
mirrors what ``create_simready_package.py`` does at startup: it
installs the Kit shim and calls ``simready.validate.initialize`` once
per test session.  The step modules assume that runtime is ready, so
without this fixture every direct API call below would fail.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

pytest_plugins = ("pytest_asyncio",)

# ``simready_foundations/nv_core/package_sample/tests/`` → the sample dir is
# one level up, and the foundations root is two levels up from there.
_TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_SAMPLE_DIR = _TESTS_DIR.parent
FOUNDATIONS_DIR = PACKAGE_SAMPLE_DIR.parent.parent

# Make ``import sr_pkg_sample`` resolve when pytest is launched from outside the
# package_sample directory.
if str(PACKAGE_SAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SAMPLE_DIR))

SAMPLE_SOURCE = (
    FOUNDATIONS_DIR
    / "sample_content"
    / "common_assets"
    / "props_general"
    / "apple_a01"
    / "simready_usd"
)


@pytest.fixture(scope="session", autouse=True)
def _validation_runtime() -> None:
    """Initialise simready.validate once per session."""
    from sr_pkg_sample import FOUNDATIONS_DOCS_DIR
    import simready.validate as sv

    sv.initialize(
        rules_and_requirements_paths=[FOUNDATIONS_DOCS_DIR / "capabilities"],
        features_paths=[FOUNDATIONS_DOCS_DIR / "features"],
        profiles_paths=[FOUNDATIONS_DOCS_DIR / "profiles" / "profiles.toml"],
    )


@pytest.fixture(scope="session")
def package_sample_dir() -> Path:
    """Root directory of the package_sample tree."""
    return PACKAGE_SAMPLE_DIR


@pytest.fixture(scope="session")
def foundations_dir() -> Path:
    """Root of the ``simready_foundations`` checkout."""
    return FOUNDATIONS_DIR


def _ensure_thumbnails(source_dir: Path) -> None:
    """Create ``.thumbs/256x256/<file>.png`` thumbnails for every USD file.

    The committed sample assets ship a legacy-convention thumbnail
    (e.g. ``.thumbs/sm_apple_a01_01_thumbnail.png``) but not the
    ``256x256/<file>.usd.png`` layout required by SR.002.  This helper
    copies the legacy file into the new location so that
    ``Package-Candidate`` pre-validation passes.
    """
    thumbs_dir = source_dir / ".thumbs"
    if not thumbs_dir.is_dir():
        return
    dest_dir = thumbs_dir / "256x256"
    dest_dir.mkdir(exist_ok=True)
    for usd in source_dir.glob("*.usd"):
        expected = dest_dir / f"{usd.name}.png"
        if expected.exists():
            continue
        legacy = next(thumbs_dir.glob("*.png"), None)
        if legacy:
            shutil.copy2(legacy, expected)
        else:
            expected.write_bytes(b"\x89PNG")


@pytest.fixture(scope="session")
def _sample_source_orig() -> Path:
    """Unmodified sample source folder on disk."""
    if not SAMPLE_SOURCE.is_dir():
        pytest.skip(f"Sample source folder missing: {SAMPLE_SOURCE}")
    return SAMPLE_SOURCE


@pytest.fixture(scope="session")
def sample_source(_sample_source_orig: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-scoped copy of the sample source with SR.002 thumbnails.

    The committed sample content uses a legacy thumbnail convention.
    This fixture copies the tree once per session and adds the
    ``256x256`` thumbnails so ``Package-Candidate`` pre-validation
    (which now includes FET033 / SR.002) passes.
    """
    root = tmp_path_factory.mktemp("sample_source")
    dest = root / _sample_source_orig.parent.name / _sample_source_orig.name
    shutil.copytree(_sample_source_orig, dest)
    _ensure_thumbnails(dest)
    return dest


@pytest.fixture
def sample_source_copy(sample_source: Path, tmp_path: Path) -> Path:
    """Writable per-test copy of the sample source folder.

    Nests the copy inside ``<asset>/<intermediate>/`` (e.g.
    ``apple_a01/simready_usd/``) so NP.005 (asset-folder-structure)
    sees the expected hierarchy.  Strips ``.metadata/`` if a previous
    run left one behind so every test starts from a clean state.
    """
    dest = tmp_path / sample_source.parent.name / sample_source.name
    shutil.copytree(sample_source, dest)
    stale_meta = dest / ".metadata"
    if stale_meta.is_dir():
        shutil.rmtree(stale_meta)
    return dest
