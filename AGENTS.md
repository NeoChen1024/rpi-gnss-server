# rpi-gnss-server — AGENTS.md

## Project structure

- `neoubxlogger/` — C++ logger (hand-written + generated parsers). Entrypoint: `neoubxlogger.cpp`.
- `scripts/` — `generate_ubx_parsers.py` (C++ codegen), `update_ubx_names.py`.
- `3rdparty/pyubx2/` — git submodule; its `src/` is added to `sys.path` at codegen time.
- `docs/` — u-blox F9 interface specification PDFs.
- `daily-ubx.sh` — cron job using `gpspipe -R | xz`.
- `rtkserv.sh` — RTKLib `str2str` NTRIP caster startup.

## neoubxlogger — C++ build

```bash
cd neoubxlogger
make setup    # create .venv + install pyrtcm pynmeagps (one-time)
make          # codegen + compile + link
make gen      # regenerate parsers only
make clean    # rm binary, .o, all *_gen.* files
```

- C++11, `c++` compiler, `-pedantic -Wall -Wextra`.
- `#DBG` (sanitizers) commented out in Makefile.
- Generated files (`*_gen.*`) have `.gitignore` entries and are auto-rebuilt on `make`.

### CLI flags

| Flag | Description |
|------|-------------|
| `-f FILE` | Read from .ubx file (default: stdin) |
| `-t HOST:PORT` | Read from TCP socket (auto-reconnects) |
| `-n` | No write |
| `-d` | Debug — single-line dump every frame |
| `-q` | Quiet daemon — suppresses status line, prints per-minute stats |

`-f`/`-t` and `-d`/`-q` are mutually exclusive.

### Codegen architecture

`scripts/generate_ubx_parsers.py` reads `UBX_PAYLOADS_GET` from `pyubx2` and produces:

- `ubx_ids_gen.hpp` — class/msg ID constants
- `ubx_struct_gen.hpp` — packed structs for fixed-size messages
- `ubx_{class}_gen.{hpp,cpp}` — parser classes (NAV, RXM, MON, TIM, ESF, HNR, LOG, SEC, CFG, ACK)
- `ubx_dump_gen.{hpp,cpp}` — universal `UBX::ubx_dump_any(ubx_frame&, FILE*)`

### Hand-written vs generated parsers

`HAND_WRITTEN = {"NAV-PVT", "NAV-EOE"}` — these use hand-coded classes in `ubx_nav.{hpp,cpp}`.

- `ubx_nav_pvt` has `get_fix_type()` (returns "3D", "2D", etc.)
- Both have custom `dump()` matching the generated single-line format.
- Generated code skips HAND_WRITTEN messages (no struct, no parser, no id conflict).
- `ubx_dump_gen.cpp` `#include`s `ubx_nav.hpp` for the two hand-written types.

### TCP reader notes

TCP input (`-t`) uses raw `read()` syscalls (not FILE*) in `ubx_read_frame_tcp()`, with `SO_RCVTIMEO` 5s and automatic reconnection on disconnect. The file/stdin path uses the original `ubx_read_frame(FILE*)`.

### `*_gen.hpp` include order

Generated `.cpp` always includes: `ubx_{class}_gen.hpp`, `ubx_ids_gen.hpp`, `inttypes.h`, `string`, `endian.h`, `cstring`.

### Hand-written include order

`ubx.hpp` includes: `ubx_def.hpp`, `ubx_names.hpp`, `ubx_struct.hpp`, `ubx_nav.hpp`.
`ubx_def.hpp` includes `ubx_ids_gen.hpp`.

## Testing

No automated test suite. Manual verification with testdata files:

```bash
cd neoubxlogger && ./neoubxlogger < ../testdata/20241103T000000.ubx
```
