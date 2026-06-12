"""
CLI-level smoke + behavior tests (real subprocess invocations).

Seeded with the commands wired in the parity work (copy, update-config) plus a
broad "every command is reachable" smoke test -- the kind that catches CLI
wiring/import regressions (e.g. an operation exported from operations/ but not
the top-level package, which takes down the whole CLI at import time).
"""
import json
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _dz(*args, **kw):
    """Run `python -m dazzlelink ...` from the repo root."""
    return subprocess.run(
        [sys.executable, "-m", "dazzlelink", *args],
        capture_output=True, text=True, cwd=REPO, **kw,
    )


ALL_COMMANDS = [
    "create", "export", "import", "scan", "convert", "mirror",
    "execute", "config", "check", "rebase", "copy", "update-config",
]


def test_cli_module_imports():
    """`import dazzlelink.cli` must succeed -- guards against an operation being
    referenced in the CLI import list but missing from the package's __init__."""
    import importlib
    importlib.import_module("dazzlelink.cli")


def test_top_level_help_lists_every_command():
    r = _dz("--help")
    assert r.returncode == 0, r.stderr
    for cmd in ALL_COMMANDS:
        assert cmd in r.stdout, f"command '{cmd}' missing from top-level --help"


@pytest.mark.parametrize("cmd", ALL_COMMANDS)
def test_each_command_has_help(cmd):
    """Every subcommand must at least parse `--help` (rc 0) -- a cheap reachability
    smoke test across the whole surface."""
    r = _dz(cmd, "--help")
    assert r.returncode == 0, f"`{cmd} --help` failed: {r.stderr[:300]}"
    assert cmd in r.stdout or "usage" in r.stdout.lower()


def test_update_config_dry_run_then_real(tmp_path):
    """update-config: dry-run must not modify; the real run must update every match."""
    # Build two plain-JSON dazzlelinks with default_mode=info via the API.
    sys.path.insert(0, os.path.join(REPO, "src"))
    from dazzlelink.config import DazzleLinkConfig
    from dazzlelink.operations.core import DazzleLink
    dl = DazzleLink(DazzleLinkConfig())
    for n in ("a", "b"):
        t = tmp_path / f"{n}.txt"
        t.write_text("x")
        dl.serialize_link(str(t), output_path=str(tmp_path / f"{n}.dazzlelink"),
                          make_executable=False, mode="info", require_symlink=False)

    def mode_of(name):
        return json.loads((tmp_path / name).read_text())["config"]["default_mode"]

    # Dry run: reports but does not change.
    r = _dz("update-config", str(tmp_path), "--mode", "open", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "Dry run" in r.stdout
    assert mode_of("a.dazzlelink") == "info", "dry-run must not modify files"

    # Real run: both files updated.
    r2 = _dz("update-config", str(tmp_path), "--mode", "open")
    assert r2.returncode == 0, r2.stderr
    assert "2 files updated" in r2.stdout
    assert mode_of("a.dazzlelink") == "open"
    assert mode_of("b.dazzlelink") == "open"


def test_copy_requires_links_and_destination():
    """copy with no symlinks found should report an error (no crash)."""
    r = _dz("copy", os.devnull, "nonexistent_dest_dir_xyz")
    # devnull is not a symlink/dir -> "No symlinks found to copy" path, rc 1.
    assert r.returncode == 1
    assert "No symlinks found" in r.stdout or "not a symlink" in r.stdout
