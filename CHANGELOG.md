# 📜 CHANGELOG.md - Dazzlelink

All notable changes to this project will be documented in this file. This project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.7.0] - 2026-03-31

### Added
- Relative path support for portable dazzlelinks across synced machines (Refs #13)
  - `target_representations.relative_path` computed during `create`
  - `execute` fallback chain: absolute -> relative -> path_representations
  - Enables dazzlelinks to work when library mount points differ between machines
- git-repokit-common subtree at `scripts/` for shared hooks and tools
- File association scripts for Windows `.dazzlelink` extension

### Fixed
- Renamed `pyproject-toml.py` to `pyproject.toml` for PyPI compatibility

## [0.6.0] - 2025-03-28

### Added

- Complete modularization of codebase for better maintainability and extensibility
- New package structure with separate modules for core functionality
- Initial integration with UNC-lib for improved network path handling
- Clearer separation between platform-specific and cross-platform code

### Changed

- Refactored UNCAdapter to leverage specialized UNC-lib functionality

## [0.5.0] - 2025-03-28

###  Added
- Initial public release candidate
- `import` command: recreates symlinks from `.dazzlelink` files with support for timestamp strategies
- `export` command: serializes existing symlinks into `.dazzlelink` format
- `create` command: allows creation of `.dazzlelink` files directly from source
- `convert` command: bulk conversion of symlinks into dazzlelinks
- `mirror` command: mirrors entire directory structures using symbolic links
- `scan` command: scans and reports existing symlinks in a directory
- `check` command: checks for broken links and optionally fixes them
- `config` command: manage global, directory, and inline configuration options
- `copy` command: copies symlinks to new destinations, preserving structure and optionally rebasing
- `rebase` command: transforms absolute to relative paths and vice versa, with powerful path-rewrite controls
- `execute` command: opens or executes symlink targets with optional modes
- Enhanced timestamp preservation for symlinks across platforms
- Improved batch operation performance for large directory processing

###  Improved
- Basic test framework with `--keep-all` support
- Path resolution and UNC handling through experimental `unc_converter` integration
- Early work toward platform-agnostic symlink representation
- Drafted v2 JSON config structure
- Improved configuration management with clearer hierarchy (global, directory, file)
- Enhanced error handling and reporting throughout the codebase
- Optimized performance for batch operations by reducing verification overhead
- Better path handling for UNC paths and network shares


### Fixed
- Initial symlink resolution bugs during serialization
- Test directory cleanup issues
- Resolved directory path handling issues in `import` command
- Fixed timestamp preservation on Windows by using proper API flags
- Work on file attribute restoration for hidden, system, and read-only files
- Improved error detection and recovery during batch operations
- More work on path normalization issues for complex UNC paths

### Known Issues
- Broken link detection occasionally misses edge cases
- UNC-to-local path mapping still under refinement for complex networks
- Test harness and logging need stabilization

---

## [0.1.0] - 2025-03-21
### Initial Development
- Created foundational `DazzleLink` class
- Designed `.dazzlelink` file format to support symlink serialization
- Drafted CLI structure using `argparse` with support for multiple subcommands
- Early experiments with Windows symlinks and path encoding
- Added UNC path normalization scaffolding
- Basic v1 JSON-based config loading introduced
- Placeholder support for future `find-best-images` integration

---

> For older historical context or dev discussions, see `/docs/roadmap.md`, [issues](https://github.com/djdarcy/dazzlelink/issues), and forums.

