# 📜 CHANGELOG.md - Dazzlelink

All notable changes to this project will be documented in this file. This project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.11.0] - 2026-07-30

**Milestone: multi-target dazzlelinks** (issue #25). One record now carries a local path AND a web URL — and the user CHOOSES which copy to open via a rung on the locality ladder. One `.dazzlelink` replaces the `.dazzlelink` + `.url` pair.

### Added
- `create --also-url <URL>` (repeatable): records web URLs alongside the local path family. Values must be scheme-form (`https://host/file`); a typo fails at create, not at open.
- `execute --prefer <rung|reach>`: prefer targets nearest a locality rung (`file`, `unc`, `internet`, ...) or reach alias (`local`, `local-network`, `remote`). A preference, not a filter — everything else stays as fallback. `--prefer remote` opens the URL even when the local copy exists.
- `execute --only <rung|reach>`: restrict to targets on that rung/reach; a miss errors cleanly, naming the reaches the record actually has.
- `execute --kind <k>` (repeatable): restrict to exact locator kinds (e.g. `url`, `path`).
- `execute --target N`: open exactly the locator numbered `[N]` by `--mode info`; out-of-range errors name the valid range. Conflicts with the selector flags (the error names every offender and acts on nothing).
- `--mode info` now lists **all targets** the record carries — numbered `[N]` (the `--target` address space) with kind and locality rung — plus the `Would open:` line computed by the same walk `--mode open` runs, with **zero network I/O** (web URLs are never probed for display).
- `execute --help` carries the locality-ladder legend, derived at runtime from the library's axis so it can never drift from the actual ladder.

### Changed
- `execute` judges reachability scheme-aware: filesystem candidates by existence, scheme-form candidates (`https://...`, `ipfs://...`) assumed openable — whether a scheme opens is the OS handler's business at open time. Records mixing paths and URLs fall back local → web naturally; path-only records behave exactly as before.
- Requires `dazzle-linklib>=0.4.0` (the locality axis + selection + `SchemeAwareReachability`).

### Deprecated
- (carried from 0.10.0) Execute's final fallback probing the **link's** own `path_representations` — now additionally skipped whenever a selector (`--prefer`/`--only`/`--kind`) narrowed the walk, so a filtered miss can't leak to the link file's old location. Removal still slated for the next minor.

## [0.10.0] - 2026-07-30

**Milestone: portable cross-references delivered** (issues #13 + #24; the collabN-local portable-paths design). Records created anywhere now carry — and can re-derive — the path forms that survive machine changes: relative (synced trees), UNC/drive (network bases), and subst expansions.

### Added
- `execute` performs **live re-resolution**: every stored form is re-derived against the *executing* machine's current drive/UNC/subst mappings (via dazzle-linklib's resolver walk + unctools' kinded `path_variants`), so a base that died since creation can resolve through whatever this machine maps today (#24).
- `create` stores **subst expansions**: a target on a subst'd drive records the underlying real path (`subst_path`), so the record outlives the alias (#24).
- Execute failure output now lists **exactly what was tried, in resolution order** (the resolver's own candidate walk), replacing the three-line summary.

### Changed
- `serialize_link` builds both `path_representations` (link) and `target_representations` (target, incl. the relative form anchored at the record's directory) via dazzle-linklib's `path_family` — one home for representation building across the stack. A symlink authored with a relative target still keeps its own relative form verbatim.
- `execute` parses records via dazzle-linklib's `from_file` (plain JSON, legacy flat, and polyglot executable forms — behavior-pinned by a regression test) and resolves via `resolve_target(base_dir=record_dir)`: relative resolution is now anchored at the record file's directory by construction.
- Resolution order is the documented priority heuristic `absolute → relative → unc → drive → subst`, matching the shipped fallback semantics.
- Requires `dazzle-linklib>=0.3.0` (which requires `unctools>=0.3.0`).

### Removed
- `src/dazzlelink/path.py` (`UNCAdapter`) — the tool's private drive↔UNC mapper, superseded at the proper stack layers (STACK-MAP V2 closed). It parsed `net use` output only; the replacements cover NetUseEnum + WNet provider enrichment + subst. Replacement map for each removed public symbol: `UNCAdapter`/`get_unc_adapter` → `unctools.converter.UNCConverter` (or the module-level functions); `convert_to_unc` → `unctools.convert_to_unc`; `convert_to_drive` → `unctools.convert_to_local`; `refresh_mappings` → `unctools.refresh_mappings`; `normalize_path` → the explicit `unctools.convert_to_unc`/`convert_to_local` (the direction-switch wrapper was retired stack-wide); representation building → `dazzle_linklib.path_family`.

### Deprecated
- Execute's final fallback (probing the **link's** own `path_representations` for an openable path) — it opens the link file's old location, not the target. Kept this release so the resolver delegation and the probe removal stay separately attributable; removal slated for the next minor.

## [0.9.1] - 2026-06-20

### Changed
- `batch_import` (the `import` command) now creates each link and applies its timestamp strategy + file attributes via dazzle-linklib (`create_link` + `apply_record_metadata`) instead of its own inline symlink/timestamp/attribute block. Behavior is unchanged; `batch_optimization` no longer gates a re-verification pass (the library does not run one). The `import` create -> delete -> recreate workflow is verified end-to-end.

## [0.9.0] - 2026-06-20

**Milestone:** the link-record core is extracted to the **dazzle-linklib** library (L2 of the DazzleLib stack); the tool begins consuming it as a thin client, so the record model lives in exactly one place across the stack.

### Changed
- `dazzlelink.data` no longer defines `DazzleLinkData` -- it re-exports the class from `dazzle-linklib`. The 389-line implementation became a 13-line re-export; the tool's behavior is unchanged (CLI test suite green).

### Added
- Dependency on `dazzle-linklib>=0.2.0` (the L2 record library).

## [0.8.0] - 2026-06-12

**Milestone:** the installable `dazzlelink` package now has full capability parity with the legacy monolith (completed across 0.7.2-0.7.5), the monolith is deprecated, and the package is validated for PyPI.

### Changed
- The legacy monolith (`legacy/dazzlelink_monolith.py`) prints a deprecation notice on invocation and is frozen -- all features and fixes land in the `dazzlelink` package, not the monolith (Refs #18).
- `.dazzlelink` and config-file reads now tolerate a leading UTF-8 BOM (`utf-8-sig`), so files hand-edited in BOM-writing tools (e.g. PowerShell `Set-Content -Encoding UTF8`) parse correctly instead of erroring.

### Notes
- Verified PyPI-ready: `python -m build` + `twine check` pass for both the wheel and sdist; the wheel includes the `dazzlelink.operations` subpackage. CLI subprocess test suite expanded (40 tests total).

## [0.7.5] - 2026-06-12

### Added
- `rebase` now also rebases `.dazzlelink` files (Refs #15): a second pass synchronizes the absolute and relative target paths stored *inside* each `.dazzlelink` JSON -- recompute the relative from a valid absolute, or the absolute from a valid relative; report files where both are broken (and leave those untouched). Previously `rebase` only rewrote live OS symlinks. The `rebase_dazzlelinks()` function is exported from the package.

### Changed
- `execute --mode info` now shows a richer display (Refs #18): the portable relative path, and a LIVE on-disk Exists/Size/Type check, falling back to the metadata stored at creation when the target is gone (previously it showed only the stored snapshot).

## [0.7.4] - 2026-06-12

### Added
- `copy` command: copy symlinks to another location -- expands directories into their symlinks, preserves structure (`--preserve-structure`/`--base-dir`), converts relative/absolute (`--relative`/`--absolute`), verifies (`--no-verify`). Restores the monolith command the modular CLI never exposed (Refs #18).
- `update-config` command: batch-edit the embedded config of many `.dazzlelink` files (`--mode`, `--pattern`, `--recursive`, `--dry-run`, `--make-executable`, `--config-level`). Likewise restored (Refs #18).

### Fixed
- `python -m dazzlelink` now propagates the command's exit code. The `__main__` entry called `main()` without `sys.exit()`, so every invocation exited 0 -- even on error -- which hid failures from scripts and CI.
- The top-level package now re-exports `update_config_batch` (previously only in `operations/`); an internal import depended on it.

## [0.7.3] - 2026-06-12

### Fixed
- POSIX executable dazzlelink generation raised `NameError: name 'stat' is not defined` -- `links.py` used `stat` in the Unix chmod path without importing it (the Windows path never reached that branch, so it surfaced only on Linux CI). Added the missing import.

### Changed
- CI (`python.yml`): added a lint step that fails on undefined names / syntax errors only (flake8 `E9,F63,F7,F82`, scoped to the package). Catches the missing-import class (a `NameError` that only fires on one platform) before the test run, without failing on style.

### Added
- `release.yml`: PyPI publish workflow using GitHub OIDC trusted publishing (no stored token), triggered when a GitHub Release is marked as the active, non-prerelease release (`release: [released]`), plus a manual `workflow_dispatch` for dry runs.

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

