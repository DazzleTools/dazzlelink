"""
Regression sweep for dazzlelink 0.9.1 / dazzle-linklib 0.2.1.

Parts:
  B  -- batch_import flag matrix (the changed path)
  C  -- recreate_link + apply_record_metadata direct API
  D  -- smoke execute --mode info + rebase on stale record

Run with:
    python tests/one-offs/test_0901_regression.py
"""

import os
import sys
import time
import json
import subprocess
import tempfile
import warnings
import traceback
from pathlib import Path

# Ensure the editable install is reachable
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

import dazzlelink
import dazzle_linklib
from dazzle_linklib import (
    DazzleLinkData,
    create_link,
    recreate_link,
    apply_record_metadata,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
REVIEW = "REVIEW"

_results = []


def record(label, status, detail=""):
    tag = f"[{status}]"
    print(f"  {tag:8s} {label}")
    if detail:
        for line in detail.strip().splitlines():
            print(f"           {line}")
    _results.append((label, status, detail))
    # Under pytest, a recorded FAIL must actually fail the collecting test so the
    # sweep is a real regression guard (otherwise these test_* functions would
    # always pass). The manual `python tests/one-offs/...` runner doesn't set
    # this env var, so it still aggregates every result in main() instead.
    if status == FAIL and "PYTEST_CURRENT_TEST" in os.environ:
        raise AssertionError(f"{label}: {detail}")


def section(name):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


def run_cli(*args, cwd=None, env=None):
    """Run dazzlelink CLI and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, "-m", "dazzlelink"] + list(args)
    r = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or os.getcwd(),
        env=env or os.environ.copy(),
    )
    return r.returncode, r.stdout, r.stderr


def make_real_file(path, content=b"dazzle test content"):
    """Create a real file at path."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(content)
    return path


def make_symlink(link_path, target_path):
    """Create a symlink, using Python's os.symlink (works with developer mode)."""
    lp = Path(link_path)
    lp.parent.mkdir(parents=True, exist_ok=True)
    if lp.is_symlink() or lp.exists():
        lp.unlink(missing_ok=True)
    os.symlink(str(target_path), str(lp))
    return str(lp)


def scratch_dir(name):
    """Create and return a named scratch directory in %TEMP%."""
    d = Path(tempfile.gettempdir()) / f"dz_0901_{name}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def minimal_record(target_path, link_path, *, modified_ts=None, created_ts=None, accessed_ts=None, attributes=None):
    """Build a minimal DazzleLinkData programmatically."""
    rec = DazzleLinkData()
    rec.set_target_path(str(target_path))
    rec.set_original_path(str(link_path))
    rec.data["link"]["type"] = "file"
    rec.data["target"]["type"] = "file"
    rec.data["target"]["exists"] = True
    if modified_ts is not None:
        rec.set_link_timestamps(
            created=created_ts,
            modified=modified_ts,
            accessed=accessed_ts,
        )
        rec.set_target_timestamps(
            created=created_ts,
            modified=modified_ts,
            accessed=accessed_ts,
        )
    if attributes:
        rec.data["link"]["attributes"] = attributes
    return rec


# ---------------------------------------------------------------------------
# Part B -- batch_import flag matrix
# ---------------------------------------------------------------------------

def test_B1_plain_recreate():
    """B1: Plain recreate (delete link, import, confirm symlink restored)."""
    section("B1: Plain recreate via dazzlelink import")
    d = scratch_dir("B1")
    target = d / "target.txt"
    link = d / "link.lnk.txt"
    dl = d / "link.lnk.txt.dazzlelink"

    make_real_file(target)
    make_symlink(link, target)

    rc, out, err = run_cli("create", str(link), str(dl), cwd=str(d))
    if rc != 0:
        record("B1.create", FAIL, f"create failed rc={rc}\n{err}")
        return
    record("B1.create", PASS, out.strip().splitlines()[0] if out.strip() else "(no output)")

    link.unlink(missing_ok=True)
    assert not link.exists() and not link.is_symlink(), "link not removed"

    rc, out, err = run_cli("import", "--pattern", "*.dazzlelink", str(d), cwd=str(d))
    if rc != 0:
        record("B1.import", FAIL, f"import returned rc={rc}\n{err}\n{out}")
        return

    is_link = link.is_symlink()
    resolves = link.exists()
    record("B1.import", PASS if is_link else FAIL,
           f"is_symlink={is_link} resolves={resolves}\n{out.strip()}")
    record("B1.symlink-resolves", PASS if resolves else FAIL,
           f"readlink={os.readlink(str(link)) if is_link else 'N/A'}")


def test_B2_use_live_target_timestamp_target():
    """B2: --use-live-target --timestamp-strategy target (the workflow.png demo path)."""
    section("B2: --use-live-target --timestamp-strategy target")
    d = scratch_dir("B2")
    target = d / "workflow.png"
    link = d / "workflow.lnk.png"
    dl = d / "workflow.lnk.png.dazzlelink"

    make_real_file(target, b"\x89PNG fake")
    make_symlink(link, target)

    rc, out, err = run_cli("create", str(link), str(dl), cwd=str(d))
    if rc != 0:
        record("B2.create", FAIL, err)
        return

    link.unlink(missing_ok=True)

    rc, out, err = run_cli(
        "import",
        "--use-live-target",
        "--timestamp-strategy", "target",
        "--pattern", "*.dazzlelink",
        str(d),
        cwd=str(d),
    )
    if rc != 0:
        record("B2.import", FAIL, f"rc={rc}\n{err}\n{out}")
        return

    is_link = link.is_symlink()
    resolves = link.exists()
    record("B2.import", PASS if is_link else FAIL,
           f"is_symlink={is_link} resolves={resolves}")

    # Check mtime proximity to target
    if is_link:
        link_mtime = os.lstat(str(link)).st_mtime
        target_mtime = os.stat(str(target)).st_mtime
        diff = abs(link_mtime - target_mtime)
        record("B2.mtime-proximity",
               PASS if diff < 5.0 else REVIEW,
               f"link_mtime={link_mtime:.3f} target_mtime={target_mtime:.3f} diff={diff:.3f}s")
    record("B2.output-no-error", PASS if "ERROR" not in out else FAIL, out.strip()[:300])


def test_B3_timestamp_strategy_symlink():
    """B3: --timestamp-strategy symlink"""
    section("B3: --timestamp-strategy symlink")
    d = scratch_dir("B3")
    target = d / "asset.bin"
    link = d / "asset.lnk.bin"
    dl = d / "asset.lnk.bin.dazzlelink"

    make_real_file(target)
    make_symlink(link, target)
    # Record the link's mtime now
    link_mtime_before = os.lstat(str(link)).st_mtime

    rc, out, err = run_cli("create", str(link), str(dl), cwd=str(d))
    if rc != 0:
        record("B3.create", FAIL, err)
        return

    link.unlink(missing_ok=True)
    time.sleep(1.1)  # ensure new link would have different mtime from current

    rc, out, err = run_cli(
        "import",
        "--timestamp-strategy", "symlink",
        "--pattern", "*.dazzlelink",
        str(d),
        cwd=str(d),
    )
    if rc != 0:
        record("B3.import", FAIL, f"rc={rc}\n{err}\n{out}")
        return

    is_link = link.is_symlink()
    record("B3.import", PASS if is_link else FAIL,
           f"is_symlink={is_link}\n{out.strip()}")
    record("B3.no-error", PASS if "ERROR" not in out else FAIL, "")


def test_B3b_timestamp_strategy_current():
    """B3b: --timestamp-strategy current (no-op on timestamps)."""
    section("B3b: --timestamp-strategy current")
    d = scratch_dir("B3b")
    target = d / "img.dat"
    link = d / "img.lnk.dat"
    dl = d / "img.lnk.dat.dazzlelink"

    make_real_file(target)
    make_symlink(link, target)

    rc, out, err = run_cli("create", str(link), str(dl), cwd=str(d))
    if rc != 0:
        record("B3b.create", FAIL, err)
        return

    link.unlink(missing_ok=True)

    rc, out, err = run_cli(
        "import",
        "--timestamp-strategy", "current",
        "--pattern", "*.dazzlelink",
        str(d),
        cwd=str(d),
    )
    is_link = link.is_symlink()
    record("B3b.import", PASS if (rc == 0 and is_link) else FAIL,
           f"rc={rc} is_symlink={is_link}")
    record("B3b.no-error", PASS if "ERROR" not in out else FAIL, "")


def test_B4_partial_timestamp_record():
    """B4: Record with only 'modified' set (None-timestamp fix regression test).

    Before the 0.2.1 fix, filekit would receive a timestamp dict with None
    values for created/accessed, abort the entire metadata apply (including
    attributes), and warn about 'NoneType'/'accessed'. After the fix it
    backfills missing with modified.
    """
    section("B4: Partial-timestamp record (None-timestamp fix)")
    d = scratch_dir("B4")
    target = d / "partial.dat"
    link = d / "partial.lnk.dat"
    dl = d / "partial.lnk.dat.dazzlelink"

    make_real_file(target)

    # Build a record with ONLY modified set (created/accessed None)
    modified_ts = time.time() - 3600  # 1 hour ago
    rec = minimal_record(target, link, modified_ts=modified_ts)
    # Verify created/accessed are None (the pre-fix problem shape)
    ts = rec.get_link_timestamps()
    assert ts.get("created") is None, f"expected created=None, got {ts.get('created')}"
    assert ts.get("accessed") is None, f"expected accessed=None, got {ts.get('accessed')}"

    rec.save_to_file(str(dl))

    # Capture warnings to ensure no filekit NoneType warning escapes
    import io
    warning_messages = []
    original_showwarning = warnings.showwarning
    def capture_warning(message, category, filename, lineno, file=None, line=None):
        warning_messages.append(str(message))
        original_showwarning(message, category, filename, lineno, file, line)
    warnings.showwarning = capture_warning

    try:
        rc, out, err = run_cli(
            "import",
            "--timestamp-strategy", "symlink",
            "--pattern", "*.dazzlelink",
            str(d),
            cwd=str(d),
        )
    finally:
        warnings.showwarning = original_showwarning

    is_link = link.is_symlink()
    none_type_error = "NoneType" in out or "NoneType" in err or "'accessed'" in err or "'accessed'" in out
    record("B4.import-succeeds", PASS if (rc == 0 and is_link) else FAIL,
           f"rc={rc} is_symlink={is_link}")
    record("B4.no-nonetype-warning", PASS if not none_type_error else FAIL,
           f"stdout: {out[:200]}\nstderr: {err[:200]}")
    record("B4.symlink-resolves", PASS if link.exists() else FAIL,
           f"target={os.readlink(str(link)) if is_link else 'N/A'}")


def test_B5_dry_run():
    """B5: --dry-run variant (no links created, output says WOULD CREATE)."""
    section("B5: --dry-run")
    d = scratch_dir("B5")
    target = d / "img.png"
    link = d / "img.lnk.png"
    dl = d / "img.lnk.png.dazzlelink"

    make_real_file(target)
    make_symlink(link, target)

    rc, out, err = run_cli("create", str(link), str(dl), cwd=str(d))
    if rc != 0:
        record("B5.create", FAIL, err)
        return

    link.unlink(missing_ok=True)

    rc, out, err = run_cli(
        "import",
        "--dry-run",
        "--pattern", "*.dazzlelink",
        str(d),
        cwd=str(d),
    )
    link_was_created = link.is_symlink()
    would_create_in_output = "WOULD CREATE" in out
    record("B5.dry-run-no-link", PASS if not link_was_created else FAIL,
           f"link_created={link_was_created}")
    record("B5.would-create-message", PASS if would_create_in_output else FAIL,
           f"output: {out.strip()[:300]}")


def test_B6_flatten():
    """B6: --flatten (multiple records in subdirs -> one flat dir)."""
    section("B6: --flatten")
    d = scratch_dir("B6")
    sub = d / "sub"
    sub.mkdir(exist_ok=True)
    dest = d / "flat_dest"
    dest.mkdir(exist_ok=True)

    # Create two targets and links in different subdirs
    targets = []
    dls = []
    for i, subdir in enumerate(["a", "b"]):
        sd = d / subdir
        sd.mkdir(exist_ok=True)
        t = sd / f"file{i}.dat"
        make_real_file(t, f"content{i}".encode())
        l = sd / f"file{i}.lnk.dat"
        make_symlink(l, t)
        dl = sd / f"file{i}.lnk.dat.dazzlelink"
        rc, out, err = run_cli("create", str(l), str(dl), cwd=str(sd))
        if rc != 0:
            record(f"B6.create-{i}", FAIL, err)
            return
        dls.append(dl)

    rc, out, err = run_cli(
        "import",
        "--flatten",
        "--recursive",
        "--pattern", "*.dazzlelink",
        "--target-location", str(dest),
        str(d),
        cwd=str(d),
    )
    created_links = list(dest.iterdir())
    flat_count = len(created_links)
    record("B6.import", PASS if rc == 0 else FAIL, f"rc={rc}")
    record("B6.flatten-count", PASS if flat_count == 2 else REVIEW,
           f"links in dest={flat_count} expected=2\nfiles: {[f.name for f in created_links]}")


def test_B7_windows_attributes():
    """B7: Record with hidden+readonly attributes -- confirm recreated link gets them."""
    section("B7: Windows file attributes (hidden + readonly)")
    d = scratch_dir("B7")
    target = d / "secret.dat"
    link = d / "secret.lnk.dat"
    dl = d / "secret.lnk.dat.dazzlelink"

    make_real_file(target)

    # Build a record with hidden=True, readonly=True
    rec = minimal_record(target, link, attributes={"hidden": True, "system": False, "readonly": True})
    rec.save_to_file(str(dl))

    rc, out, err = run_cli(
        "import",
        "--timestamp-strategy", "current",
        "--pattern", "*.dazzlelink",
        str(d),
        cwd=str(d),
    )
    is_link = link.is_symlink()
    record("B7.import-succeeds", PASS if (rc == 0 and is_link) else FAIL,
           f"rc={rc} is_symlink={is_link}")

    if is_link:
        # Check attributes via ctypes on the link itself (not following it)
        import ctypes
        FILE_ATTRIBUTE_HIDDEN = 0x2
        FILE_ATTRIBUTE_READONLY = 0x1
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(link))
        if attrs == -1:
            record("B7.attributes-check", REVIEW, f"GetFileAttributesW failed (attrs=-1)")
        else:
            has_hidden = bool(attrs & FILE_ATTRIBUTE_HIDDEN)
            has_readonly = bool(attrs & FILE_ATTRIBUTE_READONLY)
            record("B7.hidden-set", PASS if has_hidden else FAIL,
                   f"attrs=0x{attrs:08X} hidden={has_hidden}")
            record("B7.readonly-set", PASS if has_readonly else FAIL,
                   f"attrs=0x{attrs:08X} readonly={has_readonly}")

        # Check target was NOT modified (its attributes should be normal)
        target_attrs = ctypes.windll.kernel32.GetFileAttributesW(str(target))
        target_hidden = bool(target_attrs & FILE_ATTRIBUTE_HIDDEN) if target_attrs != -1 else False
        record("B7.target-untouched", PASS if not target_hidden else FAIL,
               f"target_attrs=0x{target_attrs:08X} target_hidden={target_hidden}")

        # Clean up readonly to allow scratch cleanup later
        try:
            # Remove readonly from link before cleanup
            new_attrs = attrs & ~FILE_ATTRIBUTE_READONLY
            ctypes.windll.kernel32.SetFileAttributesW(str(link), new_attrs)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Part C -- recreate_link + apply_record_metadata direct API
# ---------------------------------------------------------------------------

def test_C1_recreate_partial_timestamps():
    """C1: recreate_link on partial-timestamp record (None-timestamp regression)."""
    section("C1: recreate_link with partial timestamps (lib direct)")
    d = scratch_dir("C1")
    target = d / "real.dat"
    link = d / "real.lnk.dat"
    dl = d / "real.lnk.dat.dazzlelink"

    make_real_file(target)

    # Only modified set (created/accessed None) -- the pre-fix problem shape
    modified_ts = time.time() - 7200
    rec = minimal_record(target, link, modified_ts=modified_ts)
    rec.save_to_file(str(dl))

    try:
        created_path = recreate_link(
            str(dl),
            timestamp_strategy="symlink",
            use_live_target=False,
        )
    except Exception as e:
        record("C1.recreate-no-exception", FAIL, f"{type(e).__name__}: {e}")
        return

    is_link = Path(link).is_symlink()
    resolves = Path(link).exists()
    record("C1.recreate-no-exception", PASS, f"returned={created_path}")
    record("C1.link-created", PASS if is_link else FAIL,
           f"is_symlink={is_link} resolves={resolves}")

    if is_link:
        link_mtime = os.lstat(str(link)).st_mtime
        diff = abs(link_mtime - modified_ts)
        record("C1.mtime-applied", PASS if diff < 5.0 else REVIEW,
               f"link_mtime={link_mtime:.3f} expected={modified_ts:.3f} diff={diff:.3f}s")


def test_C2_apply_record_metadata():
    """C2: apply_record_metadata returns True when it applies, False for current+no-attrs."""
    section("C2: apply_record_metadata return values")
    d = scratch_dir("C2")
    target = d / "meta.dat"
    link = d / "meta.lnk.dat"

    make_real_file(target)
    make_symlink(link, target)

    # --- Case A: current strategy + no attributes => should return False ---
    rec_no_ts = minimal_record(target, link)
    result_a = apply_record_metadata(rec_no_ts, str(link), timestamp_strategy="current", use_live_target=False)
    record("C2.current-no-attrs-returns-False", PASS if result_a is False else FAIL,
           f"returned={result_a}")

    # --- Case B: symlink strategy + timestamps set => should return True ---
    modified_ts = time.time() - 1800
    rec_with_ts = minimal_record(target, link, modified_ts=modified_ts)
    result_b = apply_record_metadata(rec_with_ts, str(link), timestamp_strategy="symlink")
    record("C2.symlink-with-ts-returns-True", PASS if result_b is True else FAIL,
           f"returned={result_b}")

    # --- Case C: only attributes set => should return True ---
    rec_attrs_only = minimal_record(target, link, attributes={"hidden": True, "system": False, "readonly": False})
    result_c = apply_record_metadata(rec_attrs_only, str(link), timestamp_strategy="current")
    record("C2.attrs-only-returns-True", PASS if result_c is True else FAIL,
           f"returned={result_c}")

    # --- Case D: apply acts on link, not target ---
    # Get target mtime before
    target_mtime_before = os.stat(str(target)).st_mtime
    rec_ts = minimal_record(target, link, modified_ts=time.time() - 9999)
    apply_record_metadata(rec_ts, str(link), timestamp_strategy="symlink")
    target_mtime_after = os.stat(str(target)).st_mtime
    record("C2.writes-link-not-target", PASS if abs(target_mtime_after - target_mtime_before) < 1.0 else FAIL,
           f"target_mtime changed by {abs(target_mtime_after - target_mtime_before):.3f}s")

    # Clean up readonly if set
    import ctypes
    attrs = ctypes.windll.kernel32.GetFileAttributesW(str(link))
    if attrs != -1 and (attrs & 0x2):  # hidden
        ctypes.windll.kernel32.SetFileAttributesW(str(link), attrs & ~0x2)


# ---------------------------------------------------------------------------
# Part D -- Smoke tests for execute + rebase
# ---------------------------------------------------------------------------

def test_D1_execute_mode_info_real_fixture():
    """D1: execute --mode info on the real fixture."""
    section("D1: execute --mode info on real fixture")
    fixture = r"C:\code\dazzlelink\examples\Roddenberry-Saturn.lnk.png.dazzlelink"
    if not Path(fixture).exists():
        record("D1.fixture-exists", SKIP, f"not found: {fixture}")
        return

    rc, out, err = run_cli("execute", "--mode", "info", fixture)
    has_target = "Target:" in out
    has_created = "Created:" in out
    record("D1.execute-info-rc0", PASS if rc == 0 else FAIL, f"rc={rc}")
    record("D1.has-target-line", PASS if has_target else FAIL,
           out.strip()[:400])
    record("D1.has-created-line", PASS if has_created else FAIL, "")


def test_D2_rebase_stale_record():
    """D2: rebase on a dir with a stale-relative record (expect 1 changed)."""
    section("D2: rebase on stale-relative record")
    d = scratch_dir("D2")
    # Real target
    real_sub = d / "real_sub"
    real_sub.mkdir(exist_ok=True)
    target = real_sub / "target.dat"
    make_real_file(target)

    # Build a record: valid absolute, stale relative ("old_sub/target.dat")
    link = d / "link.lnk.dat"
    dl = d / "link.lnk.dat.dazzlelink"

    rec = minimal_record(target, link)
    # Manually set a stale relative path in the data
    rec.data["link"]["relative_path"] = "old_sub/target.dat"
    rec.data["link"]["path_representations"] = {
        "original_path": str(link),
        "relative_path": "old_sub/target.dat",
    }
    rec.save_to_file(str(dl))

    rc, out, err = run_cli("rebase", str(d), cwd=str(d))
    changed_line = "changed" in out.lower()
    record("D2.rebase-rc0", PASS if rc == 0 else FAIL, f"rc={rc}")
    record("D2.changed-in-output", PASS if changed_line else REVIEW,
           out.strip()[:400])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"\ndazzlelink {dazzlelink.__version__}")
    print(f"dazzle_linklib {dazzle_linklib.__version__}")
    print("\n--- 0.9.1 / lib 0.2.1 regression sweep ---")

    # Part B
    test_B1_plain_recreate()
    test_B2_use_live_target_timestamp_target()
    test_B3_timestamp_strategy_symlink()
    test_B3b_timestamp_strategy_current()
    test_B4_partial_timestamp_record()
    test_B5_dry_run()
    test_B6_flatten()
    test_B7_windows_attributes()

    # Part C
    test_C1_recreate_partial_timestamps()
    test_C2_apply_record_metadata()

    # Part D
    test_D1_execute_mode_info_real_fixture()
    test_D2_rebase_stale_record()

    # --- Summary ---
    section("SUMMARY")
    counts = {PASS: 0, FAIL: 0, REVIEW: 0, SKIP: 0}
    fails = []
    reviews = []
    for label, status, detail in _results:
        counts[status] = counts.get(status, 0) + 1
        if status == FAIL:
            fails.append((label, detail))
        elif status == REVIEW:
            reviews.append((label, detail))

    print(f"  PASS:   {counts[PASS]}")
    print(f"  FAIL:   {counts[FAIL]}")
    print(f"  REVIEW: {counts[REVIEW]}")
    print(f"  SKIP:   {counts[SKIP]}")

    if fails:
        print("\nFAILURES:")
        for label, detail in fails:
            print(f"  - {label}")
            if detail:
                for line in detail.strip().splitlines()[:4]:
                    print(f"      {line}")

    if reviews:
        print("\nREVIEW items:")
        for label, detail in reviews:
            print(f"  - {label}")

    verdict = "HOLD" if counts[FAIL] > 0 else "SHIP"
    print(f"\nVerdict: {verdict}")
    return 0 if verdict == "SHIP" else 1


if __name__ == "__main__":
    sys.exit(main())
