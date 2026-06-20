"""dazzlelink's link record -- provided by the dazzle-linklib library (L2).

The ``DazzleLinkData`` implementation moved to **dazzle-linklib** (the DazzleLib
stack's L2 link-record layer). This module re-exports it so the tool's existing
imports (``from ..data import DazzleLinkData``) keep working unchanged while the
record model lives in exactly one place across the stack.

See STACK-MAP D1 (one home per capability); extracted in stack phase P2.
"""

from dazzle_linklib import DazzleLinkData

__all__ = ["DazzleLinkData"]
