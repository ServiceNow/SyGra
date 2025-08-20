#!/bin/bash

set -e

echo "🚀 Setting up GraSP Library"
echo "============================="
echo "Installing GraSP library in development mode..."
cd grasp
poetry run pip install -e .
cd ..

