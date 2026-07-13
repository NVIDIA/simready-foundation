#!/bin/bash
set -e
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
pushd "$SCRIPT_DIR" > /dev/null
./repo.sh usd_profiles_codegen "$@"
popd > /dev/null
