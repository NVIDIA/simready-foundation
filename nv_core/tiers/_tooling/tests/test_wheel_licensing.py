# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""License declarations and built-wheel contents for every Foundation tier."""

from email.parser import BytesParser
import os
from pathlib import Path
import tomllib
import zipfile

import pytest

TIERS = Path(__file__).resolve().parents[2]
TIER_NAMES = sorted(path.name for path in TIERS.glob("simready_foundation_tier_*")
                    if (path / "pyproject.toml").is_file())


@pytest.mark.parametrize("tier_name", TIER_NAMES)
def test_tier_license_declaration(tier_name):
    tier = TIERS / tier_name
    config = tomllib.loads((tier / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["project"]["license"] == "Apache-2.0"
    assert config["project"]["license-files"] == ["LICENSE.txt"]
    assert b"Apache License" in (tier / "LICENSE.txt").read_bytes()
    notices = config["tool"]["hatch"]["build"]["hooks"]["custom"]["package_licenses"]
    assert notices and len(notices) == len(set(notices))
    for name in notices:
        assert (TIERS.parents[1] / "PACKAGE-LICENSES" / name).is_file()


@pytest.mark.parametrize("tier_name", TIER_NAMES)
def test_built_tier_wheel_includes_licenses(tier_name):
    directory = os.environ.get("SIMREADY_LICENSE_WHEEL_DIR")
    if not directory and os.environ.get("SIMREADY_REQUIRE_BUILT_TIER_WHEEL") == "1":
        directory = TIERS / "_build/dist"
    if not directory:
        pytest.skip("Set SIMREADY_LICENSE_WHEEL_DIR to qualify built tier wheels")
    wheels = list(Path(directory).glob(tier_name + "-*.whl"))
    assert len(wheels) == 1, wheels
    tier = TIERS / tier_name
    config = tomllib.loads((tier / "pyproject.toml").read_text(encoding="utf-8"))
    notices = config["tool"]["hatch"]["build"]["hooks"]["custom"]["package_licenses"]
    with zipfile.ZipFile(wheels[0]) as archive:
        metadata_path, = (name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = BytesParser().parsebytes(archive.read(metadata_path))
        assert metadata["License-Expression"] == "Apache-2.0"
        assert "LICENSE.txt" in metadata.get_all("License-File", [])
        license_path = metadata_path.removesuffix("METADATA") + "licenses/LICENSE.txt"
        assert archive.read(license_path) == (tier / "LICENSE.txt").read_bytes()
        for name in notices:
            assert archive.read("PACKAGE-LICENSES/" + name) == (
                TIERS.parents[1] / "PACKAGE-LICENSES" / name
            ).read_bytes()
