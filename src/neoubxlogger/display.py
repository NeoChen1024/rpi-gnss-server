"""Display helpers: Rich-based status line for normal/debug/quiet modes."""

from __future__ import annotations

import sys
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.live import Live

stderr_console = Console(stderr=True, highlight=False)


def print_status_line(
    *,
    iTOW: int,
    fix_type: str,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    numSV: int,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    pDOP: Optional[float] = None,
    eoe: bool = False,
) -> None:
    """Print an in-place-updating status line (like the C++ original).

    If *eoe* is True the line is prefixed with "EOE " to indicate that a
    NAV-EOE message arrived after the previous NAV-PVT.
    """
    eoe_mark = "EOE " if eoe else "    "
    date_str = f"{year:04d}/{month:02d}/{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
    pos_str = ""
    if lat is not None and lon is not None:
        pos_str = f" @ {lat:.6f},{lon:.6f}"
    dop_str = ""
    if pDOP is not None:
        dop_str = f" pDOP={pDOP:.1f}"
    line = (
        f"\r{eoe_mark}iTOW={iTOW:06d} {fix_type:>8s} {date_str}"
        f"  Sats: {numSV:02d}{pos_str}{dop_str}  "
    )
    sys.stderr.write(line)
    sys.stderr.flush()


def debug_frame(parsed: object) -> None:
    """Print a single-line debug entry for a parsed UBX message."""
    identity = getattr(parsed, "identity", "?")
    # Try to get a short summary
    summary = ""
    if identity == "NAV-PVT":
        iTOW = getattr(parsed, "iTOW", 0)
        fix = getattr(parsed, "fixType", "?")
        sv = getattr(parsed, "numSV", 0)
        summary = f"  iTOW={iTOW} fix={fix} SV={sv}"
    elif identity == "NAV-EOE":
        iTOW = getattr(parsed, "iTOW", 0)
        summary = f"  iTOW={iTOW}  [bold yellow]EOE[/]"
    elif identity == "NAV-TIMEUTC":
        summary = f"  iTOW={getattr(parsed, 'iTOW', '?')}"
    elif identity == "NAV-STATUS":
        gpsFix = getattr(parsed, "gpsFix", "?")
        summary = f"  gpsFix={gpsFix}"
    elif identity == "MON-SYS":
        summary = f"  numSvs={getattr(parsed, 'numSvs', '?')}"

    stderr_console.print(f"  {identity:<16s}{summary}")


def print_error(msg: str) -> None:
    """Print an error message that always shows (even in quiet mode)."""
    stderr_console.print(f"[bold red]ERROR:[/] {msg}")