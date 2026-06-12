"""One-off: verify Commit 1 fixes (GT-2 #18 AttributeError, GT-3 #19 precedence)."""
import os, sys, json, tempfile, shutil

# Force the in-repo src package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
import dazzlelink
from dazzlelink.operations.core import DazzleLink
from dazzlelink.operations.recreate import execute_dazzlelink
from dazzlelink.config import DazzleLinkConfig

sandbox = tempfile.mkdtemp(prefix='dl_c1_')
try:
    real = os.path.join(sandbox, 'target.txt')
    with open(real, 'w') as f:
        f.write('hello')

    # --- GT-2: serialize_link with make_executable=True must NOT raise AttributeError ---
    cfg = DazzleLinkConfig()
    dl = DazzleLink(cfg)
    out = os.path.join(sandbox, 'exec.dazzlelink')
    try:
        dl.serialize_link(real, output_path=out, make_executable=True, require_symlink=False)
        print("GT-2 PASS: serialize_link(make_executable=True) did not raise; file exists:", os.path.exists(out))
    except Exception as e:
        print("GT-2 FAIL:", type(e).__name__, e)

    # --- GT-3: file-embedded mode must beat a global 'info' config_override ---
    # Build a .dazzlelink whose embedded default_mode is 'open'
    open_file = os.path.join(sandbox, 'open.dazzlelink')
    dl.serialize_link(real, output_path=open_file, make_executable=False, mode='open', require_symlink=False)
    data = json.load(open(open_file))
    embedded = data.get('config', {}).get('default_mode')
    print("embedded default_mode in file:", embedded)

    # Simulate execute with a global config_override whose default_mode is 'info'
    global_cfg = DazzleLinkConfig()  # default_mode == 'info'
    # We can't easily capture os.startfile; instead replicate the precedence logic check
    # by reading what execute_dazzlelink would resolve. Use mode=None (no CLI), config_override=global.
    # 'open' would call os.startfile -> patch it to capture.
    captured = {}
    import dazzlelink.operations.recreate as rc
    orig_startfile = getattr(os, 'startfile', None)
    def fake_startfile(p):
        captured['opened'] = p
    if hasattr(os, 'startfile'):
        os.startfile = fake_startfile
    try:
        execute_dazzlelink(open_file, mode=None, config_override=global_cfg)
    except Exception as e:
        captured['error'] = f"{type(e).__name__}: {e}"
    finally:
        if orig_startfile:
            os.startfile = orig_startfile
    if captured.get('opened'):
        print("GT-3 PASS: file's 'open' mode won over global 'info' (target opened):", os.path.basename(captured['opened']))
    else:
        print("GT-3 RESULT:", captured)
finally:
    shutil.rmtree(sandbox, ignore_errors=True)
