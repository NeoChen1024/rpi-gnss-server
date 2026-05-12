# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Kelei Chen

"""Input sources for neoubxlogger: stdin, file, serial port, TCP socket."""

from __future__ import annotations

import io
import os
import sys
import time
import socket
from typing import Optional, Callable
from dataclasses import dataclass, field

SOCKET_TIMEOUT = 5  # seconds — timeout triggering reconnect
RECONNECT_DELAY = 2  # seconds to wait before reconnecting TCP


class _TcpStream(io.RawIOBase):
    """A reconnectable TCP stream that behaves like a file object."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._name = f"{host}:{port}"
        self._sock: Optional[socket.socket] = None
        self._connect()

    def _connect(self) -> None:
        """Resolve host via getaddrinfo and connect, trying each address."""
        addrs = socket.getaddrinfo(
            self._host, self._port,
            type=socket.SOCK_STREAM,
        )
        last_err: Optional[OSError] = None
        for family, _socktype, _proto, _canonname, sockaddr in addrs:
            sock = socket.socket(family, socket.SOCK_STREAM)
            sock.settimeout(SOCKET_TIMEOUT)
            try:
                sock.connect(sockaddr)
                self._sock = sock
                return
            except OSError as e:
                last_err = e
                sock.close()
        self._sock = None
        if last_err is not None:
            raise last_err
        raise OSError(f"Could not connect to {self._name}")

    def _reconnect(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        sys.stderr.write(
            f"TCP {self._name}: reconnecting in {RECONNECT_DELAY}s...\n"
        )
        sys.stderr.flush()
        time.sleep(RECONNECT_DELAY)
        self._connect()

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        if size == -1:
            size = 4096
        while True:
            if self._sock is None:
                self._reconnect()
            try:
                data = self._sock.recv(size)  # type: ignore[union-attr]
                if data:
                    return data
                # empty data = connection closed
                self._reconnect()
            except (socket.timeout, OSError):
                self._reconnect()

    def readinto(self, b: "bytearray | memoryview") -> int:  # type: ignore[override]
        data = self.read(len(b))
        n = len(data)
        b[:n] = data
        return n

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def __del__(self) -> None:
        self.close()


@dataclass
class InputSource:
    """Wraps a file-like stream as a UBX input source.

    Usage:
        with InputSource.stdin() as src:
            stream = src.stream()   # io.RawIOBase-compatible
            ...

        with InputSource.file("test.ubx") as src:
            stream = src.stream()
            ...

        with InputSource.serial("/dev/ttyACM0", 115200) as src:
            stream = src.stream()
            ...

        with InputSource.tcp("192.168.1.100", 2101) as src:
            stream = src.stream()
            ...
    """

    name: str
    _stream: io.RawIOBase = field(repr=False)
    _close: Optional[Callable[[], None]] = field(default=None, repr=False)

    # ── factory constructors ──────────────────────────────────────

    @staticmethod
    def stdin() -> "InputSource":
        return InputSource(
            name="<stdin>",
            _stream=sys.stdin.buffer,  # type: ignore[arg-type]
        )

    @staticmethod
    def file(path: str) -> "InputSource":
        fp = open(path, "rb")
        return InputSource(
            name=path,
            _stream=fp,  # type: ignore[arg-type]
            _close=fp.close,
        )

    @staticmethod
    def serial(port: str, baudrate: int = 115200) -> "InputSource":
        import serial  # defer import to avoid requiring pyserial for file/stdio use

        ser = serial.Serial(port, baudrate=baudrate, timeout=SOCKET_TIMEOUT)
        return InputSource(
            name=f"{port}@{baudrate}",
            _stream=ser,  # type: ignore[arg-type]
            _close=ser.close,
        )

    @staticmethod
    def tcp(host: str, port: int) -> "InputSource":
        tcp_stream = _TcpStream(host, port)
        return InputSource(
            name=f"{host}:{port}",
            _stream=tcp_stream,  # type: ignore[arg-type]
            _close=tcp_stream.close,
        )

    # ── public interface ──────────────────────────────────────────

    def stream(self) -> io.RawIOBase:
        """Return the underlying file-like stream."""
        return self._stream

    def close(self) -> None:
        if self._close is not None:
            self._close()

    def __enter__(self) -> "InputSource":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
