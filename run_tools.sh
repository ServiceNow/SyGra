#!/bin/bash

# Wrapper script for running GraSP tools

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd "$SCRIPT_DIR" || { echo "Failed to change directory to $SCRIPT_DIR"; exit 1; }

python3 -m grasp.tools "$@"

exit $?