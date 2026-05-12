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

# ── helpers ──────────────────────────────────────────────────────

GNSS_NAMES = {
    0: "GPS",
    1: "SBAS",
    2: "GAL",
    3: "BDS",
    4: "IMES",
    5: "QZSS",
    6: "GLO",
    7: "NavIC",
}

FIX_LABELS = {0: "NO FIX", 1: "DR", 2: "2D", 3: "3D", 4: "G+DR", 5: "TIME"}


def _gnss(gnss_id: int) -> str:
    return GNSS_NAMES.get(gnss_id, f"({gnss_id})")


# ── NAV-PVT (unchanged) ─────────────────────────────────────────


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
            "sec": getattr(msg, "second", 0),
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
        return FIX_LABELS.get(fix_type, "?")

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
        table.add_row(
            "UTC",
            f"{d['year']:04d}-{d['month']:02d}-{d['day']:02d} "
            f"{d['hour']:02d}:{d['min']:02d}:{d['sec']:02d}",
        )
        table.add_row("Lat", f"{d['lat']:.6f}°")
        table.add_row("Lon", f"{d['lon']:.6f}°")
        table.add_row("Height", f"{d['height']:.1f} m")
        table.add_row("MSL", f"{d['hMSL']:.1f} m")
        table.add_row("hAcc", f"{d['hAcc']:.1f} m")
        table.add_row("vAcc", f"{d['vAcc']:.1f} m")
        table.add_row(
            "Vel N/E/D",
            f"{d['velN']:.1f} / {d['velE']:.1f} / {d['velD']:.1f} m/s",
        )
        table.add_row("Speed (ground)", f"{d['gSpeed']:.1f} m/s")
        table.add_row("Heading (mot)", f"{d['headMot']:.1f}°")
        table.add_row("pDOP", f"{d['pDOP']:.1f}")
        return Panel(table, title="NAV-PVT", border_style="green")


# ── NAV-TIMEUTC ─────────────────────────────────────────────────


class NavTimeUtcView(Static):
    """Display NAV-TIMEUTC summary."""
    _data: dict = {}

    def update_data(self, msg: object) -> None:
        self._data = {
            "iTOW": getattr(msg, "iTOW", 0),
            "year": getattr(msg, "year", 0),
            "month": getattr(msg, "month", 0),
            "day": getattr(msg, "day", 0),
            "hour": getattr(msg, "hour", 0),
            "min": getattr(msg, "min", 0),
            "sec": getattr(msg, "sec", 0),
            "tAcc": getattr(msg, "tAcc", 0),
            "nano": getattr(msg, "nano", 0),
            "utcStandard": getattr(msg, "utcStandard", 0),
            "validTOW": getattr(msg, "validTOW", 0),
            "validUTC": getattr(msg, "validUTC", 0),
            "validWKN": getattr(msg, "validWKN", 0),
            "authStatus": getattr(msg, "authStatus", 0),
        }
        self.refresh()

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(0.25, self.refresh)

    def render(self) -> RenderableType:
        d = self._data
        if not d.get("year"):
            return Text("Waiting for NAV-TIMEUTC...", style="dim")
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Field", style="bold cyan")
        table.add_column("Value", style="white")
        valid_str = ""
        if d["validTOW"]:
            valid_str += "TOW "
        if d["validUTC"]:
            valid_str += "UTC "
        if d["validWKN"]:
            valid_str += "WKN "
        valid_str = valid_str.strip() or "—"
        table.add_row("Valid", valid_str)
        table.add_row(
            "UTC",
            f"{d['year']:04d}-{d['month']:02d}-{d['day']:02d} "
            f"{d['hour']:02d}:{d['min']:02d}:{d['sec']:02d}",
        )
        table.add_row("tAcc", f"{d['tAcc']} ns")
        table.add_row("nano", f"{d['nano']} ns")
        utc_std_labels = {0: "Unknown", 3: "USNO", 7: "SU", 12: "NTSC", 14: "EU"}
        table.add_row("UTC Std", utc_std_labels.get(d["utcStandard"], f"?({d['utcStandard']})"))
        auth_labels = {0: "No", 1: "Valid", 2: "Invalid", 3: "Revoked"}
        table.add_row("Auth", auth_labels.get(d["authStatus"], f"?({d['authStatus']})"))
        table.add_row("iTOW", f"{d['iTOW']} ms")
        return Panel(table, title="NAV-TIMEUTC", border_style="cyan")


# ── NAV-STATUS ──────────────────────────────────────────────────


class NavStatusView(Static):
    """Display NAV-STATUS summary."""
    _data: dict = {}

    def update_data(self, msg: object) -> None:
        self._data = {
            "iTOW": getattr(msg, "iTOW", 0),
            "gpsFix": getattr(msg, "gpsFix", 0),
            "gpsFixOk": getattr(msg, "gpsFixOk", 0),
            "carrSoln": getattr(msg, "carrSoln", 0),
            "diffSoln": getattr(msg, "diffSoln", 0),
            "diffCorr": getattr(msg, "diffCorr", 0),
            "ttff": getattr(msg, "ttff", 0),
            "msss": getattr(msg, "msss", 0),
            "spoofDetState": getattr(msg, "spoofDetState", 0),
            "carrSolnValid": getattr(msg, "carrSolnValid", 0),
            "mapMatching": getattr(msg, "mapMatching", 0),
            "psmState": getattr(msg, "psmState", 0),
            "towSet": getattr(msg, "towSet", 0),
            "wknSet": getattr(msg, "wknSet", 0),
        }
        self.refresh()

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(0.25, self.refresh)

    def render(self) -> RenderableType:
        d = self._data
        if not d.get("iTOW"):
            return Text("Waiting for NAV-STATUS...", style="dim")
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Field", style="bold cyan")
        table.add_column("Value", style="white")
        fix_label = FIX_LABELS.get(d["gpsFix"], f"?({d['gpsFix']})")
        if d["gpsFixOk"]:
            fix_label += " ✓"
        table.add_row("GPS Fix", fix_label)
        carr_labels = {0: "None", 1: "Float", 2: "Fix"}
        table.add_row("Carr Soln", carr_labels.get(d["carrSoln"], f"?({d['carrSoln']})"))
        table.add_row("Diff Soln", "Yes" if d["diffSoln"] else "No")
        table.add_row("Diff Corr", "Yes" if d["diffCorr"] else "No")
        table.add_row("TTFF", f"{d['ttff']} ms")
        spoof_labels = {0: "Unknown", 1: "No", 2: "Yes", 3: "Multiple"}
        table.add_row("Spoof", spoof_labels.get(d["spoofDetState"], f"?({d['spoofDetState']})"))
        table.add_row("MSSS", str(d["msss"]))
        table.add_row("Map Match", str(d["mapMatching"]))
        table.add_row("PSM State", str(d["psmState"]))
        table.add_row("iTOW", f"{d['iTOW']} ms")
        return Panel(table, title="NAV-STATUS", border_style="yellow")


# ── MON-SYS ─────────────────────────────────────────────────────


class MonSysView(Static):
    """Display MON-SYS system status."""
    _data: dict = {}

    def update_data(self, msg: object) -> None:
        self._data = {
            "cpuLoad": getattr(msg, "cpuLoad", 0),
            "cpuLoadMax": getattr(msg, "cpuLoadMax", 0),
            "memUsage": getattr(msg, "memUsage", 0),
            "memUsageMax": getattr(msg, "memUsageMax", 0),
            "ioUsage": getattr(msg, "ioUsage", 0),
            "ioUsageMax": getattr(msg, "ioUsageMax", 0),
            "runTime": getattr(msg, "runTime", 0),
            "bootType": getattr(msg, "bootType", 0),
            "tempValue": getattr(msg, "tempValue", 0),
            "errorCount": getattr(msg, "errorCount", 0),
            "noticeCount": getattr(msg, "noticeCount", 0),
            "warnCount": getattr(msg, "warnCount", 0),
            "msgVer": getattr(msg, "msgVer", 0),
        }
        self.refresh()

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(0.25, self.refresh)

    def render(self) -> RenderableType:
        d = self._data
        if not d.get("runTime"):
            return Text("Waiting for MON-SYS...", style="dim")
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Field", style="bold cyan")
        table.add_column("Value", style="white")
        table.add_row("CPU Load", f"{d['cpuLoad']}% (max {d['cpuLoadMax']}%)")
        table.add_row("Mem Usage", f"{d['memUsage']}% (max {d['memUsageMax']}%)")
        table.add_row("I/O Usage", f"{d['ioUsage']}% (max {d['ioUsageMax']}%)")
        runtime_h = d["runTime"] / 3600.0
        table.add_row("Run Time", f"{runtime_h:.1f} h")
        boot_labels = {0: "Cold", 1: "Warm", 2: "Hot", 4: "Unknown/FPOR"}
        table.add_row("Boot", boot_labels.get(d["bootType"], f"?({d['bootType']})"))
        table.add_row("Temp", f"{d['tempValue']} °C" if d["tempValue"] else "—")
        table.add_row("Errors", str(d["errorCount"]))
        table.add_row("Warnings", str(d["warnCount"]))
        table.add_row("Notices", str(d["noticeCount"]))
        table.add_row("Msg Ver", str(d["msgVer"]))
        return Panel(table, title="MON-SYS", border_style="magenta")


# ── NAV-SAT + NAV-SIG ──────────────────────────────────────────


class NavSatSigView(Static):
    """Combined view of active satellites and signals from NAV-SAT and NAV-SIG."""

    _sat_data: list[dict] = []
    _sig_data: list[dict] = []

    def update_sat(self, msg: object) -> None:
        num_svs = getattr(msg, "numSvs", 0)
        entries: list[dict] = []
        # Filter to only SVs with cno > 0 (visible/tracking)
        for i in range(1, num_svs + 1):
            cno = getattr(msg, f"cno_{i:02d}", 0)
            gnss_id = getattr(msg, f"gnssId_{i:02d}", 0)
            sv_id = getattr(msg, f"svId_{i:02d}", 0)
            if cno == 0:
                continue  # skip unused slots
            entries.append({
                "gnssId": gnss_id,
                "svId": sv_id,
                "cno": cno,
                "elev": getattr(msg, f"elev_{i:02d}", 0),
                "azim": getattr(msg, f"azim_{i:02d}", 0),
                "qualityInd": getattr(msg, f"qualityInd_{i:02d}", 0),
            })
        # Sort by gnssId then svId
        entries.sort(key=lambda e: (e["gnssId"], e["svId"]))
        self._sat_data = entries
        self.refresh()

    def update_sig(self, msg: object) -> None:
        num_sigs = getattr(msg, "numSigs", 0)
        entries: list[dict] = []
        for i in range(1, num_sigs + 1):
            cno = getattr(msg, f"cno_{i:02d}", 0)
            gnss_id = getattr(msg, f"gnssId_{i:02d}", 0)
            sv_id = getattr(msg, f"svId_{i:02d}", 0)
            if cno == 0 and len(entries) > 20:
                # Only include cno=0 entries if we have few total
                continue
            entries.append({
                "gnssId": gnss_id,
                "svId": sv_id,
                "sigId": getattr(msg, f"sigId_{i:02d}", 0),
                "cno": cno,
                "qualityInd": getattr(msg, f"qualityInd_{i:02d}", 0),
                "corrSource": getattr(msg, f"corrSource_{i:02d}", 0),
                "ionoModel": getattr(msg, f"ionoModel_{i:02d}", 0),
            })
        self._sig_data = entries
        self.refresh()

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(0.25, self.refresh)

    def render(self) -> RenderableType:
        if not self._sat_data and not self._sig_data:
            return Text("Waiting for NAV-SAT / NAV-SIG...", style="dim")
        table = Table(box=None, padding=(0, 1), collapse_padding=True)
        table.add_column("#", style="dim", no_wrap=True)
        table.add_column("GNSS", style="bold", no_wrap=True)
        table.add_column("SV", style="white", no_wrap=True)
        table.add_column("S", style="dim", no_wrap=True)
        table.add_column("C/N₀", style="green", no_wrap=True, justify="right")
        table.add_column("Q", style="cyan", no_wrap=True, justify="right")
        table.add_column("El", style="white", no_wrap=True, justify="right")
        table.add_column("Az", style="white", no_wrap=True, justify="right")

        # Use sig data if available for finer granularity, else sat data
        sig_by_sv: dict = {}
        for sig in self._sig_data:
            key = (sig["gnssId"], sig["svId"])
            sig_by_sv.setdefault(key, []).append(sig)

        used_keys = set()

        # Show SAT data with SIG overlay where available
        for idx, sat in enumerate(self._sat_data, start=1):
            key = (sat["gnssId"], sat["svId"])
            used_keys.add(key)
            sigs = sig_by_sv.get(key, [])
            sig_str = ""
            if sigs:
                sig_str = ",".join(
                    str(s["sigId"]) for s in sigs if s["cno"] > 0
                )
            table.add_row(
                str(idx),
                _gnss(sat["gnssId"]),
                str(sat["svId"]),
                sig_str,
                str(sat["cno"]),
                str(sat["qualityInd"]),
                str(sat["elev"]),
                str(sat["azim"]),
            )

        # Show any SIG-only entries (no SAT data)
        for sig in self._sig_data:
            key = (sig["gnssId"], sig["svId"])
            if key in used_keys:
                continue
            table.add_row(
                "",
                _gnss(sig["gnssId"]),
                str(sig["svId"]),
                str(sig["sigId"]),
                str(sig["cno"]),
                str(sig["qualityInd"]),
                "—",
                "—",
            )
            used_keys.add(key)

        return Panel(table, title="NAV-SAT / NAV-SIG", border_style="blue")


# ── RXM-SFRBX scrolling feed ────────────────────────────────────


class SfrbxFeed(Static):
    """Scrolling feed of RXM-SFRBX subframe data (one line per channel)."""
    MAX_ENTRIES = 50
    _entries: deque = deque(maxlen=MAX_ENTRIES)

    def add_sfrbx(self, msg: object) -> None:
        chn = getattr(msg, "chn", 0)
        gnss_id = getattr(msg, "gnssId", 0)
        sv_id = getattr(msg, "svId", 0)
        sig_id = getattr(msg, "sigId", 0)
        freq_id = getattr(msg, "freqId", 0)
        num_words = getattr(msg, "numWords", 0)
        words = [
            f"{getattr(msg, f'dwrd_{i:02d}', 0):08X}"
            for i in range(1, min(num_words + 1, 11))
        ]
        line = (
            f"Ch{chn:02d} {_gnss(gnss_id)}-{sv_id}/{sig_id} "
            f"F{freq_id:+d} | {' '.join(words)}"
        )
        self._entries.append(line)
        self.refresh()

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(0.25, self.refresh)

    def render(self) -> RenderableType:
        lines = list(self._entries)
        if not lines:
            return Text("Waiting for RXM-SFRBX...", style="dim")
        # Latest at top
        return Panel(
            Text("\n".join(reversed(lines)), style="bright_yellow"),
            title="RXM-SFRBX (subframes)",
            border_style="red",
        )


# ── Main App ────────────────────────────────────────────────────

# Helper CSS
MONITOR_CSS = """
Screen {
    layout: grid;
    grid-size: 3 3;
    grid-columns: 1fr 1fr 1fr;
    grid-rows: auto auto 1fr;
}
#pvt {
    height: 100%;
}
#timeutc {
    height: 100%;
}
#status {
    height: 100%;
}
#monsys {
    height: 100%;
}
#satsig {
    height: 100%;
}
#sfrbx {
    height: 100%;
}
"""


class MonitorApp(App):
    """Textual TUI for live UBX monitoring."""
    CSS = MONITOR_CSS

    def __init__(self, feed_fn: Optional[Callable[[], None]] = None) -> None:
        super().__init__()
        self._feed_fn = feed_fn

    def compose(self) -> ComposeResult:
        yield Header()
        yield NavPvtView(id="pvt")
        yield NavTimeUtcView(id="timeutc")
        yield NavStatusView(id="status")
        yield MonSysView(id="monsys")
        yield NavSatSigView(id="satsig")
        yield SfrbxFeed(id="sfrbx")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "neoubxlogger — TUI Monitor"
        if self._feed_fn is not None:
            t = threading.Thread(target=self._feed_fn, daemon=True)
            t.start()

    def handle_parsed(self, parsed: object) -> None:
        """Called from the main loop when a UBX message is parsed."""
        identity = getattr(parsed, "identity", "")

        pvt = self.query_one("#pvt", NavPvtView)
        timeutc = self.query_one("#timeutc", NavTimeUtcView)
        status = self.query_one("#status", NavStatusView)
        monsys = self.query_one("#monsys", MonSysView)
        satsig = self.query_one("#satsig", NavSatSigView)
        sfrbx = self.query_one("#sfrbx", SfrbxFeed)

        if identity == "NAV-PVT":
            pvt.update_data(parsed)

        elif identity == "NAV-TIMEUTC":
            timeutc.update_data(parsed)

        elif identity == "NAV-STATUS":
            status.update_data(parsed)

        elif identity == "NAV-SAT":
            satsig.update_sat(parsed)

        elif identity == "NAV-SIG":
            satsig.update_sig(parsed)

        elif identity == "MON-SYS":
            monsys.update_data(parsed)

        elif identity == "RXM-SFRBX":
            sfrbx.add_sfrbx(parsed)