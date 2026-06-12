# 📜 CHANGELOG.md - Dazzlelink

All notable changes to this project will be documented in this file. This project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.7.2] - 2026-06-11

### Fixed
- **Fork bomb on `execute` of an executable dazzlelink (Refs #18).** `execute` ran a script-format `.dazzlelink` via `subprocess.run(..., shell=True)`, which on Windows re-invokes the `.dazzlelink` file association (itself `dazzlelink execute`) -- unbounded recursion that spawns processes until the machine is overwhelmed. `execute` now reads the embedded JSON and opens the target directly for both plain and executable dazzlelinks; the marker is matched as an exact line (the literal also appears in the script's own source). This path became easy to hit once executable generation was fixed (below), so the two ship together.
- Executable dazzlelink generation no longer crashes and now produces a runnable script (Refs #18). Four bugs, all present since the first release and masked by the first one:
  - `serialize_link(make_executable=True)` raised `AttributeError` — `core.py` called `self._make_dazzlelink_executable`, which became the module function `links.make_dazzlelink_executable` during modularization; the call site now delegates correctly
  - `links.py` and `batch.py` used `json` without importing it (latent `NameError`; batch's affected the `update-config` path)
  - the generated script embedded a raw Windows path into a Python block, causing a `\U` `SyntaxError` — now embedded with forward slashes (ShellExecute-compatible; canonical backslash path preserved in the embedded JSON)
  - the trailing JSON data block was executed as Python (`false`/`true`/`null` → `NameError`) — now guarded by `sys.exit(0)` after `main()`
  - the same fixes are applied to the legacy monolith
- Execute mode precedence is now CLI > file-embedded > global > "info" (file-beats-global, matching the monolith): a file's embedded mode is no longer overridden by the global config default (Refs #19)

### Changed
- `convert`/`mirror` now honor `--executable` and `--mode` (the CLI config is forwarded to the operation); `execute` now honors `--config-level` (the loaded config is passed through as the fallback)

### Notes
- Generated-script path representation uses forward slashes for now (tool-mode pragmatism); canonical runtime-read is tracked for the eventual library-mode transition (#23)

## [0.7.1] - 2026-06-11

### Changed
- Relocate the git-repokit-common subtree to `scripts/repokit-common/` (disambiguating it from dazzlelink's own `scripts/` helpers) and update it to v0.2.7

## [0.7.0] - 2026-06-11

### Added
- Relative path support for portable dazzlelinks across synced machines (Refs #13)
  - `target_representations.relative_path` computed during `create`
  - `execute` fallback chain: absolute -> relative -> path_representations
  - Enables dazzlelinks to work when library mount points differ between machines
- git-repokit-common subtree at `scripts/` for shared hooks and tools
- File association scripts for Windows `.dazzlelink` extension

### Changed
- **Layout**: package moved from `dazzlelink/` to `src/dazzlelink/` (PyPA src layout); editable installs must be re-run (`pip install -e .`)
- Monolith `dazzlelink.py` moved to `legacy/dazzlelink_monolith.py` and deprecated in favor of `python -m dazzlelink` (Refs #18)
- `pyproject.toml` is now the single source of packaging truth: `requires-python>=3.10`, pywin32 as a core dependency on Windows, license `GPL-3.0-or-later`, URLs point to the DazzleTools org (Refs #2)
- File association scripts prefer the pip-installed module, falling back to the legacy monolith
- CI matrix updated to Python 3.10/3.12/3.13

### Fixed
- `dazzlelink.operations` subpackage was missing from built wheels (`packages.find` with `where=["src"]`); installs from the previous packaging config would fail at import
- File association scripts' monolith fallback pointed at the removed root `dazzlelink.py`
- Renamed `pyproject-toml.py` to `pyproject.toml` for PyPI compatibility

### Removed
- `setup.py` (broken version read), `setup.cfg` (flake8 config migrated to pyproject), `requirements.txt` (deps live in pyproject)

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

