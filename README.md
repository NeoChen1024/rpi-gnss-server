# Raspberry Pi GNSS NTP & RTK Server Project

Main Target: Arch Linux ARM on Raspberry Pi 3B+ with minimal external hardware.

## Files

| File | Purpose |
|------|---------|
| `config.txt` | Raspberry Pi boot config (UART, etc.) |
| `cmdline.txt` | Kernel command line parameters |
| `chrony.conf` | NTP configuration excerpt using GNSS PPS |
| `rtkserv.sh` | RTKLib `str2str` startup script for NTRIP caster |
| `daily-ubx.sh` | Collect raw UBX data daily (executed by cron) |
| `rawlogger/` | Original C++ UBX protocol logger |
| `pyubxlogger/src/neoubxlogger/` | Modern Python rewrite of rawlogger |

## neoubxlogger — Python UBX Protocol Logger

A modern Python rewrite of `rawlogger` using **uv** for environment management.

### Dependencies

- [pyubx2](https://github.com/semuconsulting/pyubx2) — UBX protocol parsing
- [Click](https://click.palletsprojects.com/) — CLI framework
- [Rich](https://rich.readthedocs.io/) — Terminal status output
- [Textual](https://textual.textualize.io/) — TUI monitoring dashboard
- [pySerial](https://github.com/pyserial/pyserial) — Serial port support

### Quick Start

```bash
# Install dependencies
uv sync

# Read from file, show parsed output, no write
uv run python -m neoubxlogger -f testdata/20241103T000000.ubx -nd

# Read from serial port with filtered output (only RXM-* messages)
uv run python -m neoubxlogger -s /dev/ttyACM0 -b 115200 -a "RXM-*" -o filtered

# Read from TCP socket with auto-reconnect, normal status output
uv run python -m neoubxlogger -t 192.168.1.100:5555

# Launch TUI dashboard
uv run python -m neoubxlogger -f testdata/20241103T000000.ubx -w
```

### Options

| Flag | Description |
|------|-------------|
| `-f, --file FILE` | Read from .ubx file |
| `-s, --serial PORT` | Read from serial port |
| `-b, --baud BAUD` | Serial baud rate (default: 115200) |
| `-t, --tcp HOST:PORT` | Read from TCP socket (auto-reconnects) |
| `-o, --output MODE` | Output mode: `passthrough`, `parsed`, `filtered` |
| `-a, --allow PATTERN` | Allowed messages in filtered mode (supports glob, repeatable) |
| `-n, --no-write` | Dry run — no file output |
| `-d, --debug` | Verbose debug output for every parsed frame |
| `-q, --quiet` | Silent daemon mode — errors only |
| `-w, --watch` | Textual TUI monitoring dashboard |

### Output

Log files are written to `YYYY-MM/YYYYMMDDTHHMMSS.ubx` — one directory per month, one file per session start day, matching the original C++ behaviour.

## rawlogger — Original C++ UBX Protocol Logger

The original C++ implementation in `rawlogger/`. Compile with `make` in that directory.
