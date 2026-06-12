"""Verify the generated executable .dazzlelink parses AND runs --info (no GUI)."""
import os, sys, tempfile, shutil, subprocess, py_compile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from dazzlelink.config import DazzleLinkConfig
from dazzlelink.operations.core import DazzleLink

sb = tempfile.mkdtemp(prefix='dl_exec_')
try:
    # Mimic the real hazard: a path under a 'Users'-like segment (\U escape)
    tdir = os.path.join(sb, 'Users', 'proj')
    os.makedirs(tdir)
    target = os.path.join(tdir, 'target.txt')
    open(target, 'w').write('payload')
    print("target path (note backslashes):", repr(target))

    out = os.path.join(sb, 'exec.dazzlelink')
    DazzleLink(DazzleLinkConfig()).serialize_link(
        target, output_path=out, make_executable=True, require_symlink=False)

    # (1) Does the generated script PARSE as Python? (the \U bug)
    try:
        py_compile.compile(out, doraise=True)
        print("PARSE: OK")
    except py_compile.PyCompileError as e:
        print("PARSE: FAIL ->", str(e).splitlines()[-1][:80]); raise SystemExit(1)

    # (2) Does `python <file> --info` RUN end-to-end? (the marker bug)
    r = subprocess.run([sys.executable, out, '--info'], capture_output=True, text=True)
    print("run --info rc:", r.returncode)
    print("stdout:", (r.stdout or '').strip()[:200])
    if r.stderr.strip():
        print("stderr:", r.stderr.strip()[:300])
    ok = r.returncode == 0 and 'Target' in (r.stdout or '')
    print("MARKER/RUN:", "OK" if ok else "FAIL")
finally:
    shutil.rmtree(sb, ignore_errors=True)
