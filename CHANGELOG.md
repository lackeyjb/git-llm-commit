# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] - 2025-02-05

### Added

- Initial version with changelog

## v1.2.1 (2025-02-05)

### Fix

- add version diagnostics to release script

## v1.2.0 (2025-02-05)

### Feat

- **release-script**: enhance version bump handling in release process
- add LLM_COMMIT_TEMPERATURE env var to control model creativity

### Fix

- push changelog updates in release script
- handle existing tags gracefully in release script
- improve version extraction in release script

## v1.1.0 (2025-02-05)

### Feat

- integrate Commitizen for version management and changelog generation

### Refactor

- **build**: switch build system from setuptools to hatch
