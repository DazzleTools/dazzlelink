# Dazzlelink Module

A developer-facing map of the `dazzlelink` package. The tool is a thin client over the DazzleLib stack: it owns the CLI, configuration layering, and the executable (polyglot) record format, and delegates everything with a second consumer to the stack libraries below.

## Package Structure

```
dazzlelink/
├── __init__.py              # Package initialization and high-level API
├── cli.py                   # Command-line interface
├── config.py                # Configuration handling
├── data.py                  # Re-exports the record model from dazzle-linklib
├── exceptions.py            # Custom exceptions
├── operations/              # Core operations
│   ├── __init__.py          # Operations package initialization
│   ├── core.py              # Core DazzleLink class (serialize_link)
│   ├── links.py             # Symlink + executable (polyglot) operations
│   ├── timestamps.py        # Timestamp handling
│   ├── batch.py             # Batch operations
│   └── recreate.py          # Execute/open + link recreation
```

## The DazzleLib Stack

One home per capability — each layer is its own repo and PyPI package:

| Library | Owns | Links |
|---|---|---|
| [dazzle-linklib](https://github.com/DazzleLib/dazzle-linklib) | The `.dazzlelink` record model (`DazzleLinkData`, re-exported here as `dazzlelink.data`), target resolution (the locator walk, live re-resolution, scheme-aware reachability), the locality axis behind `--prefer`/`--only`, and record discovery/rebase | [PyPI](https://pypi.org/project/dazzle-linklib/) · [API docs](https://github.com/DazzleLib/dazzle-linklib/blob/main/docs/api.md) |
| [unctools](https://github.com/DazzleLib/UNCtools) | UNC/drive/subst path identity: the kinded `path_variants` source behind the portable path family and execute-time re-derivation | [PyPI](https://pypi.org/project/unctools/) |
| [dazzle-filekit](https://github.com/DazzleLib/dazzle-filekit) | Filesystem mechanics: symlink creation, timestamp/metadata application | [PyPI](https://pypi.org/project/dazzle-filekit/) · [docs](https://app.readthedocs.org/projects/dazzle-filekit/) |
| [dazzle-lib](https://github.com/DazzleLib/dazzle-lib) | Bedrock contracts (serialization mixins, error taxonomy, the Continuum primitive the locality ladder is built on) | [PyPI](https://pypi.org/project/dazzle-lib/) |

The tool's old private UNC adapter (`path.py`) was removed in v0.10.0 once unctools + dazzle-linklib covered it — the per-symbol replacement map is in that release's CHANGELOG entry.

## Installation for Development

```bash
# Clone the repository
git clone https://github.com/DazzleTools/dazzlelink.git
cd dazzlelink

# Install in development mode
pip install -e .

# Optional: Windows-specific dependencies
pip install -e ".[windows]"

# Optional: development dependencies
pip install -e ".[dev]"
```

Working across the stack? Editable-install the libraries too (`pip install -e <path> --no-deps` for each), so a stack-wide change is testable without publishing.

## Usage as a Module

```python
import dazzlelink

# Create a dazzlelink (optionally multi-target: local path + web URL)
dazzlelink.create_link("target.txt", "link.dazzlelink")
dazzlelink.create_link("paper.pdf", "paper.pdf.dazzlelink",
                       also_urls=["https://example.org/paper.pdf"])

# Export a symlink to a dazzlelink
dazzlelink.export_link("path/to/symlink")

# Import a dazzlelink, recreating the original symlink
dazzlelink.import_link("path/to/dazzlelink")

# Open a record's target -- selectors match the CLI (prefer/only/kinds/target_index)
dazzlelink.execute("paper.pdf.dazzlelink", mode="open", prefer="remote")

# Convert all symlinks in a directory to dazzlelinks
dazzlelinks = dazzlelink.convert("/path/to/directory")

# Check for broken symlinks
results = dazzlelink.check("/path/to/directory")
```

## Command-Line Usage

See [COMMAND_REFERENCE.md](COMMAND_REFERENCE.md) for the full surface; `dazzlelink {command} -h` is always authoritative.

## Compatibility with the Monolithic Version

The monolith lives at `legacy/dazzlelink_monolith.py`, prints a deprecation notice, and is frozen — all features and fixes land in the installable package (see issue #18 for the port history). Record files remain wire-compatible in both directions.
