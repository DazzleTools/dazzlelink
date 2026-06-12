"""Allow running as: python -m dazzlelink"""
import sys

from .cli import main

if __name__ == "__main__":
    # Propagate main()'s return code as the process exit status so errors are
    # detectable by scripts/CI (without this, `python -m dazzlelink` always
    # exited 0, even on failure).
    sys.exit(main())
