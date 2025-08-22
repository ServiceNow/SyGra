#!/bin/bash

set -e

echo "🚀 Setting up GraSP Library"
echo "============================="
echo "Installing GraSP library in development mode..."
pip install poetry
poetry install
cd grasp
poetry run pip install -e .
cd ..
echo "🚀 GraSP Library setup complete"
echo "============================="

