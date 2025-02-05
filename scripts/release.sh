#!/bin/bash
set -eo pipefail

# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Use commitizen to bump version based on conventional commits
# This will:
# 1. Determine version bump from commit messages
# 2. Update __version__ in __init__.py
# 3. Create git tag
# 4. Generate changelog
if ! uv run cz bump --yes; then
    echo "No version bump needed"
    exit 0
fi

# Get the new version directly from __init__.py
VERSION=$(grep "__version__" src/git_llm_commit/__init__.py | cut -d'"' -f2)

# Push the new tag
git push origin "v${VERSION}"

# Build and upload
uv build
uv publish

echo "Successfully released version ${VERSION}"
