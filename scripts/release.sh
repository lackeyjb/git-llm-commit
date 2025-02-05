#!/bin/bash
set -e

VERSION=${1}
if [ -z "$VERSION" ]; then
    echo "Error: Version number required"
    echo "Usage: $0 VERSION"
    exit 1
fi

# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Create and push tag
git tag -a "v${VERSION}" -m "Release ${VERSION}"
git push origin "v${VERSION}"

# Build and upload
python -m build
twine check dist/*
twine upload dist/*

echo "Successfully released version ${VERSION}"
