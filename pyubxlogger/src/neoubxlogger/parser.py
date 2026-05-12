# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Kelei Chen

"""Streaming UBX parser built on top of pyubx2."""

from __future__ import annotations

import io
from typing import Iterator, Optional

from pyubx2 import UBXReader


ParsedResult = tuple[bytes, Optional[object]]
"""A tuple of (raw_frame_bytes, parsed_ubx_message_or_None)."""


def parse_stream(stream: io.RawIOBase) -> Iterator[ParsedResult]:
    """Yield (raw_bytes, parsed_msg) pairs from a UBX binary stream.

    *stream* should be a file-like object with a ``.read()`` method, typically
    obtained from ``InputSource.stream()``.

    Each yielded pair consists of:
    - ``raw_bytes``: the raw UBX frame bytes (sync chars + header + payload + CK).
    - ``parsed_msg``: a ``pyubx2.UBXMessage`` instance when the frame is valid
      and recognised, or ``None`` for unrecognised data.
    """
    ubr = UBXReader(
        stream,
        protfilter=2,       # 2 = UBX protocol only
        quitonerror=1,      # 1 = ERR_LOG — log and continue on error
        msgmode=0,          # 0 = GET (inbound parsing)
    )

    for raw, parsed in ubr:
        raw_bytes = bytes(raw) if raw is not None else b""
        yield raw_bytes, parsed