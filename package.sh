#!/bin/sh
# Build the source archive (dist/trakcli-<version>.tar.gz) for the Homebrew formula.
set -e
cd "$(dirname "$0")"
rm -rf dist
uv build --sdist
