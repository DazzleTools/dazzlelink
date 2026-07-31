"""Multi-target dazzlelink tests for 0.11.0 (issue #25).

One record carrying a local path AND a web URL, with user CHOICE via a rung on
the locality ladder. Covers the DWP acceptance checks at the tool level
(AC-1..5, 7, 8, 10, 11, 13, 14, 15); the axis/selection/reachability machinery
itself is covered lib-side in dazzle-linklib's test_locality_selection.py
(AC-6, AC-12 and the lib half of AC-10/13).
"""

import json
import os
import socket
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from dazzlelink.config import DazzleLinkConfig
from dazzlelink.exceptions import DazzleLinkException
from dazzlelink.operations.core import DazzleLink
from dazzlelink.operations.recreate import execute_dazzlelink

IS_WINDOWS = os.name == "nt"

URL = "https://example.org/doc.pdf"
URL2 = "https://mirror.example.net/doc.pdf"


def _dz(*args, **kw):
    """Run `python -m dazzlelink ...` from the repo root."""
    return subprocess.run(
        [sys.executable, "-m", "dazzlelink", *args],
        capture_output=True, text=True, cwd=REPO, **kw,
    )


def _make_record(target, out, also_urls=None):
    DazzleLink(DazzleLinkConfig()).serialize_link(
        str(target), output_path=str(out), make_executable=False,
        require_symlink=False, also_urls=also_urls,
    )
    return out


def _two_target(tmp_path, urls=(URL,)):
    """A record carrying a real local file AND url locator(s)."""
    target = tmp_path / "doc.pdf"
    target.write_text("pdf", encoding="utf-8")
    out = _make_record(target, tmp_path / "doc.pdf.dazzlelink", also_urls=list(urls))
    return target, out


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


@pytest.fixture
def no_network(monkeypatch):
    """Any socket construction explodes -- proves a code path does no network I/O."""
    def _boom(*a, **k):
        raise AssertionError("network I/O attempted in a no-network code path")

    monkeypatch.setattr(socket, "socket", _boom)


# --- AC-1: local wins by default; delete local -> URL wins ---------------------

def test_two_target_local_wins_then_url_fallback(tmp_path, opened):
    target, out = _two_target(tmp_path)

    execute_dazzlelink(str(out), mode="open")
    assert os.path.normcase(opened[-1]) == os.path.normcase(str(target))

    os.unlink(str(target))
    execute_dazzlelink(str(out), mode="open")
    assert opened[-1] == URL


# --- AC-2: url-only record opens the URL (the .url-file replacement) -----------

def test_url_only_record_opens_url(tmp_path, opened):
    target, out = _two_target(tmp_path)
    data = json.loads(out.read_text(encoding="utf-8"))
    # Strip every path form: only the explicit url locator remains.
    data["link"]["target_representations"] = {}
    data["link"]["target_path"] = None
    for key in ("target_path", "original_path"):
        data.pop(key, None)
    out.write_text(json.dumps(data), encoding="utf-8")

    execute_dazzlelink(str(out), mode="open")
    assert opened == [URL]


# --- AC-3: --kind forces / misses cleanly ---------------------------------------

def test_kind_url_forces_url_with_local_present(tmp_path, opened):
    target, out = _two_target(tmp_path)
    assert target.exists()
    execute_dazzlelink(str(out), mode="open", kinds=["url"])
    assert opened == [URL]


def test_kind_miss_errors_naming_available(tmp_path, opened):
    _target, out = _two_target(tmp_path)
    with pytest.raises(DazzleLinkException) as ei:
        execute_dazzlelink(str(out), mode="open", kinds=["ipfs"])
    msg = str(ei.value)
    assert "no locators match the selection" in msg
    assert "--kind ipfs" in msg
    # ...and names what the record DOES have, by reach.
    assert "local" in msg and "remote" in msg and "url" in msg
    assert opened == []


# --- AC-4: --target N exact pin + out-of-range ----------------------------------

def test_target_pin_opens_exactly_that_locator(tmp_path, opened, capsys):
    target, out = _two_target(tmp_path)
    # info numbers the locators; the url rides last (explicit locators after
    # the path family).
    execute_dazzlelink(str(out), mode="info")
    info = capsys.readouterr().out
    url_index = next(
        int(line.strip().split("]")[0].lstrip("["))
        for line in info.splitlines()
        if "] url" in line
    )
    execute_dazzlelink(str(out), mode="open", target_index=url_index)
    assert opened == [URL]

    execute_dazzlelink(str(out), mode="open", target_index=0)
    assert os.path.normcase(opened[-1]) == os.path.normcase(str(target))


def test_target_out_of_range_names_valid_range(tmp_path, opened):
    _target, out = _two_target(tmp_path)
    with pytest.raises(DazzleLinkException) as ei:
        execute_dazzlelink(str(out), mode="open", target_index=99)
    msg = str(ei.value)
    assert "--target 99 is out of range" in msg
    assert "valid indices 0.." in msg
    assert opened == []


# --- AC-5: info lists numbered targets + winner, zero network I/O ---------------

def test_info_lists_numbered_targets_and_winner(tmp_path, capsys, no_network):
    target, out = _two_target(tmp_path)
    execute_dazzlelink(str(out), mode="info")
    info = capsys.readouterr().out
    assert "Targets (" in info
    assert "[0] path" in info
    assert f"] url" in info and URL in info
    assert "rung: local" in info and "rung: internet" in info
    assert "Would open: [0]" in info


def test_info_would_open_url_without_probing(tmp_path, capsys, no_network):
    target, out = _two_target(tmp_path)
    os.unlink(str(target))
    execute_dazzlelink(str(out), mode="info")
    info = capsys.readouterr().out
    # The URL wins the preview -- judged by form alone (no_network proves it).
    assert "Would open:" in info and URL in info.split("Would open:")[1]


# --- AC-7: 0.10.0-reader grace ---------------------------------------------------

def test_old_reader_grace_two_target_record(tmp_path):
    """A 0.10.0 reader (filesystem-only checker, no selectors) sees a
    two-target record as a plain local record: same winner, no crash, and the
    url locator survives untouched in link.locators (unknown-key round-trip
    was proven cross-tool in the June suite; this pins the 0.11.0 shape)."""
    from dazzle_linklib import DazzleLinkData, resolve_target

    target, out = _two_target(tmp_path)
    record = DazzleLinkData.from_file(str(out))
    # 0.10.0 call shape: no reachability override, no selectors -- the default
    # checker deliberately reports urls unreachable.
    hit = resolve_target(record, base_dir=str(tmp_path))
    assert hit is not None
    assert os.path.normcase(hit["value"]) == os.path.normcase(str(target))
    os.unlink(str(target))
    assert resolve_target(record, base_dir=str(tmp_path)) is None  # old: no url fallback

    data = json.loads(out.read_text(encoding="utf-8"))
    assert {"kind": "url", "value": URL} in data["link"]["locators"]


# --- AC-8: --also-url round-trip; rebase leaves the url locator untouched --------

def test_create_also_url_roundtrip_and_rebase(tmp_path):
    target, out = _two_target(tmp_path, urls=(URL, URL2))
    data = json.loads(out.read_text(encoding="utf-8"))
    reps = data["link"]["target_representations"]
    assert reps["relative_path"] == "doc.pdf"          # path family intact
    assert data["link"]["locators"] == [
        {"kind": "url", "value": URL},
        {"kind": "url", "value": URL2},
    ]

    # Break the stored absolute so rebase rewrites the record, then verify the
    # url locators ride through the rewrite byte-identical.
    from dazzlelink.operations.batch import rebase_dazzlelinks

    data["link"]["target_path"] = str(tmp_path / "moved" / "doc.pdf")
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    result = rebase_dazzlelinks(str(tmp_path), recursive=False)
    assert str(out) in result["changed"] or result["errors"] == []

    after = json.loads(out.read_text(encoding="utf-8"))
    assert after["link"]["locators"] == [
        {"kind": "url", "value": URL},
        {"kind": "url", "value": URL2},
    ]


# --- AC-10: --prefer remote/internet beat local presence -------------------------

@pytest.mark.parametrize("spelling", ["remote", "internet"])
def test_prefer_remote_opens_url_with_local_present(tmp_path, opened, spelling):
    target, out = _two_target(tmp_path)
    assert target.exists()
    execute_dazzlelink(str(out), mode="open", prefer=spelling)
    assert opened == [URL]


def test_prefer_is_not_a_filter(tmp_path, opened):
    # URL kinds filtered OUT and remote preferred: the local file still opens
    # (everything stays fallback).
    target, out = _two_target(tmp_path)
    execute_dazzlelink(str(out), mode="open", prefer="remote",
                       kinds=["path", "relative", "unc", "drive", "subst"])
    assert os.path.normcase(opened[-1]) == os.path.normcase(str(target))


# --- AC-11: --only miss names the available reaches ------------------------------

def test_only_miss_names_available_reaches(tmp_path, opened):
    _target, out = _two_target(tmp_path)
    with pytest.raises(DazzleLinkException) as ei:
        execute_dazzlelink(str(out), mode="open", only="local-network")
    msg = str(ei.value)
    assert "--only local-network" in msg
    assert "local (" in msg and "remote (" in msg
    assert opened == []


def test_only_miss_never_falls_back_to_link_reps(tmp_path, opened):
    # The deprecated link path_representations fallback contains LIVE paths
    # (the record file's own old location) -- a selector miss must error, not
    # leak there.
    target, out = _two_target(tmp_path)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["link"]["path_representations"]  # the trap exists
    with pytest.raises(DazzleLinkException):
        execute_dazzlelink(str(out), mode="open", only="local-network")
    assert opened == []


# --- AC-13: prefer[i]-labelled tried-list keeps the preference order --------------

def test_tried_list_labels_prefer_order(tmp_path):
    target, out = _two_target(tmp_path)
    # Move the record away and kill the target: absolute and (re-anchored)
    # relative become two DISTINCT dead candidates (side-by-side they dedup
    # to one). Filter to path kinds only (url excluded) with remote preferred:
    # nothing resolves, and the tried-list is labelled in preference order.
    stray = tmp_path / "stray" / "doc.pdf.dazzlelink"
    stray.parent.mkdir()
    os.rename(str(out), str(stray))
    os.unlink(str(target))
    with pytest.raises(DazzleLinkException) as ei:
        execute_dazzlelink(str(stray), mode="open", prefer="remote",
                           kinds=["path", "relative"])
    msg = str(ei.value)
    assert "prefer[0]:" in msg and "prefer[1]:" in msg
    assert "Tried (in resolution order)" in msg


# --- AC-14: execute --help derives from the axis ----------------------------------

def test_execute_help_ladder_derives_from_axis():
    from dazzle_linklib import LOCALITY_CONTINUUM, REACH_ALIASES, SCHEME_ALIASES

    r = _dz("execute", "--help")
    assert r.returncode == 0, r.stderr
    assert "locality ladder" in r.stdout
    for rung in LOCALITY_CONTINUUM.levels():
        assert rung in r.stdout, f"rung '{rung}' missing from execute --help"
    for alias in list(REACH_ALIASES) + list(SCHEME_ALIASES):
        assert alias in r.stdout, f"alias '{alias}' missing from execute --help"
    # the open-ended kind fallthrough is documented in the legend
    assert "KIND" in r.stdout


# --- AC-15: pin + selector conflict names ALL offenders ---------------------------

def test_target_conflicts_with_selectors_names_all(tmp_path):
    _target, out = _two_target(tmp_path)
    r = _dz("execute", "--target", "1", "--prefer", "remote", "--kind", "url",
            str(out))
    assert r.returncode == 1
    assert "--prefer" in r.stderr and "--kind" in r.stderr
    assert "nothing was opened" in r.stderr


def test_prefer_scheme_alias_opens_url(tmp_path, opened):
    # AC-17: the common web spellings are tier aliases -- the trigger
    # complaint ("--prefer http") now works, local file present.
    target, out = _two_target(tmp_path)
    for spelling in ("http", "url"):
        execute_dazzlelink(str(out), mode="open", prefer=spelling)
        assert opened[-1] == URL


def test_kind_fallthrough_open_ended(tmp_path, opened):
    # AC-18: any spelling that is not a rung/alias selects that exact KIND --
    # registry-free (gopher today, user-invented protocols tomorrow).
    target, out = _two_target(tmp_path)
    data = json.loads(out.read_text(encoding="utf-8"))
    data["link"]["locators"].append(
        {"kind": "gopher", "value": "gopher://old.net/doc.pdf"})
    out.write_text(json.dumps(data), encoding="utf-8")

    execute_dazzlelink(str(out), mode="open", prefer="gopher")
    assert opened[-1] == "gopher://old.net/doc.pdf"

    execute_dazzlelink(str(out), mode="open", only="gopher")
    assert opened[-1] == "gopher://old.net/doc.pdf"

    # a spelling matching nothing: --only errors naming what the record HAS
    # (the record is the validator); --prefer never filters, local still opens.
    with pytest.raises(DazzleLinkException) as ei:
        execute_dazzlelink(str(out), mode="open", only="archie")
    assert "no locators match the selection" in str(ei.value)
    execute_dazzlelink(str(out), mode="open", prefer="archie")
    assert os.path.normcase(opened[-1]) == os.path.normcase(str(target))


def test_rungless_kind_listed_and_selectable(tmp_path, capsys, opened):
    # AC-19 at the tool: an ssh locator shows rung-less in info, is excluded
    # by rung filters, and stays selectable by name.
    _target, out = _two_target(tmp_path)
    data = json.loads(out.read_text(encoding="utf-8"))
    data["link"]["locators"].append(
        {"kind": "ssh", "value": "ssh://media-pi.lan/doc.pdf"})
    out.write_text(json.dumps(data), encoding="utf-8")

    execute_dazzlelink(str(out), mode="info")
    info = capsys.readouterr().out
    assert "] ssh" in info and "rung: ?" in info

    with pytest.raises(DazzleLinkException):
        execute_dazzlelink(str(out), mode="open", only="local-network")
    execute_dazzlelink(str(out), mode="open", only="ssh")
    assert opened[-1] == "ssh://media-pi.lan/doc.pdf"


# --- create-side validation ---------------------------------------------------------

def test_create_rejects_malformed_also_url(tmp_path):
    target = tmp_path / "t.txt"
    target.write_text("x", encoding="utf-8")
    r = _dz("create", "--also-url", "notaurl", str(target),
            str(tmp_path / "t.dazzlelink"))
    assert r.returncode == 1
    assert "scheme-form" in r.stderr and "notaurl" in r.stderr
    assert not (tmp_path / "t.dazzlelink").exists()  # nothing was created
