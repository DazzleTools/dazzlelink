"""
Regression tests for the parity work:
- GT-4 / #15: rebase_dazzlelinks() synchronizes the absolute and relative target
  paths stored inside .dazzlelink files (distinct from rebase_links on symlinks).
- GT-8: `execute --mode info` shows the richer display (relative path, a LIVE
  on-disk size/type check) instead of only the metadata stored at creation.
"""
import contextlib
import io
import json
import os

from dazzlelink.config import DazzleLinkConfig
from dazzlelink.operations import batch
from dazzlelink.operations.core import DazzleLink
from dazzlelink.operations.recreate import execute_dazzlelink


def _write_dl(path, target_path, relative_path):
    """Write a minimal .dazzlelink carrying a stored absolute + relative target."""
    data = {
        "link": {
            "target_path": target_path,
            "target_representations": {
                "relative_path": relative_path,
                "original_path": target_path,
            },
        }
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# --- GT-4 / #15: rebase_dazzlelinks ---------------------------------------

def test_rebase_recomputes_stale_relative(tmp_path):
    """Absolute valid, relative stale -> relative recomputed from absolute."""
    target = tmp_path / "target.txt"
    target.write_text("x")
    dl = tmp_path / "a.dazzlelink"
    _write_dl(dl, str(target), os.path.join("wrong", "rel.txt"))

    res = batch.rebase_dazzlelinks(str(tmp_path), recursive=False)

    assert len(res["changed"]) == 1
    after = json.loads(dl.read_text())["link"]["target_representations"]["relative_path"]
    assert os.path.normpath(os.path.join(str(tmp_path), after)) == str(target)


def test_rebase_unchanged_when_in_sync(tmp_path):
    """Absolute valid and relative already correct -> no change."""
    target = tmp_path / "target.txt"
    target.write_text("x")
    dl = tmp_path / "a.dazzlelink"
    _write_dl(dl, str(target), os.path.relpath(str(target), str(tmp_path)))

    res = batch.rebase_dazzlelinks(str(tmp_path), recursive=False)

    assert res["changed"] == []
    assert len(res["unchanged"]) == 1


def test_rebase_recomputes_absolute_from_relative(tmp_path):
    """Absolute broken but relative resolves -> absolute recomputed."""
    target = tmp_path / "target.txt"
    target.write_text("x")
    dl = tmp_path / "a.dazzlelink"
    broken_abs = str(tmp_path / "GONE" / "target.txt")
    _write_dl(dl, broken_abs, os.path.relpath(str(target), str(tmp_path)))

    res = batch.rebase_dazzlelinks(str(tmp_path), recursive=False)

    assert len(res["changed"]) == 1
    after_abs = json.loads(dl.read_text())["link"]["target_path"]
    assert os.path.exists(after_abs)


def test_rebase_both_broken_is_error(tmp_path):
    """Neither path resolves -> reported as an error, file left untouched."""
    dl = tmp_path / "a.dazzlelink"
    _write_dl(dl, str(tmp_path / "nope.txt"), os.path.join("also", "nope.txt"))

    res = batch.rebase_dazzlelinks(str(tmp_path), recursive=False)

    assert len(res["errors"]) == 1
    assert res["changed"] == []


def test_rebase_no_files_is_clean(tmp_path):
    # rebase_dazzlelinks now delegates to dazzle-linklib, which reports a
    # 'skipped' bucket (for polyglot records it won't rewrite) alongside the
    # original changed/unchanged/errors.
    res = batch.rebase_dazzlelinks(str(tmp_path), recursive=False)
    assert res == {"changed": [], "unchanged": [], "skipped": [], "errors": []}


# --- GT-8: richer execute --mode info -------------------------------------

def test_info_display_shows_relative_and_live_size(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("y" * 2048)
    out = tmp_path / "i.dazzlelink"
    DazzleLink(DazzleLinkConfig()).serialize_link(
        str(target), output_path=str(out), make_executable=False, require_symlink=False)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        execute_dazzlelink(str(out), mode="info")
    out_text = buf.getvalue()

    assert "Relative Path" in out_text
    assert "Exists: Yes" in out_text
    assert "Size:" in out_text and ("KB" in out_text or "bytes" in out_text)
    assert "Type:" in out_text
