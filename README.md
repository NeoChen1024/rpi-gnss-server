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
| `neoubxlogger/` | C++ UBX protocol logger |

## neoubxlogger — C++ UBX Protocol Logger

The original C++ implementation in `neoubxlogger/`.

### Build

```bash
cd neoubxlogger
make setup    # one-time: create .venv with Python codegen deps
make          # codegen + compile + link
```

### Usage

```bash
# Read from file, passthrough to daily output
./neoubxlogger < input.ubx

# Read from file, no write
./neoubxlogger -f input.ubx -n

# TCP stream (auto-reconnects on disconnect)
./neoubxlogger -t 192.168.1.100:5555 -n

# TCP + quiet daemon mode (per-minute stats only)
./neoubxlogger -t 192.168.1.100:5555 -n -q

# Debug output (single-line dump every frame)
./neoubxlogger -f input.ubx -d
```

### Options

| Flag | Description |
|------|-------------|
| `-f FILE` | Read from .ubx file (default: stdin) |
| `-t HOST:PORT` | Read from TCP socket (auto-reconnects) |
| `-n` | No write — passthrough to file disabled |
| `-d` | Debug — dump every frame to stderr (single-line format) |
| `-q` | Quiet daemon mode — suppress status line, show per-minute stats only |

`-f` and `-t` are mutually exclusive. `-d` and `-q` are mutually exclusive.

### Example daemon invocation

```bash
./neoubxlogger -t gnss-receiver.local:5555 -n -q
```

Output:
```
Connected to gnss-receiver.local:5555
[neoubxlogger stats] avg rate: 12.3 KiB/s, frames: 452, FIX 100%
[neoubxlogger stats] avg rate: 11.8 KiB/s, frames: 438, FIX 100%
...
```
