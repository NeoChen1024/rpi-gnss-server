# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Kelei Chen

"""Output handling: raw passthrough, parsed, and filtered file writing with rotation."""

from __future__ import annotations

import io
import os
import sys
import errno
from fnmatch import fnmatch
from typing import Optional


class OutputWriter:
    """Manages output file rotation mirroring the original C++ behaviour.

    Directory structure::

        YYYY-MM/
            YYYYMMDDTHHMMSS.ubx

    Directory is created on month change, file is rotated on day change.
    """

    def __init__(
        self,
        mode: str = "passthrough",
        no_write: bool = False,
        allowed_messages: Optional[set[str]] = None,
    ) -> None:
        self.mode = mode  # "passthrough" | "parsed" | "filtered"
        self.no_write = no_write
        self.allowed_messages = allowed_messages or set()

        # Separate glob patterns from exact matches
        self._exact: set[str] = set()
        self._patterns: list[str] = []
        for msg in self.allowed_messages:
            if "*" in msg or "?" in msg:
                self._patterns.append(msg)
            else:
                self._exact.add(msg)

        self._out: Optional[io.BufferedWriter] = None
        self._current_day: Optional[tuple[int, int, int]] = None  # (year, month, day)
        self._current_month: Optional[tuple[int, int]] = None  # (year, month)
        self._current_filename: str = ""

    def _match(self, identity: str) -> bool:
        """Check *identity* against allowed messages (exact match or glob)."""
        if identity in self._exact:
            return True
        for pattern in self._patterns:
            if fnmatch(identity, pattern):
                return True
        return False

    def _make_dir(self, year: int, month: int) -> str:
        dirname = f"{year:04d}-{month:02d}"
        try:
            os.makedirs(dirname, mode=0o755, exist_ok=True)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise
        return dirname

    def _make_path(
        self, year: int, month: int, day: int, hour: int, minute: int, second: int
    ) -> str:
        dirname = self._make_dir(year, month)
        filename = (
            f"{year:04d}{month:02d}{day:02d}T{hour:02d}{minute:02d}{second:02d}.ubx"
        )
        return os.path.join(dirname, filename)

    def _open(self, path: str) -> None:
        if self._out is not None:
            self._out.close()
        self._out = open(path, "wb")
        self._current_filename = path

    def _should_accept(self, identity: Optional[str]) -> bool:
        """Return True if this message should be written in filtered mode."""
        if self.mode != "filtered":
            return True
        if identity is None:
            return False
        return self._match(identity)

    def write(
        self,
        raw_bytes: bytes,
        parsed: Optional[object] = None,
        ts: Optional[tuple[int, int, int, int, int, int]] = None,
    ) -> None:
        """Write data according to the configured output mode.

        Parameters
        ----------
        raw_bytes : bytes
            The raw UBX frame bytes (for passthrough mode).
        parsed : object or None
            A ``pyubx2.UBXMessage`` instance (for parsed/filtered mode).
        ts : tuple or None
            ``(year, month, day, hour, minute, second)`` timestamp for filename
            rotation.  Extracted from NAV-PVT when available.
        """
        if self.no_write:
            return

        identity: Optional[str] = None
        if parsed is not None:
            identity = getattr(parsed, "identity", None)  # e.g. "NAV-PVT"

        if self.mode in ("parsed", "filtered") and not self._should_accept(identity):
            return

        # Determine what bytes to write
        if self.mode == "passthrough":
            out_bytes = raw_bytes
        elif parsed is not None:
            # Re-serialize the parsed message back to UBX binary
            out_bytes = parsed.serialize()  # type: ignore[union-attr]
        else:
            return  # parsed/filtered mode but no parsed message — skip

        if not out_bytes:
            return

        # File rotation: need a valid timestamp to open a new file
        if ts is not None:
            year, month, day, hour, minute, second = ts
            current_day = (year, month, day)
            current_month = (year, month)

            # Open new file on day change or if none open
            if self._out is None or current_day != self._current_day:
                path = self._make_path(year, month, day, hour, minute, second)
                if self._out is not None:
                    if current_month != self._current_month:
                        sys.stderr.write(
                            f"\nCreated directory {year:04d}-{month:02d}\n"
                        )
                self._open(path)
                sys.stderr.write(f"\nOpened file {path}\n")
                self._current_day = current_day
                self._current_month = current_month

        if self._out is not None:
            self._out.write(out_bytes)
            self._out.flush()

    def close(self) -> None:
        if self._out is not None:
            self._out.close()
            self._out = None
