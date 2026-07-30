"""Portable-paths tests for 0.10.0 (issues #13 + #24 delegation).

Covers: create writes the path family (populate via linklib); the moved-tree
scenario (#13's owed unit test: relative resolution from the record's own
directory, NOT CWD); subst end-to-end (create on a live subst alias -> resolve
after the alias dies, via the stored expansion); polyglot execute parity after
the parse swap to linklib from_file (AC-G); and the tried-list diagnostics.
"""

import json
import os
import shutil
import string
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dazzlelink.config import DazzleLinkConfig
from dazzlelink.exceptions import DazzleLinkException
from dazzlelink.operations.core import DazzleLink
from dazzlelink.operations.recreate import execute_dazzlelink
from dazzlelink.operations import links as links_ops

IS_WINDOWS = os.name == "nt"


def _make_record(target, out):
    DazzleLink(DazzleLinkConfig()).serialize_link(
        str(target), output_path=str(out), make_executable=False, require_symlink=False
    )
    return out


@pytest.fixture
def opened(monkeypatch):
    """Capture what execute would open instead of launching it."""
    calls = []
    if IS_WINDOWS:
        monkeypatch.setattr(os, "startfile", lambda p: calls.append(p), raising=False)
    else:
        import subprocess as sp

        monkeypatch.setattr(sp, "run", lambda *a, **k: calls.append(a[0][-1]))
    return calls


# --- create writes the family (#13 create-side) -----------------------------

def test_create_writes_relative_and_original(tmp_path):
    target = tmp_path / "asset.pdf"
    target.write_text("x", encoding="utf-8")
    out = _make_record(target, tmp_path / "asset.pdf.dazzlelink")

    data = json.loads(out.read_text(encoding="utf-8"))
    reps = data["link"]["target_representations"]
    assert reps["original_path"] == str(target)
    assert reps["relative_path"] == "asset.pdf"


def test_create_cross_drive_omits_relative(tmp_path):
    # Record dir on another drive than the target -> no relative key at all.
    drive = os.path.splitdrive(str(tmp_path))[0].upper()
    other = "D:" if drive != "D:" else "E:"
    target = tmp_path / "t.txt"
    target.write_text("x", encoding="utf-8")
    dl = DazzleLink(DazzleLinkConfig())
    try:
        rec_path = other + "\\__dz_cross_test.dazzlelink"
        dl.serialize_link(str(target), output_path=rec_path,
                          make_executable=False, require_symlink=False)
    except Exception:
        pytest.skip(f"drive {other} not writable/present")
    try:
        data = json.loads(open(rec_path, encoding="utf-8-sig").read())
        assert "relative_path" not in data["link"]["target_representations"]
    finally:
        os.unlink(rec_path)


# --- the moved-tree scenario (#13's owed unit test) ---------------------------

def test_moved_tree_resolves_via_relative_from_any_cwd(tmp_path, opened, monkeypatch):
    # Library tree A: target + record side-by-side. Sync to B, delete A.
    tree_a = tmp_path / "treeA"
    tree_a.mkdir()
    target = tree_a / "book.pdf"
    target.write_text("pdf", encoding="utf-8")
    _make_record(target, tree_a / "book.pdf.dazzlelink")

    tree_b = tmp_path / "treeB"
    shutil.copytree(tree_a, tree_b)
    shutil.rmtree(tree_a)  # the absolute path is now dead

    monkeypatch.chdir(tmp_path)  # deliberately NOT the record dir
    execute_dazzlelink(str(tree_b / "book.pdf.dazzlelink"), mode="open")

    assert len(opened) == 1
    assert os.path.normcase(opened[0]) == os.path.normcase(str(tree_b / "book.pdf"))


# --- subst end-to-end (#24 create-side expansion) -----------------------------

def _free_drive_letter():
    import ctypes

    bits = ctypes.windll.kernel32.GetLogicalDrives()
    used = {c for i, c in enumerate(string.ascii_uppercase) if bits & (1 << i)}
    for c in "QRSTUVWXY":
        if c not in used:
            return c
    return None


@pytest.mark.skipif(not IS_WINDOWS, reason="subst is Windows-only")
def test_subst_alias_record_survives_alias_death(tmp_path, opened):
    letter = _free_drive_letter()
    if letter is None:
        pytest.skip("no free drive letter")
    drive = f"{letter}:"
    subprocess.run(["subst", drive, str(tmp_path)], check=True)
    try:
        from unctools.detector import _clear_path_type_cache

        _clear_path_type_cache()
        target_alias = f"{drive}\\asset.bin"
        (tmp_path / "asset.bin").write_text("x", encoding="utf-8")
        out = tmp_path / "asset.bin.dazzlelink"
        _make_record(target_alias, out)

        data = json.loads(out.read_text(encoding="utf-8"))
        reps = data["link"]["target_representations"]
        # Create-time expansion: the subst alias was expanded to the real path.
        assert "subst_path" in reps
        assert os.path.normcase(reps["subst_path"]) == os.path.normcase(str(tmp_path / "asset.bin"))
    finally:
        subprocess.run(["subst", drive, "/d"], check=True)

    # The alias is dead; execute must resolve via the stored expansion.
    from unctools.detector import _clear_path_type_cache

    _clear_path_type_cache()
    execute_dazzlelink(str(out), mode="open")
    assert len(opened) == 1
    assert os.path.normcase(opened[0]) == os.path.normcase(str(tmp_path / "asset.bin"))


# --- polyglot execute parity (AC-G) -------------------------------------------

def test_polyglot_execute_info_and_open(tmp_path, opened, capsys):
    target = tmp_path / "poly.bin"
    target.write_text("x", encoding="utf-8")
    out = tmp_path / "poly.bin.dazzlelink"
    _make_record(target, out)
    links_ops.make_dazzlelink_executable(str(out))
    head = out.read_text(encoding="utf-8", errors="ignore")[:200]
    assert "DAZZLELINK" in head or head.startswith(("#!", "@", "REM", ":", "<#"))

    execute_dazzlelink(str(out), mode="info")
    info = capsys.readouterr().out
    assert "Target:" in info

    execute_dazzlelink(str(out), mode="open")
    assert len(opened) == 1
    assert os.path.normcase(opened[0]) == os.path.normcase(str(target))


# --- failure diagnostics (F4.1 tried-list parity) ------------------------------

def test_execute_failure_lists_tried_candidates(tmp_path):
    target = tmp_path / "gone.bin"
    target.write_text("x", encoding="utf-8")
    out = tmp_path / "gone.bin.dazzlelink"
    _make_record(target, out)
    # Move the record AWAY from the tree and kill the target: every stored
    # form (absolute, relative-from-new-location) is now dead.
    stray_dir = tmp_path / "stray"
    stray_dir.mkdir()
    stray = stray_dir / "gone.bin.dazzlelink"
    os.rename(str(out), str(stray))
    os.unlink(str(target))

    with pytest.raises(DazzleLinkException) as ei:
        execute_dazzlelink(str(stray), mode="open")
    msg = str(ei.value)
    assert "Tried (in resolution order)" in msg
    assert str(target) in msg  # the dead absolute is in the tried list
