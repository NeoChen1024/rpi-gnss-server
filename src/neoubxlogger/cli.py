"""neoubxlogger — CLI entry point using Click."""

from __future__ import annotations

import sys
import time
from typing import Optional

import click

from neoubxlogger.input import InputSource
from neoubxlogger.parser import parse_stream
from neoubxlogger.output import OutputWriter
from neoubxlogger.display import (
    stderr_console,
    print_status_line,
    debug_frame,
    print_error,
)


# ── helpers ─────────────────────────────────────────────────────


def _extract_pvt_ts(parsed: object) -> Optional[tuple[int, int, int, int, int, int]]:
    """Extract (y, m, d, H, M, S) from a NAV-PVT message."""
    identity = getattr(parsed, "identity", "")
    if identity != "NAV-PVT":
        return None
    return (
        getattr(parsed, "year", 0),
        getattr(parsed, "month", 0),
        getattr(parsed, "day", 0),
        getattr(parsed, "hour", 0),
        getattr(parsed, "min", 0),
        getattr(parsed, "sec", 0),
    )


def _fix_type_label(fix_type: int) -> str:
    labels = {0: "NO", 1: "DR", 2: "2D", 3: "3D", 4: "G+DR", 5: "TIME"}
    return labels.get(fix_type, "?")


# ── run modes ────────────────────────────────────────────────────


def run_normal(
    src: InputSource,
    writer: OutputWriter,
    quiet: bool = False,
    debug: bool = False,
) -> None:
    """Standard mode: read, parse, print status, write."""
    from pyubx2 import UBXMessageError  # type: ignore[import-untyped]

    last_status: dict = {}
    last_eoe_itow: Optional[int] = None

    for raw_bytes, parsed in parse_stream(src.stream()):
        # Debug output for every parsed frame
        if debug and parsed is not None:
            debug_frame(parsed)

        # Extract PVT timestamp for file rotation and status
        ts = _extract_pvt_ts(parsed) if parsed is not None else None
        identity = getattr(parsed, "identity", "") if parsed is not None else None

        # Write to output file
        writer.write(raw_bytes, parsed=parsed, ts=ts)

        # Handle NAV-PVT for status line
        if identity == "NAV-PVT":
            iTOW = getattr(parsed, "iTOW", 0)
            last_status = {
                "iTOW": iTOW,
                "fix_type": _fix_type_label(getattr(parsed, "fixType", 0)),
                "year": getattr(parsed, "year", 0),
                "month": getattr(parsed, "month", 0),
                "day": getattr(parsed, "day", 0),
                "hour": getattr(parsed, "hour", 0),
                "minute": getattr(parsed, "min", 0),
                "second": getattr(parsed, "sec", 0),
                "numSV": getattr(parsed, "numSV", 0),
                "lat": getattr(parsed, "lat", 0) / 1e7,
                "lon": getattr(parsed, "lon", 0) / 1e7,
                "pDOP": getattr(parsed, "pDOP", 0) / 100.0,
            }
            if not quiet:
                print_status_line(**last_status)

        # Handle NAV-EOE for status line marker
        if identity == "NAV-EOE":
            eoe_itow = getattr(parsed, "iTOW", 0)
            pvt_itow = last_status.get("iTOW", 0)
            if eoe_itow != pvt_itow:
                print_error(
                    f"EOE iTOW mismatch! {eoe_itow} != {pvt_itow}"
                )
            if not quiet:
                sys.stderr.write(" EOE")
                sys.stderr.flush()
            last_eoe_itow = eoe_itow


def _run_monitor(
    src: InputSource, writer: OutputWriter
) -> None:
    """TUI mode: run Textual app with parsed message feed."""
    from neoubxlogger.monitor import MonitorApp

    def _feed() -> None:
        for raw_bytes, parsed in parse_stream(src.stream()):
            if parsed is not None:
                # Write output in the worker thread
                ts = _extract_pvt_ts(parsed)
                writer.write(raw_bytes, parsed=parsed, ts=ts)
                # Send to TUI via thread-safe call
                app.call_from_thread(app.handle_parsed, parsed)
            else:
                # Pass through non-UBX bytes too
                writer.write(raw_bytes, parsed=None)

    app = MonitorApp(feed_fn=_feed)
    app.run()


# ── Click CLI ────────────────────────────────────────────────────


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-f", "--file",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Read from a .ubx file instead of stdin.",
)
@click.option(
    "-s", "--serial",
    type=str,
    metavar="PORT",
    help="Read from serial port (e.g. /dev/ttyACM0).",
)
@click.option(
    "-b", "--baud",
    type=int,
    default=115200,
    show_default=True,
    metavar="BAUD",
    help="Baud rate for serial port.",
)
@click.option(
    "-a", "--allow",
    type=str,
    multiple=True,
    metavar="PATTERN",
    help="Allow only given message(s) in 'filtered' mode (can be repeated).  "
         "Supports glob patterns like 'RXM-*' or 'MON-*'.",
)
@click.option(
    "-t", "--tcp",
    type=str,
    metavar="HOST:PORT",
    help="Read from TCP socket (auto-reconnects on timeout/disconnect).",
)
@click.option(
    "-o", "--output",
    type=click.Choice(["passthrough", "parsed", "filtered"]),
    default="passthrough",
    show_default=True,
    help="Output mode for writing .ubx files.",
)
@click.option(
    "-n", "--no-write",
    is_flag=True,
    help="Dry run — do not write any output files.",
)
@click.option(
    "-d", "--debug",
    is_flag=True,
    help="Verbose debug output for every parsed UBX frame.",
)
@click.option(
    "-q", "--quiet",
    is_flag=True,
    help="Silent daemon mode — only print error messages.",
)
@click.option(
    "-w", "--watch",
    is_flag=True,
    help="Textual TUI monitoring dashboard.",
)
def main(
    file: Optional[str],
    serial: Optional[str],
    baud: int,
    tcp: Optional[str],
    output: str,
    allow: tuple[str, ...],
    no_write: bool,
    debug: bool,
    quiet: bool,
    watch: bool,
) -> None:
    """neoubxlogger — UBX protocol logger for u-blox GNSS receivers.

    Reads raw UBX binary data from a file, serial port, TCP socket, or stdin,
    optionally parses UBX frames, and writes the data to time-rotated output
    files in YYYY-MM/ directories.
    """
    # ── Validate conflicting options ─────────────────────────────
    input_count = sum([file is not None, serial is not None, tcp is not None])
    if input_count > 1:
        click.secho(
            "ERROR: Only one of --file, --serial, --tcp may be specified.",
            fg="red",
            err=True,
        )
        sys.exit(1)

    if quiet and watch:
        click.secho(
            "ERROR: --quiet and --watch are mutually exclusive.",
            fg="red",
            err=True,
        )
        sys.exit(1)

    if quiet and debug:
        click.secho(
            "ERROR: --quiet and --debug are mutually exclusive.",
            fg="red",
            err=True,
        )
        sys.exit(1)

    # ── Set up input source ─────────────────────────────────────
    if serial is not None:
        src = InputSource.serial(serial, baudrate=baud)
    elif tcp is not None:
        parts = tcp.rsplit(":", 1)
        if len(parts) != 2:
            click.secho(
                f"ERROR: Invalid TCP spec '{tcp}'. Expected HOST:PORT.",
                fg="red",
                err=True,
            )
            sys.exit(1)
        host, port_str = parts
        try:
            port = int(port_str)
        except ValueError:
            click.secho(
                f"ERROR: Invalid port number '{port_str}'.",
                fg="red",
                err=True,
            )
            sys.exit(1)
        src = InputSource.tcp(host, port)
    elif file is not None:
        src = InputSource.file(file)
    else:
        src = InputSource.stdin()

    # ── Set up output writer ─────────────────────────────────────
    allowed_messages: set[str] = set()
    if allow:
        allowed_messages = set(allow)
    writer = OutputWriter(
        mode=output,
        no_write=no_write,
        allowed_messages=allowed_messages if allowed_messages else None,
    )

    # ── Run ──────────────────────────────────────────────────────
    try:
        if watch:
            _run_monitor(src, writer)
        else:
            run_normal(src, writer, quiet=quiet, debug=debug)
    except KeyboardInterrupt:
        pass
    finally:
        src.close()
        writer.close()
        if not quiet:
            sys.stderr.write("\nShutdown.\n")