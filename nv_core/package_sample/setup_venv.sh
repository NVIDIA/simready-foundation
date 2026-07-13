#!/usr/bin/env bash
#
# setup_venv.sh — provision the .venv that the package_sample scripts and
# their integration tests expect.
#
# Creates (or reuses) a Python virtual environment at
# ``<package_sample>/.venv`` (i.e. right next to this script) and installs
# the packages listed in ``requirements.txt``.  When local wheel paths are
# supplied via --*-wheel flags, the corresponding packages are
# force-installed first so they take precedence over index versions.
#
# By default the only index is https://pypi.nvidia.com/.  Pass
# --extra-index <url> (repeatable) to add more.
#
# Re-running this script is safe: it upgrades existing installs in place.
#
# Prerequisites:
#   - Python 3.10+ on PATH (override with PYTHON_BIN=...)
#   - Network access to https://pypi.nvidia.com/ (publicly browsable)
#   - All three packages (simready-validate, omniverse-asset-validator,
#     omni-wrapp-minimal) must be resolvable from the configured indexes
#     or supplied as local wheels.  Packages not yet on pypi.nvidia.com
#     can be provided via --extra-index <url> or --*-wheel <path>.
#
# Usage:
#   ./setup_venv.sh                                     # everything from pypi.nvidia.com
#   ./setup_venv.sh --extra-index <url>                 # add a private index
#   ./setup_venv.sh --wrapp-wheel <path>                # WRAPP from a local wheel
#   ./setup_venv.sh --simready-validate-wheel <path>    # simready-validate from a local wheel
#   ./setup_venv.sh --asset-validator-wheel <path>      # omniverse-asset-validator from a local wheel
#   ./setup_venv.sh --recreate                          # wipe .venv/ first

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

NVIDIA_INDEX="https://pypi.nvidia.com/"

step() {
    printf '\n\033[1;36m==> %s\033[0m\n' "$*"
}

die() {
    printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2
    exit 1
}

usage() {
    sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'
}

# --- arg parsing ------------------------------------------------------------

WRAPP_WHEEL=""
VALIDATE_WHEEL=""
ASSET_VALIDATOR_WHEEL=""
EXTRA_INDEXES=()
RECREATE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --wrapp-wheel)
            [[ $# -ge 2 ]] || die "--wrapp-wheel requires a path argument"
            WRAPP_WHEEL="$2"
            shift 2
            ;;
        --simready-validate-wheel)
            [[ $# -ge 2 ]] || die "--simready-validate-wheel requires a path argument"
            VALIDATE_WHEEL="$2"
            shift 2
            ;;
        --asset-validator-wheel)
            [[ $# -ge 2 ]] || die "--asset-validator-wheel requires a path argument"
            ASSET_VALIDATOR_WHEEL="$2"
            shift 2
            ;;
        --extra-index)
            [[ $# -ge 2 ]] || die "--extra-index requires a URL argument"
            EXTRA_INDEXES+=("$2")
            shift 2
            ;;
        --recreate)
            RECREATE=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "Unknown argument: $1 (use --help)"
            ;;
    esac
done

if [[ -n "$WRAPP_WHEEL" ]]; then
    [[ -f "$WRAPP_WHEEL" ]] || die "WRAPP wheel not found at: $WRAPP_WHEEL"
fi
if [[ -n "$VALIDATE_WHEEL" ]]; then
    [[ -f "$VALIDATE_WHEEL" ]] || die "simready-validate wheel not found at: $VALIDATE_WHEEL"
fi
if [[ -n "$ASSET_VALIDATOR_WHEEL" ]]; then
    [[ -f "$ASSET_VALIDATOR_WHEEL" ]] || die "omniverse-asset-validator wheel not found at: $ASSET_VALIDATOR_WHEEL"
fi

command -v "$PYTHON_BIN" >/dev/null || die "'$PYTHON_BIN' not found on PATH (override with PYTHON_BIN=...)"

# --- venv -------------------------------------------------------------------

if [[ $RECREATE -eq 1 && -d "$VENV_DIR" ]]; then
    step "Removing existing .venv (--recreate)"
    rm -rf "$VENV_DIR"
fi

if [[ ! -d "$VENV_DIR" ]]; then
    step "Creating virtual environment at $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
else
    step "Reusing existing virtual environment at $VENV_DIR"
fi

VENV_PIP="$VENV_DIR/bin/pip"
VENV_PY="$VENV_DIR/bin/python"

step "Upgrading pip inside .venv"
"$VENV_PIP" install --upgrade pip

PIP_INSTALL=("$VENV_PIP" install --extra-index-url "$NVIDIA_INDEX")
for idx_url in "${EXTRA_INDEXES[@]+"${EXTRA_INDEXES[@]}"}"; do
    PIP_INSTALL+=(--extra-index-url "$idx_url")
done

# --- 1. omniverse-asset-validator ------------------------------------------

if [[ -n "$ASSET_VALIDATOR_WHEEL" ]]; then
    step "Installing omniverse-asset-validator from local wheel: $ASSET_VALIDATOR_WHEEL"
    # Force-reinstall so a locally-built wheel overrides any older pypi install,
    # then a plain install picks up any missing runtime deps.
    "$VENV_PIP" install --force-reinstall --no-deps "$ASSET_VALIDATOR_WHEEL"
fi

# --- 2. wheel overrides (simready-validate, WRAPP) -------------------------

if [[ -n "$VALIDATE_WHEEL" ]]; then
    step "Installing simready-validate from local wheel: $VALIDATE_WHEEL"
    # Force-reinstall so local edits in a rebuilt wheel override an older
    # install, then a plain install picks up any missing runtime deps.
    "$VENV_PIP" install --force-reinstall --no-deps "$VALIDATE_WHEEL"
    "${PIP_INSTALL[@]}" "$VALIDATE_WHEEL"
fi

if [[ -n "$WRAPP_WHEEL" ]]; then
    step "Installing WRAPP from local wheel: $WRAPP_WHEEL"
    "${PIP_INSTALL[@]}" "${WRAPP_WHEEL}[local]"
fi

# --- 3. requirements.txt ---------------------------------------------------

step "Installing dependencies from requirements.txt"
"${PIP_INSTALL[@]}" -r "$SCRIPT_DIR/requirements.txt"

# --- sanity check -----------------------------------------------------------

step "Done. Sanity check:"
"$VENV_PY" - <<'PY'
import simready.validate as sv
import omni.asset_validator as av
import omni.usd_profiles as up
import wrapp
print(f"  simready.validate       {sv.__file__}")
print(f"  omni.asset_validator    {av.__file__}")
print(f"  omni.usd_profiles       {up.__file__}")
print(f"  wrapp                   {wrapp.__file__}")
PY

# Verify the local-file storage backend is actually wired up; without
# the ``[local]`` extra (or an equivalent backend) WRAPP fails with
# "No storage backend available to handle file URL" as soon as
# the create step touches a local path, long after this script exits.
step "Verifying WRAPP storage backends"
WRAPP_VERSION_OUT="$("$VENV_DIR/bin/wrapp" version 2>&1 || true)"
printf '%s\n' "$WRAPP_VERSION_OUT"
if printf '%s\n' "$WRAPP_VERSION_OUT" | grep -qE '^Local File System: *DISABLED'; then
    die "WRAPP's Local File System backend is DISABLED after install — the ``[local]`` extra did not apply.  Check the pip output above for a warning about the extra, and make sure --wrapp-wheel points at a wheel that declares it (e.g. ``omni_wrapp_minimal-*.whl``)."
fi

cat <<EOF

Next steps:
  cd $SCRIPT_DIR
  source .venv/bin/activate
  pytest tests/ -v
EOF
