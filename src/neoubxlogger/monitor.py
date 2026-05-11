"""Textual TUI live monitoring dashboard for neoubxlogger."""

from __future__ import annotations

import threading
from typing import Optional, Callable
from collections import deque

from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich.console import RenderableType

from textual.app import App, ComposeResult
from textual.widgets import Static, Header, Footer


class NavPvtView(Static):
    """Display NAV-PVT summary."""
    _data: dict = {}

    def update_data(self, msg: object) -> None:
        self._data = {
            "iTOW": getattr(msg, "iTOW", 0),
            "fixType": getattr(msg, "fixType", 0),
            "numSV": getattr(msg, "numSV", 0),
            "year": getattr(msg, "year", 0),
            "month": getattr(msg, "month", 0),
            "day": getattr(msg, "day", 0),
            "hour": getattr(msg, "hour", 0),
            "min": getattr(msg, "min", 0),
            "sec": getattr(msg, "sec", 0),
            "lat": getattr(msg, "lat", 0) / 1e7,
            "lon": getattr(msg, "lon", 0) / 1e7,
            "height": getattr(msg, "height", 0) / 1000.0,
            "hMSL": getattr(msg, "hMSL", 0) / 1000.0,
            "hAcc": getattr(msg, "hAcc", 0) / 1000.0,
            "vAcc": getattr(msg, "vAcc", 0) / 1000.0,
            "velN": getattr(msg, "velN", 0) / 100.0,
            "velE": getattr(msg, "velE", 0) / 100.0,
            "velD": getattr(msg, "velD", 0) / 100.0,
            "gSpeed": getattr(msg, "gSpeed", 0) / 100.0,
            "headMot": getattr(msg, "headMot", 0) / 1e5,
            "pDOP": getattr(msg, "pDOP", 0) / 100.0,
        }
        self.refresh()

    def _fix_str(self, fix_type: int) -> str:
        labels = {
            0: "NO FIX",
            1: "DR",
            2: "2D",
            3: "3D",
            4: "G+DR",
            5: "TIME",
        }
        return labels.get(fix_type, f"?")

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(0.25, self.refresh)

    def render(self) -> RenderableType:
        d = self._data
        if not d:
            return Text("Waiting for NAV-PVT...", style="dim")
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Field", style="bold cyan")
        table.add_column("Value", style="white")
        table.add_row("iTOW", f"{d['iTOW']} ms")
        table.add_row("Fix", self._fix_str(d["fixType"]))
        table.add_row("SVs", str(d["numSV"]))
        table.add_row("UTC",
                       f"{d['year']:04d}-{d['month']:02d}-{d['day']:02d} "
                       f"{d['hour']:02d}:{d['min']:02d}:{d['sec']:02d}")
        table.add_row("Lat", f"{d['lat']:.6f}°")
        table.add_row("Lon", f"{d['lon']:.6f}°")
        table.add_row("Height", f"{d['height']:.1f} m")
        table.add_row("MSL", f"{d['hMSL']:.1f} m")
        table.add_row("hAcc", f"{d['hAcc']:.1f} m")
        table.add_row("vAcc", f"{d['vAcc']:.1f} m")
        table.add_row("Vel N/E/D",
                       f"{d['velN']:.1f} / {d['velE']:.1f} / {d['velD']:.1f} m/s")
        table.add_row("Speed (ground)", f"{d['gSpeed']:.1f} m/s")
        table.add_row("Heading (mot)", f"{d['headMot']:.1f}°")
        table.add_row("pDOP", f"{d['pDOP']:.1f}")
        return Panel(table, title="NAV-PVT", border_style="green")


class MessageFeed(Static):
    """Scrolling feed of recent UBX messages."""
    MAX_ENTRIES = 20
    _entries: deque = deque(maxlen=MAX_ENTRIES)

    def add_message(self, identity: str, summary: str = "") -> None:
        self._entries.append(f"{identity:<16s} {summary}")
        self.refresh()

    def render(self) -> RenderableType:
        lines = list(self._entries)
        if not lines:
            return Text("(no messages yet)", style="dim")
        return Panel(
            Text("\n".join(reversed(lines)), style="white"),
            title="Recent Messages",
            border_style="blue",
        )


class MonitorApp(App):
    """Textual TUI for live UBX monitoring."""
    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 2;
    }
    #pvt {
        height: 100%;
    }
    #feed {
        height: 100%;
    }
    #bottom-left {
        height: 100%;
    }
    #bottom-right {
        height: 100%;
    }
    """

    def __init__(self, feed_fn: Optional[Callable[[], None]] = None) -> None:
        super().__init__()
        self._feed_fn = feed_fn

    def compose(self) -> ComposeResult:
        yield Header()
        yield NavPvtView(id="pvt")
        yield MessageFeed(id="feed")
        yield Static(id="bottom-left")
        yield Static(id="bottom-right")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "neoubxlogger — TUI Monitor"
        # Start the feed thread now that the app is running
        if self._feed_fn is not None:
            t = threading.Thread(target=self._feed_fn, daemon=True)
            t.start()

    def handle_parsed(self, parsed: object) -> None:
        """Called from the main loop when a UBX message is parsed."""
        identity = getattr(parsed, "identity", "")
        pvt = self.query_one("#pvt", NavPvtView)
        feed = self.query_one("#feed", MessageFeed)

        if identity == "NAV-PVT":
            pvt.update_data(parsed)
            feed.add_message("NAV-PVT",
                             f"iTOW={getattr(parsed, 'iTOW', 0)}")
        elif identity == "NAV-EOE":
            feed.add_message("NAV-EOE",
                             f"iTOW={getattr(parsed, 'iTOW', 0)}")
        elif identity == "NAV-TIMEUTC":
            feed.add_message("NAV-TIMEUTC")
        elif identity == "NAV-STATUS":
            feed.add_message("NAV-STATUS",
                             f"gpsFix={getattr(parsed, 'gpsFix', '?')}")
        elif identity == "NAV-SAT":
            feed.add_message("NAV-SAT",
                             f"numSvs={getattr(parsed, 'numSvs', '?')}")
        elif identity == "RXM-SFRBX":
            feed.add_message("RXM-SFRBX")
        elif identity == "MON-SYS":
            feed.add_message("MON-SYS",
                             f"numSvs={getattr(parsed, 'numSvs', '?')}")