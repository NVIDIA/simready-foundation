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
"""Guard the test pack against unowned filesystem cleanup."""

import re
from pathlib import Path


def test_suite_and_installer_do_not_delete_files_directly():
    suite_root = Path(__file__).resolve().parents[4]
    checked_roots = (
        suite_root / "install.py",
        suite_root / "packages" / "simready_benchmark_kit_suite" / "src",
    )
    forbidden = re.compile(r"(?:shutil\.rmtree|os\.(?:remove|unlink)|\.unlink|\.rmdir)\s*\(")
    violations = []

    for checked_root in checked_roots:
        sources = (checked_root,) if checked_root.is_file() else checked_root.rglob("*.py")
        for source in sources:
            for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
                if forbidden.search(line):
                    violations.append("%s:%d" % (source.relative_to(suite_root), line_number))

    assert not violations, "Filesystem deletion found outside the Benchmark ownership gateway: %s" % ", ".join(
        violations
    )
