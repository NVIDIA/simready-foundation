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
"""simready-benchmark-kit-suite -- editable install + verify.

By default this script does NOT clean caches or uninstall old versions:
that work is wasted on a fresh build environment. Pass `--clean` or
`--rebuild` (or use `--clean-only`) to force the legacy clean step when
you actually need a deep reset.

Usage:
    py install.py              Install/update the suite
    py install.py --clean      Clean caches and uninstall old versions, then install
    py install.py --rebuild    Alias for --clean
    py install.py --clean-only Only clean; do not install
    py install.py --remove     Uninstall the suite only (NO install). Use this
                               before testing path-based test-pack discovery so
                               the entry-point install can't shadow your result.
    py install.py --verify     Only verify the installation
    py install.py --run-tests  Install and run the utility-test suite
    py install.py --help       Show this help

This script installs ONLY simready-benchmark-kit-suite (this repo).
The framework (simready-benchmark, simready-benchmark-engine-kit) is NOT touched by
--remove. To uninstall the framework + Kit plugin too, run
simready-explorer/source/libraries/simready-benchmark/install.bat --remove.

The framework (simready-benchmark) is a hard dependency -- pip resolves it
automatically from PyPI if it is not already in site-packages. If you
are working from a local framework clone (no PyPI), build and install
its wheels first from the simready-explorer repo:

    cd <path-to-simready-explorer>
    repo.bat python_package          (Windows; ./repo.sh on Linux/macOS)
    pip install _build/packages/dist/simready_benchmark-*.whl \
                _build/packages/dist/simready_benchmark_engine_kit-*.whl

Then come back here and run `py install.py`. pip's resolver will pick up
the just-installed framework and skip the PyPI fetch.
"""
import os
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_NAMES = [
    "simready-benchmark-kit-suite",
    # Legacy names: uninstall if a previous install lingers in site-packages
    "simready-test-kit-suite",
    "simready-tests-kit",
]


def _print_header(msg):
    print("\n" + "=" * 60)
    print("  " + msg)
    print("=" * 60)


def _print_step(msg):
    print("  [*] " + msg)


def _print_ok(msg):
    print("  [OK] " + msg)


def _print_fail(msg):
    print("  [FAIL] " + msg)


def clean_pycache():
    _print_step("Removing __pycache__ directories and .pyc files...")
    removed = 0
    for root, dirs, files in os.walk(SCRIPT_DIR):
        if ".git" in root:
            continue
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                removed += 1
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                try:
                    os.remove(os.path.join(root, f))
                    removed += 1
                except OSError:
                    pass
    _print_ok("Removed %d cached items" % removed)


def clean_build_artifacts():
    _print_step("Removing build artifacts (.egg-info, dist, build)...")
    removed = 0
    for root, dirs, _ in os.walk(SCRIPT_DIR):
        if ".git" in root:
            continue
        for d in list(dirs):
            if d.endswith(".egg-info") or d in ("dist", "build"):
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                removed += 1
                dirs.remove(d)
    _print_ok("Removed %d build artifacts" % removed)


def check_framework_available():
    """Return True if `simready_benchmark` is importable from sys.executable.

    Pre-empts pip's cryptic "No matching distribution found for simready-benchmark"
    when the user runs install.bat against a Python that doesn't have the
    framework installed. install.bat uses `py` (Windows Python launcher,
    default Python on PATH); if you installed simready-benchmark into a different
    Python (e.g. a venv, or the simready-explorer bundled Python at
    `_build/target-deps/python/python.exe`), `py` won't see it.
    """
    result = subprocess.run(
        [sys.executable, "-c", "import simready_benchmark"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def explain_framework_missing():
    _print_fail("simready-benchmark is not installed in this Python.")
    _print_fail("Active Python: %s" % sys.executable)
    _print_fail("")
    _print_fail("Two options:")
    _print_fail("")
    _print_fail("(A) Run this script with a Python that already has simready-benchmark.")
    _print_fail("    If you have a built simready-explorer clone, its bundled Python")
    _print_fail("    is the canonical one (matches what simready_benchmark.bat uses):")
    _print_fail("")
    _print_fail("      <path-to-simready-explorer>\\_build\\target-deps\\python\\python.exe \\")
    _print_fail("        %s" % os.path.join(SCRIPT_DIR, "install.py"))
    _print_fail("")
    _print_fail("(B) Install simready-benchmark into this Python first, then re-run install.bat.")
    _print_fail("    From a built simready-explorer clone:")
    _print_fail("")
    _print_fail("      %s -m pip install \\" % sys.executable)
    _print_fail("        <simready-explorer>\\_build\\packages\\dist\\simready_benchmark-*.whl \\")
    _print_fail("        <simready-explorer>\\_build\\packages\\dist\\simready_benchmark_engine_kit-*.whl")
    _print_fail("")
    _print_fail("    Or from PyPI (once published):")
    _print_fail("      %s -m pip install simready-benchmark[kit]" % sys.executable)


def uninstall_old_packages():
    _print_step("Uninstalling old package versions...")
    for name in PACKAGE_NAMES:
        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", name, "-y"],
            capture_output=True,
            text=True,
        )
    _print_ok("Old versions removed")


def install_package():
    _print_step("Installing simready-benchmark-kit-suite (editable)...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--no-warn-script-location", "-q"],
        cwd=SCRIPT_DIR,
    )
    if result.returncode != 0:
        _print_fail("pip install failed (exit %d)" % result.returncode)
        _print_fail("If 'simready-benchmark' resolution failed, the framework is not")
        _print_fail("yet installed. Either install it from PyPI:")
        _print_fail("  pip install simready-benchmark")
        _print_fail("or build and install its wheels from a local clone of")
        _print_fail("simready-explorer:")
        _print_fail("  cd <path-to-simready-explorer>")
        _print_fail("  repo.bat python_package   (Windows; ./repo.sh on Linux/macOS)")
        _print_fail("  pip install _build/packages/dist/simready_benchmark-*.whl \\")
        _print_fail("              _build/packages/dist/simready_benchmark_engine_kit-*.whl")
        return False
    _print_ok("Suite installed")
    return True


VERIFY_CHECKS = [
    ("simready_benchmark (framework dep)", "import simready_benchmark; print(simready_benchmark.PROTOCOL_VERSION)"),
    ("simready_benchmark_kit_suite", "import simready_benchmark_kit_suite; print('ok')"),
    (
        "tests entry pt",
        (
            "from importlib.metadata import entry_points; "
            "eps = entry_points(group='simready_benchmark.tests'); "
            "names = [ep.name for ep in eps]; "
            "assert 'simready_benchmark_kit_suite' in names, str(names); "
            "print('suite registered')"
        ),
    ),
]


def verify_installation():
    _print_step("Verifying installation...")
    all_ok = True
    for name, code in VERIFY_CHECKS:
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=SCRIPT_DIR,
        )
        if r.returncode == 0:
            _print_ok("%s: %s" % (name, r.stdout.strip()))
        else:
            _print_fail("%s: %s" % (name, r.stderr.strip()))
            all_ok = False
    return all_ok


def run_quick_tests():
    _print_step("Running quick test suite...")
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q", "--tb=short", "--no-header"],
        cwd=SCRIPT_DIR,
    )
    if r.returncode == 0:
        _print_ok("All tests passed")
        return True
    _print_fail("Some tests failed (exit %d)" % r.returncode)
    return False


def remove_suite():
    """Uninstall simready-benchmark-kit-suite (and legacy names) only.

    Verifies removal with `pip list` so the user sees an obvious result
    rather than a silent "Skipping <pkg> as it is not installed" from
    pip. The framework + Kit plugin are NOT touched -- use
    simready-explorer's install.bat --remove for those.
    """
    _print_header("Uninstalling simready-benchmark-kit-suite")
    _print_step("Active Python: %s" % sys.executable)
    uninstall_old_packages()

    # Re-check after uninstall. pip exits 0 even when "Skipping ... not
    # installed", so a manual confirmation is the only way to be sure.
    _print_step("Verifying the suite is gone...")
    check = subprocess.run(
        [
            sys.executable,
            "-c",
            "from importlib.metadata import entry_points; "
            "eps = entry_points(group='simready_benchmark.tests'); "
            "names = [ep.name for ep in eps]; "
            "print('simready_benchmark_kit_suite' in names)",
        ],
        capture_output=True,
        text=True,
    )
    if check.returncode == 0 and check.stdout.strip() == "False":
        _print_ok("simready_benchmark_kit_suite is no longer entry-point-registered")
    elif check.returncode == 0 and check.stdout.strip() == "True":
        _print_fail("simready_benchmark_kit_suite is STILL entry-point-registered.")
        _print_fail("It may be installed in a different Python or pinned by")
        _print_fail("some other mechanism. Try: pip show simready-benchmark-kit-suite")
        return 1
    else:
        _print_fail("Could not verify removal: %s" % check.stderr.strip())

    print()
    print("  Next: test path-based discovery by pointing engines.toml")
    print("        [tests].paths at the suite SOURCE dir:")
    print(
        "          %s"
        % os.path.join(SCRIPT_DIR, "packages", "simready_benchmark_kit_suite", "src", "simready_benchmark_kit_suite")
    )
    print("        Then run: simready-benchmark --sr-specs <path> --list-tests")
    return 0


def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__)
        return 0

    clean_only = "--clean-only" in args
    verify_only = "--verify" in args
    run_tests = "--run-tests" in args
    remove_only = "--remove" in args
    do_clean = clean_only or "--clean" in args or "--rebuild" in args

    if remove_only:
        return remove_suite()

    if verify_only:
        _print_header("Verifying simready-benchmark-kit-suite installation")
        return 0 if verify_installation() else 1

    _print_header("simready-benchmark-kit-suite Setup")

    # Pre-flight: bail with an actionable error if simready-benchmark isn't in
    # this Python. Otherwise pip will fail with a cryptic
    # "No matching distribution found for simready-benchmark>=N" deep into the
    # install and the user is left guessing about Python-env confusion.
    if not check_framework_available():
        _print_header("simready-benchmark not found in this Python")
        explain_framework_missing()
        print("\nSetup FAILED.")
        return 1

    if do_clean:
        _print_header("Cleaning caches and old installations")
        clean_pycache()
        clean_build_artifacts()
        uninstall_old_packages()

        if clean_only:
            _print_ok("Clean complete. Run 'py install.py' to install.")
            return 0

    _print_header("Installing the suite")
    if not install_package():
        print("\nSetup FAILED.")
        return 1

    _print_header("Verifying installation")
    if not verify_installation():
        print("\nSetup completed but verification FAILED.")
        return 1

    if run_tests:
        _print_header("Running test suite")
        if not run_quick_tests():
            print("\nInstallation succeeded but some tests failed.")
            return 1

    _print_header("Setup Complete")
    print("\n  Suite installed. `simready-benchmark --list-tests` will now show the FET catalog.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
