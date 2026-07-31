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
# The locality axis + scheme-aware checker (0.4.0, issue #25): execute's
# default reachability judge -- filesystem candidates by existence,
# scheme-form candidates (https://...) assumed openable without probing.
from dazzle_linklib import SchemeAwareReachability as _SchemeAwareReachability
from dazzle_linklib import locator_rung as _locator_rung
from dazzle_linklib import reach_of as _reach_of
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

def _pinned_candidate(record, locators, target_index, base_dir):
    """The locator pinned by ``--target N``, anchored if relative.

    N addresses the same enumeration ``--mode info`` prints (``get_locators``
    order). Raises with the valid range when N misses it.
    """
    if not locators:
        raise DazzleLinkException("--target: this record has no locators")
    if not (0 <= target_index < len(locators)):
        raise DazzleLinkException(
            f"--target {target_index} is out of range: this record has "
            f"{len(locators)} locator(s), valid indices 0..{len(locators) - 1}"
        )
    loc = locators[target_index]
    candidate = loc.get("value")
    if (loc.get("kind") == "relative" and base_dir and candidate
            and not os.path.isabs(candidate)):
        candidate = os.path.normpath(os.path.join(base_dir, candidate))
    return loc, candidate


def _available_selection(locators):
    """One-line summary of the reaches (and kinds) a record's locators cover.

    Feeds the no-match error so a failed --only/--kind names what the record
    DOES have instead of leaving the user to guess.
    """
    by_reach = {}
    for loc in locators:
        kind = loc.get("kind") or "?"
        rung = _locator_rung(kind)
        reach = _reach_of(rung) if rung else "unknown"
        by_reach.setdefault(reach, set()).add(kind)
    return "; ".join(
        f"{reach} ({', '.join(sorted(kinds))})"
        for reach, kinds in sorted(by_reach.items())
    ) or "(no locators)"


def _would_open(record, locators, base_dir, prefer=None, only=None,
                kinds=None, target_index=None):
    """The (index, value) the open walk would use, or ``None`` if nothing wins.

    Judged by SchemeAwareReachability: scheme-form values are ASSUMED
    reachable -- never probed, so info stays offline-correct with zero
    network I/O -- and filesystem values are exists-checked. The index is
    the position in ``locators`` (the ``--target`` address space); a
    machine-derived variant maps back to the locator it was derived from.
    """
    checker = _SchemeAwareReachability()
    if target_index is not None:
        _loc, candidate = _pinned_candidate(record, locators, target_index, base_dir)
        return (target_index, candidate) if checker.is_reachable(candidate) else None
    for loc, candidate in _iter_candidates(
        record, base_dir=base_dir, variants=_default_path_variants,
        prefer=prefer, only=only, kinds=kinds,
    ):
        if checker.is_reachable(candidate):
            try:
                idx = locators.index(loc)
            except ValueError:
                idx = None
            return (idx, candidate)
    return None


def execute_dazzlelink(dazzlelink_path, mode=None, config_override=None,
                       prefer=None, only=None, kinds=None, target_index=None):
    """
    Execute or open a dazzlelink file

    Args:
        dazzlelink_path (str): Path to the dazzlelink file
        mode (str, optional): Override execution mode for this execution
            If None, uses the mode from config_override or the dazzlelink file
        config_override (DazzleLinkConfig, optional): Configuration object to use
            If provided, its settings take precedence over the file's embedded configuration
        prefer (str, optional): Locality rung or reach alias -- reorders the
            candidate walk by rank-distance toward it (a preference: everything
            else remains as fallback)
        only (str, optional): Locality rung or reach alias -- restricts the walk
            to locators on that rung/reach
        kinds (list, optional): Locator kinds to restrict the walk to (e.g. ['url'])
        target_index (int, optional): Pin exactly locator [N] as numbered by
            info mode; reachability-checked, clean error when out of range
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
        if not target_path and not record.get_locators():
            # A record without a stored target_path is still valid when it
            # carries locators (issue #25: the url-only record -- the
            # .url-file replacement). Invalid = NO way to reach anything.
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

        # The record file's directory anchors relative locators -- both the
        # open walk and info's would-open preview need it.
        base_dir = os.path.dirname(os.path.abspath(dazzlelink_path))

        # Execute based on mode
        if execute_mode == "info":
            # Show information about the dazzlelink
            print("DazzleLink Information:")
            if target_path:
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
            # A url-only record has no stored target_path: the Targets listing
            # below is its whole story.
            if target_path:
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

            # Multi-target listing (issue #25): every locator the record
            # carries, numbered exactly as --target N addresses them, with
            # its locality rung. "Would open" runs the same walk as
            # --mode open, judged by the scheme-aware checker -- scheme-form
            # locators are ASSUMED openable, so info performs zero network I/O.
            locators = record.get_locators()
            if locators:
                print(f"\n Targets ({len(locators)}):")
                for i, loc in enumerate(locators):
                    kind = loc.get("kind") or "?"
                    rung = _locator_rung(kind) or "?"
                    print(f"  [{i}] {kind:<9} rung: {rung:<9} {loc.get('value')}")
                would = _would_open(record, locators, base_dir,
                                    prefer=prefer, only=only, kinds=kinds,
                                    target_index=target_index)
                if would is not None:
                    idx, candidate = would
                    idx_label = f"[{idx}]" if idx is not None else "(derived)"
                    print(f"\n Would open: {idx_label} {candidate}")
                else:
                    print("\n Would open: (none reachable with the current selection)")
                print("  (select with --target N, or --prefer/--only <rung|reach>)")

        elif execute_mode == "open" or execute_mode == "auto":
            # Resolution is the library's walk (priority order: path ->
            # relative -> unc -> drive -> subst -> explicit locators), with
            # relative locators anchored at the record file's directory and
            # LIVE RE-RESOLUTION: each candidate is re-derived against THIS
            # machine's current drive/UNC/subst mappings (issue #24), so a
            # base stored dead on the creating machine can resolve via the
            # form this machine maps. The scheme-aware checker (issue #25)
            # judges reachability: filesystem candidates by existence,
            # scheme-form candidates (https://...) assumed openable -- the
            # OS handler owns whether a scheme actually opens. Selectors
            # shape the walk: kinds filter -> only filter -> prefer
            # rank-distance reordering.
            selection_active = bool(prefer or only or kinds)
            checker = _SchemeAwareReachability()
            if target_index is not None:
                # Explicit pin: exactly the locator info numbered [N].
                locators = record.get_locators()
                loc, candidate = _pinned_candidate(
                    record, locators, target_index, base_dir
                )
                if not checker.is_reachable(candidate):
                    raise DazzleLinkException(
                        f"--target {target_index} ({loc.get('kind')}: "
                        f"{candidate}) is not reachable"
                    )
                resolved_path = candidate
            else:
                hit = _resolve_target(
                    record, base_dir=base_dir, variants=_default_path_variants,
                    reachability=checker, prefer=prefer, only=only, kinds=kinds,
                )
                resolved_path = hit["value"] if hit else None

            if resolved_path is None and not selection_active:
                # DEPRECATED fallback (removal slated for the next minor):
                # probe the LINK's own stored path_representations. Dubious --
                # it opens the link file's old location, not the target -- but
                # kept one release so the delegation and the probe removal stay
                # separately attributable. Never taken when a selector narrowed
                # the walk: an --only/--kind miss must not leak to the link
                # file's old location.
                path_reps = link_data.get("link", {}).get("path_representations", {}) or {}
                for key, candidate in path_reps.items():
                    if isinstance(candidate, str) and candidate and os.path.exists(candidate):
                        debug_print(f"Resolved via deprecated link path_representations[{key}]")
                        resolved_path = candidate
                        break

            if resolved_path is None:
                # Diagnostic parity: list exactly what the resolver tried, in
                # order, by re-walking the same candidate generator (labelled
                # prefer[i]-style when a preference reordered the walk).
                tried = []
                for i, (_loc, candidate) in enumerate(_iter_candidates(
                    record, base_dir=base_dir, variants=_default_path_variants,
                    prefer=prefer, only=only, kinds=kinds,
                )):
                    label = f"prefer[{i}]: " if prefer else ""
                    tried.append(f"  {label}{candidate}")
                if not tried and selection_active:
                    # The selection filtered out every locator -- name what
                    # the record DOES have so the next command is obvious.
                    active = ", ".join(
                        part for part in (
                            f"--only {only}" if only else None,
                            "--kind " + ", ".join(kinds) if kinds else None,
                            f"--prefer {prefer}" if prefer else None,
                        ) if part
                    )
                    raise DazzleLinkException(
                        f"no locators match the selection ({active}); this "
                        f"record has: {_available_selection(record.get_locators())}"
                    )
                tried_lines = "\n".join(tried) or "  (no candidates)"
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
