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
uv run cz bump --yes

# Get the new version from __init__.py
VERSION=$(python -c "from git_llm_commit import __version__; print(__version__)")

# Push the new tag
git push origin "v${VERSION}"

# Build and upload
uv build
uv publish

echo "Successfully released version ${VERSION}"
