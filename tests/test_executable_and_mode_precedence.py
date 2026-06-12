"""
Regression tests for the Commit-1 correctness fixes (monolith-vs-modular DWP).

Covers:
- GT-2 / issue #18: serialize_link(make_executable=True) no longer raises
  AttributeError (the call site delegated to a method that never existed) and
  the executable-script generator no longer NameErrors on `json` (a missing
  import that the AttributeError had masked).
- GT-3 / issue #19: execute mode precedence is CLI > file-embedded > global
  fallback > "info" (file-beats-global, matching the monolith). This direction
  was chosen by the user verbatim: "File beats global (matches monolith)".

These tests do not require symlink-creation privilege: serialize_link is called
with require_symlink=False so a plain file stands in for the link target.
"""
import json
import os
import py_compile
import subprocess
import sys

import pytest

from dazzlelink.config import DazzleLinkConfig
from dazzlelink.operations.core import DazzleLink
from dazzlelink.operations import links
from dazzlelink.operations.recreate import execute_dazzlelink


def _make_dazzlelink(tmp_path, mode=None, make_executable=False, name="link.dazzlelink"):
    """Serialize a plain file into a .dazzlelink and return its path."""
    target = tmp_path / "target.txt"
    target.write_text("payload")
    out = tmp_path / name
    dl = DazzleLink(DazzleLinkConfig())
    dl.serialize_link(
        str(target), output_path=str(out),
        make_executable=make_executable, mode=mode, require_symlink=False,
    )
    return out, target


# --------------------------------------------------------------------------
# GT-2 / #18 -- executable generation must not crash
# --------------------------------------------------------------------------

def test_serialize_with_make_executable_does_not_raise(tmp_path):
    """#18: make_executable=True previously raised AttributeError at core.py:313."""
    out, _ = _make_dazzlelink(tmp_path, make_executable=True)
    assert out.exists()
    head = out.read_text(encoding="utf-8")[:80]
    # The executable form is a script wrapper (shebang on POSIX, @echo on Windows)
    # or carries the DAZZLELINK marker -- in all cases it is NOT bare JSON.
    assert head.lstrip().startswith("#!") or "@echo" in head or "DAZZLELINK" in head


def test_make_dazzlelink_executable_module_fn_has_json(tmp_path):
    """The generator uses json.* -- regression for the missing `import json`."""
    out, _ = _make_dazzlelink(tmp_path, make_executable=False)
    data = json.loads(out.read_text(encoding="utf-8"))
    # Calling the module function directly must not NameError on json.
    links.make_dazzlelink_executable(str(out), data)
    assert out.exists()


def test_generated_executable_parses_as_python(tmp_path):
    """The generated script must be valid Python.

    Regression for two pre-existing bugs the AttributeError had masked:
    (1) a raw Windows path embedded in the triple-quoted block produced an
    invalid escape (\\U / \\x) SyntaxError -- now embedded with forward slashes;
    (2) the trailing JSON data block was executed as Python (lowercase
    false/true/null -> NameError) -- now guarded by sys.exit(0) after main().
    Build a target path with a 'Users' segment so a Windows-style path would
    carry the \\U hazard.
    """
    target = tmp_path / "Users" / "proj" / "target.txt"
    target.parent.mkdir(parents=True)
    target.write_text("payload")
    out = tmp_path / "exec.dazzlelink"
    DazzleLink(DazzleLinkConfig()).serialize_link(
        str(target), output_path=str(out), make_executable=True, require_symlink=False)
    # Must compile cleanly (no SyntaxError from the embedded path or data block).
    py_compile.compile(str(out), doraise=True)


def test_generated_executable_runs_info(tmp_path):
    """`python <generated.dazzlelink> --info` must run to completion (rc 0).

    Exercises the full self-executing path: the script parses, main() extracts
    its own embedded JSON via the DAZZLELINK_DATA_BEGIN marker, prints info, and
    sys.exit(0) stops before the trailing data block. Regression for the
    JSON-as-code NameError.
    """
    out, _ = _make_dazzlelink(tmp_path, make_executable=True)
    r = subprocess.run([sys.executable, str(out), "--info"],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"generated script failed: {r.stderr[:400]}"
    assert "Target" in r.stdout


def test_generated_executable_embeds_forward_slash_path(tmp_path):
    """The batch `start`/`echo` lines embed the path with forward slashes.

    ShellExecute (which `start` invokes) accepts forward slashes; this keeps the
    embedded path free of the invalid-escape hazard and renders cleanly.
    """
    target = tmp_path / "Users" / "t.txt"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    out = tmp_path / "fwd.dazzlelink"
    DazzleLink(DazzleLinkConfig()).serialize_link(
        str(target), output_path=str(out), make_executable=True, require_symlink=False)
    start_lines = [ln for ln in out.read_text(encoding="utf-8").splitlines()
                   if ln.startswith('start "" "')]
    assert start_lines, "no batch start line found in generated script"
    # The embedded path uses forward slashes, not backslashes.
    assert "\\" not in start_lines[0]
    assert "/" in start_lines[0]


# --------------------------------------------------------------------------
# GT-3 / #19 -- mode precedence (file beats global, matches monolith)
# --------------------------------------------------------------------------

def test_executable_dazzlelink_execute_never_shells_the_file(tmp_path, monkeypatch, capsys):
    """FORK-BOMB regression: executing a script-format (executable) dazzlelink
    must NOT re-run the file via the shell. On Windows, shell-running a
    .dazzlelink invokes its file association -- which is `dazzlelink execute` --
    causing unbounded recursion. Execute must read the embedded JSON and act on
    the target directly. Here: info mode must touch NO subprocess at all.
    """
    out, _ = _make_dazzlelink(tmp_path, mode="info", make_executable=True)
    import subprocess

    def _guard(cmd, *a, **k):
        flat = cmd if isinstance(cmd, str) else " ".join(map(str, cmd))
        assert ".dazzlelink" not in flat, f"execute shelled the dazzlelink file: {flat!r}"
        return None

    monkeypatch.setattr(subprocess, "run", _guard)
    execute_dazzlelink(str(out), mode="info")
    assert "DazzleLink Information" in capsys.readouterr().out


def test_executable_dazzlelink_open_targets_file_not_self(tmp_path, monkeypatch):
    """Open mode on an executable dazzlelink opens the TARGET directly, never
    the .dazzlelink itself (the fork-bomb path)."""
    out, target = _make_dazzlelink(tmp_path, mode="open", make_executable=True)
    opened = {}
    import subprocess

    def _guard(cmd, *a, **k):
        flat = cmd if isinstance(cmd, str) else " ".join(map(str, cmd))
        assert ".dazzlelink" not in flat, f"execute shelled the dazzlelink file: {flat!r}"
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "xdg-open":
            opened["p"] = cmd[1]
        return None

    monkeypatch.setattr(subprocess, "run", _guard)
    if hasattr(os, "startfile"):
        monkeypatch.setattr(os, "startfile", lambda p: opened.setdefault("p", p), raising=False)
    execute_dazzlelink(str(out), mode=None, config_override=DazzleLinkConfig())
    assert opened.get("p"), "open mode did not open anything"
    assert ".dazzlelink" not in opened["p"], "open mode opened the dazzlelink itself, not the target"


@pytest.fixture
def capture_open(monkeypatch):
    """Capture the path that 'open'/'auto' mode would launch, cross-platform."""
    captured = {}

    def fake_startfile(path):
        captured["opened"] = path

    # Windows path
    if hasattr(os, "startfile"):
        monkeypatch.setattr(os, "startfile", fake_startfile, raising=False)
    # POSIX path: recreate.py calls subprocess.run(['xdg-open', target])
    import subprocess
    real_run = subprocess.run

    def fake_run(cmd, *a, **k):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "xdg-open":
            captured["opened"] = cmd[1]
            return None
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return captured


def test_file_mode_beats_global(tmp_path, capture_open):
    """File embedded 'open' wins over a global 'info' config (the #19 fix)."""
    out, target = _make_dazzlelink(tmp_path, mode="open")
    global_cfg = DazzleLinkConfig()            # default_mode == 'info'
    execute_dazzlelink(str(out), mode=None, config_override=global_cfg)
    assert capture_open.get("opened") is not None, "file's 'open' mode was ignored"


def test_cli_mode_beats_file(tmp_path, capsys, capture_open):
    """CLI --mode info overrides a file embedded as 'open'."""
    out, _ = _make_dazzlelink(tmp_path, mode="open")
    execute_dazzlelink(str(out), mode="info", config_override=DazzleLinkConfig())
    assert capture_open.get("opened") is None, "CLI mode did not override file mode"
    assert "DazzleLink Information" in capsys.readouterr().out


def test_fieldless_file_resolves_to_info_not_global(tmp_path, capsys, capture_open):
    """Monolith parity (user's verbatim choice 'File beats global'): a file that
    does not specify a mode resolves to 'info', NOT a global 'open' override --
    the global config is vestigial at execute time, exactly as in the monolith."""
    out = tmp_path / "fieldless.dazzlelink"
    out.write_text(json.dumps({
        "link": {"target_path": str(tmp_path / "t.txt")},
        # no "config"/"default_mode" key at all
    }), encoding="utf-8")
    (tmp_path / "t.txt").write_text("x")
    global_open = DazzleLinkConfig()
    global_open.set("default_mode", "open")
    execute_dazzlelink(str(out), mode=None, config_override=global_open)
    assert capture_open.get("opened") is None, "global 'open' should not override a fieldless file"
    assert "DazzleLink Information" in capsys.readouterr().out
