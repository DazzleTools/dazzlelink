"""
Symlink recreation functionality for Dazzlelink.

This module provides functions for recreating symbolic links from dazzlelink files.
"""

import os
import sys
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

from ..exceptions import DazzleLinkException
from dazzle_linklib import recreate_link as _linklib_recreate_link
from dazzle_linklib import DazzleLinkData as _LinklibRecord
from dazzle_linklib import default_path_variants as _default_path_variants
from dazzle_linklib import resolve_target as _resolve_target
# _iter_candidates is the resolver's own walk -- api.md blesses consumer use
# for diagnostics (the "what was tried, in what order" failure output).
from dazzle_linklib.resolver import _iter_candidates

# Add debugging support
VERBOSE = os.environ.get('DAZZLELINK_VERBOSE', '0') == '1'
logger = logging.getLogger(__name__)

def _format_size(size):
    """Human-readable byte size (bytes / KB / MB)."""
    if size < 1024:
        return f"{size} bytes"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def debug_print(message):
    """Print debug messages if VERBOSE is enabled"""
    if VERBOSE:
        print(f"DEBUG: {message}")
        logger.debug(message)

def recreate_link(dazzlelink_path, target_location=None, timestamp_strategy='current', 
                update_dazzlelink=False, use_live_target=False, batch_mode=False):
    """
    Recreate a symbolic link from a .dazzlelink file
    
    Args:
        dazzlelink_path (str): Path to the dazzlelink file
        target_location (str, optional): Override location for the recreated symlink
        timestamp_strategy (str): Strategy for setting timestamps ('current', 'symlink', 'target', 'preserve-all')
        update_dazzlelink (bool): Whether to update the dazzlelink metadata during recreation
        use_live_target (bool): Whether to check the live target file for timestamps
        batch_mode (bool): Accepted for backward compatibility; now a no-op
            (the library does not run the old per-link re-verification pass)

    Returns:
        str: Path to the created symbolic link
    """
    # Delegate to dazzle-linklib's recreate_link (the L2 operation): it loads the
    # record, creates the symlink (via filekit), applies the timestamp strategy,
    # restores file attributes, and -- with update_record -- folds live-target
    # timestamps back into the saved record. ``batch_mode`` is accepted for
    # backward compatibility but is a no-op: the library does not run the tool's
    # old per-link timestamp re-verification pass.
    try:
        return _linklib_recreate_link(
            dazzlelink_path,
            target_location=target_location,
            timestamp_strategy=timestamp_strategy,
            use_live_target=use_live_target,
            update_record=update_dazzlelink,
        )
    except Exception as e:
        raise DazzleLinkException(f"Failed to recreate link from {dazzlelink_path}: {str(e)}")

def execute_dazzlelink(dazzlelink_path, mode=None, config_override=None):
    """
    Execute or open a dazzlelink file
    
    Args:
        dazzlelink_path (str): Path to the dazzlelink file
        mode (str, optional): Override execution mode for this execution
            If None, uses the mode from config_override or the dazzlelink file
        config_override (DazzleLinkConfig, optional): Configuration object to use
            If provided, its settings take precedence over the file's embedded configuration
    """
    try:
        # Parse via the library's record reader (plain JSON, legacy flat, and
        # the polyglot executable form -- exact-line marker, utf-8-sig).
        # IMPORTANT: never shell-execute an executable (script-format)
        # dazzlelink here. On Windows, running the .dazzlelink file through the
        # shell invokes the .dazzlelink file association -- which is itself
        # `dazzlelink execute` -- producing unbounded recursion (a fork bomb).
        # Both formats carry the same JSON; we read it and open the target
        # directly below, identically for both.
        record = _LinklibRecord.from_file(dazzlelink_path)
        link_data = record.to_dict()

        target_path = record.get_target_path()
        if not target_path:
            raise DazzleLinkException(f"Invalid dazzlelink format in {dazzlelink_path}")
        # Legacy flat records stored default_mode at the top level; the nested
        # form lives under config (record accessor). Mode precedence itself is
        # tool policy and stays here.
        default_mode = link_data.get("default_mode") or record.get_default_mode()
        
        # Use mode precedence (matches the monolith): the file knows best what it
        # wants, the CLI always wins, and the global/directory config is only a
        # last-resort fallback when neither the CLI nor the file expressed a
        # preference. See issue #19 -- the previous order let the global config's
        # perpetual "info" default override every file's embedded mode.
        # 1. Command line mode override
        # 2. Dazzlelink file's embedded mode
        # 3. Config override (global/directory) fallback
        execute_mode = mode
        if execute_mode is None:
            execute_mode = default_mode
        if execute_mode is None and config_override is not None:
            execute_mode = config_override.get("default_mode")
        if execute_mode is None:
            execute_mode = "info"
        
        # Execute based on mode
        if execute_mode == "info":
            # Show information about the dazzlelink
            print("DazzleLink Information:")
            print(f"\n Target:\n{target_path}")

            # Original (link) path if available
            if "original_path" in link_data:
                print(f"\n Original Path:\n{link_data['original_path']}")
            elif "link" in link_data and "original_path" in link_data["link"]:
                print(f"\n Original Path:\n{link_data['link']['original_path']}")

            # Relative path (portable cross-machine target) if stored
            target_reps = link_data.get("link", {}).get("target_representations", {})
            rel_path = target_reps.get("relative_path")
            if rel_path:
                print(f"\n Relative Path:\n{rel_path}")

            # Creation date if available
            if "creation_date" in link_data:
                print(f"\n Created: {link_data['creation_date']}")

            # Target details -- prefer a LIVE check of the current on-disk target,
            # falling back to the metadata stored when the dazzlelink was created.
            target_exists = os.path.exists(target_path)
            print("\n Target Details:")
            print(f"  Exists: {'Yes' if target_exists else 'No'}")
            if target_exists:
                print(f"  Size: {_format_size(os.path.getsize(target_path))}")
                _, ext = os.path.splitext(target_path)
                print(f"  Type: {ext[1:].upper() if ext else 'Unknown'}")
            elif "target" in link_data:
                target_info = link_data["target"]
                print(f"  Type: {target_info.get('type', 'Unknown')}")
                if target_info.get('size') is not None:
                    print(f"  Size: {_format_size(target_info['size'])} (at creation)")

        elif execute_mode == "open" or execute_mode == "auto":
            # Resolution is the library's walk (priority order: path ->
            # relative -> unc -> drive -> subst -> ...), with relative locators
            # anchored at the record file's directory and LIVE RE-RESOLUTION:
            # each candidate is re-derived against THIS machine's current
            # drive/UNC/subst mappings (issue #24), so a base stored dead on
            # the creating machine can resolve via the form this machine maps.
            base_dir = os.path.dirname(os.path.abspath(dazzlelink_path))
            hit = _resolve_target(
                record, base_dir=base_dir, variants=_default_path_variants
            )
            resolved_path = hit["value"] if hit else None

            if resolved_path is None:
                # DEPRECATED fallback (removal slated for the next minor):
                # probe the LINK's own stored path_representations. Dubious --
                # it opens the link file's old location, not the target -- but
                # kept one release so the delegation and the probe removal stay
                # separately attributable.
                path_reps = link_data.get("link", {}).get("path_representations", {}) or {}
                for key, candidate in path_reps.items():
                    if isinstance(candidate, str) and candidate and os.path.exists(candidate):
                        debug_print(f"Resolved via deprecated link path_representations[{key}]")
                        resolved_path = candidate
                        break

            if resolved_path is None:
                # Diagnostic parity: list exactly what the resolver tried, in
                # order, by re-walking the same candidate generator.
                tried = [
                    candidate
                    for _loc, candidate in _iter_candidates(
                        record, base_dir=base_dir, variants=_default_path_variants
                    )
                ]
                tried_lines = "\n".join(f"  {c}" for c in tried) or "  (no candidates)"
                raise DazzleLinkException(
                    f"Target not found. Tried (in resolution order):\n{tried_lines}"
                )

            # Open the resolved target
            if os.name == 'nt':
                os.startfile(resolved_path)
            else:
                import subprocess
                subprocess.run(['xdg-open', resolved_path])
        
        else:
            raise DazzleLinkException(f"Unknown execution mode: {execute_mode}")
            
    except Exception as e:
        raise DazzleLinkException(f"Failed to execute dazzlelink {dazzlelink_path}: {str(e)}")
