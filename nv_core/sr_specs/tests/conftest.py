# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Session-wide pytest bootstrap for the SimReady Foundation test suite.

`conftest.py` is a special filename pytest auto-loads BEFORE collecting any
test_*.py module in this directory or below. We use that ordering to run the
simready.validate codegen pipeline once at module level (below the imports).

Without this, importing any of the capability validation modules from
docs/capabilities/aif/*/validation.py raises AttributeError because they
reference enums like `omni.capabilities.AifMetadataRequirements` that do not
physically exist in the omni.capabilities package: they are generated from
JSON/TOML requirement definitions and INJECTED into that module at runtime
by the loader. The same load also populates RequirementsRegistry, which is
what `tests/_harness.py` queries to translate spec codes (like "AM.002") to
the actual rule classes the engine should run.

Adding a new domain (robotics, etc.) does not require touching this file as
long as the new domain's requirements live under docs/capabilities/.
"""
from pathlib import Path

from simready.validate.impl.loader import load_validation_implementation

# Walk up: tests/conftest.py -> tests/ -> sr_specs/. The docs/ tree lives
# inside sr_specs/ and holds the capability/feature/profile definitions the
# loader needs to read.
_SR_SPECS_DIR = Path(__file__).resolve().parent.parent
_DOCS_DIR = _SR_SPECS_DIR / "docs"

# Module-level call: runs exactly once when pytest imports this conftest, BEFORE
# any test_*.py module is collected. The loader:
#   - reads JSON/TOML requirement definitions under docs/capabilities/,
#   - generates Python enums for them and injects them into omni.capabilities,
#   - imports every capability's validation.py (which causes the @register_rule
#     and @register_requirements decorators to populate the framework registries),
#   - registers features (docs/features) and profiles (docs/profiles).
# This is the same setup the `simready-validate` CLI performs when it starts.
load_validation_implementation(
    rules_and_requirements_paths=[_DOCS_DIR / "capabilities"],
    features_paths=[_DOCS_DIR / "features"],
    profiles_paths=[_DOCS_DIR / "profiles" / "profiles.toml"],
)
